# Orchestrator runbook

This is the orchestrator's half of the weekly run: the person-shaped job of
starting the work, carrying files between agents, and deciding when to stop.
The other half — every command, check and gotcha — is in `AGENTS.md`, and the
shell agent follows it on its own. **The orchestrator never runs pipeline
commands itself and never edits a data file.** It sends messages, moves files,
and escalates.

Three parties:

| Role | What it is | What it touches |
|---|---|---|
| Orchestrator | you (Dot) | messages, and files in `data/categorized/` |
| Shell agent | Codex, open in the repo on the desktop | every command in `AGENTS.md` |
| Chat agents | fresh ChatGPT chats, one per prompt | one prompt + its attachments, nothing else |

---

## One-time setup (the user does this)

1. **Shell agent: Codex on the desktop (Grink), opened in
   `~/projects/encore-browser`.** Not a cloud sandbox: `data/` is gitignored,
   so last week's files, the hammer history and the raw scrape exist only on
   that disk. Allow it to run commands without asking for approval, with
   network access — it scrapes HiBid and pushes to GitHub. It reads
   `AGENTS.md` by itself; it needs no other instructions.
2. **Chat agents: fresh ChatGPT chats, the same model every week.** They need
   file upload and file download. They must **not** have repo or shell access:
   a coding agent handed a chunk may decide to run the pipeline scripts itself.
3. **The orchestrator must be able to:** send the shell agent a message and
   read its reply; read files in `data/categorized/` on the desktop; attach
   them to a ChatGPT chat; download the file a chat returns; and write that
   file into `data/categorized/` under an exact name.
4. **Supervise the first week end to end** before putting it on a schedule.

---

## Input each week: the auction ID(s)

The ID is the number in the auction's HiBid address:
`encoreauctions.hibid.com/catalog/<ID>/…`. Most weeks have one Encore
auction. When there are two, you need both, and which one closes **Sunday**
and which **Monday** — the shell agent prefixes lot numbers by that.

If you are not certain which auction is this week's, ask the user. A wrong
ID produces a clean-looking site full of the wrong lots.

---

## Stage 1 — start the run

Send the shell agent exactly:

```
Run this week's auction <ID>.
```

Two-auction week:

```
Run this week's auction: Sunday <SUNDAY_ID>, Monday <MONDAY_ID>.
```

It scrapes, prepares the files, and stops with a checklist that begins
`READY TO HAND OFF`. That checklist is your work order:

```
Flagging (7 chats), attach data/categorized/context.yaml to EVERY one:
  paste  data/categorized/auction_<ID>_chunk_01_prompt.md
  attach data/categorized/auction_<ID>_chunk_01.json
  save   data/categorized/auction_<ID>_chunk_01_flags.json
  ...
```

- **Use the names exactly as the checklist prints them.** Never build a file
  name yourself — two-auction weeks use `auction_combined_…`, mid-week deltas
  use `auction_<ID>_d1_…`, and the chunk count is not always 7.
- If the shell agent's reply does not include the checklist, send:
  `Print the handoff checklist (python3 tools/render_prompts.py <ID>).`
  That re-prints it without changing any file.
- If it stops anywhere else, or reports an error or warning, go to
  **Escalate**.

---

## Stage 2 — the flagging chats (one per chunk)

For **each** `paste / attach / save` group in the checklist. They are
independent, so they can run in parallel:

1. Open a **new** ChatGPT chat. Never reuse one, not even for the same chunk.
2. Paste the **entire** text of the `paste` file. Do not edit, trim or
   summarise it.
3. Attach **two** files: `data/categorized/context.yaml` **and** the chunk
   file on the `attach` line.
4. **Read test.** The chat's first line states how many buckets it read. The
   prompt says what the number must be. If it reports a different number, says
   it cannot read a file, or judges no lots, that chat has failed. Discard it
   and start again at step 1.
5. **Save the reply.** The chat returns a downloadable file. Save it under the
   **exact `save` path** from the checklist, whatever name the chat gave it.
   If it printed the JSON instead of returning a file, save **only** the JSON
   array, from the opening `[` to the closing `]`, and nothing before or after
   it. The bucket-count sentence must not be in the file. The checker parses the
   file as pure JSON and rejects anything else.
6. **Check the tail before saving.** The last element of the array must be
   `{"chunk_complete": "<the last lot_number the prompt names>"}`. If it is
   missing, or the chat says it could not finish, discard it and start a new
   chat. Never ask it to "continue": a continuation splits one answer into two
   pieces, and the checker accepts only one file per chunk.

When every `save` file exists, send:

```
All flagging responses are saved. Continue.
```

### If the shell agent reports chunks that did not reconcile

It prints `the flagging responses did not reconcile` and names chunks
(`chunk 03: …`). Re-run **only those chunks**, each in a new chat with the same
prompt file and attachments, and overwrite their `save` files. Then send
`Continue.` again.

- Each chunk gets at most **two** re-runs. A third failure means escalate.
- **Never** ask the shell agent to re-run `tools/chunk_flagging.py`, re-chunk,
  or "start the chunks over". That rewrites every chunk, and every response
  already collected becomes wrong.
- Never edit a saved response to make it pass.

---

## Stage 3 — the recall chat (one more)

After the flagging responses reconcile, the shell agent stops a second time
with one more chat:

```
Recall repair (1 chat), attach context.yaml like the flagging chats:
  paste  data/categorized/auction_<ID>_recall_prompt.md
  attach data/categorized/context.yaml
  attach data/categorized/auction_<ID>_recall.json
  save   data/categorized/auction_<ID>_recall_flags.json
```

Same procedure as Stage 2: a new chat, the whole prompt, both attachments, the
read test, JSON only, and a `chunk_complete` tail. Then send:

```
Recall response saved. Continue.
```

If it says nothing needs re-judging, there is no recall chat. Send
`Continue.`

---

## Stage 4 — finish

The shell agent now merges, verifies, builds, checks the bundle, deploys,
commits and tidies, all on its own. Wait for its final report. It should
contain:

- the lot count and the bundle numbers from `AGENTS.md` step 7
  (`carry personal_match`, `are personal_match=true`, `carry a bat_subtype`,
  `have 2+ buckets`, `carry a hammer_key`, `scrapes:`)
- how many recall suspects were confirmed vs refused
- that the deploy is live at `https://perpalicious.github.io/encore-browser/`
- that the commit was pushed to `main`

If any of those is missing, ask the shell agent for it before reporting done.
`0 with resale` is expected: resale is off by default.

---

## Escalate: stop and message the user

You handle exactly two things yourself: re-running a chat that failed
(Stage 2, up to two re-runs per chunk) and saying `Continue.` at the two
handoffs. **Everything else goes to the user**, quoted word for word, and you
wait. Do not answer the shell agent's questions on the user's behalf, and do
not tell it to "proceed anyway".

Always escalate when:

- the shell agent stops anywhere other than the two handoffs, or reports an
  error or a warning
- a chunk fails a third time
- `verify_passes.py` fails
- the merge reports `Merged <n> new items` with `n` other than 0
- the build lists bucket names under its "no group" warning
- `personal_match`, `bat_subtype` or 2+-bucket counts are 0 or near 0
- recall confirmed nearly all of its suspects
- a bucket was shown 20 or more candidates and kept none
- `git push` hits a conflict on `auction_bundle.json`
- you are unsure which auction is this week's

Never instruct the shell agent to: skip a step or a check, hand-edit a JSON
file, re-run `tools/chunk_flagging.py` mid-pass, delete anything in
`data/hammer/`, turn resale on, or change `buckets.yaml` / `profile.yaml`.
Each of those needs the user's own say-so.

---

## If the shell agent's session ends between stages

The files on disk carry the state, so a fresh Codex session can pick up the
run. Open one in the repo and send the line for the stage you were at:

| Where you were | Send |
|---|---|
| flagging responses saved | `Continue the weekly run for auction <ID> from step 5 (tools/expand_flags.py <ID>). All chunk responses are saved.` |
| recall response saved | `Continue the weekly run for auction <ID> from step 5a (tools/recall_check.py <ID> apply). The recall response is saved.` |
| no recall chat this week | `Continue the weekly run for auction <ID> from the merge in step 5. Recall had nothing to re-judge.` |

---

## Mid-week delta (optional)

New lots appear after the weekly run (Tue, Thu, Fri). To bring them onto the
site, send:

```
Run a mid-week delta for auction <ID>.
```

Then follow Stages 2–4 as written. The checklist's file names carry the delta
suffix (`auction_<ID>_d1_chunk_01_prompt.md`, etc.), which is one more reason
to copy names from the checklist and never build them. A delta can be one or
two chunks. If the shell agent says nothing is new, the delta is done.
