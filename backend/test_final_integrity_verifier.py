"""Saved-content policy checks; no providers, application DB or network."""
import copy
import importlib
import importlib.util
import json
import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest


FIXTURES = Path(__file__).parent / "tests/fixtures"
DEFER_WARNING = "Runtime integration explicitly deferred. Approved design only; no runtime release or materialization."


@pytest.fixture
def verifier():
    assert importlib.util.find_spec("verify_final_integrity") is not None, "Final integrity verifier is missing"
    return importlib.import_module("verify_final_integrity")


@pytest.fixture
def run_c():
    saved = json.loads((FIXTURES / "frostpeak_run_c_integrity.json").read_text(encoding="utf-8"))
    reviewed = saved["reviewed"]
    # The retained final differs in this section only; hashes below bind the full pair.
    final = {**copy.deepcopy(reviewed), **saved["final_section_overrides"]}
    return reviewed, final, saved["frozen_settings"]


def test_run_c_allows_only_its_derived_memory_marker(run_c):
    assert importlib.util.find_spec("verify_final_integrity") is not None, "Final integrity verifier is missing"
    verifier = importlib.import_module("verify_final_integrity")
    reviewed, final, settings = run_c
    before = copy.deepcopy(run_c)
    report = verifier.verify_final_integrity(reviewed, final, settings)
    assert report["verdict"] == "EQUAL_EXCEPT_DOCUMENTED_METADATA"
    assert report["reviewed_sha256"] == "dbe29661c605d09f589d3963c4c94b33021af9f19e3c8b20dd10d79096e1b118"
    assert report["final_sha256"] == "11b12b7aabc3f2c7f02982f7450c66b9af4336d1f22bf98f12960bf7618052b7"
    assert report["differing_paths"] == ["/npc_memory_design/memory_unspecified"]
    assert report["permitted_additions"] == [{"path": "/npc_memory_design/memory_unspecified", "value": True}]
    assert report["offending_paths"] == []
    assert run_c == before


def test_fixed_b4b_pair_is_exact_not_a_metadata_exception(verifier):
    saved = json.loads((FIXTURES / "frostpeak_b4c_reviewed.json").read_text(encoding="utf-8"))
    report = verifier.verify_final_integrity(saved["content"], copy.deepcopy(saved["content"]), saved["config"])
    assert report["verdict"] == "EXACT"
    assert report["reviewed_sha256"] == report["final_sha256"] == "8c6b049ab9793c5594de8e4be45248e6644541b7ed732b71957bfc6533955817"
    assert report["differing_paths"] == report["offending_paths"] == []


@pytest.mark.parametrize("fault,path", [
    ("extra", "/summary/content/unexpected"),
    ("changed", "/summary/content/description"),
    ("removed", "/summary/confidence"),
    ("hidden", "/narrative_direction/memory_unspecified"),
    ("flag_value", "/npc_memory_design/memory_unspecified"),
    ("number_type", "/summary/content/count"),
])
def test_unexpected_additions_edits_deletions_and_type_changes_fail(verifier, run_c, fault, path):
    reviewed, final, settings = run_c
    if fault == "extra":
        final["summary"]["content"]["unexpected"] = "Not reviewed"
    elif fault == "changed":
        final["summary"]["content"]["description"] = "Invented premise"
    elif fault == "removed":
        del final["summary"]["confidence"]
    elif fault == "hidden":
        final["narrative_direction"]["memory_unspecified"] = True
    elif fault == "flag_value":
        final["npc_memory_design"]["memory_unspecified"] = 1
    else:
        reviewed["summary"]["content"]["count"] = 1
        final["summary"]["content"]["count"] = True
    report = verifier.verify_final_integrity(reviewed, final, settings)
    assert report["verdict"] == "MISMATCH"
    assert path in report["differing_paths"] and path in report["offending_paths"]


@pytest.mark.parametrize("fault", ["no_opt_in", "truthy_opt_in", "content", "citation", "no_warning"])
def test_memory_flag_requires_the_reviewed_predicate_not_final_claims(verifier, run_c, fault):
    reviewed, final, settings = run_c
    if fault == "no_opt_in":
        settings["allow_unspecified_memory"] = False
    elif fault == "truthy_opt_in":
        settings["allow_unspecified_memory"] = 1
    elif fault == "content":
        reviewed["npc_memory_design"]["content"] = {"rules": ["Remember a choice"]}
    elif fault == "citation":
        reviewed["npc_memory_design"]["citations"] = ["a-source"]
    else:
        reviewed["npc_memory_design"]["warnings"] = [" "]
    final["npc_memory_design"] = {**copy.deepcopy(reviewed["npc_memory_design"]), "memory_unspecified": True}
    report = verifier.verify_final_integrity(reviewed, final, settings)
    assert report["verdict"] == "MISMATCH"
    assert "/npc_memory_design/memory_unspecified" in report["offending_paths"]


@pytest.mark.parametrize("fault", [None, "wrong_warning", "no_opt_in", "truthy_opt_in", "missing_warning", "removed_existing_warning"])
def test_runtime_metadata_is_exact_and_requires_frozen_deferral(verifier, run_c, fault):
    reviewed, final, settings = run_c
    reviewed["unity_runtime_preview"] = {"content": {}, "citations": [], "confidence": "Low", "warnings": ["Already reviewed"]}
    final["unity_runtime_preview"] = {**copy.deepcopy(reviewed["unity_runtime_preview"]), "runtime_deferred": True,
                                      "warnings": ["Already reviewed", DEFER_WARNING]}
    settings["defer_runtime"] = True
    if fault == "wrong_warning":
        final["unity_runtime_preview"]["warnings"][1] = "Runtime approved"
    elif fault == "no_opt_in":
        settings["defer_runtime"] = False
    elif fault == "truthy_opt_in":
        settings["defer_runtime"] = "true"
    elif fault == "missing_warning":
        final["unity_runtime_preview"]["warnings"].pop()
    elif fault == "removed_existing_warning":
        final["unity_runtime_preview"]["warnings"].pop(0)
    report = verifier.verify_final_integrity(reviewed, final, settings)
    assert report["verdict"] == ("MISMATCH" if fault else "EQUAL_EXCEPT_DOCUMENTED_METADATA")
    if fault:
        assert any(path.startswith("/unity_runtime_preview/") for path in report["offending_paths"])
    else:
        assert {item["path"] for item in report["permitted_additions"]} == {
            "/npc_memory_design/memory_unspecified", "/unity_runtime_preview/runtime_deferred", "/unity_runtime_preview/warnings/1"}


def test_existing_flag_is_not_permission_to_change_a_reviewed_value(verifier, run_c):
    reviewed, final, settings = run_c
    reviewed["npc_memory_design"]["memory_unspecified"] = False
    report = verifier.verify_final_integrity(reviewed, final, settings)
    assert report["verdict"] == "MISMATCH"
    assert "/npc_memory_design/memory_unspecified" in report["offending_paths"]


def test_all_unexpected_paths_are_reported_with_json_pointer_escaping(verifier, run_c):
    reviewed, final, settings = run_c
    final["summary"]["warnings"].append("Unreviewed warning")
    final["summary"]["content"]["a/b~c"] = "Unreviewed value"
    report = verifier.verify_final_integrity(reviewed, final, settings)
    assert report["offending_paths"] == ["/summary/content/a~1b~0c", "/summary/warnings/1"]


@pytest.mark.parametrize("mismatch", [False, True])
def test_cli_prints_the_same_report_without_a_provider(verifier, run_c, monkeypatch, capsys, mismatch):
    if mismatch:
        run_c[1]["summary"]["content"]["description"] = "Unreviewed text"
    monkeypatch.setattr(verifier, "read_run", lambda run_id, database_url: run_c)
    assert verifier.main(["fc541ba1-fa2d-48bc-bf04-20822bc37b18", "--database-url", "postgresql://disposable-only"]) == (1 if mismatch else 0)
    assert json.loads(capsys.readouterr().out)["verdict"] == ("MISMATCH" if mismatch else "EQUAL_EXCEPT_DOCUMENTED_METADATA")


def test_unicode_hash_uses_utf8_not_ascii_escapes(verifier):
    report = verifier.verify_final_integrity({"label": "café"}, {"label": "café"}, {})
    assert report["reviewed_sha256"] == hashlib.sha256(b'{"label":"caf\xc3\xa9"}').hexdigest()
    assert report["verdict"] == "EXACT"


def test_run_reader_sets_read_only_before_approval_linked_selects(verifier, run_c, monkeypatch):
    import sqlalchemy
    reviewed, final, settings = run_c
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    results = [None]
    for row in ({"game_project_id": "isolated-fixture", "status": "completed", "model_config": settings},
                {"content": final, "immutable": True}, {"content": reviewed}):
        result = MagicMock()
        result.mappings.return_value.one_or_none.return_value = row
        results.append(result)
    connection.execute.side_effect = results
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_args, **_kwargs: engine)
    assert verifier.read_run("fc541ba1-fa2d-48bc-bf04-20822bc37b18", "postgresql://fixture-only") == run_c
    calls = connection.execute.call_args_list
    assert str(calls[0].args[0]) == "SET TRANSACTION READ ONLY"
    assert all(str(call.args[0]).startswith("SELECT ") for call in calls[1:])
    assert "review.decision = 'approve'" in str(calls[-1].args[0])
    assert "review.artifact_id = artifact.id" in str(calls[-1].args[0])
    assert calls[-1].args[1] == {"run_id": "fc541ba1-fa2d-48bc-bf04-20822bc37b18", "project": "isolated-fixture"}


def test_cli_database_error_does_not_print_credentials(verifier, monkeypatch, capsys):
    from sqlalchemy.exc import OperationalError
    def fail(*_args):
        raise OperationalError("private SQL", {}, RuntimeError("secret-in-connection-url"))
    monkeypatch.setattr(verifier, "read_run", fail)
    assert verifier.main(["fc541ba1-fa2d-48bc-bf04-20822bc37b18"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "OperationalError" in captured.err
    assert "secret-in-connection-url" not in captured.err and "private SQL" not in captured.err
