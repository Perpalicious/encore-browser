# Encore Lot Browser Product Recommendations

## Context

Encore Lot Browser is most useful as a pre-auction capture tool, not a bidding tool.
The goal is to move faster than HiBid, scan a large auction before it goes live,
find useful or high-impact lots, and then save or act on those lots in HiBid
itself closer to closing time.

The tool should stay free to operate, using existing subscriptions and local/static
processing where possible. That constraint is important: improvements should favor
better organization, local scoring, saved metadata, and clearer workflows over
paid data sources or live bidding integrations.

## Product Direction

The current app is already a strong fast browser. The next useful shift is to make
it more of a pre-auction capture queue.

The app should help answer:

- What should I notice before the auction starts?
- What is probably useful to my real life?
- What might I forget to search for manually?
- What is worth opening on HiBid and saving there?
- What have I already reviewed, skipped, or marked as interesting?

Because the user's net is intentionally wide, the app should not rely only on a
long exact list of specific items. It should support broad life areas, recurring
targets, and discovery.

## Core Insight

The main problem is not just finding exact items like "tarps" or "kitchen knives."
The user's useful-item universe is much broader:

- Toddler and family needs
- DIY repair and maintenance
- Lawn care
- Pool and cabana upkeep
- Outdoor living
- Car detailing
- Cooking and baking
- Storage and organization
- Cleaning supplies
- Tools, consumables, and household restock
- High-value resale or high-retail finds

So the app should not ask the user to perfectly remember every item they might
want. It should help surface things future-them would be glad they noticed.

## Recommended Concept: Life Areas

Add a personal layer above exact item buckets, organized around use cases or life
areas.

Possible life areas:

- Toddler / family
- Home repair
- Lawn care
- Pool / cabana
- Outdoor living
- Car detailing
- Cooking / baking
- Cleaning
- Storage / organization
- Tools / consumables
- Home comfort
- Resale / high-value finds

These should be separate from HiBid's category tree. HiBid categories are useful
for browsing, but they do not always match how the user thinks or how useful an
item is.

Example:

`Cooking / baking` could include knives, cookware, bakeware, mixers, food scales,
thermometers, storage containers, cutting boards, silicone mats, and vacuum
sealers.

`Pool / cabana` could include hoses, pumps, outdoor bins, patio lighting, towels,
extension cords, tarps, furniture covers, shade items, bug control, and outdoor
fans.

`Home repair` could include tools, adhesives, batteries, chargers, extension
cords, fasteners, shop organization, safety gear, and hardware.

## Recommended Concept: Targets Within Life Areas

Specific item filters are still useful, but they should sit inside broader life
areas instead of becoming one giant checklist.

Examples:

- Kitchen knives
- Tie-downs / ratchet straps
- Tarps
- Power tool batteries
- Extension cords
- Storage totes
- Garden hoses
- Detailing towels
- Pool supplies
- Lego
- Bed linens
- Bath towels
- Smart locks
- Mechanical keyboards
- King bed frames

Each target could eventually support:

- Aliases and synonyms
- Common misspellings
- Brand hints
- Exclusions
- Priority
- Relevant life areas
- Minimum condition
- Whether it is mainly personal-use, resale, or both

Example target:

```yaml
name: Tie-downs / ratchet straps
life_areas:
  - Home repair
  - Outdoor living
aliases:
  - tie downs
  - tie-downs
  - ratchet straps
  - cargo straps
  - bungee cords
priority: high
```

## Recommended Concept: Intent Filters

Add broad, forgiving filters that match how the user thinks while scanning.

Possible intent filters:

- Useful around the house
- Tools and repair
- Outdoor season
- Toddler / family
- Kitchen upgrade
- Baking
- Pool / cabana
- Car detailing
- Storage / organization
- Cleaning / restock
- Consumables
- High resale
- High retail value
- New / like-new only
- Quick wins

These filters should be allowed to overlap. A storage tote could be useful for
toddler, garage, pool, and general organization.

## Recommended Concept: Wide Net Review Mode

Build a mode specifically for fast pre-auction scanning.

Instead of starting from the full grid, show a prioritized queue of likely useful
lots.

The queue could rank lots using local signals:

- Matches one or more life areas
- Matches a recurring target
- New or like-new condition
- High estimated retail
- Good resale range
- Medium/high resale confidence
- Good/fair resale outlook
- Known useful brand
- Has an image
- Not already reviewed or skipped
- Newly added since the last scrape

The workflow could be:

1. Show next likely useful lot.
2. User opens it on HiBid, watches it locally, skips it, or marks maybe.
3. App advances to the next lot.

This would reduce repeated scrolling and help the user make faster decisions.

## Recommended Concept: Reviewed / Skipped / Maybe

Watched currently means "I care about this." That is useful, but pre-auction
triage also needs negative and uncertain states.

Add local states:

- Watched: worth tracking
- Maybe: might be worth coming back to
- Skipped: reviewed and not useful
- Opened on HiBid: already handed off

This would make wide-net browsing less repetitive. The user could filter out
skipped lots and focus only on unreviewed inventory.

## Recommended Concept: New Since Last Scrape

Auctions grow throughout the week. A high-impact filter would be:

- New since last scrape
- Previously seen
- Newly categorized
- Newly valued for resale

This would make incremental review much faster. The user would not need to
rescan thousands of lots after each refresh.

## Recommended Concept: High-Impact View

Add a "High Impact" or "Best Bets" view that combines multiple signals.

Possible scoring inputs:

- Life-area match
- Target priority
- Bat's List match
- Resale estimate
- Resale confidence
- Resale outlook
- Estimated retail price
- Condition
- Brand terms
- Image availability

This does not require paid services. A simple local scoring formula could be
good enough to bring likely useful items to the top.

Example ranking idea:

```text
target priority
+ life-area match
+ condition bonus
+ resale confidence bonus
+ high retail estimate bonus
+ known brand bonus
- poor outlook penalty
- missing image penalty
```

## Searchability Improvements

The current fuzzy search is strong, but the product could go further by turning
common searches into reusable structures.

Recommended improvements:

- Saved searches for frequent terms
- Search presets generated from targets
- Synonym expansion for target searches
- Brand-aware matching
- Misspelling aliases for common auction text errors
- Search within current life area or target
- Search only unreviewed lots
- Search only new lots

Example:

Clicking "Kitchen knives" could search across:

```text
knife, knives, cutlery, chef knife, santoku, paring, utility knife,
Wusthof, Wüsthof, Henckels, Shun, Global, Victorinox, Miyabi
```

## Bat's List Improvements

Bat's List is already useful, but it could become more actionable.

Recommended improvements:

- Add an "All Bat's List" option so the Bat tab can show every flagged lot.
- Keep the existing group -> bucket flow for focused browsing.
- Let Bat buckets be used as filters across all tabs.
- Add priority to Bat buckets.
- Allow buckets to map to one or more life areas.
- Add "new Bat's List matches since last scrape."
- Add "unreviewed Bat's List matches."

## HiBid Handoff Improvements

Because saving and bidding happen in HiBid, the viewer should make that handoff
faster.

Useful features:

- Clear "Open on HiBid" action on cards and panels
- Copy visible lot links
- Copy watched lot links
- Mark as opened on HiBid
- Filter watched lots not yet opened on HiBid
- Open next unreviewed target
- Show lot number prominently for manual lookup
- Build a simple "HiBid save checklist" from watched/maybe lots

The app should not try to become the bidding system. It should make the pre-bid
capture step faster and more reliable.

## Existing Data That Should Be Surfaced More

The scraper already captures fields that are useful for faster decisions.

Worth surfacing more prominently:

- Current bid
- Close time
- Lot status
- Estimated retail price
- Additional images
- Condition
- Resale range
- Resale confidence
- Resale outlook

For pre-auction browsing, current bid may be less important early, but close time,
condition, retail estimate, image availability, and resale estimate are still
useful triage signals.

## Quick Wins

These are likely low-effort/high-impact:

- Add auction name, auction ID, and build/scrape timestamp to the viewer.
- Add an "All Bat's List" option.
- Apply category/day filters consistently to watched lots.
- Add "reviewed," "skipped," and "maybe" local states.
- Add "hide skipped" and "show unreviewed only."
- Add a simple sort dropdown.
- Show current bid and close time in the expand panel.
- Show additional images in the expand panel.
- Add saved search chips for frequent targets.
- Add "new since last scrape" if prior scrape/bundle metadata is available.
- Add a "copy watched lot links" action.

## Medium-Sized Opportunities

- Add a "My Targets" tab with life areas and target buckets.
- Add target aliases/synonyms in YAML.
- Generate target matches during the build step.
- Add priority to targets and buckets.
- Add a high-impact local score.
- Add a triage queue view.
- Add seasonal presets such as summer/outdoor, toddler, kitchen, repair, pool.
- Add user notes on watched/maybe lots.

## Larger Opportunities

### Personalized Auction Assistant View

Create a view that summarizes:

- Best 50 likely useful lots
- High-priority targets not reviewed
- Good resale opportunities
- New useful lots since last scrape
- Watched lots grouped by close order
- Maybe lots worth a second pass

### Cross-Auction Memory

Track patterns across auctions:

- Items often watched
- Items often skipped
- Brands that repeatedly matter
- Buckets that tend to produce useful finds
- Seasonal needs
- Previously seen lots

### Outcome Tracking

If the user chooses to record outcomes manually, the app could learn which kinds
of lots were actually worth attention.

Possible states:

- Saved on HiBid
- Bid on
- Won
- Lost
- Regretted missing
- Not worth it

This could improve future ranking without requiring external paid services.

## Suggested Product Priority

1. Reviewed / skipped / maybe states.
2. New since last scrape.
3. My Targets / Life Areas taxonomy.
4. Target aliases and synonym matching.
5. High-impact sort or score.
6. HiBid handoff helpers.
7. Triage queue.
8. Cross-auction memory.

This order improves the current workflow first, then adds more personalization.

## Summary

For this user's workflow, the app should evolve from "fast auction browser" into
"wide-net pre-auction capture system."

Specific item filters are useful, but the bigger opportunity is a flexible
personal usefulness layer:

- Life areas for broad discovery
- Targets for recurring exact wants
- Signals for ranking and prioritization
- Review states for workflow progress
- HiBid handoff helpers for the real save/bid step

The key product question should be:

> Would future-me be glad I noticed this before the auction went live?

The app should help surface those lots quickly, even when the user did not
remember to search for them explicitly.
