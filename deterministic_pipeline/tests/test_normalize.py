from deterministic_pipeline.normalize import (
    canonical_record, normalize_text, product_fingerprint, strict_fingerprint,
)


def test_normalization_is_idempotent_and_preserves_source():
    source = {"title": "  Govee—LED / Strip™  ", "condition": "Excellent"}
    before = dict(source)
    once = normalize_text(source["title"])
    assert normalize_text(once) == once
    assert once == "govee led strip"
    assert source == before
    assert canonical_record(source)["title"] == once


def test_fingerprints_separate_condition_but_product_identity_does_not():
    sealed = {"title": "Keychron K2 Keyboard", "model": "K2",
              "condition": "Brand New - Sealed"}
    used = {**sealed, "condition": "Good"}
    other_model = {**sealed, "model": "K8", "title": "Keychron K8 Keyboard"}
    assert strict_fingerprint(sealed) != strict_fingerprint(used)
    assert product_fingerprint(sealed) == product_fingerprint(used)
    assert product_fingerprint(sealed) != product_fingerprint(other_model)
