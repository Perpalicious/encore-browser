# Pass sources — what each model pass reads and writes

Reference for the model passes. Written 2026-08-30, revised 2026-09-05 when the
four-way category split was replaced by dedup + chunking: it says which file
supplies which part of each prompt, and which assumptions about those files are
wrong.

This does **not** restate the pipeline. `CLAUDE.md` owns the run order (scrape →
slim → dedup/chunk → passes → reconcile → merge → verify → build → deploy) and
is the authority on everything either side of the passes. Read it first; this
file only covers the model calls that sit in the middle of it, at step 4.

There are **two jobs — flagging and resale — and they do not take the same
inputs.** The most common way to get this wrong is to assume the resale pass
wants the same attachments as flagging. It does not: flagging needs
`context.yaml` on every chat, resale needs no config at all. Flagging is
additionally split across several chunk files; resale is one call.

---

## The flagging pass (chunked)

One call per chunk. Every chunk gets the **identical** prompt and the
**complete** taxonomy; chunks differ only in which lots they carry.

| Source | Path | Role |
|---|---|---|
| Prompt template | `prompts/flagging.md` | `{{PLACEHOLDERS}}` for the per-chat values |
| Rendered prompt | `data/categorized/auction_<ID>_chunk_NN_prompt.md` | Written by `tools/render_prompts.py` (called from `chunk_flagging.py`). Complete: paste whole |
| Config | `data/categorized/context.yaml` | `buckets.yaml` + `profile.yaml` concatenated by `tools/chunk_flagging.py`. Attach to every chat |
| Row schema | `prompts/input_fields.md` | Appended to every rendered prompt; an absent key is meaningful and the model needs telling |
| Rationale | `PROMPTS.md` | Why the prompt is shaped as it is and what fails silently. Not itself a source of prompt text |
| Data in | `data/categorized/auction_<ID>_chunk_NN.json` | Written by `tools/chunk_flagging.py` |
| Data out | `data/categorized/auction_<ID>_chunk_NN_flags.json` | Consumed by `tools/expand_flags.py` |

Each rendered prompt carries its own chunk's row count, last `lot_number`
(the `chunk_complete` value), the bucket count for the attachment read-test,
and its output name `auction_<ID>_chunk_NN_flags.json`. Typically 7 chunks of
2,750 products plus `context.yaml` — 8 uploads.

### The recall repair (one chat, after `expand_flags.py`)

Same inputs as a flagging chunk — `context.yaml` **is** required — but the
rows come from the pass's own output rather than the auction. Built by
`tools/recall_check.py <ID> plan`, folded back by `... apply`.

| Source | Path | Role |
|---|---|---|
| Prompt template | `prompts/recall.md` | Same output schema and sentinel as flagging |
| Rendered prompt | `data/categorized/auction_<ID>_recall_prompt.md` | Written by `recall_check.py plan`. Complete: paste whole |
| Config | `data/categorized/context.yaml` | The same file the flagging chats used. Attach |
| Data in | `data/categorized/auction_<ID>_recall.json` | Unflagged products with a `suspect` list: the bucket and the evidence (a flagged sibling, or a seed in a dominated category) |
| Data out | `data/categorized/auction_<ID>_recall_flags.json` | Consumed by `recall_check.py apply`, which rewrites `_flags.json` in place |

Typically 400-500 rows. The chat may confirm a bucket outside the `suspect`
list; it may not touch a product that is not in its input, and `apply`
refuses a response that tries.

Two properties the automation must not break:

- **The pass returns matches only**, then `{"chunk_complete": "<LAST LOT>"}` as
  the final array element. Non-matches are expanded locally by
  `tools/expand_flags.py`. The sentinel is the truncation detector; without it
  a short response is indistinguishable from a chunk with few matches.
- **Products, not lots.** Input rows are one per distinct product (dedup on
  title + condition + the fields that can change the answer), and
  `tools/expand_flags.py` fans each answer back out to every lot in the group.
  25,195 lots → 19,250 products on 2026-08-30.

An earlier four-way category split (A–D) lived in `passes.yaml` and
`tools/split_passes.py`. It was never run against a live auction, was replaced
by dedup + chunking in `11e383b`, and the files were deleted in the commit that
added "How to refresh this" to `data/Watch/FINDINGS.md`. See the section below
for why it bought less than it appeared to; `git show 99f50e3` has the code.

## The resale pass

| Source | Path |
|---|---|
| Prompt template | `prompts/resale.md` (+ `prompts/input_fields.md`) |
| Rendered prompt | `data/categorized/auction_<ID>_resale_prompt.md`, written by `tools/slim_resale.py` |
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

### 1. Do not slice `buckets.yaml` per chunk

It is tempting: chunk 4 is 100% Home Goods, so why send all 62 buckets? Because
HiBid's own categories are unreliable in exactly the way that matters here — a
Barbie filed under Home Goods must still come back as `Barbies`, and 59% of
Hand tools inventory sits under *Lawn & Garden*, not Construction. Narrowing
the taxonomy to a chunk's apparent subject destroys precisely those catches.

This is also why the A–D split bought less than it looked like it did. Its
per-pass `focus_buckets` lists were explicitly advisory, and `buckets.yaml` was
attached in full regardless, so they narrowed nothing — they were a hint, and a
hint keyed off an unreliable category. Chunks carry no hint at all and lose
nothing by it.

Products are ordered by category before cutting, so a chunk is *mostly* one
kind of thing. That is a property of the ordering, not a licence to slice the
taxonomy. The same reasoning applies to `profile.yaml`: send all of it. Both
travel as one `context.yaml`, so there is nothing to get wrong per chunk.

### 2. Chunking exists now — do not re-derive it

This used to say chunking was a gap you had to fill yourself. It is filled:
`tools/chunk_flagging.py` dedups and cuts, `tools/expand_flags.py` reconciles
and fans out. Between them they own the completeness guarantee, and both fail
loudly and write nothing rather than producing a short file.

The trap that remains is **regenerating chunks mid-run**. `chunk_flagging.py`
rewrites every chunk file and the group map, so responses already collected get
reconciled against chunks they were never judged from.

`tools/prefilter.py` also emits paste boundaries (`order_candidates`, surfaced
in `_prefilter.json`), left over from the older shortlist flow. Those are not
the chunk boundaries and nothing reads them.

### 3. The row count and last lot come from disk, not from the model

The completeness rule in each prompt states a real row count and the real
last `lot_number`, and `tools/render_prompts.py` fills both from the input
file on disk. A concrete number is what makes the model's own count checkable,
and the last lot is what `tools/expand_flags.py` compares the sentinel
against. Do not let the model supply either from its own reading of the
attachment — a run that read 2,000 of 2,750 rows would honestly report the
last lot *it* saw. The renderer also refuses to write a prompt with any
`{{PLACEHOLDER}}` left unfilled.

### 4. Wire into the existing verification, do not reimplement it

These already exist and are precisely the anti-truncation net. Treat a non-zero
exit as "retry that pass", not as something to route around:

| Check | Catches |
|---|---|
| `tools/expand_flags.py` | A missing or invalid response, a missing/wrong `chunk_complete` sentinel (truncation), a `lot_number` not in that chunk, a lot judged twice, a forbidden key, `is_bats_list` disagreeing with `bats_buckets`. Writes nothing on any of them |
| `merge_categorized` — `n_added` must be **0** | A hallucinated or stale `lot_number` not in this week's auction |
| `tools/expand_resale.py` | Any product left unvalued; exits non-zero and writes nothing |
| `tools/verify_passes.py` | Lot-set SHA vs *this week's* slimmed file, duplicate lot_numbers, `bats_subtype` coverage <90%, bucket names absent from `buckets.yaml`, `is_bats_list` disagreeing with `bats_buckets` |

`verify_passes.py` also prints a per-bucket `shown / kept / rate` table. Those
columns are scored against `tools/prefilter.py`'s shortlist, which no longer
decides what the model sees — so read them as a comparison between the two.
A bucket shown ≥20 candidates and keeping **none** is still worth chasing; a
high `rate` no longer means the shortlist is doing the judging, and a large
`outside` count is now expected rather than alarming.

Personal care is the thing to watch. Those buckets had almost no coverage
before 2026-08-30 — if they come back near-zero, `context.yaml` did not attach,
which the bucket-count read-test at the top of the prompt is there to catch.

---

## The prompts are templates (resolved 2026-09-11)

The prompt bodies used to be markdown blockquotes embedded in `PROMPTS.md`,
which meant stripping `> ` prefixes out of a document that also explains
itself. They now live in `prompts/flagging.md`, `prompts/resale.md` and the
shared `prompts/input_fields.md`, with `{{PLACEHOLDERS}}` for the per-chat
values; `PROMPTS.md` keeps the rationale. `tools/render_prompts.py` fills them
in — an automated run wants `render_flagging()` / `render_resale()` from that
module, or the rendered `_prompt.md` files that `chunk_flagging.py` and
`slim_resale.py` leave next to their inputs.

---

## Config files at a glance

| File | Size | Read by | In a prompt? |
|---|---|---|---|
| `buckets.yaml` | ~100 KB, 72 buckets | `prefilter.py`, `chunk_flagging.py`, `verify_passes.py`, `build/groups.py` | **Yes**, via `context.yaml`, every chunk |
| `profile.yaml` | 16 KB — `sizes`, `projects`, `not_wanted`, `interests`, `proven_resale` | `prefilter.py`, `chunk_flagging.py`, `verify_passes.py` | **Yes**, via `context.yaml`, every chunk |
| `context.yaml` | 83 KB, generated | — | **This is the file that gets uploaded.** Regenerated every run |
| `bats_list.yaml` | 6.5 KB | nothing | No |

`buckets.yaml` is the file built from three months of real bid/watch history
(see its header comment near the Personal care group, and
`data/Watch/FINDINGS.md`) — that history is what took it from 48 buckets to 62.
`FINDINGS.md` also carries the method for refreshing it from a later export,
including the sampling trap that made the first pass at these numbers wrong.
