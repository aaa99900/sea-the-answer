"""MEPC source integrity and one-time upgrade; no external services required."""
import base64
import copy
import json
from pathlib import Path
import pytest
from api import knowledge_update as update
from api.rag_preprocessing import preprocess_sections
from api.store import Workspace

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'knowledge'
BUNDLE = json.loads((KNOWLEDGE / 'mepc-2026.json').read_text())
SEED = json.loads((KNOWLEDGE / 'seed.json').read_text())


def test_exact_requested_documents_and_old_titles():
    assert len(BUNDLE) == len({d['id'] for d in BUNDLE}) == 10
    assert {Path(d['file']).name for d in BUNDLE} == {
        'MEPC.352(78).pdf', 'MEPC.353(78).pdf', 'MEPC.354(78).pdf', 'MEPC.355(78).pdf',
        'MEPC.412(84).pdf', 'MEPC 83-17-Add.1 - Annex 4.pdf',
        *{f'MEPC 84-16{suffix} - Report Of The Marine Environment Protection Committee On Its Eighty-Fourth Session (Secretariat).pdf'
          for suffix in ('', '-Add.1', '-Add.2', '-Add.3')},
    }
    assert all(d['title'].startswith('(테스트용) ') and not d['title'].endswith('(가상)') for d in SEED)


@pytest.mark.parametrize('raw', BUNDLE, ids=lambda d: d['id'])
def test_searchable_pages_and_original_pdf(raw):
    payload = update.document_payload(raw, KNOWLEDGE)
    assert 'file' not in payload['document'] and 'meta' not in payload['document']
    original = (KNOWLEDGE / raw['file']).read_bytes()
    assert original.startswith(b'%PDF-') and len(original) <= 25 * 1024 * 1024
    assert base64.b64decode(payload['file']['base64']) == original
    assert payload['meta']['issuer'] == 'IMO'
    assert not raw['title'].startswith('(테스트용)')
    assert len(raw['title']) <= 200 and len(raw['reference']) <= 200
    assert 0 < len(raw['sections']) <= 1000
    assert 0 < sum(len(s['text']) for s in raw['sections']) <= 2000000
    pages = [s['page'] for s in raw['sections']]
    assert pages == sorted(set(pages))
    assert all(0 < len(s['text']) <= 20000 for s in raw['sections'])
    chunks = preprocess_sections(raw['sections'])
    assert chunks and all(c['page'] in pages for c in chunks)


class UpgradeStore:
    def __init__(self):
        self.docs = [
            {'id': 'old-current', 'logical_id': 'old', 'title': '기존 문서 (가상)', 'active': True},
            {'id': 'old-revision', 'logical_id': 'old', 'title': '기존 구버전', 'active': False},
            {'id': 'custom', 'logical_id': 'custom', 'title': '직접 등록한 문서', 'active': True},
            {'id': 'prefixed', 'logical_id': 'prefixed', 'title': '(테스트용) 기존 표시 (가상)', 'active': True},
        ]
        self.settings, self.saved = {}, []

    def one(self, sql, params=()):
        if 'WHERE key=' in sql:
            return {'value': self.settings[params[0]]} if params[0] in self.settings else None
        if 'WHERE logical_id=' in sql:
            return next((d for d in self.docs if d['logical_id'] == params[0]), None)
        if 'FROM documents' in sql:
            return self.docs[0] if self.docs else None
        return {'ok': 1}

    def all(self, sql, params=()):
        assert sql == 'SELECT id,title,active FROM documents FOR UPDATE'
        return copy.deepcopy(self.docs)

    def run(self, sql, params=()):
        if sql.startswith('UPDATE documents SET title='):
            next(d for d in self.docs if d['id'] == params[1])['title'] = params[0]
        elif sql.startswith('INSERT INTO settings(key,value) VALUES(%s,%s)'):
            assert params[0] not in self.settings
            self.settings[params[0]] = params[1]
        else:
            assert 'autoBackup' in sql

    def save_document(self, payload):
        d = payload['document']
        self.saved.append(payload)
        self.docs.append({'id': d['id'], 'logical_id': d['id'], 'title': d['title'], 'active': True})
        return {'id': d['id'], 'status': 'created'}


def test_existing_database_upgrade_is_once_and_preserves_deletions(monkeypatch):
    store, queued = UpgradeStore(), []
    monkeypatch.setattr(update, 'enqueue', lambda db, ident: queued.append(ident))
    Workspace.bootstrap(store)
    assert [d['id'] for d in store.docs[:4]] == ['old-current', 'old-revision', 'custom', 'prefixed']
    assert [d['title'] for d in store.docs[:4]] == ['(테스트용) 기존 문서', '(테스트용) 기존 구버전', '(테스트용) 직접 등록한 문서', '(테스트용) 기존 표시']
    assert queued == ['old-current', 'custom', 'prefixed']
    assert len(store.saved) == 10
    store.docs[-1]['active'] = False
    before = copy.deepcopy(store.docs)
    Workspace.bootstrap(store)
    assert store.docs == before and len(store.saved) == 10 and len(queued) == 3


def test_fresh_database_has_twenty_documents(monkeypatch):
    store = UpgradeStore()
    store.docs = []
    monkeypatch.setattr(update, 'enqueue', lambda *args: None)
    Workspace.bootstrap(store)
    assert len(store.docs) == 20
    assert all(d['title'].startswith('(테스트용)') for d in store.docs[:10])
    assert all(not d['title'].startswith('(테스트용)') for d in store.docs[10:])
    Workspace.bootstrap(store)
    assert len(store.docs) == 20


def test_failed_import_does_not_record_success_marker(monkeypatch):
    store = UpgradeStore()
    monkeypatch.setattr(update, 'enqueue', lambda *args: None)
    def fail(_payload):
        raise RuntimeError('test import failure')
    monkeypatch.setattr(store, 'save_document', fail)
    with pytest.raises(RuntimeError, match='test import failure'):
        Workspace.bootstrap(store)
    assert update.UPDATE_KEY not in store.settings
    # Database.__exit__ owns PostgreSQL rollback; this double only checks the marker.
