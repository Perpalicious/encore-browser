import json
import os
from pathlib import Path

import pytest

from deterministic_pipeline.__main__ import PUBLISHED_BUNDLE, main


def raw_file(path: Path):
    path.write_text(json.dumps({"items": [{
        "lot_number": "1", "title": "Mechanical keyboard",
        "description": "", "description_raw": "Condition: Excellent",
        "condition": "Excellent", "hibid_category_path": "Computers & Electronics",
        "image_url": "https://example.test/image.jpg",
        "thumb_url": "https://example.test/thumb.jpg",
        "lot_url": "https://encoreauctions.hibid.com/lot/1/",
    }]}))


def test_cli_is_shadow_only_by_default(tmp_path):
    raw = tmp_path / "raw.json"
    raw_file(raw)
    published_before = PUBLISHED_BUNDLE.read_bytes()
    output = tmp_path / "shadow"
    assert main(["--auction-id", "test", "--raw", str(raw),
                 "--output-dir", str(output)]) == 0
    assert (output / "auction_test_categorized.json").exists()
    assert (output / "auction_test_performance.json").exists()
    assert PUBLISHED_BUNDLE.read_bytes() == published_before


def test_cli_cannot_target_production_with_build_output(tmp_path):
    raw = tmp_path / "raw.json"
    raw_file(raw)
    assert main(["--auction-id", "test", "--raw", str(raw),
                 "--output-dir", str(tmp_path / "out"),
                 "--build-output", str(PUBLISHED_BUNDLE)]) == 1
    assert not (tmp_path / "out").exists()


def test_publish_option_does_not_exist(tmp_path):
    raw = tmp_path / "raw.json"
    raw_file(raw)
    output = tmp_path / "out"
    with pytest.raises(SystemExit):
        main(["--auction-id", "test", "--raw", str(raw),
              "--output-dir", str(output), "--publish"])
    assert not output.exists()


def test_build_output_directory_is_rejected_before_sidecars(tmp_path):
    raw = tmp_path / "raw.json"
    raw_file(raw)
    target = tmp_path / "bundle-dir"
    target.mkdir()
    output = tmp_path / "out"
    assert main(["--auction-id", "test", "--raw", str(raw),
                 "--output-dir", str(output), "--build-output", str(target)]) == 1
    assert not output.exists()


def test_cli_rejects_production_hard_link_before_sidecars(tmp_path):
    raw = tmp_path / "raw.json"
    raw_file(raw)
    alias = tmp_path / "production-alias.json"
    try:
        os.link(PUBLISHED_BUNDLE, alias)
    except OSError as error:
        pytest.skip(f"filesystem cannot create hard link: {error}")
    before = PUBLISHED_BUNDLE.read_bytes()
    output = tmp_path / "out"
    assert main(["--auction-id", "test", "--raw", str(raw),
                 "--output-dir", str(output), "--build-output", str(alias)]) == 1
    assert not output.exists()
    assert alias.read_bytes() == before
    assert PUBLISHED_BUNDLE.read_bytes() == before


def test_cli_accepts_explicit_nonproduction_build_output(tmp_path):
    raw = tmp_path / "raw.json"
    raw_file(raw)
    output = tmp_path / "out"
    target = tmp_path / "review-bundle.json"
    assert main(["--auction-id", "test", "--raw", str(raw),
                 "--output-dir", str(output), "--build-output", str(target)]) == 0
    assert target.exists()


def test_cli_config_error_leaves_no_sidecars(tmp_path):
    import yaml

    raw = tmp_path / "raw.json"
    raw_file(raw)
    profile = tmp_path / "profile.yaml"
    document = yaml.safe_load((Path(__file__).resolve().parents[2] / "profile.yaml").read_text())
    document["sizes"]["unknown"] = "value"
    profile.write_text(yaml.safe_dump(document, sort_keys=False))
    output = tmp_path / "out"
    assert main(["--auction-id", "test", "--raw", str(raw),
                 "--output-dir", str(output), "--profile", str(profile)]) == 1
    assert not output.exists()
