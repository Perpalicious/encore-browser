import copy
import http.client
import json
import os
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from deterministic_pipeline.config import load_rules
from deterministic_pipeline.review import (
    ATTESTATION_STATEMENT, ConflictError, ReviewError, SessionStore,
    atomic_json, export_gold, generate_session, handler, load_session,
    validate_export_path, validate_generation_path, validate_review,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(__file__).parent / "fixtures/review_raw.json"


@pytest.fixture(scope="module")
def rules():
    return load_rules(ROOT / "buckets.yaml", ROOT / "profile.yaml")


def complete(review):
    return {**review, "reviewed": True, "expected_buckets": [],
            "forbidden_buckets": [], "expected_subtype": None,
            "expected_evidence_kinds": [], "expected_personal": False,
            "critical_assertions": [], "rationale": "Reviewed as a negative example by Bat."}


def attest_args():
    return "Bat", date.today().isoformat(), True


def test_sampling_is_deterministic_stratified_deduplicated_and_unlabelled(tmp_path, rules):
    first = generate_session(RAW, tmp_path / "one.json", rules, "Bat", per_stratum=2)
    second = generate_session(RAW, tmp_path / "two.json", rules, "Bat", per_stratum=2)
    assert [row["id"] for row in first["items"]] == [row["id"] for row in second["items"]]
    assert first["sampling"]["products_seen"] == 5
    assert first["sampling"]["coverage"]["positive:Keyboards & PC peripherals"]["available"]
    assert any("multi_label" in row["selection_keys"] for row in first["items"])
    assert any("personal_hard_gate" in row["selection_keys"] for row in first["items"])
    assert all(row["review"]["reviewed"] is False and row["review"]["expected_buckets"] is None
               for row in first["items"])


def test_zero_candidate_generation_is_refused(tmp_path, rules):
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps({"items": [{"lot_number": "1", "title": "Wooden shelf",
        "condition": "Good", "hibid_category_path": "Furniture - Shelves"}]}))
    with pytest.raises(ReviewError, match="zero reviewable"):
        generate_session(raw, tmp_path / "session.json", rules, "Bat")


def test_generation_path_fails_closed_before_touching_inputs(tmp_path, rules):
    raw = tmp_path / "raw.json"; raw.write_bytes(RAW.read_bytes())
    original = raw.read_bytes()
    with pytest.raises(ReviewError):
        generate_session(raw, raw, rules, "Bat")
    assert raw.read_bytes() == original
    protected = [ROOT / "buckets.yaml", ROOT / "profile.yaml",
                 ROOT / "viewer/src/data/auction_bundle.json"]
    hashes = {path: path.read_bytes() for path in protected}
    for path in protected:
        with pytest.raises(ReviewError):
            validate_generation_path(path, [raw, *protected])
    assert all(path.read_bytes() == content for path, content in hashes.items())
    unsafe = ROOT / "unsafe-review-session.json"
    with pytest.raises(ReviewError, match="protected repository"):
        validate_generation_path(unsafe, [raw, *protected])
    assert not unsafe.exists()
    broken = tmp_path / "broken-link"; broken.symlink_to(tmp_path / "missing")
    with pytest.raises(ReviewError, match="symlink"):
        validate_generation_path(broken, [raw, *protected])


def test_atomic_backup_resume_audit_and_optimistic_concurrency(tmp_path, rules):
    path = tmp_path / "session.json"; session = generate_session(RAW, path, rules, "Bat")
    item = session["items"][0]; store = SessionStore(path, rules)
    saved = store.update(item["id"], complete(item["review"]), "Bat", 0)
    assert saved["revision"] == 1 and saved["audit"][0]["actor"] == "Bat"
    assert path.with_name("session.json.bak").is_file()
    with pytest.raises(ConflictError, match="stale"):
        store.update(item["id"], complete(item["review"]), "Bat", 0)
    path.write_text("broken")
    assert load_session(path, rules)["schema_version"] == 2


def test_validation_rejects_duplicates_vocab_subtype_and_bad_critical(tmp_path, rules):
    session_path = tmp_path / "session.json"
    item = generate_session(RAW, session_path, rules, "Bat")["items"][0]
    review = complete(item["review"])
    for field in ("expected_buckets", "forbidden_buckets", "expected_evidence_kinds", "critical_assertions"):
        with pytest.raises(ReviewError, match="duplicate"):
            validate_review({**review, field: ["x", "x"]}, rules, item["source"], item["prediction"])
    with pytest.raises(ReviewError, match="unknown evidence"):
        validate_review({**review, "expected_evidence_kinds": ["invented"]}, rules, item["source"], item["prediction"])
    with pytest.raises(ReviewError, match="unknown critical"):
        validate_review({**review, "critical_assertions": ["invented"]}, rules, item["source"], item["prediction"])
    with pytest.raises(ReviewError, match="not controlled"):
        validate_review({**review, "expected_buckets": ["Smart locks"],
                         "expected_subtype": "invented"}, rules, item["source"], item["prediction"])
    with pytest.raises(ReviewError, match="keyboard assertion"):
        validate_review({**review, "critical_assertions": ["keyboard"]}, rules, item["source"], item["prediction"])
    with pytest.raises(ReviewError, match="min_positive"):
        SessionStore(session_path, rules).update_exemptions({
            "Smart locks": {"reason": "Reviewed supply is too small for standard coverage.",
                            "min_positive": True, "min_negative": 1}}, "Bat", 0)


def test_incomplete_and_inadequate_coverage_do_not_write(tmp_path, rules):
    session_path, output = tmp_path / "session.json", tmp_path / "gold.json"
    session = generate_session(RAW, session_path, rules, "Bat")
    with pytest.raises(ReviewError, match="remain unreviewed"):
        export_gold(session_path, output, rules, *attest_args())
    store = SessionStore(session_path, rules)
    for item in session["items"]:
        store.update(item["id"], complete(item["review"]), "Bat", 0)
    with pytest.raises(ReviewError, match="coverage validation failed"):
        export_gold(session_path, output, rules, *attest_args())
    assert not output.exists()


def make_adequate_session(tmp_path, rules):
    path = tmp_path / "session.json"; session = generate_session(RAW, path, rules, "Bat")
    template = session["items"][0]; names = [rule.name for rule in rules.buckets]
    subtype = rules.buckets[0].subtypes[0]; items = []
    audit = [{"at": "2026-09-14T00:00:00+00:00", "actor": "Bat",
              "changes": {"reviewed": {"before": False, "after": True}}}]
    for index in range(20):
        item = copy.deepcopy(template); item["id"] = f"p-{index}"; item["revision"] = 1
        item["source"] = {**item["source"], "lot_number": f"p{index}",
                          "title": "Keyboard Shark WandVac positive"}
        item["review"] = {"reviewed": True, "expected_buckets": names, "forbidden_buckets": [],
            "expected_subtype": subtype, "expected_evidence_kinds": ["title_seed"],
            "expected_personal": index == 0,
            "critical_assertions": ["keyboard", "proven_resale"] if index == 0 else [],
            "rationale": "Human reviewed positive across configured buckets."}
        if index == 0:
            item["prediction"]["provenance"]["personal_evidence"] = [{"kind": "proven_resale"}]
        item["audit"] = copy.deepcopy(audit); items.append(item)
    for index in range(20):
        item = copy.deepcopy(template); item["id"] = f"n-{index}"; item["revision"] = 1
        item["source"] = {**item["source"], "lot_number": f"n{index}"}
        item["review"] = {"reviewed": True, "expected_buckets": [], "forbidden_buckets": names,
            "expected_subtype": None, "expected_evidence_kinds": [], "expected_personal": False,
            "critical_assertions": ["personal_hard_gate"] if index == 0 else [],
            "rationale": "Human reviewed near-negative for every configured bucket."}
        if index == 0:
            item["prediction"]["provenance"]["personal_hard_gates"] = ["functional:No"]
            item["source"]["functional"] = "No"
        item["audit"] = copy.deepcopy(audit); items.append(item)
    session["items"] = items; session["revision"] = 1; atomic_json(path, session)
    return path


def test_adequate_gold_writes_even_when_accuracy_fails(tmp_path, rules):
    output = tmp_path / "gold.json"
    report = export_gold(make_adequate_session(tmp_path, rules), output, rules, *attest_args())
    assert output.is_file() and not report["accuracy_gates_passed"] and report["coverage_failures"] == []
    metadata = json.loads(output.read_text())["review_metadata"]
    assert metadata["attestation_statement"] == ATTESTATION_STATEMENT and metadata["attestation_checked"]


def test_export_path_rejects_aliases_directories_and_protected_repo(tmp_path):
    session = tmp_path / "session.json"; session.write_text("x")
    for target in (session, ROOT / "README.md", ROOT / "viewer/src/data/auction_bundle.json"):
        with pytest.raises(ReviewError):
            validate_export_path(target, [session, ROOT / "viewer/src/data/auction_bundle.json"])
    directory = tmp_path / "dir"; directory.mkdir()
    with pytest.raises(ReviewError, match="directory"):
        validate_export_path(directory, [session])
    symlink = tmp_path / "symlink"; symlink.symlink_to(session)
    with pytest.raises(ReviewError): validate_export_path(symlink, [session])
    hardlink = tmp_path / "hardlink"; os.link(session, hardlink)
    with pytest.raises(ReviewError, match="hard-linked"): validate_export_path(hardlink, [session])
    backup = tmp_path / "session.json.bak"; backup.write_text("recovery")
    with pytest.raises(ReviewError, match="aliases"):
        validate_export_path(backup, [session, backup])


def web_request(connection, server, method, path, body=None, headers=None):
    values = {"Host": f"127.0.0.1:{server.server_port}", **(headers or {})}
    connection.request(method, path, body, values); response = connection.getresponse()
    data = response.read(); return response.status, json.loads(data) if data else None


def test_server_protects_origin_csrf_content_type_blindness_and_stale_writes(tmp_path, rules):
    path = tmp_path / "session.json"; generate_session(RAW, path, rules, "Bat")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(SessionStore(path, rules), "Bat"))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        status, body = web_request(connection, server, "GET", "/api/session")
        item = body["items"][0]; assert status == 200 and "prediction" not in item and "selection_keys" not in item
        token, origin = body["csrf_token"], f"http://127.0.0.1:{server.server_port}"
        payload = json.dumps({"review": complete(item["review"]), "expected_revision": 0})
        status, _ = web_request(connection, server, "POST", f"/api/item/{item['id']}", payload,
                                {"Content-Type": "text/plain", "Origin": origin, "X-CSRF-Token": token})
        assert status == 415
        status, _ = web_request(connection, server, "POST", f"/api/item/{item['id']}", payload,
                                {"Content-Type": "application/json", "Origin": "https://evil.test", "X-CSRF-Token": token})
        assert status == 403
        headers = {"Content-Type": "application/json", "Origin": origin, "X-CSRF-Token": token}
        status, saved = web_request(connection, server, "POST", f"/api/item/{item['id']}", payload, headers)
        assert status == 200 and "prediction" not in saved["item"] and "selection_keys" not in saved["item"]
        assert web_request(connection, server, "POST", f"/api/item/{item['id']}", payload, headers)[0] == 409
        for invalid_length in ("abc", "-1"):
            bad_length = http.client.HTTPConnection("127.0.0.1", server.server_port)
            bad_length.request("POST", "/api/exemptions", "{}", {
                "Host": f"127.0.0.1:{server.server_port}", "Origin": origin,
                "Content-Type": "application/json", "X-CSRF-Token": token,
                "Content-Length": invalid_length})
            response = bad_length.getresponse(); assert response.status == 400
            assert json.loads(response.read())["error"]
        bad = http.client.HTTPConnection("127.0.0.1", server.server_port)
        bad.request("GET", "/api/session", headers={"Host": "evil.test"}); assert bad.getresponse().status == 400
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_drift_malformed_and_no_network(tmp_path, rules, monkeypatch):
    path = tmp_path / "session.json"; session = generate_session(RAW, path, rules, "Bat")
    session["source"]["ruleset"] = "changed"; atomic_json(path, session)
    with pytest.raises(ReviewError, match="drift"): load_session(path, rules)
    path.write_text("broken"); path.with_name("session.json.bak").unlink(missing_ok=True)
    with pytest.raises(ReviewError, match="cannot read"): load_session(path, rules)
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert generate_session(RAW, tmp_path / "local.json", rules, "Bat")["items"]
