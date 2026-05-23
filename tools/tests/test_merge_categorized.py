"""
Tests for `python -m merge_categorized` — combining a freshly-categorized
batch into the existing categorized file with new-wins dedup and atomic write.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from merge_categorized.__main__ import merge, main


def _cat(lot_number, category="Electronics", **kw):
    base = {"lot_number": str(lot_number), "title": f"item {lot_number}", "category": category}
    base.update(kw)
    return base


class TestMergePure:
    def test_no_overlap_appends(self):
        existing = [_cat("1"), _cat("2")]
        new = [_cat("3"), _cat("4")]
        merged, added, updated = merge(existing, new)
        assert [m["lot_number"] for m in merged] == ["1", "2", "3", "4"]
        assert added == 2
        assert updated == 0

    def test_full_overlap_new_wins(self):
        existing = [_cat("1", category="OLD"), _cat("2", category="OLD")]
        new = [_cat("1", category="NEW"), _cat("2", category="NEW")]
        merged, added, updated = merge(existing, new)
        assert [m["lot_number"] for m in merged] == ["1", "2"]
        assert [m["category"] for m in merged] == ["NEW", "NEW"]
        assert added == 0
        assert updated == 2

    def test_partial_overlap(self):
        existing = [_cat("1"), _cat("2", category="OLD")]
        new = [_cat("2", category="NEW"), _cat("3")]
        merged, added, updated = merge(existing, new)
        # Existing order preserved, then truly-new appended
        assert [m["lot_number"] for m in merged] == ["1", "2", "3"]
        # The "2" entry is the new one
        assert next(m for m in merged if m["lot_number"] == "2")["category"] == "NEW"
        assert added == 1
        assert updated == 1

    def test_empty_existing(self):
        merged, added, updated = merge([], [_cat("1"), _cat("2")])
        assert [m["lot_number"] for m in merged] == ["1", "2"]
        assert added == 2 and updated == 0

    def test_empty_new(self):
        existing = [_cat("1"), _cat("2")]
        merged, added, updated = merge(existing, [])
        assert merged == existing
        assert added == 0 and updated == 0


class TestCLI:
    def _write(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_envelope_preserved_from_existing(self, tmp_path, capsys):
        existing_path = tmp_path / "existing.json"
        new_path = tmp_path / "new.json"
        out_path = tmp_path / "out.json"
        self._write(existing_path, {
            "auction_id": 741675,
            "auction_name": "BIG AUCTION",
            "scraped_at": "2026-05-22T00:00:00Z",
            "item_count": 1,
            "items": [_cat("1", category="OLD")],
        })
        self._write(new_path, {
            "items": [_cat("1", category="CORRECTED"), _cat("2"), _cat("3")],
        })

        exit_code = main([
            "--existing", str(existing_path),
            "--new", str(new_path),
            "--output", str(out_path),
        ])
        assert exit_code == 0

        out = json.loads(out_path.read_text())
        # Existing envelope wins (auction_id from existing, not new)
        assert out["auction_id"] == 741675
        assert out["auction_name"] == "BIG AUCTION"
        # item_count updated
        assert out["item_count"] == 3
        # Dedup happened, new wins for "1"
        items_by_ln = {m["lot_number"]: m for m in out["items"]}
        assert items_by_ln["1"]["category"] == "CORRECTED"
        assert "2" in items_by_ln and "3" in items_by_ln

        # Summary line on stdout
        out_text = capsys.readouterr().out
        assert "2 new items" in out_text
        assert "1 updates" in out_text
        assert "total now 3" in out_text

    def test_in_place_update(self, tmp_path):
        existing_path = tmp_path / "existing.json"
        new_path = tmp_path / "new.json"
        self._write(existing_path, {
            "auction_id": 1,
            "items": [_cat("1", category="A")],
        })
        self._write(new_path, {"items": [_cat("2", category="B")]})

        exit_code = main([
            "--existing", str(existing_path),
            "--new", str(new_path),
            "--output", str(existing_path),
        ])
        assert exit_code == 0

        result = json.loads(existing_path.read_text())
        assert result["auction_id"] == 1
        assert result["item_count"] == 2
        assert [i["lot_number"] for i in result["items"]] == ["1", "2"]

    def test_bare_list_inputs(self, tmp_path):
        existing_path = tmp_path / "existing.json"
        new_path = tmp_path / "new.json"
        out_path = tmp_path / "out.json"
        self._write(existing_path, [_cat("1")])
        self._write(new_path, [_cat("2")])

        exit_code = main([
            "--existing", str(existing_path),
            "--new", str(new_path),
            "--output", str(out_path),
        ])
        assert exit_code == 0

        out = json.loads(out_path.read_text())
        assert out["item_count"] == 2
        assert [i["lot_number"] for i in out["items"]] == ["1", "2"]

    def test_atomic_write_no_leftover_tmp(self, tmp_path):
        """A successful write must not leave a `.tmp` file behind."""
        existing_path = tmp_path / "existing.json"
        new_path = tmp_path / "new.json"
        out_path = tmp_path / "out.json"
        self._write(existing_path, {"items": [_cat("1")]})
        self._write(new_path, {"items": [_cat("2")]})

        main([
            "--existing", str(existing_path),
            "--new", str(new_path),
            "--output", str(out_path),
        ])
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == [], f"Found stray tmp files: {leftovers}"

    def test_atomic_write_rollback_on_failure(self, tmp_path, monkeypatch):
        """If os.replace fails, existing target stays intact and no tmp leaks."""
        existing_path = tmp_path / "existing.json"
        new_path = tmp_path / "new.json"
        out_path = tmp_path / "out.json"
        self._write(existing_path, {"items": [_cat("1", category="ORIGINAL")]})
        self._write(new_path, {"items": [_cat("2")]})
        # Pre-seed the target with content that must NOT be replaced
        self._write(out_path, {"items": [_cat("0", category="PRECIOUS")]})

        # Sabotage os.replace
        from merge_categorized import __main__ as mc
        def boom(*_a, **_kw):
            raise OSError("simulated disk full")
        monkeypatch.setattr(mc.os, "replace", boom)

        with pytest.raises(OSError, match="simulated disk full"):
            main([
                "--existing", str(existing_path),
                "--new", str(new_path),
                "--output", str(out_path),
            ])

        # Original out_path content untouched
        out_contents = json.loads(out_path.read_text())
        assert out_contents["items"][0]["category"] == "PRECIOUS"
        # No tmp left behind
        assert list(tmp_path.glob("*.tmp")) == []

    def test_missing_existing_file_exits_nonzero(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            main([
                "--existing", str(tmp_path / "nope.json"),
                "--new", str(tmp_path / "new.json"),
                "--output", str(tmp_path / "out.json"),
            ])
        assert exc.value.code == 1
