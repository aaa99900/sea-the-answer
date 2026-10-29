"""Fixed-evidence CLI checks; all model calls use mock HTTP, never a real LLM."""

from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from api import config, llm
from scripts import evaluate_llm as evaluation


SETTINGS = config.LLMSettings("http://localhost:11434/v1", "mock-model", "", "json_schema")


def cases(*ids):
    return [case for case in evaluation.load_cases() if not ids or case["id"] in ids]


def model_transport(monkeypatch, answer):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(llm.httpx, "post", client.post)
    return calls, client


def test_default_cli_offline_baseline_has_sixteen_checked_seed_cases(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Offline evaluation must not read configuration or contact a model")

    monkeypatch.setattr(config, "llm_settings", forbidden)
    monkeypatch.setattr(llm, "grounded_statements", forbidden)
    assert evaluation.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == report["execution"] == "extractive"
    assert report["model_call_attempted"] is False
    assert report["model"] is None and report["response_format"] is None
    assert report["summary"] == {"cases": 16, "answered": 16, "insufficient": 0, "model_error": 0}
    assert len(report["llm_code_sha256"]) == 64
    assert report["semantic_review"] == "pending"
    for row in report["results"]:
        assert row["generation"] == "extractive"
        assert row["model_call_attempted"] is False
        assert row["citation_valid"] is True
        assert row["semantic_review"] == "pending"
        assert row["expected"]["facts"] and row["sources"]
    english = next(row for row in report["results"] if row["id"] == "english-lookout-korean-answer")
    assert english["contains_hangul"] is False  # The offline baseline copies English evidence.


def test_llm_mode_uses_production_transport_and_preserves_original_english_quote(monkeypatch):
    selected = cases("english-lookout-korean-answer")
    evidence = selected[0]["evidence"][0]
    statement = {"text": "모든 선박은 항상 시각과 청각으로 적절한 경계를 유지해야 합니다.",
                 "chunkId": evidence["id"],
                 "quote": "Every vessel shall at all times maintain a proper look-out by sight and hearing"}
    calls, client = model_transport(monkeypatch, {"insufficient": False, "statements": [statement]})
    with client:
        report = evaluation.evaluate(selected, "llm", settings=SETTINGS)
    assert len(calls) == 1
    request = json.loads(calls[0].content)
    assert request["model"] == "mock-model"
    assert request["response_format"]["type"] == "json_schema"
    assert json.loads(request["messages"][1]["content"])["evidence"][0]["text"] == evidence["text"]
    assert "Korean" in request["messages"][0]["content"]
    assert report["execution"] == "real_model" and report["model_call_attempted"] is True
    row = report["results"][0]
    assert row["outcome"] == "answered" and row["statements"] == [statement]
    assert row["citation_valid"] is True and row["contains_hangul"] is True
    assert row["semantic_review"] == "pending"


def test_valid_citation_does_not_grade_wrong_answer_as_semantically_correct(monkeypatch):
    selected = cases("sulphur-limits")
    evidence = selected[0]["evidence"][0]
    wrong = {"text": "문서에서 말하는 황 한도는 99%입니다.", "chunkId": evidence["id"], "quote": evidence["text"]}
    calls, client = model_transport(monkeypatch, {"insufficient": False, "statements": [wrong]})
    with client:
        row = evaluation.evaluate(selected, "llm", settings=SETTINGS)["results"][0]
    assert len(calls) == 1
    assert row["citation_valid"] is True and row["outcome"] == "answered"
    assert row["semantic_review"] == "pending"
    assert "accuracy" not in row and "semantic_correct" not in row


def test_insufficient_response_is_normal_without_claiming_a_valid_citation(monkeypatch):
    calls, client = model_transport(monkeypatch, {"insufficient": True, "statements": []})
    with client:
        report = evaluation.evaluate(cases("unsupported-captain-name"), "llm", settings=SETTINGS)
    row = report["results"][0]
    assert len(calls) == 1 and row["outcome"] == "insufficient"
    assert row["citation_valid"] is None and row["expected_insufficient_matches"] is True
    assert row["generation"] == "llm" and row["semantic_review"] == "pending"
    assert report["summary"]["model_error"] == 0


def test_bad_citation_is_model_error_without_extractive_fallback(monkeypatch):
    selected = cases("sulphur-limits")
    bad = {"text": "잘못된 인용", "chunkId": selected[0]["evidence"][0]["id"], "quote": "존재하지 않는 긴 인용문입니다."}
    calls, client = model_transport(monkeypatch, {"insufficient": False, "statements": [bad]})
    with client:
        row = evaluation.evaluate(selected, "llm", settings=SETTINGS)["results"][0]
    assert len(calls) == 1 and row["outcome"] == "model_error"
    assert row["generation"] is None and row["statements"] == [] and row["citation_valid"] is False


def test_model_error_creates_report_and_exit_one_without_private_exception(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "llm_settings", lambda: SETTINGS)

    def fail(*_args, **_kwargs):
        raise httpx.ConnectError("PRIVATE_API_KEY=https://secret-host.example/?secret=password")

    monkeypatch.setattr(llm, "grounded_statements", fail)
    output = tmp_path / "failure.json"
    assert evaluation.main(["--mode", "llm", "--case", "sulphur-limits", "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    serialized = json.dumps(report) + captured.out + captured.err
    assert "PRIVATE_API_KEY" not in serialized and "secret-host" not in serialized and "password" not in serialized
    assert report["summary"]["model_error"] == 1
    assert report["results"][0]["error_type"] == "ConnectError"


def test_repeated_case_selection_and_new_utf8_report(tmp_path, capsys):
    output = tmp_path / "선택-평가.json"
    assert evaluation.main(["--case", "sulphur-limits", "--case", "cii-scope", "--output", str(output)]) == 0
    assert capsys.readouterr().out == ""
    report = json.loads(output.read_text(encoding="utf-8"))
    assert [row["id"] for row in report["results"]] == ["sulphur-limits", "cii-scope"]
    assert "연료" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("reason", ["existing_output", "unknown_case", "missing_settings"])
def test_invalid_cli_input_fails_before_model_call(monkeypatch, tmp_path, capsys, reason):
    called = []
    monkeypatch.setattr(llm, "grounded_statements", lambda *_args, **_kwargs: called.append(True))
    monkeypatch.setattr(config, "llm_settings", lambda: None if reason == "missing_settings" else SETTINGS)
    output = tmp_path / "existing.json"
    args = ["--mode", "llm", "--case", "sulphur-limits"]
    if reason == "existing_output":
        output.write_text("preserve me", encoding="utf-8")
        args += ["--output", str(output)]
    elif reason == "unknown_case":
        args += ["--case", "does-not-exist"]
    assert evaluation.main(args) == 1
    assert called == []
    assert capsys.readouterr().err.startswith("Evaluation failed:")
    if reason == "existing_output":
        assert output.read_text(encoding="utf-8") == "preserve me"


@pytest.mark.parametrize("mutation", ["duplicate_case", "duplicate_source", "missing_document", "missing_heading", "wrong_anchor", "short_anchor", "invalid_expected"])
def test_fixture_drift_and_ambiguous_sources_are_rejected(tmp_path, mutation):
    data = deepcopy(json.loads(evaluation.DEFAULT_CASES.read_text(encoding="utf-8")))[:1]
    if mutation == "duplicate_case":
        data.append(deepcopy(data[0]))
    elif mutation == "duplicate_source":
        data[0]["sources"].append(deepcopy(data[0]["sources"][0]))
    elif mutation == "invalid_expected":
        data[0]["expected"]["insufficient"] = "false"
    else:
        field, value = {"missing_document": ("document_id", "not-in-seed"),
                        "missing_heading": ("heading", "absent-heading"),
                        "wrong_anchor": ("anchor", "not present in this source"),
                        "short_anchor": ("anchor", "짧음")}[mutation]
        data[0]["sources"][0][field] = value
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        evaluation.load_cases(path)


def test_duplicate_seed_document_is_rejected(tmp_path):
    documents = json.loads(evaluation.DEFAULT_SEED.read_text(encoding="utf-8"))
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(documents + [documents[0]], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate source document"):
        evaluation.load_cases(seed_path=path)


def test_unwritable_output_fails_before_any_model_call(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(config, "llm_settings", lambda: SETTINGS)
    monkeypatch.setattr(llm, "grounded_statements", lambda *_args: calls.append(True) or [])
    output = tmp_path / "missing-parent" / "report.json"
    assert evaluation.main(["--mode", "llm", "--output", str(output)]) == 1
    assert calls == [] and not output.exists()


def test_input_fingerprint_covers_question_and_source_text():
    selected = cases("sulphur-limits")
    original = evaluation.evaluate(selected, "extractive")["evaluation_input_sha256"]
    assert len(original) == 64
    assert evaluation.evaluate(deepcopy(selected), "extractive")["evaluation_input_sha256"] == original
    for field in ("question", "text"):
        changed = deepcopy(selected)
        target = changed[0] if field == "question" else changed[0]["evidence"][0]
        target[field] += " source changed"
        assert evaluation.evaluate(changed, "extractive")["evaluation_input_sha256"] != original
