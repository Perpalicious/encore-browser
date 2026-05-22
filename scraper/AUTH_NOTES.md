# HiBid GraphQL — Auth probe findings

**Probed**: 2026-05-22, from the build environment (WSL2 / datacenter IP).

## What was tested

1. **Anonymous POST** to `https://encoreauctions.hibid.com/graphql` with a valid `LotSearchLotOnly` payload (auction 741675, pageLength 3) → **HTTP 403 Cloudflare**.
2. **GET catalog page first** (`https://encoreauctions.hibid.com/catalog/741675`) to seed cookies, then retry POST with browser User-Agent, `Origin` and `Referer` headers → still **HTTP 403 Cloudflare**.

Cloudflare's response is the static "Sorry, you have been blocked" interstitial — i.e. our IP/network signature is being challenged with JavaScript (which `curl` cannot solve). Both unauthenticated paths in the brief therefore fail from this environment.

## Conclusion → use `HIBID_TOKEN`

The scraper is built for all three paths the brief lists, in this priority order:

1. **Anonymous** — no Authorization header, no cookies. Tried first.
2. **Cookie-seeded** — GET catalog page first, then POST with the resulting cookies. Tried second.
3. **JWT bearer** — read `HIBID_TOKEN` from `.env` (via `python-dotenv`), pass as `Authorization: Bearer ...`.

For weekly operation from your machine, path 1 or 2 may work (your home IP is not flagged by Cloudflare the way our build environment was). If both fail when you run it, fall back to path 3:

### How to get a fresh `HIBID_TOKEN`

1. Open Chrome / Firefox.
2. Log in at <https://hibid.com> (creates the bearer-token session).
3. Open DevTools → Network tab.
4. Navigate to `https://encoreauctions.hibid.com/catalog/<AUCTION_ID>`.
5. Find any POST to `/graphql`. In Request Headers, copy the value of `Authorization:` after the literal word `Bearer ` (one space). It is a long string starting with `eyJ...`.
6. Put it in `.env` at the project root:
   ```
   HIBID_TOKEN=eyJhbGc...
   ```
7. Run `python -m scraper --auction-id <ID> --output data/raw/auction_<ID>.json`.

Tokens expire after a few hours. If you get an auth error, repeat steps 1–6.

## Redaction guarantee

The scraper never logs, prints, or persists the token value. All error messages and log lines that touch the token replace it with the literal `<HIBID_TOKEN redacted>`. The token is read from `.env` only — `.env` is gitignored.
