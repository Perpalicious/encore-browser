# What the bid/watch history actually says

Source: 29 screenshots of the Encore "Bids" (234 lots) and "Watch List"
(731 lots) tabs, auctions **2026-05-31 → 2026-08-24**. Transcribed and
deduplicated to `history_2026-05-31_to_2026-08-24.tsv` — 736 unique lots
(234 bid, 502 watch-only). Outcomes: 167 Outbid, 67 May Have Won.

Supply baseline: the two weeks still on disk (2026-08-08 and 2026-08-16),
**54,463 lots**.

> **Read raw counts as exposure, not preference.** These auctions run the
> same product across dozens of lots, so a frequently-listed item collects
> engagement simply by appearing. Every ranking below is normalised against
> supply. See "Sampling, not sweeping".

## 1. The taxonomy gap

Scoring all 736 tracked lots against current `buckets.yaml` seeds *and*
`profile.yaml` pseudo-bucket seeds:

| | lots | share |
|---|---|---|
| matched at least one bucket / seed | 507 | 69% |
| **matched nothing at all** | **229** | **31%** |
| …of the 234 real *bids* | **94 unmatched** | **40%** |

Two of every five things actually bid on have nowhere to land. That is not
fixable in `PROMPTS.md` — a category with no bucket and no seed cannot be
surfaced by any prompt.

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
it appears.** Buckets under ~50 supply lots are noisy — flagged †.

**Genuinely over-indexed**

| bucket | supply | tracked | bid | lift |
|---|---|---|---|---|
| Hatchimals † | 1 | 3 | 1 | 222 |
| Surprise toys † | 11 | 27 | 15 | 182 |
| Barbies † | 49 | 31 | 12 | 47 |
| 3D printing supplies † | 32 | 13 | 4 | 30 |
| Tie-downs † | 23 | 7 | 1 | 23 |
| Nightstands † | 35 | 8 | 4 | 17 |
| Garage & tool organization † | 44 | 9 | 2 | 15 |
| Brand chef knives | 99 | 15 | 5 | 11 |
| Outdoor furniture & hammocks | 121 | 16 | 8 | 9.8 |
| Keyboards & PC peripherals | 490 | 44 | 5 | **6.6** |
| Garden hose | 232 | 15 | 3 | 4.8 |
| BBQ accessories | 193 | 12 | 4 | 4.6 |
| King bed frames | 154 | 8 | 7 | 3.8 |

**At or below baseline — raw counts flattered these**

| bucket | supply | tracked | lift | note |
|---|---|---|---|---|
| Cleaning supplies & tools | 1,315 | 43 | 2.4 | looked like the #2 interest on raw count |
| Kitchen appliances | 1,859 | 22 | 0.9 | at baseline |
| Glassware & drinkware | 465 | 5 | 0.8 | |
| Brand boots & shoes | 808 | 7 | 0.6 | **suppressed — `sizes.shoe` is `null`** |
| Board games | 457 | 4 | 0.6 | |
| Electronics | 3,015 | 22 | **0.5** | biggest supply of any bucket |
| Bedding & pillows | 1,156 | 5 | **0.3** | |

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
`Shatterproof / outdoor dishware` are thin on *both* axes.

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
