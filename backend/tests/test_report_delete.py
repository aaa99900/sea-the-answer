"""Report deletion permissions/conflicts and review race regressions (no live DB)."""
from unittest.mock import Mock

import pytest

from api import deps
from api.errors import ApiError
from api.store import Workspace
from test_authentication import auth
from test_fastapi_api import ADMIN


def store_with_report(version=3):
    store = object.__new__(Workspace)
    store.one = Mock(return_value={"title": "Review report", "version": version})
    store.run = Mock()
    store.audit = Mock()
    return store


@pytest.mark.parametrize("role", ["guest", "operator", "viewer"])
def test_non_admin_cannot_delete_even_their_own_report(role):
    store = store_with_report()
    with pytest.raises(ApiError) as error:
        store.delete_report({"id": "owner", "role": role}, {"id": "report-1", "version": 3})
    assert error.value.status == 403
    store.one.assert_not_called()
    store.run.assert_not_called()


@pytest.mark.parametrize("version", [None, 0, -1, True, "3"])
def test_invalid_version_never_deletes(version):
    store = store_with_report()
    with pytest.raises(ApiError) as error:
        store.delete_report(ADMIN, {"id": "report-1", "version": version})
    assert error.value.status == 400
    store.run.assert_not_called()


def test_stale_or_missing_report_does_not_change_data():
    store = store_with_report()
    with pytest.raises(ApiError) as error:
        store.delete_report(ADMIN, {"id": "report-1", "version": 2})
    assert error.value.code == "VERSION_CONFLICT"
    store.run.assert_not_called()
    store.one.return_value = None
    with pytest.raises(ApiError) as error:
        store.delete_report(ADMIN, {"id": "missing", "version": 3})
    assert error.value.status == 404
    store.run.assert_not_called()


def test_delete_closes_pending_reviews_keeps_history_and_audits():
    store = store_with_report()
    assert store.delete_report(ADMIN, {"id": "report-1", "version": 3}) == {"ok": True, "id": "report-1"}
    assert "FOR UPDATE" in store.one.call_args.args[0]
    calls = store.run.call_args_list
    assert "status='pending'" in calls[0].args[0]
    assert "status='rejected'" in calls[0].args[0]
    assert calls[0].args[1][-1] == "report-1"
    assert [call.args[0] for call in calls[1:]] == [
        "DELETE FROM report_meta WHERE id=%s", "DELETE FROM reports WHERE id=%s"]
    store.audit.assert_called_once_with(ADMIN, "report", "보고서 삭제", "report-1",
                                       {"title": "Review report", "version": 3})


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_review_rechecks_after_waiting_for_concurrent_delete(decision):
    store = store_with_report()
    pending = {"id": "change-1", "kind": "report.approve", "status": "pending",
               "payload": {"id": "report-1", "version": 3}}
    store.one.side_effect = [pending, None, {**pending, "status": "rejected"}]
    store.apply_change = Mock()
    with pytest.raises(ApiError) as error:
        store.review_change(ADMIN, {"id": "change-1", "decision": decision})
    assert error.value.status == 409
    store.apply_change.assert_not_called()
    store.run.assert_not_called()


def test_delete_api_requires_csrf_admin_and_routes_to_store(monkeypatch, auth):
    client, headers, _accounts = auth
    writes = []

    class ReportWorkspace(deps.Workspace):
        delete_report = Workspace.delete_report
        permit = Workspace.permit

        def one(self, query, params=()):
            if "FROM reports" in query:
                return {"title": "Report", "version": 3}
            return super().one(query, params)

        def run(self, query, params=()):
            writes.append((query, params))

    monkeypatch.setattr(deps, "Workspace", ReportWorkspace)
    payload = {"id": "report-1", "version": 3}
    assert client.post("/api/reports/delete", json=payload).status_code == 403
    denied = client.post("/api/reports/delete", headers=headers, json=payload)
    assert denied.status_code == 401 and denied.json()["error"]["code"] == "AUTH_REQUIRED"
    assert not writes
    for role in ("operator", "viewer"):
        assert client.post("/api/auth/login", headers=headers,
                           json={"username": role, "password": "Test-only-password"}).status_code == 200
        denied = client.post("/api/reports/delete", headers=headers, json=payload)
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "FORBIDDEN"
        assert not writes
    assert client.post("/api/auth/login", headers=headers,
                       json={"username": "admin", "password": "Test-only-password"}).status_code == 200
    deleted = client.post("/api/reports/delete", headers=headers, json=payload)
    assert deleted.status_code == 200 and deleted.json() == {"ok": True, "id": "report-1"}
    assert len(writes) == 3
