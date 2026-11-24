"""Public catalogue compatibility and execution boundaries after Tool consolidation."""
import json
import subprocess
import sys

import pytest

from api.errors import ApiError
from api.routes import system
from api.store.tools import ToolStore
from tools import basic, registry, workflows
from tools.schemas import SkillRequest


class RecordedTools(ToolStore):
    def __init__(self):
        self.runs = []

    def run(self, sql, params):
        self.runs.append((sql, params))


def test_existing_http_catalogue_is_a_projection_not_a_second_definition():
    public = system.tools(None)
    assert [t['name'] for t in public['tools']] == ['calculate_emissions', 'voyage_time']
    assert public['assistantTools'] == registry.catalog()
    for tool in registry.TOOLS.values():
        if tool.http:
            assert set(tool.http.inputs) == set(tool.http.aliases)
            assert set(tool.http.aliases.values()) <= set(tool.args.model_fields)
    # Consumers may edit a response without changing later requests.
    public['tools'][0]['input']['fuel'] = 'changed by caller'
    assert registry.http_catalog()[0]['input']['fuel'] == 't, 0..1e7'


def test_http_and_model_input_names_resolve_to_the_same_calculator_and_record():
    call = registry.Call(*registry.parse_call('calculate_emissions',
        {'fuel_t':100, 'factor':3.114, 'dwt':50000, 'distance_nm':1200}))
    payload = registry.http_payload(call)
    assert payload == {'fuel':100, 'factor':3.114, 'dwt':50000, 'distance':1200}
    db = RecordedTools()
    result = db.calculate_emissions(payload)
    assert result['emission'] == pytest.approx(311.4)
    assert result['intensity'] == pytest.approx(5.19)
    assert result['officialCiiRating'] is None
    assert len(db.runs) == 1
    sql, args = db.runs[0]
    assert sql == 'INSERT INTO tool_runs VALUES(%s,%s,%s,%s,%s,%s)'
    assert args[:3] == (result['id'], 'calculate_emissions', 'HAEDAP-EMISSIONS-1')
    assert args[3].obj == payload
    assert args[4].obj == basic.calculate_emissions(payload)


def test_voyage_time_preserves_utc_and_ship_clock_semantics():
    call = registry.Call(*registry.parse_call('voyage_time', {
        'start':'2026-11-15T00:00:00Z', 'end':'2026-11-16T00:00:00Z',
        'start_offset_min':540, 'end_offset_min':480,
    }))
    payload = registry.http_payload(call)
    assert payload['before'] == 540 and payload['after'] == 480
    db = RecordedTools()
    result = db.voyage_time(payload)
    assert result['elapsedHours'] == 24
    assert result['clockHours'] == 23
    assert result['shipStart'] == '2026-11-15T09:00:00.000'
    assert result['shipEnd'] == '2026-11-16T08:00:00.000'
    assert result['version'] == 'HAEDAP-TIME-1'
    assert db.runs[0][1][1] == 'voyage_time'


@pytest.mark.parametrize('field,value', [('fuel',True), ('fuel','100'), ('factor',0), ('dwt',0), ('distance',float('nan'))])
def test_invalid_http_calculations_never_write_run_records(field, value):
    payload = {'fuel':100, 'factor':3.114, 'dwt':50000, 'distance':1200, field:value}
    db = RecordedTools()
    with pytest.raises(ApiError) as failure:
        db.calculate_emissions(payload)
    assert failure.value.code == 'INVALID_INPUT'
    assert not db.runs


def test_workflow_catalogue_stays_separate_from_model_allowlist_and_keeps_resources():
    catalogue = registry.workflow_catalog()
    assert workflows.catalog() == catalogue
    assert len(catalogue['skills']) == 6
    assert {s['id'] for s in catalogue['skills']} == set(SkillRequest.model_json_schema()['properties']['skill']['enum'])
    assert len(registry.TOOLS) == 14
    assert not {'report-draft', 'checklist', 'qa-evaluation'} & set(registry.TOOLS)
    for item in catalogue['skills']:
        assert workflows.instructions(item['id']).strip()
    json.dumps(catalogue, allow_nan=False)


@pytest.mark.parametrize('modules', [('tools.execution','api.main'), ('api.main','tools.execution')])
def test_cold_imports_do_not_create_api_tool_cycles(modules):
    script = '; '.join('import '+name for name in modules)
    result = subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stderr
