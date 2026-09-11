"""
Render the ready-to-paste ChatGPT prompts for this week's passes.

    python3 tools/render_prompts.py <ID>

Reads  prompts/flagging.md, prompts/resale.md, prompts/input_fields.md
       data/categorized/auction_<ID>_chunk_NN.json     (from chunk_flagging.py)
       data/categorized/auction_<ID>_for_resale.json   (from slim_resale.py, if present)
       buckets.yaml                                     (for the bucket count)
Writes data/categorized/auction_<ID>_chunk_NN_prompt.md  (one per chunk)
       data/categorized/auction_<ID>_resale_prompt.md    (if the resale input exists)

`tools/chunk_flagging.py` and `tools/slim_resale.py` both call this at the end
of their own run, so normally nothing needs to invoke it by hand. It is safe to
re-run at any time: it only reads the chunk files, never rewrites them, so
unlike `chunk_flagging.py` it cannot invalidate responses already collected.

Why
---
The prompt templates carry four values that differ per chat — the input file
name, the output file name, the row count, and the last `lot_number` — plus
the bucket count that proves `context.yaml` attached. Each of those used to
be substituted by hand from a printout, and each is load-bearing:

  - the row count and last lot are what make the completeness rule
    checkable (`tools/expand_flags.py` compares the sentinel against the
    chunk on disk, not against whatever the model claims it read);
  - the output name is what `expand_flags.py` reconciles against, and a
    response saved under the wrong chunk number fails as "lot_numbers not in
    this chunk";
  - the bucket count is the read-test for the attachment.

They are all deterministic from files already on disk, so a person retyping
them only adds a way to get one wrong. Every rendered prompt is complete:
paste the whole file into a chat, attach what its header names, done.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "prompts"
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def _as_items(data) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, list):
        return data
    sys.exit("Error: expected a JSON array or an object with an items array")


def count_buckets() -> int:
    import yaml

    path = Path("buckets.yaml")
    if not path.exists():
        sys.exit("Error: buckets.yaml not found. Run from the repo root.")
    buckets = yaml.safe_load(path.read_text(encoding="utf-8"))
    return len(buckets.get("buckets", buckets))


def render(template: str, values: dict[str, str]) -> str:
    """Fill a template, refusing to leave any placeholder behind."""
    body = (TEMPLATES / template).read_text(encoding="utf-8")
    body += (TEMPLATES / "input_fields.md").read_text(encoding="utf-8")
    for key, value in values.items():
        body = body.replace("{{" + key + "}}", str(value))
    left = sorted(set(PLACEHOLDER.findall(body)))
    if left:
        sys.exit(f"Error: {template} still has unfilled placeholders: {left}")
    return body


def render_flagging(auction_id: str, out_dir: Path = Path("data/categorized"),
                    n_buckets: int | None = None) -> list[tuple[Path, Path]]:
    """One prompt per chunk. Returns (chunk_path, prompt_path) pairs."""
    chunks = sorted(out_dir.glob(f"auction_{auction_id}_chunk_[0-9][0-9].json"))
    if not chunks:
        sys.exit(f"Error: no chunk files for {auction_id} in {out_dir}. "
                 f"Run tools/chunk_flagging.py first.")
    if n_buckets is None:
        n_buckets = count_buckets()

    # Stale prompts from a previous chunking (fewer chunks this time) would
    # otherwise sit next to the live ones and look just as ready to paste.
    for old in out_dir.glob(f"auction_{auction_id}_chunk_[0-9][0-9]_prompt.md"):
        old.unlink()

    written = []
    for chunk_path in chunks:
        rows = _as_items(json.loads(chunk_path.read_text(encoding="utf-8")))
        if not rows:
            sys.exit(f"Error: {chunk_path} is empty")
        stem = chunk_path.stem                       # auction_<ID>_chunk_NN
        prompt_path = out_dir / f"{stem}_prompt.md"
        prompt_path.write_text(render("flagging.md", {
            "CONTEXT_FILE": "context.yaml",
            "INPUT_FILE": chunk_path.name,
            "OUTPUT_FILE": f"{stem}_flags.json",
            "N": f"{len(rows):,}",
            "LAST_LOT": str(rows[-1]["lot_number"]),
            "N_BUCKETS": str(n_buckets),
        }), encoding="utf-8")
        written.append((chunk_path, prompt_path))
    return written


def render_resale(auction_id: str,
                  out_dir: Path = Path("data/categorized")) -> tuple[Path, Path] | None:
    """One prompt for the resale pass, or None if its input is not built."""
    src = out_dir / f"auction_{auction_id}_for_resale.json"
    if not src.exists():
        return None
    rows = _as_items(json.loads(src.read_text(encoding="utf-8")))
    if not rows:
        sys.exit(f"Error: {src} is empty")
    prompt_path = out_dir / f"auction_{auction_id}_resale_prompt.md"
    prompt_path.write_text(render("resale.md", {
        "INPUT_FILE": src.name,
        "OUTPUT_FILE": f"auction_{auction_id}_resale_deduped.json",
        "N": f"{len(rows):,}",
        "LAST_LOT": str(rows[-1]["lot_number"]),
    }), encoding="utf-8")
    return src, prompt_path


def print_handoff(auction_id: str, flagging: list[tuple[Path, Path]] | None,
                  resale: tuple[Path, Path] | None) -> None:
    """The checklist the user works through, one chat per line group."""
    out_dir = Path("data/categorized")
    print()
    print("READY TO HAND OFF — one fresh chat per prompt. Each prompt file is "
          "complete:\npaste the whole thing, attach the files it names, save "
          "the reply under the name it gives.")
    if flagging:
        print()
        print(f"Flagging ({len(flagging)} chats), attach "
              f"{out_dir / 'context.yaml'} to EVERY one:")
        for chunk_path, prompt_path in flagging:
            print(f"  paste  {prompt_path}")
            print(f"  attach {chunk_path}")
            print(f"  save   {chunk_path.with_name(chunk_path.stem + '_flags.json')}")
    if resale:
        src, prompt_path = resale
        print()
        print("Resale (1 chat), attach NO config files:")
        print(f"  paste  {prompt_path}")
        print(f"  attach {src}")
        print(f"  save   {out_dir / f'auction_{auction_id}_resale_deduped.json'}")


def main(auction_id: str) -> None:
    out_dir = Path("data/categorized")
    has_chunks = any(out_dir.glob(f"auction_{auction_id}_chunk_[0-9][0-9].json"))
    flagging = render_flagging(auction_id) if has_chunks else None
    resale = render_resale(auction_id)
    if not flagging and not resale:
        sys.exit(f"Error: nothing to render for {auction_id} — run "
                 f"tools/chunk_flagging.py and/or tools/slim_resale.py first.")
    print_handoff(auction_id, flagging, resale)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
