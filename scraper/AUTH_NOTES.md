# HiBid GraphQL — auth situation & current strategy

## Summary

HiBid is fronted by **Cloudflare**, which performs **TLS fingerprinting** in
addition to IP / behaviour heuristics. Any HTTP client whose TLS handshake
doesn't match a real browser is rejected with **HTTP 403** at the edge — and
that rejection happens **before** the request reaches HiBid, so it is
independent of whether you send credentials.

This is why our original `httpx`-based implementation failed on all three
auth tiers from both the build environment **and** a residential home IP with
a valid `HIBID_TOKEN`. The block is on the client signature, not the
identity. Sending a Bearer token doesn't help if the TLS handshake doesn't
look like Chrome.

## Current solution — `curl_cffi`

The scraper uses [`curl_cffi`](https://github.com/lexiforest/curl_cffi),
which wraps libcurl with browser-impersonation patches that produce TLS and
HTTP/2 fingerprints indistinguishable from real Chrome / Firefox / Safari.
Concretely we use `impersonate="chrome124"`. Cloudflare lets these through
without challenge for the read-only catalog endpoints we use.

In practice **anonymous** requests now succeed from a normal residential
or datacenter IP — no token required. The cookie-seeded and Bearer-token
paths are kept as fallbacks in case HiBid tightens rules later.

## Three-tier auth order (unchanged)

1. **Anonymous** — no `Authorization` header, no cookies.
2. **Cookie-seeded** — GET the public catalog page first to acquire any
   session cookies Cloudflare sets, then POST `/graphql` with those cookies.
3. **JWT bearer** — read `HIBID_TOKEN` from `.env` (loaded via
   `python-dotenv`) and send `Authorization: Bearer <token>`.

The scraper probes each strategy in order on page 1 and uses the first that
returns a valid GraphQL JSON body (HTTP 200 + `Content-Type: application/json`
+ `data` or `errors` key present).

### How to obtain a fresh `HIBID_TOKEN` (only if all paths fail)

1. Log in at <https://hibid.com> in a real browser.
2. Open DevTools → Network tab.
3. Navigate to `https://encoreauctions.hibid.com/catalog/<AUCTION_ID>`.
4. Find any POST to `/graphql` in the network log.
5. In Request Headers, copy the value after `Authorization: Bearer ` (long
   string starting with `eyJ...`).
6. Put it in `.env` at the project root:
   ```
   HIBID_TOKEN=eyJhbGc...
   ```
7. Run `python -m scraper --auction-id <ID> --output data/raw/auction_<ID>.json`.

Tokens expire after a few hours.

## GraphQL schema notes

GraphQL **introspection is disabled** on HiBid's endpoint (returns
`INTROSPECTION_NOT_ALLOWED`). Our query string was reverse-engineered from
HiBid's own public PWA JavaScript bundle at
`https://cdn.hibid.com/cdn/pwa/<version>/main.<hash>.js` — search the bundle
for `lotSearch` to confirm the signature if it changes.

The current shape uses a single `LotSearchInput` argument plus separate
`pageLength` / `pageNumber` args, and results are nested inside
`lotSearch.pagedResults.{results,totalCount,...}`. The auction's display
name lives on the `auction(id:)` query as the `eventName` field.

## Redaction guarantee

The scraper never logs, prints, or persists the token value. Any error
message that touches the token is filtered through `_redact_token`, which
replaces it with the literal `<HIBID_TOKEN redacted>`. Cookie values are
similarly redacted. The `.env` file is gitignored.

## If `curl_cffi` is ever blocked too

If HiBid escalates and starts detecting `curl_cffi`'s impersonation (e.g.
by checking JS-execution challenges), the documented fallback is
**Playwright-driven browser automation**: load the catalog page in a real
headless Chromium, let it solve any JS challenge, then either scrape the
rendered DOM or extract the Bearer token from the page's IndexedDB /
localStorage and continue with HTTP requests. This is **not implemented**
in v1 — we'd rather not maintain a 200MB browser dependency for what is
currently a 3-tier HTTP scraper. Re-evaluate only if `curl_cffi` starts
returning 403s in practice.
