"""Unit tests for tools/recall_check.py's suspect detection."""

from tools.recall_check import find_suspects, sibling_key

KB = "Keyboards & PC peripherals"
CRAFT = "Kids' craft & activity"
VAC = "Vacuums & floor care"

BUCKETS = [
    {"name": KB, "seeds": ["keyboard", "mouse"], "exclude": ["keyboard tray"]},
    {"name": CRAFT, "seeds": ["light pad"]},
    {"name": VAC, "seeds": ["vacuum"], "exclude": ["vacuum toy"]},
    {"name": "Electronics", "seeds": []},
]


def _lot(n, title, category="X", flagged=()):
    return ({"lot_number": n, "title": title, "condition": "Good", "category": category},
            {"lot_number": n, "is_bats_list": bool(flagged),
             "bats_buckets": list(flagged), "personal_match": False})


def _run(specs, groups=None):
    slim, flags = zip(*specs)
    groups = groups or {r["lot_number"]: [r["lot_number"]] for r in slim}
    return {r["lot_number"]: r for r in find_suspects(list(slim), groups, list(flags), BUCKETS)}


def test_sibling_key_skips_sizes_and_singletons():
    assert sibling_key("45 J'S.O.L.E COWBOY BOOTS FOR MEN") == "COWBOY BOOTS FOR"
    assert sibling_key("L AVIDLOVE WOMENS BABYDOLL") == "AVIDLOVE WOMENS BABYDOLL"
    assert sibling_key("AREA RUGS") is None


def test_short_key_is_brand_plus_line_code_only():
    assert sibling_key("PHYLOSAL A3 LED LIGHT PAD", 2) == "PHYLOSAL A3"
    assert sibling_key("LOGITECH MX KEYS FOR MAC", 2) == "LOGITECH MX"
    assert sibling_key("PHILIPS AVENT BOTTLE WARMER", 2) is None
    assert sibling_key("LA ROCHE-POSAY CLEANSER", 2) is None


def test_three_word_sibling_is_a_suspect():
    out = _run([
        _lot("1", "PHYLOSAL A3 LED LIGHT PAD FOR DIAMOND PAINTING", flagged=[CRAFT]),
        _lot("2", "PHYLOSAL A3 LED LIGHT PAD, ULTRA-THIN BOX"),
    ])
    assert list(out) == ["2"]
    assert out["2"]["suspect"][0]["bucket"] == CRAFT
    assert "DIAMOND PAINTING" in out["2"]["suspect"][0]["because"]


def test_short_key_reaches_a_different_third_word():
    out = _run([
        _lot("1", "PHYLOSAL A3 LED LIGHT PAD FOR DIAMOND PAINTING", flagged=[CRAFT]),
        _lot("2", "PHYLOSAL A3 RECHARGEABLE LIGHT BOARD WITH BAG"),
    ])
    assert out["2"]["suspect"][0]["bucket"] == CRAFT


def test_short_key_uses_dominance_not_unanimity():
    # Every MX lot carries both buckets; Keyboards still owns the family.
    out = _run([
        _lot("1", "LOGITECH MX MASTER 3S WIRELESS MOUSE", flagged=[KB, "Electronics"]),
        _lot("2", "LOGITECH MX ANYWHERE 2S BLUETOOTH MOUSE", flagged=[KB, "Electronics"]),
        _lot("3", "LOGITECH MX PALM REST FOR MX KEYS"),
    ])
    assert {s["bucket"] for s in out["3"]["suspect"]} == {KB, "Electronics"}


def test_brand_pair_families_are_not_used():
    out = _run([
        _lot("1", "PHILIPS AVENT BOTTLE WARMER", flagged=["Electronics"]),
        _lot("2", "PHILIPS AVENT SOOTHIE PACIFIER"),
    ])
    assert "2" not in out


def test_exclude_list_blocks_sibling_evidence():
    out = _run([
        _lot("1", "NEXT LEVEL RACING KEYBOARD MOUNT", flagged=[KB]),
        _lot("2", "NEXT LEVEL RACING KEYBOARD TRAY (NLR-A012)"),
    ])
    assert "2" not in out


def test_seed_in_dominated_category_is_a_suspect():
    cat = "Cleaning Equipment"
    specs = [_lot(str(i), f"SHARK NAVIGATOR UPRIGHT VACUUM {i}", cat, flagged=[VAC])
             for i in range(15)]
    specs.append(_lot("miss", "BISSELL POWERFORCE VACUUM", cat))
    specs.append(_lot("toy", "CASDON DYSON VACUUM TOY", cat))
    out = _run(specs)
    assert "miss" in out and out["miss"]["suspect"][0]["bucket"] == VAC
    assert "vacuum" in out["miss"]["suspect"][0]["because"].lower()
    assert "toy" not in out


def test_small_categories_give_no_seed_evidence():
    cat = "Cleaning Equipment"
    specs = [_lot(str(i), f"SHARK NAVIGATOR UPRIGHT VACUUM {i}", cat, flagged=[VAC])
             for i in range(5)]
    specs.append(_lot("miss", "BISSELL POWERFORCE VACUUM", cat))
    assert "miss" not in _run(specs)


def test_flagged_products_are_never_candidates_and_qty_counts_the_group():
    slim1, f1 = _lot("1", "PHYLOSAL A3 LED LIGHT PAD FOR DIAMOND PAINTING", flagged=[CRAFT])
    slim2, f2 = _lot("2", "PHYLOSAL A3 LED LIGHT PAD, ULTRA-THIN BOX")
    slim3, f3 = _lot("3", "PHYLOSAL A3 LED LIGHT PAD, ULTRA-THIN BOX")
    slim4, f4 = _lot("4", "PHYLOSAL A3 LED LIGHT PAD, ULTRA-THIN BOX", flagged=["Electronics"])
    groups = {"1": ["1"], "2": ["2", "3"], "4": ["4"]}
    out = {r["lot_number"]: r for r in find_suspects(
        [slim1, slim2, slim3, slim4], groups, [f1, f2, f3, f4], BUCKETS)}
    assert list(out) == ["2"]
    assert out["2"]["qty"] == 2
