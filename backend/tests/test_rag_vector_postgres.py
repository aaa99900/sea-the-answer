"""Real rollback-only PG + real Chroma, deterministic fake embeddings (offline)."""
import os

import pytest
from fastapi.testclient import TestClient

from api import main
from api.errors import ApiError
from api.rag_vector import VectorIndex
from rag_postgres_support import configure_api, isolated_workspace
from test_rag_vector import Encoder
from test_rag_postgres import payload


@pytest.mark.parametrize("mode", ["vector", "hybrid"])
def test_api_modes_scope_revisions_and_citations(monkeypatch, tmp_path, mode):
    dsn = os.getenv("HAEDAP_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("HAEDAP_TEST_DATABASE_URL not configured")
    import chromadb
    from chromadb.config import Settings
    db = chromadb.PersistentClient(path=str(tmp_path), settings=Settings(anonymized_telemetry=False))
    index = VectorIndex(create=True, db=db, encoder=Encoder(), model_contract={"test": 1})
    monkeypatch.setenv("HAEDAP_RETRIEVAL_MODE", mode)
    monkeypatch.setattr("api.rag_vector.VectorIndex", lambda: index)
    with isolated_workspace(dsn) as (store, request_workspace):
        configure_api(monkeypatch, request_workspace)
        store.run("UPDATE documents SET active=false")
        data = payload()
        data["document"]["sections"] = [{"page": 21, "heading": "선급 정지", "text": "선급 자동 정지의 가상 검증용 근거입니다."}]
        identity = store.save_document(data)["id"]
        guest_user = {"role": "guest"}
        index.index(store.search_candidates(guest_user))
        client = TestClient(main.app, base_url="http://localhost:5173")
        health = client.get("/api/health").json()
        assert health["retrieval"] == ("vector-e5" if mode == "vector" else "hybrid-rrf")
        headers = {"X-Haedap-Token": health["csrfToken"]}
        response = client.post("/api/search", headers=headers, json={"question": "선급 정지"})
        assert response.status_code == 200
        evidence = response.json()["evidence"]
        assert evidence[0]["document_id"] == identity and evidence[0]["page"] == 21
        assert "score" not in evidence[0]
        answer = client.post("/api/ask", headers=headers, json={"question": "선급 정지", "task": "documents"}).json()
        assert answer["statements"][0]["chunkId"] == evidence[0]["id"]
        assert answer["statements"][0]["quote"] in evidence[0]["text"]
        assert store.search(guest_user, "선급", document_ids=[identity])
        assert store.search(guest_user, "선급", kind="imo") == []
        data["expectedId"] = identity
        data["meta"]["scope"] = "admin"
        store.save_document(data)
        assert store.search(guest_user, "선급") == []
        with pytest.raises(ApiError):
            store.search(guest_user, "선급", document_ids=[identity])
        assert store.search({"role": "admin"}, "선급")
        data["meta"]["scope"] = "all"
        data["document"]["sections"][0]["text"] += " 개정된 추가 근거입니다."
        revised = store.save_document(data)["id"]
        assert revised != identity
        # Missing new vectors must fall back, never return old active revision.
        assert {row["document_id"] for row in store.search(guest_user, "선급")} == {revised}
        index.index(store.search_candidates(guest_user))
        assert {row["document_id"] for row in store.search(guest_user, "선급")} == {revised}
        data["expectedId"] = revised
        data["meta"]["status"] = "retired"
        store.save_document(data)
        assert store.search(guest_user, "선급") == []
        data["meta"]["status"] = "active"
        store.save_document(data)
        store.delete_document(revised)
        assert store.search(guest_user, "선급") == []
