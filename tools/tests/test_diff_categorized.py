"""
Tests for `python -m diff_categorized` — extracting raw lots that aren't
yet in the categorized JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from diff_categorized.__main__ import diff, main


def _raw(**kw):
    # Default lot_number is derived from id so test fixtures vary together.
    base = {"id": 100001, "title": "ITEM"}
    base.update(kw)
    base.setdefault("lot_number", str(base["id"]))
    return base


def _cat(**kw):
    """Categorized item where lot_number actually holds the HiBid id (observed shape)."""
    base = {"lot_number": "100001", "title": "ITEM 100001", "category": "Electronics"}
    base.update(kw)
    return base


class TestDiffPure:
    def test_no_overlap_returns_all_raw(self):
        raw = [_raw(id=1, lot_number="1"), _raw(id=2, lot_number="2")]
        existing = []  # nothing categorized yet
        assert diff(raw, existing) == raw

    def test_full_overlap_returns_empty(self):
        raw = [_raw(id=1, lot_number="1"), _raw(id=2, lot_number="2")]
        existing = [_cat(lot_number="1"), _cat(lot_number="2")]
        assert diff(raw, existing) == []

    def test_partial_overlap(self):
        raw = [_raw(id=1, lot_number="1"),
               _raw(id=2, lot_number="2"),
               _raw(id=3, lot_number="3")]
        # Categorized has only id 1 (under lot_number key)
        existing = [_cat(lot_number="1")]
        result = diff(raw, existing)
        assert [r["id"] for r in result] == [2, 3]

    def test_matches_by_id_when_categorized_used_id_as_lot_number(self):
        """In observed samples, the agent puts HiBid id in lot_number."""
        raw = [_raw(id=282846987, lot_number="1")]
        existing = [_cat(lot_number="282846987")]
        assert diff(raw, existing) == []

    def test_matches_by_display_lot_number_when_agent_used_that(self):
        raw = [_raw(id=100001, lot_number="42")]
        existing = [_cat(lot_number="42")]
        assert diff(raw, existing) == []

    def test_preserves_order(self):
        raw = [_raw(id=i, lot_number=str(i)) for i in (10, 20, 30, 40)]
        existing = [_cat(lot_number="20")]
        result = diff(raw, existing)
        assert [r["id"] for r in result] == [10, 30, 40]


class TestCLI:
    def _write(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_happy_path_envelope_shape(self, tmp_path):
        raw_path = tmp_path / "raw.json"
        existing_path = tmp_path / "existing.json"
        out_path = tmp_path / "to_categorize.json"
        self._write(raw_path, {
            "auction_id": 741675,
            "auction_name": "TEST",
            "scraped_at": "2026-05-22T00:00:00Z",
            "item_count": 3,
            "items": [_raw(id=1), _raw(id=2), _raw(id=3)],
        })
        self._write(existing_path, {"items": [_cat(lot_number="1")]})

        exit_code = main([
            "--raw", str(raw_path),
            "--existing", str(existing_path),
            "--output", str(out_path),
        ])
        assert exit_code == 0

        out = json.loads(out_path.read_text())
        assert out["auction_id"] == 741675
        assert out["auction_name"] == "TEST"
        assert out["item_count"] == 2
        assert [i["id"] for i in out["items"]] == [2, 3]

    def test_bare_list_input(self, tmp_path):
        raw_path = tmp_path / "raw.json"
        existing_path = tmp_path / "existing.json"
        out_path = tmp_path / "out.json"
        self._write(raw_path, [_raw(id=1), _raw(id=2)])
        self._write(existing_path, [_cat(lot_number="1")])

        exit_code = main([
            "--raw", str(raw_path),
            "--existing", str(existing_path),
            "--output", str(out_path),
        ])
        assert exit_code == 0

        out = json.loads(out_path.read_text())
        # No envelope means no auction_id/etc — just item_count + items
        assert out["item_count"] == 1
        assert out["items"][0]["id"] == 2

    def test_no_new_lots_exits_nonzero(self, tmp_path, capsys):
        raw_path = tmp_path / "raw.json"
        existing_path = tmp_path / "existing.json"
        out_path = tmp_path / "out.json"
        self._write(raw_path, {"items": [_raw(id=1)]})
        self._write(existing_path, {"items": [_cat(lot_number="1")]})

        exit_code = main([
            "--raw", str(raw_path),
            "--existing", str(existing_path),
            "--output", str(out_path),
        ])
        assert exit_code == 1
        err = capsys.readouterr().err
        assert "Nothing to do" in err
        # Crucially: output file must NOT have been written
        assert not out_path.exists()

    def test_missing_raw_file_exits_nonzero(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            main([
                "--raw", str(tmp_path / "doesnotexist.json"),
                "--existing", str(tmp_path / "existing.json"),
                "--output", str(tmp_path / "out.json"),
            ])
        assert exc.value.code == 1
