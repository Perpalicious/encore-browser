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
| Prompt template | `PROMPTS.md` § *Pass 1 → Prompt* | The blockquote body. Substitute `N` and `<LAST LOT>` |
| Config | `data/categorized/context.yaml` | `buckets.yaml` + `profile.yaml` concatenated by `tools/chunk_flagging.py`. Attach to every chat |
| Row schema | `PROMPTS.md` § *Input fields* | Must be in the prompt; an absent key is meaningful and the model needs telling |
| Output contract | `PROMPTS.md` § *Shared rules* | Must be in the prompt |
| Data in | `data/categorized/auction_<ID>_chunk_NN.json` | Written by `tools/chunk_flagging.py` |
| Data out | `data/categorized/auction_<ID>_chunk_NN_flags.json` | Consumed by `tools/expand_flags.py` |

`tools/chunk_flagging.py` prints the substitutions per chunk: row count for `N`
and last `lot_number` for `<LAST LOT>`. Typically 7 chunks of 2,750 products
plus `context.yaml` — 8 uploads.

Two properties the automation must not break:

- **The pass returns matches only**, then `{"chunk_complete": "<LAST LOT>"}` as
  the final array element. Non-matches are expanded locally by
  `tools/expand_flags.py`. The sentinel is the truncation detector; without it
  a short response is indistinguishable from a chunk with few matches.
- **Products, not lots.** Input rows are one per distinct product (dedup on
  title + condition + the fields that can change the answer), and
  `tools/expand_flags.py` fans each answer back out to every lot in the group.
  25,195 lots → 19,250 products on 2026-08-30.

`passes.yaml` and `tools/split_passes.py` defined an earlier four-way category
split (A–D) and are no longer in the run. They were never actually run against
a live auction. Nothing reads `passes.yaml` except `split_passes.py`.

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

### 1. Do not slice `buckets.yaml` per chunk

It is tempting: chunk 4 is 100% Home Goods, so why send all 62 buckets? Because
HiBid's own categories are unreliable in exactly the way that matters here — a
Barbie filed under Home Goods must still come back as `Barbies`, and 59% of
Hand tools inventory sits under *Lawn & Garden*, not Construction. Narrowing
the taxonomy to a chunk's apparent subject destroys precisely those catches.

This is also why the A–D split bought less than it looked like it did. Its
`focus_buckets` lists were advisory (`passes.yaml`, header comment) and
`buckets.yaml` was attached in full regardless, so they narrowed nothing — they
were a hint, and a hint keyed off an unreliable category. Chunks carry no hint
at all and lose nothing by it.

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

### 3. Substitute the real row count and last lot

`PROMPTS.md` § *Shared rules* requires replacing the literal `N` and
`<LAST LOT>` before sending. A concrete number is what makes the model's own
count checkable, and `<LAST LOT>` is what the sentinel is compared against —
leaving either placeholder in makes the completeness rule unenforceable.
`tools/chunk_flagging.py` prints both per chunk; `tools/slim_resale.py` prints
the resale row count.

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

## Known friction: the prompts are prose

The prompt bodies live as markdown blockquotes embedded in explanatory prose in
`PROMPTS.md`. Extracting them means stripping `> ` prefixes out of a document
that also explains itself, and the surrounding rationale is genuinely worth
keeping for humans.

If this proves fragile, the clean fix is to split the prompt text into
`prompts/flagging.md` and `prompts/resale.md` and have `PROMPTS.md` keep the
rationale and link to them. It was tried once, as part of an automated-run
experiment that was reverted for unrelated reasons (cost), and the extraction
itself was not the problem. Still not done — flagged so the decision stays
deliberate.

Match on the `##` / `###` headings rather than line numbers; the file is edited
often enough that any line table here goes stale.

---

## Config files at a glance

| File | Size | Read by | In a prompt? |
|---|---|---|---|
| `buckets.yaml` | 67 KB, 62 buckets | `prefilter.py`, `chunk_flagging.py`, `verify_passes.py`, `build/groups.py` | **Yes**, via `context.yaml`, every chunk |
| `profile.yaml` | 16 KB — `sizes`, `projects`, `not_wanted`, `interests`, `proven_resale` | `prefilter.py`, `chunk_flagging.py`, `verify_passes.py` | **Yes**, via `context.yaml`, every chunk |
| `context.yaml` | 83 KB, generated | — | **This is the file that gets uploaded.** Regenerated every run |
| `passes.yaml` | 5.9 KB — `fallback` + 4 `passes` | `split_passes.py` only | **No** — the A–D split is not in the run |
| `bats_list.yaml` | 6.5 KB | nothing | No |

`buckets.yaml` is the file built from three months of real bid/watch history
(see its header comment near the Personal care group, and `data/Watch/`) —
that history is what took it from 48 buckets to 62. `passes.yaml` cites the same
source for the 77.4% shortlist-reach figure that justifies the four-way split,
but its content is not derived from it.
