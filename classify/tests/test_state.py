import json

import pytest

from classify import chunking, config
from classify.state import BLOCKED, INGESTED, PENDING, SUPERSEDED, PassRun
from classify.tests.conftest import lot, write_output


def prepared(n_lots=12, max_rows=500):
    lots = [lot(i) for i in range(1, n_lots + 1)]
    config.write_json(config.pass_input_path("test", "a"), lots)
    run = PassRun("test", "a")
    run.prepare(max_rows=max_rows, max_bytes=chunking.MAX_BYTES)
    return run


def test_prepare_covers_every_lot_and_writes_the_prompt(repo):
    run = prepared(12)
    assert run.prompt_path.exists()
    assert run.all_lots() == {f"S-{i}" for i in range(1, 13)}
    assert all(m["state"] == PENDING for m in run.chunks.values())
    assert run.data["bucket_count"] == 3, "must read the fixture's 3 buckets, not 62"


def test_prompt_omits_the_cand_block_when_the_input_has_no_cand(repo):
    """Pass files carry no `cand`; describing it would be dead text."""
    run = prepared(4)
    assert "About `cand`" not in run.prompt_path.read_text(encoding="utf-8")


def test_prompt_includes_the_cand_block_when_the_input_has_cand(repo):
    lots = [lot(i, cand=["Hand tools"]) for i in range(1, 5)]
    config.write_json(config.pass_input_path("test", "a"), lots)
    run = PassRun("test", "a")
    run.prepare(max_rows=500, max_bytes=chunking.MAX_BYTES)
    assert "About `cand`" in run.prompt_path.read_text(encoding="utf-8")


def test_a_good_output_is_ingested(repo):
    run = prepared(12)
    cid = run.dispatchable()[0]
    write_output(run, cid)
    report = run.ingest()
    assert len(report["accepted"]) == 1
    assert run.chunks[cid]["state"] == INGESTED
    assert run.covered_lots() == run.all_lots()


def test_finalize_refuses_while_lots_are_outstanding(repo):
    run = prepared(600, max_rows=500)          # two chunks
    write_output(run, run.dispatchable()[0])
    run.ingest()
    with pytest.raises(SystemExit, match="unaccounted for"):
        run.finalize()


def test_finalize_writes_the_flags_file(repo):
    run = prepared(12)
    cid = run.dispatchable()[0]
    write_output(
        run, cid,
        matches=[{"lot_number": "S-1", "is_bats_list": True,
                  "bats_buckets": ["Hand tools"], "personal_match": False,
                  "bats_subtype": "screwdrivers"}],
        no_match=[f"S-{i}" for i in range(2, 13)],
    )
    run.ingest()
    path = run.finalize()
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "auction_test_flags_a.json"
    assert len(rows) == 12
    assert sum(1 for r in rows if r["is_bats_list"]) == 1
    assert all(set(r) >= {"lot_number", "is_bats_list", "bats_buckets",
                          "personal_match"} for r in rows)


def test_first_failure_retries_rather_than_bisecting(repo):
    run = prepared(12)
    cid = run.dispatchable()[0]
    write_output(run, cid, no_match=["S-1"])           # short
    report = run.ingest()
    assert len(report["rejected"]) == 1
    assert run.chunks[cid]["state"] == PENDING
    assert run.chunks[cid]["attempts"] == 1
    assert cid in run.dispatchable(), "must be offered for one clean retry"


def test_the_rejected_output_is_kept_as_evidence(repo):
    run = prepared(12)
    cid = run.dispatchable()[0]
    write_output(run, cid, no_match=["S-1"])
    run.ingest()
    kept = list(run.rejected_dir.glob("*.attempt1"))
    assert len(kept) == 1
    assert not (run.out_dir / chunking.filename(cid)).exists(), \
        "the bad output must be moved aside so the retry is not re-counted"


def test_second_failure_bisects(repo):
    run = prepared(60, max_rows=60)                     # one 60-lot chunk
    cid = run.dispatchable()[0]
    for _ in range(2):
        write_output(run, cid, no_match=["S-1"])
        report = run.ingest()
    assert run.chunks[cid]["state"] == SUPERSEDED
    kids = report["bisected"][0][1]
    assert kids == ["a/000.0", "a/000.1"]
    assert sorted(run.dispatchable()) == kids
    covered = set(run.chunks[kids[0]]["lots"]) | set(run.chunks[kids[1]]["lots"])
    assert covered == {f"S-{i}" for i in range(1, 61)}, "bisection must be lossless"
    assert run.all_lots() == covered, "the superseded parent must not double-count"


def test_bisection_converges_on_the_bad_lot(repo):
    """Halving isolates the offender instead of resending 60 lots forever."""
    run = prepared(60, max_rows=60)
    poison = "S-37"
    for _ in range(12):
        pending = run.dispatchable()
        if not pending:
            break
        for cid in pending:
            lots = run.chunks[cid]["lots"]
            if poison in lots and len(lots) > 1:
                write_output(run, cid, no_match=[l for l in lots if l != poison])
            else:
                write_output(run, cid)
        run.ingest()
    blocked = run.blocked()
    assert blocked, "the poisoned chunk must end up blocked, not loop"
    offending = {l for cid in blocked for l in run.chunks[cid]["lots"]}
    assert poison in offending
    assert len(offending) < 60, "bisection should narrow the blame, not blame everything"


def test_a_chunk_below_the_floor_blocks_instead_of_bisecting(repo):
    run = prepared(12)                                   # 12 < MIN_CHUNK
    cid = run.dispatchable()[0]
    for _ in range(2):
        write_output(run, cid, no_match=["S-1"])
        run.ingest()
    assert run.chunks[cid]["state"] == BLOCKED
    assert run.blocked() == [cid]


def test_blocked_lots_still_stop_finalize(repo):
    run = prepared(12)
    cid = run.dispatchable()[0]
    for _ in range(2):
        write_output(run, cid, no_match=["S-1"])
        run.ingest()
    with pytest.raises(SystemExit, match="unaccounted for"):
        run.finalize()


def test_output_from_a_different_fingerprint_is_rejected(repo):
    run = prepared(12)
    cid = run.dispatchable()[0]
    write_output(run, cid, fingerprint="from-last-week")
    report = run.ingest()
    assert "different configuration" in report["rejected"][0][1][0]


def test_editing_buckets_marks_the_run_stale(repo):
    run = prepared(12)
    write_output(run, run.dispatchable()[0])
    run.ingest()
    assert run.is_stale()[0] is False

    (repo / "buckets.yaml").write_text(
        (repo / "buckets.yaml").read_text(encoding="utf-8")
        + '  - name: "New bucket"\n    group: "g"\n    description: "d"\n',
        encoding="utf-8",
    )
    stale, changed = PassRun("test", "a").is_stale()
    assert stale
    assert "buckets_sha" in changed


def test_re_prepare_after_a_taxonomy_change_discards_prior_work(repo, capsys):
    run = prepared(12)
    write_output(run, run.dispatchable()[0])
    run.ingest()
    assert run.covered_lots()

    (repo / "buckets.yaml").write_text(
        (repo / "buckets.yaml").read_text(encoding="utf-8")
        + '  - name: "New bucket"\n    group: "g"\n    description: "d"\n',
        encoding="utf-8",
    )
    fresh = PassRun("test", "a")
    fresh.prepare(max_rows=500, max_bytes=chunking.MAX_BYTES)
    assert fresh.covered_lots() == set(), "results from the old taxonomy must not survive"
    assert "fingerprint changed" in capsys.readouterr().out


def test_re_prepare_keeps_valid_work_when_nothing_changed(repo):
    run = prepared(12)
    write_output(run, run.dispatchable()[0])
    run.ingest()
    again = PassRun("test", "a")
    again.prepare(max_rows=500, max_bytes=chunking.MAX_BYTES)
    assert again.covered_lots() == again.all_lots()
    assert again.dispatchable() == []
