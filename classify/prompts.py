"""Assemble the per-pass worker prompt.

One prompt per pass, not per chunk: the chunk id, row count, paths and
fingerprint reach the worker in its task message instead. If they were baked
in here, every chunk would have a different prompt_sha and the per-pass
fingerprint would say nothing.

The full buckets.yaml and full profile.yaml are inlined every time. That is
deliberate and `docs/PASS_SOURCES.md` §1 is emphatic about why: focus_buckets
is advisory, and slicing the taxonomy per pass turns the hint into a hard
filter — a Barbie filed under Home Goods lands in pass B and must still come
back as `Barbies`, and 59% of Hand tools inventory sits under Lawn & Garden.
Inlining also removes the manual flow's worst failure: nobody can forget to
re-attach a file that is read from disk on every run.
"""

from __future__ import annotations

from classify import config


def _focus_buckets(spec: dict) -> str:
    names = [str(n) for n in (spec.get("focus_buckets") or [])]
    return ", ".join(names) if names else "(none listed — judge against all buckets)"


def wants_cand_section(lots: list[dict]) -> bool:
    """Whether the input actually carries `cand` / `profile` keys.

    The pass files written by tools/split_passes.py do not — those keys come
    from the older shortlist flow in tools/prefilter.py. Including the "About
    cand" block anyway would describe a field the worker cannot see, so it is
    conditional on the data rather than assumed.
    """
    return any("cand" in lot or "profile" in lot for lot in lots)


def build(pass_id: str, lots: list[dict]) -> str:
    """The fully-substituted prompt for one pass."""
    template = config.PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    spec = config.pass_spec(pass_id)
    buckets = config.load_buckets()

    cand = ""
    if wants_cand_section(lots):
        cand = config.PROMPT_CAND_PATH.read_text(encoding="utf-8")

    substitutions = {
        "{{PASS_NAME}}": str(spec.get("name") or pass_id.upper()),
        "{{FOCUS_BUCKETS}}": _focus_buckets(spec),
        "{{BUCKET_COUNT}}": str(len(buckets)),
        "{{CAND_SECTION}}": cand,
        "{{INPUT_FIELDS}}": (config.REPO_ROOT / "prompts" / "input_fields.md")
            .read_text(encoding="utf-8").strip(),
        "{{BUCKETS_YAML}}": config.BUCKETS_PATH.read_text(encoding="utf-8").rstrip(),
        "{{PROFILE_YAML}}": config.PROFILE_PATH.read_text(encoding="utf-8").rstrip(),
    }
    text = template
    for token, value in substitutions.items():
        text = text.replace(token, value)

    leftover = [t for t in substitutions if t in text]
    if leftover:
        raise SystemExit(f"Error: prompt still contains {leftover} after substitution")
    return text
