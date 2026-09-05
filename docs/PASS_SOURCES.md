# Pass sources — what each model pass reads and writes

Reference for building an automated run of the five model passes. Written
2026-08-30 for an agent doing the planning: it says which file supplies which
part of each prompt, and which assumptions about those files are wrong.

This does **not** restate the pipeline. `CLAUDE.md` owns the run order (scrape →
slim → shortlist → split → passes → merge → verify → build → deploy) and is the
authority on everything either side of the passes. Read it first; this file only
covers the five model calls that sit in the middle of it, at step 4.

There are **five passes, and they do not take the same inputs.** The most common
way to get this wrong is to assume the resale pass wants the same attachments as
the flagging passes. It does not.

---

## The four flagging passes (A–D)

One call per pass. Each judges a disjoint category slice of the auction, so
every lot is judged exactly once.

| Source | Path | Role |
|---|---|---|
| Prompt template | `PROMPTS.md` § *Pass 1 → Prompt* | The blockquote body. Substitute `<PASS NAME>` and `<FOCUS BUCKETS>` |
| Pass definitions | `passes.yaml` | Supplies those two substitutions: `name` and `focus_buckets` |
| Bucket taxonomy | `buckets.yaml` | All 62 buckets, every pass — see "Do not slice" below |
| Household profile | `profile.yaml` | All of it, every pass |
| Row schema | `PROMPTS.md` § *Input fields* | Must be in the prompt; an absent key is meaningful and the model needs telling |
| Output contract | `PROMPTS.md` § *Shared rules* | Must be in the prompt |
| Data in | `data/categorized/auction_<ID>_pass_<a\|b\|c\|d>.json` | Written by `tools/split_passes.py` |
| Data out | `data/categorized/auction_<ID>_flags_<a\|b\|c\|d>.json` | Consumed by `merge_categorized` |

Per-pass substitutions, from `passes.yaml` (volumes are week of 2026-08-16):

| pass | `name` | focus buckets | lots | covers |
|---|---|---|---|---|
| A | Bed, bath & personal care | 13 | 6,595 | Bed/Bath, Linens, Carpet — **all personal care lives here** |
| B | Kitchen, home, food & cleaning | 30 | 7,770 | rest of Home Goods, Furniture, Business & Industrial |
| C | Tools, outdoor & sports | 22 | 4,891 | Construction & Farm, Lawn & Garden, Sporting Goods |
| D | Tech, toys, fashion & the tail | 17 | 7,767 | Electronics, Kid & Baby, Toys, Fashion, tail — **also the fallback** |

Pass D is `fallback` in `passes.yaml`: any lot whose category is missing or
unrecognised lands there, so nothing is ever dropped.

## The resale pass

| Source | Path |
|---|---|
| Prompt template | `PROMPTS.md` § *Pass 2 → Prompt* |
| Row schema + output contract | `PROMPTS.md` § *Input fields* and § *Shared rules* |
| Data in | `data/categorized/auction_<ID>_for_resale.json` (from `tools/slim_resale.py`) |
| Data out | `data/categorized/auction_<ID>_resale_deduped.json` |

**No config files.** Not `buckets.yaml`, not `profile.yaml`. This pass is pure
valuation and has no notion of buckets or interests; attaching them is noise.

Its input is one row per *distinct product*, not per lot — these auctions list
the same item many times (58 identical lots is normal). `tools/expand_resale.py`
fans each valuation back out afterwards. Note the `_deduped` suffix on the
output: writing this pass's result straight to `_resale.json` leaves most of the
auction unvalued.

## Not a source for anything

`bats_list.yaml` — the ancestor of `buckets.yaml`, last touched 2026-07-13. No
code reads it. `CC_HANDOFF_BRIEF.md` still says "do not modify", which is why it
is still here. Ignore it.

---

## Four things that will bite an automated run

### 1. Do not slice `buckets.yaml` per pass

It is tempting: pass A lists only 13 focus buckets, so why send all 62? Because
`focus_buckets` is **advisory by design** (`passes.yaml`, header comment). It
says where a bucket's inventory usually sits; it does not say what the model may
assign.

HiBid's own categories are unreliable in exactly the way that matters here — a
Barbie filed under Home Goods lands in pass B and must still come back as
`Barbies`, and 59% of Hand tools inventory sits under *Lawn & Garden*, not
Construction. Slicing turns the advisory hint into a hard filter and
structurally destroys the cross-category catches the four-way split exists to
preserve. Send the full file every time.

The same reasoning applies to `profile.yaml`: send all of it.

### 2. Chunking is a gap you have to fill yourself

The passes are 4,891–7,770 lots each — far more than one response. There is no
chunking helper for them.

`tools/prefilter.py` *does* emit paste boundaries (`order_candidates`, surfaced
in `_prefilter.json`), but that was written for the older shortlist flow.
**`tools/split_passes.py` has no equivalent** — it writes whole files and prints
per-pass counts, nothing more.

So the automation needs its own chunk-and-reassemble layer, and that layer is
where truncation hides. A run that stops early produces valid JSON that is
simply short, and is indistinguishable from success by eye. Chunk on row
boundaries, track which rows each chunk was given, and reconcile lot sets rather
than trusting a response to be complete.

### 3. Substitute the real row count

`PROMPTS.md` § *Shared rules* requires replacing the literal `N` in each
completeness instruction with the actual row count before sending. A concrete
number is what makes the model's own count checkable; leaving `N` in makes the
instruction unenforceable. `tools/split_passes.py` prints the count per pass and
`tools/slim_resale.py` prints the resale row count.

### 4. Wire into the existing verification, do not reimplement it

These already exist and are precisely the anti-truncation net. Treat a non-zero
exit as "retry that pass", not as something to route around:

| Check | Catches |
|---|---|
| `merge_categorized` — `n_added` must be **0** on all four chains | A hallucinated or stale `lot_number` not in this week's auction |
| `tools/expand_resale.py` | Any product left unvalued; exits non-zero and writes nothing |
| `tools/verify_passes.py` | Lot-set SHA vs *this week's* slimmed file, duplicate lot_numbers, `bats_subtype` coverage <90%, bucket names absent from `buckets.yaml`, `is_bats_list` disagreeing with `bats_buckets` |

`verify_passes.py` also prints a per-bucket `shown / kept / rate` table. Two
shapes matter: a bucket shown ≥20 candidates keeping **none** (the pass refused
the whole bucket), and a rate **above 95%** (the shortlist is doing the judging
and the bucket's seeds have become a whitelist).

Pass A is the one to watch. It is the densest slice and had almost no bucket
coverage before 2026-08-30 — if it returns near-zero flags, the personal-care
buckets did not attach.

---

## Known friction: the prompts are prose

The prompt bodies live as markdown blockquotes embedded in explanatory prose in
`PROMPTS.md`. Extracting them means stripping `> ` prefixes out of a document
that also explains itself, and the surrounding rationale is genuinely worth
keeping for humans.

If this proves fragile, the clean fix is to split the prompt text into
`prompts/flagging.md` and `prompts/resale.md` and have `PROMPTS.md` keep the
rationale and link to them. Not done yet — flagged so the decision is
deliberate rather than discovered mid-implementation.

Section line numbers as of 2026-08-30 (they drift — match on the headings):

| Section | Lines |
|---|---|
| `## Input fields` | 29–67 |
| `## Shared rules (apply to both passes)` | 68–93 |
| `### Prompt` (Pass 1, flagging) | 147–274 |
| `### Prompt` (Pass 2, resale) | 337–396 |

---

## Config files at a glance

| File | Size | Read by | In a prompt? |
|---|---|---|---|
| `buckets.yaml` | 69 KB, 62 buckets | `prefilter.py`, `split_passes.py`, `verify_passes.py`, `build/groups.py` | **Yes**, all four flagging passes |
| `profile.yaml` | 16 KB — `sizes`, `projects`, `not_wanted`, `interests`, `proven_resale` | `prefilter.py`, `split_passes.py`, `verify_passes.py` | **Yes**, all four flagging passes |
| `passes.yaml` | 5.9 KB — `fallback` + 4 `passes` | `split_passes.py` | **No** — read `name` / `focus_buckets` out of it to fill the template |
| `bats_list.yaml` | 6.5 KB | nothing | No |

`buckets.yaml` is the file built from three months of real bid/watch history
(see its header comment near the Personal care group, and `data/Watch/`) —
that history is what took it from 48 buckets to 62. `passes.yaml` cites the same
source for the 77.4% shortlist-reach figure that justifies the four-way split,
but its content is not derived from it.
