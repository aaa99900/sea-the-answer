"""Offline voyage persistence and the app's daily operation import contract."""

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone

import pytest

from api.store.operations import OperationStore
from scripts.publish_simulated_voyage import publish
from scripts.simulate_voyage import VOYAGE_DAYS, advance, operation_csv
from tools.operation_import import classify, daily_rows


DEPARTURE = date(2026, 11, 10)
START = datetime.combine(DEPARTURE, time.min, tzinfo=timezone.utc)
ARRIVAL = START + timedelta(days=VOYAGE_DAYS)


def test_resuming_a_voyage_keeps_daily_records_and_stops_at_arrival(tmp_path):
    resumed_db = tmp_path / "resumed.sqlite3"
    before_first_midnight = advance(resumed_db, DEPARTURE, START + timedelta(hours=23))
    assert before_first_midnight["records"] == []

    halfway = advance(resumed_db, DEPARTURE, START + timedelta(days=7, hours=12))
    assert len(halfway["records"]) == 7
    assert 0 < halfway["simulation"]["current"]["distance_nm"]

    resumed = advance(resumed_db, DEPARTURE, ARRIVAL + timedelta(days=3))
    direct = advance(tmp_path / "direct.sqlite3", DEPARTURE, ARRIVAL)
    repeated = advance(resumed_db, DEPARTURE, ARRIVAL + timedelta(days=30))

    records = resumed["records"]
    assert len(records) == VOYAGE_DAYS == 28
    assert records[:7] == halfway["records"]
    assert records == direct["records"] == repeated["records"]
    assert len({row["id"] for row in records}) == VOYAGE_DAYS
    days = [date.fromisoformat(row["date"]) for row in records]
    assert days == [days[0] + timedelta(days=offset) for offset in range(VOYAGE_DAYS)]

    current = resumed["simulation"]["current"]
    assert current["status"] == "arrived"
    for key in ("status", "latitude", "longitude", "distance_nm", "speed_kn"):
        assert current[key] == direct["simulation"]["current"][key] == repeated["simulation"]["current"][key]
    assert -90 <= current["latitude"] <= 90
    assert -180 <= current["longitude"] <= 180
    assert current["distance_nm"] == pytest.approx(sum(row["distance"] for row in records), rel=1e-4)


class EmptyOperationStore(OperationStore):
    """Only the registered simulator ship exists in this import fixture."""

    def __init__(self, ship):
        self.ship = ship

    def one(self, query, parameters):
        if "SELECT 1 FROM ships" in query:
            return {"id": self.ship["id"]} if parameters == (self.ship["id"],) else None
        if "FROM operations" in query:
            return None
        raise AssertionError(query)

    def operations(self):
        return []


def test_simulation_csv_uses_the_existing_daily_import_and_validation(tmp_path):
    dataset = advance(tmp_path / "voyage.sqlite3", DEPARTURE, ARRIVAL)
    assert len(dataset["ships"]) == 1
    ship = OperationStore().validate_ship(dataset["ships"][0])
    assert ship["sample"] is True

    export = tmp_path / "simulated-operations.csv"
    export.write_text(operation_csv(dataset["records"]), encoding="utf-8", newline="")
    plan = classify([(export.name, export)])
    rows = daily_rows(plan["daily"])
    validated = EmptyOperationStore(ship).validate_rows(rows)

    assert validated["errors"] == []
    assert len(rows) == VOYAGE_DAYS
    assert [row["id"] for row in validated["rows"]] == [row["id"] for row in dataset["records"]]
    assert all(row["sample"] is True and row["ship"] == ship["id"] for row in validated["rows"])
    assert all(row["position"] and row["voyage"] for row in validated["rows"])
    for imported, generated in zip(validated["rows"], dataset["records"]):
        for key in ("fuel", "factor", "distance", "speed"):
            assert imported[key] == pytest.approx(generated[key])


class InMemoryPublisherApp:
    """Apply the app's ship and row normalization without HTTP or a database."""

    def __init__(self):
        self.data = {"ships": [], "records": []}
        self.writes = []

    def request(self, path, body=None):
        if path == "operations":
            return deepcopy(self.data)
        if path == "operations/validate":
            return {"valid": not self.validate(body["rows"])["errors"]}
        assert path == "changes", path
        if body["kind"] == "ship.save":
            assert not self.data["ships"]
            ship = OperationStore().validate_ship(body["payload"])
            self.data["ships"].append({**ship, "version": 1})
        else:
            assert body["kind"] == "operation.import"
            checked = self.validate(body["payload"]["rows"])
            assert not checked["errors"]
            self.data["records"].extend({**row, "version": 1} for row in checked["rows"])
        self.writes.append(deepcopy(body))
        return {"status": "approved"}

    def validate(self, rows):
        store = EmptyOperationStore(self.data["ships"][0])
        store.operations = lambda: self.data["records"]
        return store.validate_rows(rows)


def test_publisher_appends_only_new_completed_days_and_rejects_conflicts(tmp_path):
    log = tmp_path / "publish.sqlite3"
    app = InMemoryPublisherApp()
    first = advance(log, DEPARTURE, START + timedelta(days=1, hours=23))
    preview = publish(app, first, apply=False)
    assert preview["pending_days"] == 1 and app.writes == []

    published = publish(app, first, apply=True)
    assert published["imported_days"] == published["completed_days"] == 1
    assert [request["kind"] for request in app.writes] == ["ship.save", "operation.import"]
    assert [row["id"] for row in app.data["records"]] == [first["records"][0]["id"]]

    again = publish(app, first, apply=True)
    assert again["already_present"] == 1 and again["imported_days"] == 0
    assert len(app.writes) == 2

    next_day = advance(log, DEPARTURE, START + timedelta(days=2, hours=12))
    resumed = publish(app, next_day, apply=True)
    assert resumed["already_present"] == resumed["imported_days"] == 1
    assert len(app.writes) == 3
    assert app.writes[-1] == {"kind": "operation.import", "payload": {"rows": next_day["records"][1:]}}
    assert [row["id"] for row in app.data["records"]] == [row["id"] for row in next_day["records"]]

    # A remote edit must stop the next day from being imported as well.
    app.data["records"][0]["fuel"] += 1
    before = deepcopy(app.data)
    third_day = advance(log, DEPARTURE, START + timedelta(days=3))
    with pytest.raises(ValueError, match="differs"):
        publish(app, third_day, apply=True)
    assert app.data == before and len(app.writes) == 3
