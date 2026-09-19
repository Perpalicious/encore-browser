"""Tests for tools/tidy.py — the post-deploy sweep of data/categorized.

One promise: it never removes a file a later step still reads. The files the
delta loop needs (`_dN_flags.json`, `_for_agent.json`, `_categorized.json`,
`_resale.json`) survive, and chat inputs survive while their pass is still
open — chunks before `_flags.json`, resale inputs before `_resale.json`, a
planned recall before `apply`.
"""

from __future__ import annotations

from pathlib import Path

from tools import tidy


def _touch(out_dir: Path, *names: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (out_dir / name).write_text("{}", encoding="utf-8")


def _names(paths) -> set[str]:
    return {p.name for p in paths}


FINISHED_WEEK = [
    "auction_77_categorized.json", "auction_77_resale.json", "auction_77_for_agent.json",
    "auction_77_base.json", "auction_77_prefilter.json", "auction_77_flags.json",
    "auction_77_resale_deduped.json",
    "auction_77_chunk_01.json", "auction_77_chunk_01_flags.json",
    "auction_77_chunk_01_prompt.md", "auction_77_flag_groups.json",
    "auction_77_recall.json", "auction_77_recall_flags.json",
    "auction_77_recall_prompt.md", "auction_77_flags_before_recall.json",
    "auction_77_for_resale.json", "auction_77_resale_groups.json",
    "auction_77_resale_prompt.md",
    "auction_77_candidates.json", "auction_77_sweep.json",
    "context.yaml", "README.md", "auction_703264_categorized.json",
]


def test_finished_week_keeps_exactly_what_later_steps_read(tmp_path):
    _touch(tmp_path, *FINISHED_WEEK)
    doomed, kept = tidy.plan("77", tmp_path)
    assert kept == []
    survivors = set(FINISHED_WEEK) - _names(doomed)
    assert survivors == {
        "auction_77_categorized.json", "auction_77_resale.json",
        "auction_77_for_agent.json", "auction_77_base.json",
        "auction_77_prefilter.json", "auction_77_flags.json",
        "auction_77_resale_deduped.json",
        "README.md", "auction_703264_categorized.json",
    }


def test_deltas_are_swept_but_their_flags_and_resale_survive(tmp_path):
    _touch(tmp_path, "auction_77_categorized.json", "auction_77_flags.json",
           "auction_77_d1_flags.json", "auction_77_d1_resale.json",
           "auction_77_d1_for_agent.json", "auction_77_d1_resale_deduped.json",
           "auction_77_d1_chunk_01.json", "auction_77_d1_chunk_01_flags.json",
           "auction_77_d1_chunk_01_prompt.md", "auction_77_d1_flag_groups.json",
           "auction_77_d1_for_resale.json", "auction_77_d1_resale_groups.json",
           "auction_77_d2_flags.json", "auction_77_d2_chunk_01.json")
    assert tidy.delta_ids("77", tmp_path) == ["77_d1", "77_d2"]
    doomed, _ = tidy.plan("77", tmp_path)
    assert _names(doomed) == {
        "auction_77_d1_chunk_01.json", "auction_77_d1_chunk_01_flags.json",
        "auction_77_d1_chunk_01_prompt.md", "auction_77_d1_flag_groups.json",
        "auction_77_d1_for_resale.json", "auction_77_d1_resale_groups.json",
        "auction_77_d2_chunk_01.json",
    }


def test_chunks_survive_while_flagging_pass_is_open(tmp_path):
    _touch(tmp_path, "auction_77_categorized.json",
           "auction_77_d1_chunk_01.json", "auction_77_d1_chunk_01_flags.json",
           "auction_77_d1_chunk_02.json", "auction_77_d1_flag_groups.json")
    doomed, kept = tidy.plan("77", tmp_path)
    assert doomed == []
    assert any("still open" in k for k in kept)


def test_planned_recall_survives_until_applied(tmp_path):
    _touch(tmp_path, "auction_77_categorized.json", "auction_77_flags.json",
           "auction_77_recall.json", "auction_77_recall_prompt.md",
           "auction_77_recall_flags.json")
    doomed, kept = tidy.plan("77", tmp_path)
    assert not any("recall" in n for n in _names(doomed))
    assert any("apply" in k for k in kept)

    _touch(tmp_path, "auction_77_flags_before_recall.json")
    doomed, kept = tidy.plan("77", tmp_path)
    assert {"auction_77_recall.json", "auction_77_recall_prompt.md",
            "auction_77_recall_flags.json",
            "auction_77_flags_before_recall.json"} <= _names(doomed)
    assert kept == []


def test_resale_inputs_survive_until_expanded(tmp_path):
    _touch(tmp_path, "auction_77_categorized.json", "auction_77_flags.json",
           "auction_77_for_resale.json", "auction_77_resale_groups.json",
           "auction_77_resale_prompt.md", "auction_77_resale_deduped.json")
    doomed, kept = tidy.plan("77", tmp_path)
    assert not any("resale" in n for n in _names(doomed))
    assert any("resale" in k for k in kept)


def test_lot_prefixed_ids_do_not_bleed_into_each_other(tmp_path):
    # `combined` must not pick up files from a hypothetical `combined_x` ID,
    # and `77` must not sweep `776904`'s files.
    _touch(tmp_path, "auction_77_categorized.json", "auction_77_flags.json",
           "auction_776904_chunk_01.json", "auction_776904_flags.json",
           "auction_776904_d1_chunk_01.json", "auction_776904_d1_flags.json")
    doomed, _ = tidy.plan("77", tmp_path)
    assert doomed == []
    assert tidy.delta_ids("77", tmp_path) == []
