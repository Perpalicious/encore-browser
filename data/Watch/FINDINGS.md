# What the bid/watch history actually says

Source: 39 screenshots of the Encore "Bids" and "Watch List" tabs, auctions
**2026-05-31 → 2026-09-20**. Transcribed and deduplicated to
`data/Watch/history.tsv` — 1,011 unique lots (343 bid, 668 watch-only).
Outcomes: 252 Outbid, 91 May Have Won.

Last refreshed **2026-09-23**, which added 98 lots (39 bid, 59 watch) from
auction 776904, closed 9/20/26. All 98 joined to the archived
`data/archive/2026-09-20/auction_776904_for_agent.json` on `lot_number` with
a matching title prefix, and — new this time — to
`data/hammer/2026-09-20_776904.json` for what each product actually sold for.
The three most recent batches (2026-09-10, -15, -23) carry **full
untruncated titles** and a real `condition` instead of the brand-only
inference the earlier batches were stuck with. Doing the export while the
week's slimmed file is still on disk — or in the dated archive, *which is the
same week* — is what buys that; see Step 1.

`history.tsv` is **append-only and local** (gitignored — it is a per-lot log
of what this household bid on, and this repo is public). This file is the
tracked summary of it. To add a new export and refresh these numbers, follow
"How to refresh this" at the bottom.

Supply baseline: the four weeks still on disk (2026-08-08, 2026-08-16,
2026-08-30, 2026-09-06), **102,350 lots**. The previous refresh used the first
two of those (54,463 lots). Every lift below was computed against both bases;
the ranking is unchanged and no bucket moves a tier, so the wider denominator
is a precision gain rather than a change of method.

> **Read raw counts as exposure, not preference.** These auctions run the
> same product across dozens of lots, so a frequently-listed item collects
> engagement simply by appearing. Every ranking below is normalised against
> supply. See "Sampling, not sweeping".

## 1. The taxonomy gap

Scoring all 913 tracked lots against current `buckets.yaml` seeds *and*
`profile.yaml` pseudo-bucket seeds:

| | lots | share |
|---|---|---|
| matched at least one bucket / seed | 743 | 81% |
| **matched nothing at all** | **170** | **19%** |
| …of the 304 real *bids* | **56 unmatched** | **18%** |

**The 2026-08-30 taxonomy expansion halved this, and the measurement is
apples-to-apples.** Re-scoring the *same* 736 rows the original 31% / 40% was
computed from, against the current 62-bucket taxonomy, gives 19% / 20% — so
the improvement is the new buckets, not the new rows. The 97 rows added on
2026-09-10 land at 22% / 20% independently, which says the gap is stable
rather than still closing. The 80 rows added on 2026-09-15 land at 14% / 4%
— but scored against the 63-bucket taxonomy that had just been edited
*around* this week's bundle (see the 2026-09-15 section), so that batch
cannot be read as the gap closing on its own.

One in five things bid on still has nowhere to land, and that is not fixable
in `PROMPTS.md` — a category with no bucket and no seed cannot be surfaced by
any prompt. What is left, though, is a different problem from the one this
section originally described: it is now mostly **seeds missing from buckets
that already exist**, not missing buckets. See §7.

**This table scores on `title` alone**, because that is the only field
`history.tsv` carries for the batches captured before 2026-09-10. Production
also matches on the HiBid breadcrumb, which rescues some of these — a Funko Pop
matching no seed still shortlists through `Toys - Action Figures`. Where a
batch joins to its own week's slimmed file, score it the production way
instead; §7 does exactly that for the 2026-09-06 rows and gets a smaller, more
truthful gap (17.8% of bids, not 20%).

## 2. Sampling, not sweeping — the correction that re-ranks everything

Joining tracked lots back to the weeks we hold supply for:

- **Shark FlexStyle HD430C, week of 8/16: 46 identical lots available. Bid on 2.**
- **Keyboards, week of 8/08: 76 lots available. Engaged with 7.**
  Of the 69 ignored, **17 were ≥$150 and New/Like New** — including a
  Logitech G915 X TKL at $270 Like New, while a near-identical G915 X TKL
  at $261 *was* watched.

So a repeated-SKU run means "this product was listed many times", not "this
product is wanted many times". The earlier reading of 62 same-product runs as
quantity-seeking was wrong; the runs mostly track what the auction over-lists.

**The Shark WandVac is the real exception** (21 bids, 16 in one auction), and
for a specific reason: one has already been resold successfully, so the resale
value is known rather than estimated. That is a *proven-resale* signal about
one SKU — not a general appetite for bulk. Nothing in the config expresses it.
`Product testing & resale` is a pseudo-bucket whose five seeds (`wholesale
lot`, `case pack`, `bulk lot`, `pallet`, `retail box`) match none of it.

## 3. Interest per unit of exposure

`lift` = share of tracked lots ÷ share of supply. **1.0 = exactly as often as
it appears.** Buckets under ~100 supply lots across the four weeks are noisy —
flagged †. (The previous refresh flagged under ~50 on a two-week base; same
threshold, wider base.)

**Read this table against the current 62-bucket taxonomy.** The version it
replaces was scored against the 48-bucket one, so buckets created or split on
2026-08-30 — `Vacuums & floor care`, `Audio & headphones`, the Personal care
and Food & drink groups — have no prior row to compare against, and
`Cleaning supplies & tools` and `Electronics` lost lots to them.

**Genuinely over-indexed**

| bucket | supply (4 wks) | tracked | bid | lift |
|---|---|---|---|---|
| Hatchimals † | 1 | 3 | 1 | 369 |
| Surprise toys † | 32 | 27 | 15 | 104 |
| Barbies † | 72 | 35 | 15 | 60 |
| 3D printing supplies † | 64 | 14 | 4 | 27 |
| Tie-downs † | 41 | 7 | 1 | 21 |
| Kids' outdoor water play | 196 | 28 | 11 | 18 |
| Nightstands † | 65 | 8 | 4 | 15 |
| Garage & tool organization † | 83 | 10 | 2 | 15 |
| Brand chef knives | 165 | 15 | 5 | 11 |
| Laundry baskets † | 68 | 6 | 0 | 11 |
| Outdoor furniture & hammocks | 202 | 16 | 8 | 9.7 |
| Bath towels | 105 | 6 | 1 | 7.0 |
| Beverages & drink mixes | 120 | 6 | 2 | 6.1 |
| Keyboards & PC peripherals | 1,100 | 55 | 11 | 6.1 |
| Car care & detailing | 145 | 7 | 3 | 5.9 |
| Garden hose | 486 | 22 | 4 | 5.6 |
| Storage bins & totes | 354 | 16 | 2 | 5.6 |
| Lawn treatment & pest control | 181 | 8 | 3 | 5.4 |
| **Vacuums & floor care** | 1,946 | 65 | **34** | **4.1** |
| BBQ accessories | 374 | 12 | 4 | 3.9 |
| King bed frames | 266 | 8 | 7 | 3.7 |

`Vacuums & floor care` is the one to note: split out of `Cleaning supplies &
tools` on 2026-08-30 and now carrying **34 of the 279 bids on its own** — more
than any other bucket, at a lift of 4.1 on the second-largest supply in the
table. The split was justified on supply volume alone; the bid data since
supports it independently.

**Mid — above baseline, unremarkable** (lift 2.4–3.5): Power tools, Sports &
recreation gear, Seating & occasional furniture, Brand cookware, Home gym &
weightlifting, Kids' craft & activity, Adhesives & tape, Snacks &
confectionery, Bed linens, Lawn equipment, Tarps, Dinnerware, Smart home,
Cleaning supplies & tools, Kids' toys & games, Pool & hot tub, Garden &
lawncare misc.

**At or below baseline**

| bucket | supply (4 wks) | tracked | bid | lift | note |
|---|---|---|---|---|---|
| Glassware & drinkware | 900 | 7 | 3 | 1.0 | at baseline |
| Kitchen appliances | 3,497 | 23 | 7 | 0.8 | |
| Batteries & chargers | 668 | 4 | 0 | 0.7 | |
| Electronics | 4,877 | 28 | 8 | 0.7 | biggest supply of any bucket |
| Brand boots & shoes | 1,662 | 8 | 1 | 0.6 | still suppressed — `sizes.shoe` is `null` |
| Board games | 835 | 4 | 0 | 0.6 | |
| Video games & VR | 496 | 2 | 0 | 0.5 | |
| Lego | 282 | 1 | 0 | 0.4 | |
| Oral & dental care | 1,195 | 4 | 2 | 0.4 | gated — see below |
| Skincare & body | 2,936 | 7 | 6 | 0.3 | gated — see below |
| Bedding & pillows | 2,261 | 5 | 0 | 0.3 | |
| Shaving & grooming | 1,055 | 2 | 2 | 0.2 | gated — see below |
| Hair styling tools | 2,467 | 4 | 3 | 0.2 | |
| Hair care products | 1,528 | 2 | 2 | 0.2 | gated — see below |

### The seven gated buckets need a gated denominator

**This is a correction to the method, not just to a number.** Since 2026-08-30
seven buckets carry `condition_in: [Brand New - Sealed, New (Adjusted
Quantity), Best Before (Grocery)]`, so the shortlist never offers the opened
stock. Scoring them against *ungated* supply divides by lots the pass was
never shown, and understates every one of them by 4-25×:

| gated bucket | ungated supply | gated supply | tracked | bid | lift (ungated) | **lift (gated)** |
|---|---|---|---|---|---|---|
| Cosmetics & nail | 375 | 15 | 5 | 2 | 1.6 | **41** |
| Pantry & cooking staples | 357 | 34 | 4 | 3 | 1.4 | **15** |
| Snacks & confectionery | 253 | 63 | 6 | 4 | 2.9 | **12** |
| Beverages & drink mixes | 120 | 77 | 6 | 2 | 6.1 | **9.6** |
| Skincare & body | 2,973 | 139 | 7 | 6 | 0.3 | **6.2** |
| Supplements & protein | 227 | 43 | 2 | 2 | 1.1 | **5.7** |
| Hair care products | 1,628 | 103 | 2 | 2 | 0.2 | **2.4** |

`Skincare & body` is the clearest case: 0.3 on the ungated denominator reads
as the second-worst bucket in the taxonomy, and 6.2 on the gated one puts it
alongside `Garden hose`. Nothing about the household changed — only what the
shortlist is allowed to show.

Two caveats on that table. The gated supply column is scored on `title` +
`category` (the gate needs the lot in hand), the tracked column on `title`
alone, which inflates the denominator slightly and makes these numbers
conservative. And `Cosmetics & nail` at a gated supply of 15 over four weeks
is far below the † threshold — treat 41 as "clearly over-indexed", not as a
figure.

**The same reading applies to the ungated personal-care buckets.** Their lift
is low, but almost everything tracked in them was *bid on*, not watched:
Hair care 2/2, Shaving & grooming 2/2, Personal care & grooming 1/1, Skincare
& body 6/7, Hair styling tools 3/4. Low exposure share, near-perfect
conversion — the opposite shape from `Home gym & weightlifting` (20 tracked,
**0 bids**) or `Audio & headphones` (10 tracked, 0 bids), which are watched
and never bid.

## 4. The gate is condition, then price

Keyboards, week of 8/08 — engaged vs ignored:

| | n | median retail | Fair / Heavily Used |
|---|---|---|---|
| engaged | 7 | $156 | **0 (0%)** |
| ignored | 69 | $119 | 10 (14%) |

Condition separates more cleanly than price does. This matches the stated
behaviour: other mechanical keyboards do show up, and get passed over on
price or condition. Worth encoding as a ranking input rather than leaving
it to the model to infer.

**Seed noise, same bucket:** `Keyboards & PC peripherals` matches 262 lots a
week, of which ~47 (18%) are off-target — Corsair RGB case fans and fan
controllers, Logitech driving-force shifters and clutch modules, USB unifying
receivers, mousepads. Tightening `corsair` / `logitech` bare-brand seeds would
cut that.

### Half of this check stopped being runnable on 2026-08-30

`est_retail_price` is **0% from the 2026-08-30 week onward** — 27,011/27,023 on
2026-08-16, then 0/25,195 and 0/22,692. It went the same way as `model`,
`size`, `notes` and the damage flags when HiBid moved the structured detail
into the per-lot report image, but `tools/slim.py`'s docstring lists only the
others, so this one went unremarked. Consequences:

- the price half of "condition, then price" can no longer be measured on a
  current week, only on the 8/08 and 8/16 archives;
- Step 1 below used to promise the same-week join yields `est_retail_price`
  for free. It does not any more. It still yields the full title and
  `condition`, which is the larger part of the value;
- in the viewer, `est_retail_price` was a displayed field, a sort key, and the
  denominator of the `▲ VALUE` badge, so all three had been inert since
  2026-08-30. Confirmed against the deployed bundle at the time: 0 of 22,692
  lots carried a retail price.

**Resolved the same day: the field was removed from the pipeline entirely**
(2026-09-10). Not recovered from the report image — the call was that a
self-reported, unverified retail reference is not worth a second money figure
beside an actual resale estimate. Gone from the scraper parse, the Lot schema,
the slimmed agent input, the viewer's card/row/detail, the sort control and
the value badge. The consequence for this document is below.

The condition half still works, and on the 9/6 week it still separates,
though less sharply than on 8/08: `Keyboards & PC peripherals` engaged 11,
**0% Fair/Heavily Used**, against 293 ignored at 6%. `Kids' toys & games`
engaged 17 at 0% against 5%. Whole-export condition mix, all 97 lots: 41
Excellent, 18 Brand New - Sealed, 18 Brand New - Open Box, 15 Good, 3 New
(Adjusted Quantity), 3 Best Before, **3 Fair, 0 Heavily Used**.

## 5. Buckets with no engagement still earn their place

Scan coverage and pick precision are different jobs, and a bucket doing the
first will always look dead on bid metrics. Supply over the two weeks:

| bucket | supply (2 wks) | ~per week |
|---|---|---|
| Coffee & espresso | 111 | ~55 |
| Specialty cooking & baking ingredients | 87 | ~44 |
| Extension cords & power strips | 82 | ~41 |
| Starbucks coffee | 12 | ~6 |
| Shatterproof / outdoor dishware | 7 | ~4 |

The first three carry real weekly inventory and should stay regardless of
bid rate — they exist to be scanned. Only `Starbucks coffee` and
`Shatterproof / outdoor dishware` are thin on *both* axes. (Both were merged
away on 2026-08-30; `Specialty cooking & baking ingredients` was renamed
`Pantry & cooking staples` and broadened.)

**Confirmed over four months, not two weeks.** `Coffee & espresso` now stands
at 233 supply lots across the four weeks on disk (~58/week) and **still zero
tracked lots** — not one watch in 833. `Extension cords & power strips`: 156
supply (~39/week), zero tracked. Four months of history saying "never bid on"
is a far stronger statement than the two weeks this section was written from,
and the conclusion is unchanged: both stay. They exist to be scanned. A bucket
is retired for being thin on supply *and* engagement, and these are thin on
one axis only.

**Food coverage should expand, not shrink.** Untapped supply, 2 weeks:

| candidate bucket | supply | ~per week |
|---|---|---|
| Tea & drink mixes | 210 | ~105 |
| Pantry & cooking staples | 207 | ~104 |
| Energy & soft drinks | 170 | ~85 |
| Snacks & confectionery | 124 | ~62 |
| Supplements & protein | 89 | ~44 |
| Baby & kids food | 78 | ~39 |

(Counts from broad keyword probes and include some noise — moisturisers
matching "candy", board games matching "chocolate" — so treat as an upper
bound on a real bucket's yield.) History supports the interest even without
buckets: Quest protein cookies ×2 **both bid**, Crystal Light **bid**,
Taco Bell kit **bid**, Monster Energy ×3, Ghirardelli, Thai Kitchen.

## 6. Missing categories, by evidence

Counts are `lots (bids)` from the 736-row history.

> **Mostly resolved.** Items 1-9 below were the input to the 2026-08-30
> taxonomy expansion and all have buckets now; item 10 (apparel) is half done
> — `sizes.apparel` is set, `sizes.shoe` is still `null`. Kept as the record of
> what the evidence looked like before the change, and as the worked example
> of how to read a cluster. The live version of this question is §7.

1. **Personal care & grooming** — 16 (8). No bucket. Hair care is the spine:
   L'Oréal EverPure shampoo+conditioner (2 bids), Shark FlexStyle (2), Dyson
   Airwrap, Philips OneBlade. Plus sun/skin (IT Cosmetics SPF, Attitude) and
   dental (Waterpik, Sonicare, ultrasonic retainer cleaner — bid).
   - *sub-category* **Nail care** — 5 lots, 2 bids, all distinct products:
     Modelones gel kit, APRÈS Gel-X tips, OPI xPRESS/ON, Glamnetic.
2. **Handheld & cordless vacuums** — WandVac (proven resale, see §2),
   Dustbuster ×2, Levoit, Shark Cyclone, StainStriker, plus wet/dry.
3. **Seating & occasional furniture** — 15 (2). No bucket. Coffee tables ×4,
   bar stools ×3, hanging/egg chairs ×3, bean bag, kneeling chair (bid),
   VIVO footrest (bid). Only `Nightstands` and `King bed frames` exist today.
4. **Car care & detailing** — 5 (3). Chemical Guys kit, Meguiar's ×3.
   `profile.yaml` says *"generic car accessories are not wanted"* and scopes
   Vehicle to Tesla-fit only; the behaviour is the reverse.
5. **Kids' outdoor water play** — ~19 (9). Water tables ×8, electric water
   guns ×6, X-Shot / Super Soaker ×5. Seasonal, currently scattered.
6. **Snacks & branded beverages** — 7 (4). See §5.
7. **Irrigation timers** — 8 (0). Orbit B-Hyve ×4, Melnor ×2, Diivoo.
   `Garden hose` exists; its seeds don't reach timers.
8. **Kids' craft & activity** — ~12 (5). Crayola tracing pad (bid), air-dry
   clay (bid), Play-Doh (bid), markers, epoxy resin ×3, Montessori table (bid).
9. **Lawn treatment & pest** — 8 (2). Diatomaceous earth ×3, Turf Builder
   spreader (bid), WeedClear, dethatchers ×2.
10. **Apparel** — ~13 (3), and **blocked on config**: `sizes.shoe` and
    `sizes.apparel` are both `null`, so the pass is told to reject wrong sizes
    against a blank. `Brand boots & shoes` lift of 0.6 on 808 supply lots is
    probably this, not disinterest. Cheapest single fix on the list.

## 7. The gap is now seeds, not buckets

The 2026-09-06 export is the first batch that can be scored the way production
actually scores: every row joined to `auction_764523_for_agent.json`, so each
one carries `title`, `category` and `condition` and can be run through the real
shortlist rule rather than the title-only proxy §1 is stuck with.

Under that rule the shortlist reaches **37 of the 45 bids (82.2%)**. The eight
it misses are seven distinct products, and **every one of them belongs to a
bucket that already exists**:

| unmatched bid | HiBid category | bucket it belongs in | why it missed |
|---|---|---|---|
| CHAPIN 20004 SPRAYER TANK ×2 bids (+2 watched) | `Construction & Farm - Turf Equipment - Sprayers` | `Garden & lawncare misc` / `Lawn equipment` | no `sprayer` / `chapin` seed, and no bucket claims that crumb |
| PHILIPS ALL-IN-ONE 3000 TRIMMER, 13-PIECE KIT | `Home Goods - Bed / Bath Items` | `Shaving & grooming` | seeds miss the bucket's single most obvious product |
| NAPOLEON BBQ HEAT PLATE 4-PACK | `Home Goods - Grills` | `BBQ accessories` | no `heat plate` / `napoleon` seed |
| TRAMONTINA TRI-PLY WOK 12.5" (×2 bids across history) | `Home Goods - Kitchen / Housewares` | `Brand cookware` | brand not seeded |
| GLASS TREATMENT KIT — REPELS SOAP SCUM (+1 watched) | `Home Goods - Bed / Bath Items` | `Cleaning supplies & tools` | shower/glass treatment is not a seeded form |
| VTECH KIDI STAR DJ MIXER (+MARBLE RUSH watched; ×2 bids across history) | `Home Goods - Musical Instruments` | `Kids' toys & games` | brand not seeded |
| GAOY MILKY WHITE & JELLY NUDE GEL SET | `Home Goods - Bed / Bath Items` | `Cosmetics & nail` | gel-polish sets not reached by the nail seeds |

That is a different remedy from the one §1 originally called for. Adding
buckets was right in August, when whole categories had nowhere to land; the
residue is seed coverage, which is cheaper and carries no taxonomy risk.
Brands worth seeding on this evidence: `chapin`, `tramontina`, `vtech`,
`napoleon`. Across the full history the unmatched bids also repeat on
SALTON ×2, METHOD ×2, GILDAN ×2, OONI ×2, FUNKO ×2.

**One of these is a `categories:` fix, not a seed fix.** Both Chapin bids sit
under `Construction & Farm - Turf Equipment - Sprayers`, a crumb no bucket
claims. A breadcrumb prefix reaches every sprayer in that aisle including the
bare-SKU ones a brand seed never will — which is the axis `categories:` exists
for. The other six are ordinary seed gaps.

**Do not batch these in blind.** Each one widens a shortlist, and Step 4 below
applies: add them, then re-run `--backtest` before trusting the edit, and watch
the `Electronics` share guard.

**No new bucket is warranted by this export.** Two things look like candidates
and are not. Home-gym equipment clusters this week — bumper plates ×2, gym
floor mats, a plate tree rack, a walking pad — but `Home gym & weightlifting`
already exists and across three auctions carries **20 tracked lots and zero
bids**: watched, never bid, which is the shape §5 describes. And Funko Pop is
2 bids in fourteen weeks, under the 5-distinct-products-across-2-auctions bar
in Step 4; it is also *already shortlisted*, reaching `Dolls & plush` through
the `Toys - Action Figures` crumb despite `funko` appearing in no seed list.
Whether a vinyl collectible belongs in `Dolls & plush` is a real question, but
it is not an urgent one and this export does not settle it.


---

# What was changed on 2026-08-30

## Taxonomy: 48 → 62 buckets, 9 → 11 groups

**New group "Personal care" (6):** Hair care products, Hair styling tools,
Skincare & body, Oral & dental care, Shaving & grooming, Cosmetics & nail.
~840 lots a week of supply and no bucket at all before this.

**New group "Food & drink" (5):** Coffee & espresso (moved out of Kitchen &
dining), Pantry & cooking staples, Snacks & confectionery, Beverages & drink
mixes, Supplements & protein.

**Other new buckets (5):** Vacuums & floor care (split out of Cleaning
supplies & tools, ~438/wk), Audio & headphones (split out of Electronics),
Seating & occasional furniture, Car care & detailing, Lawn treatment & pest
control, Kids' outdoor water play, Kids' craft & activity.

**Merged away (2):** `Starbucks coffee` → Coffee & espresso (12 lots a
fortnight did not justify a bucket). `Shatterproof / outdoor dishware` →
Dinnerware (7 lots a fortnight). Both carried as `aliases` so `--backtest`
still scores last week's labels.

**Renamed (1):** `Specialty cooking & baking ingredients` →
`Pantry & cooking staples`, broadened. The old seeds reached only premium
baking and scored zero engagement on 87 supply lots.

## The consumable condition gate

New optional `condition_in:` field on a bucket, honoured by
`tools/prefilter.py`. Applied as `["New"]` to the seven sealed-consumable
buckets. It is deliberately **not** the quality gate the prefilter docstring
forbids — that one asks "is this brand good enough", which is judgement and
belongs to the Agent. This asks "is this sealed thing sealed", which is a fact
the scrape already carries. A lot with no condition recorded is never gated out.

Effect: Skincare & body drops from 920 candidates a week to ~93, without
losing anything that would have survived a look at the photos.

**Caveat: the backtest cannot validate this gate.** None of last week's
accepted labels belong to the gated buckets, so there are no pairs to lose.
Its justification is the measured condition distribution plus the stated rule,
not a recall measurement. Worth re-checking after the first live run.

## Other fixes

- **`sizes.apparel`** set to `{womens: M, mens: L}`. `sizes.shoe` still null.
- **Vehicle interest corrected** — it said "generic car accessories are not
  wanted" while the history showed three car-detailing bids and one Tesla part.
  It now claims `Car care & detailing` and scopes the Tesla-fit rule to parts.
- **`proven_resale`** added to `profile.yaml` as a top-level, user-maintained
  list. One entry: the Shark WandVac. Also documents the inverse rule — do not
  read a same-product run as appetite, because 46 FlexStyle lots produced 2 bids.
- **Keyboards & PC peripherals** — excludes for RGB case fans, fan controllers,
  sim-racing shifters and clutch modules that bare `corsair`/`logitech` seeds
  were pulling in (~18% of that bucket).
- **Electronics** — excludes for the phone-case/screen-protector/cable noise the
  Phones breadcrumb was contributing. 8.7% → 7.0%, back under the share guard
  it had been failing before this change.
- **Garden hose** — timer and irrigation seeds. Recall 94.2% → 95.7%.
- **`DEFAULT_MAX_ROWS`** 12000 → 13000, as headroom only. The week of 08-16
  lands at 11,891 (44.0%), which is under the *old* cap.

## Measurements after the change

| check | before | after |
|---|---|---|
| LOT recall (reached model) | 98.0% (4035/4119) | **97.9%** (4034/4119) |
| PAIR recall (right bucket) | 96.3% | 92.9% |
| candidate rows, week of 08-16 | 10,033 (37.1%) | 11,891 (44.0%) |
| Electronics share | 8.7% (**failing**) | 7.0% (passing) |
| `prefilter.py` exit code | 1 | **0** |
| unit tests | 137 | 137 passing |

LOT recall holds at the ≥97% floor. **The PAIR drop is entirely two intentional
reroutes** and not a regression: 65 lots labelled `Cleaning supplies & tools`
now shortlist as `Vacuums & floor care`, and 83 labelled `Electronics` now
shortlist as `Audio & headphones` (81) or are the deliberate accessory excludes
(2). The backtest structurally cannot credit those, because the destination
buckets did not exist when last week's labels were written. Every other bucket
is unchanged or better.

---

# What the 2026-09-10 refresh found

**One auction. 97 lots, 45 bids.** Per the cadence table below, a single week
answers *coverage* questions — did a gate hide something, is a seed missing —
and cannot move a *rate*. Every lift ratio in §3 moved because the taxonomy
changed on 2026-08-30 and the supply base widened from two weeks to four,
**not** because 45 new bids moved it. Do not read any single row as a trend.

What this export can answer, and does:

## The consumable condition gate is safe — checked on its first live run

The 2026-08-30 note said the gate's justification was a condition distribution
plus a stated rule, that `--backtest` structurally could not validate it, and
that it was "worth re-checking after the first live run". This is that check,
and it is the one measurement here that a single week *can* settle, because it
is a question about coverage rather than about rates.

Replaying all seven gated buckets over the 97 engaged lots of auction 764523:
**the gate hid nothing that was engaged with.** No lot that was bid on or
watched was seed-matched into a gated bucket and then excluded on condition.
The engaged lots in gated buckets were 4 × `Skincare & body` at Brand New -
Sealed (all four bid), 2 × `Snacks & confectionery` at Best Before (both bid),
and 2 × `Beverages & drink mixes` (watched).

The volume claim held too. `Skincare & body` was predicted to fall from ~920
candidates a week to ~93; on the live week it shortlisted **83** of 22,692
lots. Every one of its four engaged lots survived.

And measured the other way round — shortlist recall over the 45 real bids,
gate on versus gate off — the answer is identical, 37/45 either way. The gate
removed roughly 90% of the personal-care shortlist and cost **zero** recall
against what was actually bid on.

## Sampling, not sweeping — still true, with one shift

This week's repeated-SKU runs, engagement against real supply in the same
auction:

| product run | supply | tracked | bid |
|---|---|---|---|
| BISSELL PowerClean hand vacuum | 19 | 9 | 3 |
| SHARK WandVac WV200C | 16 | 6 | 4 |
| CHAPIN 20004 sprayer tank | 31 | 4 | 2 |
| Razer (any) | 68 | 5 | 0 |
| Logitech G515 TKL | 3 | 2 | 2 |

The WandVac pattern from §2 repeats — 16 available, 6 tracked, 4 bid — and a
second handheld vacuum now behaves the same way. **Do not promote the Bissell
to `proven_resale` on this.** That list is for SKUs with a completed resale at
a known price; the Bissell has engagement, which §2 is specifically about not
mistaking for appetite. It is worth watching across the next two exports.

The Razer row is the counter-example that keeps the correction honest: 68 lots
of supply, 5 watched, nothing bid.

## `est_retail_price` is gone — and has now been removed outright

See §4. Zero coverage since the 2026-08-30 week, the deployed bundle included,
which left a displayed figure, a sort order and the `▲ VALUE` badge all inert.

**Removed from the tool on 2026-09-10** rather than recovered. Two reasons:
HiBid no longer publishes it, and it was never a price anyone paid — it is the
auction house's own unverified retail reference, and the resale pass already
estimates what a lot is actually worth. `scraper/condition.py` carries the full
rationale so a future run does not quietly re-add it if the line reappears.

**What this costs this document.** Step 4's question 3 — "is a gate
mis-tuned?" — was answered by comparing condition *and* `est_retail_price`
between engaged and ignored lots within a bucket. The price half is now
permanently unavailable on current weeks; the 8/08 and 8/16 archives are the
last data that can answer it, and §4's keyboards table is the last time it was
measured. Condition still separates cleanly and remains the usable half.

## Numbers that moved, and why

| | before | after | cause |
|---|---|---|---|
| tracked lots | 736 | 833 | +97 from this export |
| bids | 234 | 279 | +45 |
| unmatched share (title-only) | 31% | 19% | 2026-08-30 taxonomy, not new rows |
| unmatched bids (title-only) | 40% | 20% | same |
| shortlist recall vs real bids | 77.4% | **82.2%** | same; scored the production way, §7 |
| supply base | 54,463 (2 wks) | 102,350 (4 wks) | two more weeks kept on disk |

## What is worth doing about it

Nothing in this export justifies a new bucket or a re-ranking. Three things
are worth acting on, in order of cheapness:

1. **Seven shortlist gaps, all in buckets that already exist** (§7). Six seed
   additions plus one `categories:` claim on `Construction & Farm - Turf
   Equipment - Sprayers`. Re-run `--backtest` after, per Step 4.
2. **`sizes.shoe` is still `null`** — called the cheapest single fix on the
   list in §6 six weeks ago, still open, and `Brand boots & shoes` is still
   sitting at a lift of 0.6 on 1,662 supply lots.
3. ~~**Decide what to do about `est_retail_price`**~~ — **done 2026-09-10**:
   removed from the pipeline entirely. See §4.


---

# What the 2026-09-15 refresh found

**One auction (774972, closed 9/13/26). 80 lots, 25 bids.** Same rule as
last time: one week answers coverage questions and cannot move a rate. No
lift ratio in §3 was recomputed for this refresh; the supply base is still
the four weeks listed at the top. This week's slimmed file adds 28,034 lots
to what is on disk, so the next refresh that *does* recompute lifts has
130,384 lots of supply to divide by.

**Taxonomy caveat.** The working tree carried an uncommitted edit to
`buckets.yaml` when this refresh ran — `Glassware & drinkware` split into
glass-only plus a new `Insulated drinkware` bucket (63 buckets). Everything
below is scored against that 63-bucket version, because it is what the next
run will use. The bundle this week's *pass* produced was judged on the
62-bucket taxonomy; the five Stanley / Owala / Contigo lots therefore show
up as `Glassware & drinkware` in the pass column and as `Insulated drinkware`
in the shortlist column. Both are right for their moment.

## The pass now reaches nearly everything that was bid on

This is the first refresh since the shortlist stopped deciding what the
model sees (2026-08-30) *and* the recall-repair chat was added (2026-09-14),
so for the first time there are two separate recall figures to keep apart:

| measured against the 25 real bids | recall |
|---|---|
| shortlist (`tools/prefilter.py`, gate on) | 23/25 = 92.0% |
| shortlist, gate off | 24/25 = 96.0% |
| **the flagging pass as shipped** (`_categorized.json`, after recall repair) | **24/25 = 96.0%** |

Over all 80 tracked lots the pass flagged **79**; the shortlist reached 73
(91.2%). The pass's one miss, on both counts, is the Kimberly-Clark WyPall
X70 wiper box (Brand New - Sealed, bid, outbid) — a shop consumable that no
bucket describes and no seed names. One SKU in one week is not a bucket.

Read the shortlist row against history, not the pass row: 77.4% before the
2026-08-30 taxonomy, 82.2% on the 2026-09-06 week, 92.0% now. That is two
consecutive weeks of the coverage question ("is a seed missing?") answering
"less and less". Shortlist size this week was 12,989 of 28,034 lots
(46.3%), against 44.8% last week, so the recall did not come from widening
the net.

The pass row is the one production cares about and it has no prior figure
to compare to — treat 24/25 as the baseline for the next export.

## The consumable condition gate hid one bid — and it was won

The 2026-09-10 check found the gate hid nothing engaged with. This week it
hid exactly one lot: **7888, Neutrogena Ultra Sheer SPF 60 sunscreen,
graded "Brand New - Open Box"**, seed-matched into `Skincare & body` and
gated out because that bucket allows only Sealed / Adjusted Quantity /
Best Before. It was bid on and it is the batch's "May Have Won".

Two things make this smaller than it looks:

- `condition_in` is enforced **only** in `tools/prefilter.py`. It shapes the
  shortlist and the `--backtest` figure and nothing else; `chunk_flagging.py`
  and `recall_check.py` never read it. The pass saw the lot and flagged it
  (`Skincare & body` / `sunscreen`). Cost to production: zero. Cost to the
  shortlist metric: the one-bid gap between the gate-on and gate-off rows
  above.
- The bucket description's own rule — "Brand New - Open Box … on a bottle
  almost always means opened, which is an automatic pass" — is stated for a
  single bottle. This listing is a **twin-pack**: the outer box is opened,
  the bottles inside are sealed. The pass applied the description with that
  nuance (it flagged 5 Open Box lots in `Skincare & body` this week, against
  67 Sealed and 15 Adjusted Quantity), and the household agreed with it.

Not worth changing on one lot. Worth watching: if a second Open Box multipack
gets engaged with, add "Brand New - Open Box" to `Skincare & body`'s
`condition_in` so the shortlist metric stops under-reporting, and tighten the
description to say "opened *bottle*", not "opened box". The gate's other six
buckets hid nothing: the other engaged consumables were 4 × Scotts EZ Seed
(watched, ungated bucket), 3 × Meguiar's (watched, ungated), and the 3M Aura
N95 20-pack (bid, won, Brand New - Sealed, not a gated bucket either).

## Sampling, not sweeping — the WandVac run again, and one new run

| product run | supply | tracked | bid |
|---|---|---|---|
| SHARK WandVac WV200C | 20 | 10 | 6 |
| STANLEY Quencher / IceFlow | 26 | 3 | 3 |
| SHARK FlexStyle HD430C | 22 | 2 | 1 |
| PHILIPS OneBlade Intimate | 9 | 2 | 2 |
| AMAZON BASICS wet/dry vac | 5 | 3 | 1 |
| BISSELL vacuums (any) | 46 | 3 | 1 |
| SCOTTS EZ Seed | 4 | 4 | 0 |
| Keyboards & keycaps (any) | 121 | 5 | 1 |
| Logitech (any) | 233 | 2 | 0 |
| Razer (any) | 86 | 0 | 0 |
| Barbie (any) | 31 | 1 | 0 |

The WandVac is the `proven_resale` SKU and behaves like it: half the supply
tracked, six bids, one May Have Won. It is the only run on this list where
engagement tracks supply, and §2 already explains why.

The Bissell question from 2026-09-10 answers itself the way that note hoped:
46 lots of supply this week, 3 tracked, 1 bid. It was never appetite — do
not promote it.

**Insulated drinkware is the new run and it is a bids run, not a watch run.**
Five bids (two Stanley Quencher H2.0, a Stanley IceFlow, an Owala FreeSip
kids' bottle, a Contigo Streeterville), zero watch-only, all outbid. Against
26 lots of Stanley supply that is 3 tracked / 3 bid — no browsing, straight
to bidding. History had only a hint of this before: one bid (a Hydro Flask
mug, 9/6) and two watches (a Stanley Quencher 9/6, a Thermos Funtainer 8/9).
With this week that is five distinct products bid on across two auctions —
the "5+ distinct products across 2+ auctions" bar from Step 4, met exactly
and no more, for a category that until the pending edit shared a bucket with
wine glasses and was seeded on "tumbler" alone. The edit was made from the bundle before this export was
transcribed; this export is the independent confirmation.

Keyboards keep doing what §2 said: 121 lots, 5 tracked, one bid — and the
bid was a keycap set, not a keyboard. Logitech at 233 lots and 2 watches is
the widest exposure-to-interest gap on the board.

## Numbers that moved, and why

| | before | after | cause |
|---|---|---|---|
| tracked lots | 833 | 913 | +80 from this export |
| bids | 279 | 304 | +25 |
| unmatched share (title-only) | 19% | 19% | unchanged |
| unmatched bids (title-only) | 20% | 18% | this batch landed at 4%; small against 304 |
| shortlist recall vs real bids, same-week | 82.2% (37/45) | **92.0%** (23/25) | seeds; net did not widen (44.8% → 46.3%) |
| pass recall vs real bids, same-week | — | **96.0%** (24/25) | first measurement; new baseline |
| supply on disk | 102,350 (4 wks) | 130,384 (5 wks) | this week's `_for_agent.json`; lifts not recomputed |

## What is worth doing about it

1. **Nothing to the taxonomy.** The one pending edit (`Insulated drinkware`)
   is confirmed by this export, not contradicted. Commit it.
2. **The 2026-09-10 list is still open.** The Chapin sprayer was watched
   again (10372, Excellent, `Construction & Farm - Turf Equipment -
   Sprayers`) and is still unmatched by any seed or `categories:` claim —
   the pass caught it anyway (`Lawn treatment & pest control` / `spreaders
   & sprayers`), which is the pattern for every one of this week's shortlist
   misses. Same for the Kryptonite U-lock, the Lacoste towels, the Gardena
   auto-reel and the Method cleaner: all unmatched, all flagged. The
   shortlist gap is now purely a *measurement* gap. Close it when convenient;
   it no longer costs a lot.
3. **`sizes.shoe` is still `null`.** Ten weeks now. A UGG kids' clog was
   watched this week, and the profile still cannot say whether it fits
   anyone.

**Superseded the same day.** Items 1 and 3 were written before the
2026-09-15 rescope landed: the user narrowed Bat's List from a 40%-of-auction
scan to a targeted list (63 → 72 buckets; catch-alls retired, most buckets
brand-gated, the best ones split — see SCOPE POLICY in `buckets.yaml`), and
`sizes.shoe` is now deliberately `null` because footwear is brand-gated
instead of size-gated (listings mislabel sizes). The lift table in §3 and the
shortlist figures above are scored against the pre-rescope taxonomy; the
next refresh should recompute them against the 72-bucket one. Measured at
the time of the rescope: seed reach over all 913 tracked lots 81% → 83%,
over the 304 bids 81% → 84%, while the shortlist fell 12,989 → 8,712.

# What the 2026-09-20 refresh found

**One auction (776904, closed 9/20/26). 98 lots, 39 bids** — 62 distinct
products tracked, 26 bid on. Same rule as before: one week answers coverage
questions and cannot move a rate, so no lift in §3 was recomputed.

This is the **first export judged entirely on the 72-bucket rescope**: the
rescope landed 2026-09-15 and this week's flags were written 2026-09-16, so
the pass column, the shortlist column and the taxonomy all agree for once.
The slimmed file joined against includes both mid-week deltas (27,953 lots).

## Recall held on everything but the consumable gate

| measured against the 39 real bids | recall |
|---|---|
| shortlist (`tools/prefilter.py`, gate on) | 35/39 = 89.7% |
| shortlist, gate off | 38/39 = 97.4% |
| **the flagging pass as shipped** (`_categorized.json`) | **35/39 = 89.7%** |

Over all 98 tracked lots the pass gave a bucket to 93, plus one personal-only
pick (a Garant garden cart, caught by the `Yard & lawn` pseudo-seed
`garden cart`). The shortlist reached 90. Shortlist size was 8,124 of
27,953 lots (29.1%), against 46.3% before the rescope — the rescope narrowed
the net by a third and bid recall with the gate off went *up*.

The drop from last week's 96.0% is **entirely the consumable condition
gate**, and this time the pass agreed with it. Last week the gate hid one
bid and the pass overrode it (the Neutrogena twin-pack). This week the gate
hid three bids and the pass refused all three:

| lot | product | grade | outcome |
|---|---|---|---|
| 21197 | Après Gel-X stiletto tips, 280ct | Excellent | **May Have Won** |
| 8731 | Après Extend Gel (the Gel-X tip adhesive) | Excellent | Outbid |
| 13785 | Frito-Lay variety pack, 42 × 28 g | Brand New - Open Box | Outbid |

The fourth miss is an Amazon Basics clear umbrella (Excellent, outbid),
which no bucket or seed describes. One SKU; not a bucket.

## The gate is refusing things that are wanted

**Après Gel-X is a repeat purchase, not a new interest.** The same stiletto
tips SKU was bid on and won on 7/27 (lot 23105). Two bids this week, one won
— on "Excellent", HiBid's most common grade (11,148 in the label count),
which on a box of 280 plastic tips means the box was opened, not that
anything was used. `Cosmetics & nail`'s `condition_in` and its "CONSUMABLE:
prefer New. An opened polish … is a pass" line are written for a bottle of
polish, and the pass applied them to tips.

The seed side had a bug on top of that: the bucket's `apres ` seed has never
matched a single lot. HiBid drops the è, so the brand renders "APR S" in every
title across the six archived weeks. Fixed in this refresh (`apr s `, checked
to match only the seven Après lots on disk). It changed no number above —
`gel x` was already matching both lots before the gate removed them.

**The Frito-Lay bid is the second opened-multipack engagement.** The 9/15
section set this trigger: "if a second Open Box multipack gets engaged with".
Here it is, in `Snacks & confectionery` rather than `Skincare & body`: 27 lots
of the 42-pack, 26 sealed or best-before (all flagged, 10 watched) and one
Open Box (not flagged) — and the one bid went on the Open Box lot. An opened
outer carton of 42 individually sealed bags is the twin-pack case again.

Both are the same rule mis-stated: the consumable gate should refuse an
opened *unit*, and it is refusing an opened *box of sealed units*. Changing
it widens Bat's List, which needs the user's say-so (SCOPE POLICY) — see
"What is worth doing" below.

## Sampling, not sweeping — and the first sale prices

| product run | supply | tracked | bid | May Have Won | sold for (median, range) |
|---|---|---|---|---|---|
| GOUTIME hammock stands (both SKUs) | 49 | 11 | 10 | 2 | $10.50 ($6–17), 24/24 sold |
| FRITO-LAY 42 × 28 g variety pack | 27 | 11 | 1 | 0 | $13 sealed, $16 open box |
| BISSELL PowerClean Pet 2389D | 9 | 5 | 3 | 1 | $10 Excellent ($7–13) |
| SHARK WandVac WV200C | 26 | 2 | 1 | 1 | $17 Excellent ($16–24) |
| STANLEY (any) | 44 | 3 | 3 | 0 | $7–16, all graded Good |
| DCYOURHOME pellet bin | 3 | 3 | 3 | 0 | $14–15 |
| EUCERIN (any) | 32 | 2 | 2 | 1 | $4–6 |
| ULTIMATE EARS (any) | 8 | 7 | 0 | 0 | Boom 4 $65, Wonderboom 4 $42.50 |
| DYSON Car+Boat | 58 | 2 | 0 | 0 | $100 ($82.50–140), 43 sold |
| Keyboards & keycaps (any) | 130 | 7 | 2 | 0 | Razer Huntsman V3 Pro $44–88 |
| Razer (any) | 59 | 4 | 0 | 0 | |
| Logitech (any) | 243 | 0 | 0 | 0 | |

**The hammock stand is the week's one real same-product bid run.** Ten bids
across identical lots, two May Have Won, against a product that sold 24 times
at a $10.50 median. Hammocks have been engaged with in five auctions since 6/7
(Suncreat, Amazon Basics, double-hammock-with-stand), and `Outdoor furniture &
hammocks` caught every one of them. Nothing to change in the taxonomy. Whether
it is wanting one at a price or wanting several is not something the capture
can tell — it looks like the WandVac's 16 bids of 2026-07-19, which turned
out to be resale.

**Ultimate Ears is the new watch-only run:** 7 of 8 lots tracked, none bid.
Pellet storage bins are the opposite — 3 of 3 supply, 3 bids, all outbid at
$14–15.

**Hammer prices are the new axis.** This is the first refresh with the week's
`data/hammer/` file on disk, and it answers what the gate question in §4 lost
when `est_retail_price` went: what an outbid lot actually took. Stanley
graded Good cleared $7–16; the UGG throw $27; the Furby $30. Joined on
`title` + `condition` the same way the build does — product-level, not per
lot, because the hammer file carries no lot numbers.

Logitech: 243 lots, zero tracked — still the widest exposure-to-interest gap
on the board, and wider than last week's 233 / 2.

## Numbers that moved, and why

| | before | after | cause |
|---|---|---|---|
| tracked lots | 913 | 1,011 | +98 from this export |
| bids | 304 | 343 | +39 |
| unmatched share (title-only, 72 buckets) | 17.2% | 15.8% | this batch landed at 3.1%; the 913-row figure was 19% on the 63-bucket taxonomy |
| unmatched bids (title-only, 72 buckets) | 16.4% | 14.9% | this batch 1/39 (the umbrella) |
| shortlist recall vs real bids, same-week | 92.0% (23/25) | 89.7% (35/39) | consumable gate, 3 lots; gate off 97.4% |
| pass recall vs real bids, same-week | 96.0% (24/25) | 89.7% (35/39) | the pass refused the same 3 lots |
| shortlist share of auction | 46.3% | 29.1% | the 2026-09-15 rescope |
| supply on disk | 130,384 (5 wks) | 158,337 (6 wks) | this week's archive; lifts not recomputed |

## What is worth doing about it

1. **Done: the Après seed.** `apres ` → `apr s ` in `Cosmetics & nail`.
2. **Done 2026-09-23, with the user's say-so: the OUTER-BOX RULE.**
   `Cosmetics & nail` and `Snacks & confectionery` now admit "Brand New -
   Open Box" and "Excellent" in `condition_in`; `Skincare & body` admits
   Open Box only (see below). Their
   descriptions (plus `profile.yaml` `not_wanted`) say to flag those grades
   and leave the seal check to the photos. The user's reasoning: graders
   use those two grades inconsistently and an opened outer box is almost
   never a problem. "Good" and below stay out, and the other four gated
   buckets are unchanged — widening either would flood the list. Shortlist
   effect on 776904: Cosmetics 9 → 34, Snacks 62 → 85, Skincare 155 → 289.
   Skincare was first given "Excellent" too (155 → 532) and the user cut it
   back to Open Box the same day as too many lots. All three of this week's
   gate misses still shortlist — none of them was Skincare. The Neutrogena
   twin-pack of 9/13 (Open Box) is covered.
3. **The §3 lift table is still owed a recompute on the 72-bucket taxonomy**
   (flagged by the 9/15 rescope note). Supply is now 158,337 lots over six
   weeks and the history is 343 bids — enough for the quarterly question.
   Not attempted on a one-week refresh.

---

# How to refresh this

Everything above is a **measurement**, not an opinion, and every number is
reproducible from `history.tsv` plus a week's slimmed lots. Follow this method
so a later refresh is comparable to this one. Deviating silently is worse than
not refreshing at all — two numbers computed different ways look like a trend.

## Cadence: monthly at the very least, quarterly is better

A typical week yields only **~20-100 tracked lots, of which ~13-45 are bids**.
The conclusions above rest on **279 bids over fourteen weeks**. One week cannot
move a lift ratio; it can only produce noise that looks like a signal.

| span | ~bids | what it can honestly answer |
|---|---|---|
| 1 week | 13-45 | coverage questions only — "did a gate hide something?", "is a seed missing?" |
| 1 month | 60-100 | "is there a new interest with no bucket?" |
| 1 quarter | ~250 | "should a bucket be re-ranked or retired?" |

The 1-week row used to read "nothing — do not act on it", which was too
strong. One week cannot move a *rate* — a lift ratio, a bid share — because
the sample is a rounding error against 279 bids. It answers a *coverage*
question completely, because coverage is a yes/no per lot: the 2026-09-10
export settled whether the condition gate hides anything engaged with (it does
not) and surfaced seven shortlist gaps, off 45 bids. Ask which kind of question
you have before deciding a week is too small for it.

## Step 1 — capture

Screenshot the **Bids** and **Watch List** tabs, range filter set to cover only
the period *since the last export* — not the full three months again.

**Save the files to `data/Watch/Bids Temp/` — do not attach them to the chat
instead.** They have to be croppable, and cropping is what makes the
transcription accurate rather than approximate:

- The captures are tall (1110 x 3656 in the 2026-08-30 export). Read whole,
  they are downscaled to ~0.55x and the lot titles sit right at the edge of
  legibility — which is how a brand gets misread and silently becomes a wrong
  bucket.
- Cropping each capture into vertical thirds with ~45px of overlap renders the
  text at full resolution. The overlap matters: without it a tile row lands on
  a cut boundary and is lost from both halves.
- Crop bounds have to be **detected per capture, not assumed**. The page
  shifted left partway through the 2026-08-30 set, and a fixed right edge
  clipped the fourth column of tiles. Detecting the coloured tile borders
  (red = Outbid, green = May Have Won, blue = watch-only) finds the real
  extents; take the full page width on the right, because a final row with
  fewer than four tiles otherwise reports a too-narrow bound. This took two
  re-crop cycles to get right — all of which needs the files on disk.

Roughly 29 captures covered the first three months; the 2026-09-10 export of a
single auction took 3 (969 x 3428 and similar, four tiles per row, ~9 rows per
capture), and so did 2026-09-15 (980 x 3437, 1009 x 3351, 980 x 1130). They
are disposable once `history.tsv` is updated (~47 MB), and `data/Watch/` is
gitignored apart from this file.

**Chat attachments can be fine — check for a path.** The 2026-09-20 captures
were attached in the chat, but the harness stored each one on disk (the image
block names its source path). Copying them into `Bids Temp/` and cropping the
two tall ones (950 x 3663, 960 x 3671) into overlapping quarters worked
exactly as a saved capture would; all 98 rows passed the prefix check first
time. The rule is about being croppable, not about the channel.

The 2026-09-15 captures were pasted into the chat instead of saved, so no
cropping was possible. It worked — 79 of 80 rows joined on the first pass —
but only because the same-week join below existed to prove it, and because
three captures at ~1000px wide are legible where the 2026-08-30 set's 1110 x
3656 were not. Do not read that as the cropping discipline being optional:
a single misread digit in a lot number joins to a *different product* and
the prefix check is the only thing that catches it. Save to disk when the
capture is tall.

**A tile can clip the lot number.** HiBid keys a small number of lots with a
letter suffix (`14418a`), and the tile renders "Lot 14418". The join then
returns the wrong product (here a sequin dress for an Amazon Basics wet/dry
vac) and the prefix check fails on that one row. The fix is to search the
slimmed file by title, take the suffixed key, and log *that* — it is the
`lot_number` every downstream file uses.

**Check the captures butt up against each other before transcribing.** A
capture that ends mid-row leaves a partial row at the top of the next one; its
border colours are legible even when its text is not, and matching that colour
sequence against the previous capture's last row proves the two are
contiguous. Two of the three 2026-09-10 captures chained that way. The third
pair both ended and began on a clean row boundary, which proves nothing — a
dropped row between them would look identical. Prefer a few pixels of overlap
between captures for the same reason the crops overlap.

Two more things that cost real accuracy the first time:

- **Do not change browser zoom after setting the capture region.** That is what
  truncated every title in the 2026-08-30 export and forced brand-only
  inference on a few hundred rows.
- **Export the same week the auction closes, if you can.** While
  `auction_<ID>_for_agent.json` is still in `data/categorized/`, every row
  joins on `lot_number` and yields the full untruncated title and `condition`
  for free — which makes the truncation in the captures survivable, and is
  worth more than the cropping discipline above. It no longer yields
  `est_retail_price`; that field has been 0% since 2026-08-30 (§4). One week
  later the file is archived and the join is *unsafe*, not merely unavailable
  — lot numbers are recycled across weeks (93.9% overlap), so a stale join
  silently returns a different product. Verified: of 11 lots probed against
  the wrong week, 10 mismatched.

  **Verify the join, do not assume it.** Check the transcribed truncated title
  is a prefix of the joined full title, for every row, and only then overwrite
  the titles. On 2026-09-10 all 97 rows passed, which is simultaneously the
  proof that the lot numbers were read correctly off the screenshots and that
  the right week was joined. A batch where some rows fail that check is a
  wrong-week join, not a transcription slip — stop and re-date it.

## Step 2 — transcribe and append

Transcribe to the same five columns and **append**; never rewrite history:

```
date	lot	title	signal	outcome
8/24/26	28267	SHARK WANDVAC HANDHELD	bid	Outbid
```

- `signal` is `bid` or `watch`. A lot that was both is `bid` — bidding is the
  strictly stronger signal.
- `outcome` is `Outbid` / `MayHaveWon`, empty for watch-only.
- Deduplicate on `(date, lot)`. The Watch List is a superset of Bids, and the
  capture regions overlap by design, so the same lot appears several times.

## Step 3 — normalise against supply, always

**This is the step that is easy to skip and invalidates everything if you do.**
These auctions list the same product across dozens of lots, so raw engagement
counts measure *what the auction over-lists*, not what is wanted. Measured:
the Shark FlexStyle had **46 identical lots** in one week and got 2 bids;
keyboards had 76 lots and 7 engagements, with 17 ignored despite being ≥$150
and New/Like New.

For each bucket compute:

```
lift = (bucket's share of tracked lots) / (bucket's share of supply)
```

Supply = matching the bucket's seeds over one or two weeks' `_for_agent.json`.
**lift 1.0 = engaged with exactly as often as it appears.** Flag any bucket
under ~50 supply lots per two weeks as noisy — Hatchimals scored a lift of 222
on a supply of one.

**A bucket with `condition_in:` must be divided by its GATED supply.** The
shortlist never offers that bucket's opened stock, so counting it in the
denominator divides by lots the pass was never shown. Measured 2026-09-10,
this understated the seven gated buckets by 4-25× — `Skincare & body` reads
0.3 ungated and 6.2 gated, which is the difference between "retire it" and
"one of the stronger buckets in the taxonomy". Apply the same `condition_in`
allowlist to the supply scan; `tools/prefilter.py`'s `Matcher.match` already
does this when passed a `condition`.

**Also read the bid share of tracked.** Lift measures exposure-adjusted
attention, and a bucket can be low-exposure and near-perfect conversion at the
same time: `Hair care products` is 2/2 bids and `Home gym & weightlifting` is
0/20, and lift alone puts them a rung apart in the wrong direction.

Normalising re-ranked the original analysis substantially: Electronics fell to
**0.5** and Bedding & pillows to **0.3**, both of which looked like top
interests on raw counts alone.

## Step 4 — ask only what history can answer

Three questions are worth the effort. The rest are noise at this sample size.

1. **Is there a new interest with no bucket?** Cluster the bids matching no
   bucket. A cluster of 5+ distinct products across 2+ auctions is a real
   candidate; one repeated SKU is not.
2. **Has a bucket stopped earning its place?** Low lift *plus* low supply. Low
   lift with healthy supply is not grounds to retire anything — see §5, some
   buckets exist to be scanned, not bid on. `Coffee & espresso` carries ~55
   lots a week and zero bids, and stays.
3. **Is a gate mis-tuned?** Compare the condition of engaged vs ignored lots
   within one bucket. This used to compare `est_retail_price` too; that field
   was removed on 2026-09-10 and only the 8/08 and 8/16 archives still carry
   it, so price is no longer an axis a refresh can use.

Then update `buckets.yaml` / `profile.yaml`, and **re-measure before trusting
the edit**:

```bash
cp data/archive/<LAST_RUN_DATE>/auction_combined_for_agent.json \
   data/categorized/auction_bt_for_agent.json
python3 tools/prefilter.py bt --backtest \
   data/archive/<LAST_RUN_DATE>/auction_combined_categorized.json
rm data/categorized/auction_bt_for_agent.json
```

## The trap that produced a wrong answer the first time

The backtest above scores seeds against **labels the flagging pass itself
produced**. Where the seeds and the pass miss the same thing, it reports
agreement and measures nothing. It said 97.9% recall while the real figure
against actual bids was **77.4%**.

So: use `--backtest` to check a seed edit did not *regress* anything, and use
`history.tsv` to find what neither the seeds nor the pass has ever seen. They
answer different questions and the first one cannot substitute for the second.

**Refreshed 2026-09-10**: replaying the current shortlist over the 45 bids of
auction 764523 — full haystack, condition gate on, same rule production uses —
gives **82.2% recall against real bids** (37/45), against the 77.4% measured
before the 2026-08-30 taxonomy change. Shortlist size on that week was 10,158
of 22,692 lots (44.8%). Turning the condition gate off changes the recall
figure by nothing at all: 37/45 either way.

That last fact is the cheapest version of this whole check, and worth
repeating every refresh. Run the shortlist over the lots this household
actually bid on, with the gate on and with it off. If a gate ever starts
costing recall, this is where it shows up first, and it costs one join.
