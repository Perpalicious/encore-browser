"""Tests for tools/render_prompts.py.

The rendered prompt is what removes the hand-substitution step, so what these
guard is that every value the human used to type is in the file, correct, and
that no placeholder survives. A prompt with a wrong `chunk_complete` value
would make `expand_flags.py` reject a perfectly good response; a leftover `N`
makes the completeness rule unenforceable.
"""

from __future__ import annotations

import json

import pytest

from tools import chunk_flagging, render_prompts, slim_resale
from tools.tests.test_chunk_flagging import BUCKETS, PROFILE, _lot, write_slim


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "data" / "categorized").mkdir(parents=True)
    (tmp_path / "buckets.yaml").write_text(BUCKETS)
    (tmp_path / "profile.yaml").write_text(PROFILE)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def prompt(repo, name):
    return (repo / "data" / "categorized" / name).read_text()


class TestFlagging:
    def test_chunk_flagging_writes_one_prompt_per_chunk(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 26)])
        chunk_flagging.main("X", rows_per_chunk=10)
        names = sorted(p.name for p in (repo / "data" / "categorized").glob("*_prompt.md"))
        assert names == [f"auction_X_chunk_{n:02d}_prompt.md" for n in (1, 2, 3)]

    def test_values_come_from_that_chunk(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 26)])
        chunk_flagging.main("X", rows_per_chunk=10)
        chunk = json.loads(prompt(repo, "auction_X_chunk_02.json"))
        text = prompt(repo, "auction_X_chunk_02_prompt.md")
        assert f'{{"chunk_complete": "{chunk[-1]["lot_number"]}"}}' in text
        assert f"`auction_X_chunk_02.json` contains {len(chunk)} rows" in text
        assert "**`auction_X_chunk_02_flags.json`**" in text
        assert "should be 2." in text  # BUCKETS defines two

    def test_no_placeholder_survives(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 6)])
        chunk_flagging.main("X", rows_per_chunk=10)
        text = prompt(repo, "auction_X_chunk_01_prompt.md")
        assert "{{" not in text
        assert "<LAST LOT>" not in text
        assert "Input fields" in text  # the shared field block is appended

    def test_rerender_does_not_touch_chunks(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 26)])
        chunk_flagging.main("X", rows_per_chunk=10)
        before = {p.name: p.read_bytes() for p in
                  (repo / "data" / "categorized").glob("auction_X_chunk_??.json")}
        render_prompts.main("X")
        after = {p.name: p.read_bytes() for p in
                 (repo / "data" / "categorized").glob("auction_X_chunk_??.json")}
        assert before == after

    def test_stale_prompts_are_removed_on_rechunk(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 26)])
        chunk_flagging.main("X", rows_per_chunk=5)
        chunk_flagging.main("X", rows_per_chunk=100)
        names = sorted(p.name for p in (repo / "data" / "categorized").glob("*_prompt.md"))
        assert names == ["auction_X_chunk_01_prompt.md"]

    def test_nothing_to_render_is_an_error(self, repo):
        with pytest.raises(SystemExit):
            render_prompts.main("X")


class TestResale:
    def test_slim_resale_writes_the_prompt(self, repo):
        write_slim(repo, [_lot(i, f"THING {i}") for i in range(1, 8)])
        slim_resale.main("X")
        rows = json.loads(prompt(repo, "auction_X_for_resale.json"))
        text = prompt(repo, "auction_X_resale_prompt.md")
        assert f"contains {len(rows)} rows. Return exactly {len(rows)} objects" in text
        assert f"`lot_number` is `{rows[-1]['lot_number']}`" in text
        assert "**`auction_X_resale_deduped.json`**" in text
        assert "{{" not in text
        assert "context.yaml" not in text  # resale attaches no config
