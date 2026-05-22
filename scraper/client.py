"""
HiBid GraphQL HTTP client.

HiBid sits behind Cloudflare, which fingerprints TLS handshakes. Standard
Python HTTP clients (httpx, requests, urllib) all give a fingerprint that
Cloudflare flags — anonymous, cookie-seeded, and Bearer-token requests are
all rejected with HTTP 403 regardless of credentials. We use `curl_cffi`
with `impersonate="chrome124"`, which mimics a real Chrome TLS handshake
and passes Cloudflare's check.

Three-tier auth strategy is preserved:
  1. Anonymous            — no Authorization header, no cookies.
  2. Cookie-seeded        — GET catalog page first to acquire session
                            cookies, then POST with those cookies.
  3. JWT bearer (HIBID_TOKEN) — passed as Authorization: Bearer.

In practice the anonymous path now works for read-only catalog browsing,
so the cookie and JWT paths are kept only as fallbacks. Any error message
that might touch a token replaces it with ``<HIBID_TOKEN redacted>``;
cookie values are similarly redacted. Tokens are never logged or persisted.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Optional

from curl_cffi import requests as cffi_requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRAPHQL_URL = "https://encoreauctions.hibid.com/graphql"
CATALOG_URL_TEMPLATE = "https://encoreauctions.hibid.com/catalog/{auction_id}"

# Browser preset for TLS fingerprint impersonation
IMPERSONATE = "chrome124"

RATE_LIMIT_SLEEP = 0.25  # 250 ms between requests
REQUEST_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# GraphQL query
# ---------------------------------------------------------------------------
# Schema reverse-engineered from the HiBid public PWA bundle:
# `lotSearch(input: LotSearchInput, pageLength, pageNumber) { pagedResults {...} }`.
# Introspection is server-disabled, so this is what HiBid's own frontend uses.

LOT_SEARCH_QUERY = """
query LotSearchLotOnly($auctionId: Int!, $pageNumber: Int!, $pageLength: Int!) {
  lotSearch(
    input: {auctionId: $auctionId, status: ALL, sortOrder: SALE_ORDER}
    pageLength: $pageLength
    pageNumber: $pageNumber
  ) {
    pagedResults {
      pageLength
      pageNumber
      totalCount
      filteredCount
      results {
        id
        lotNumber
        lead
        description
        featuredPicture { thumbnailLocation fullSizeLocation }
        pictures { fullSizeLocation }
        lotState { highBid status timeLeftTitle }
        category { categoryName fullCategory }
      }
    }
  }
}
""".strip()

AUCTION_INFO_QUERY = """
query AuctionInfo($id: Int!) {
  auction(id: $id) { id eventName }
}
""".strip()


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------


def _redact_token(token: Optional[str], text: str) -> str:
    """Replace occurrences of token in text with ``<HIBID_TOKEN redacted>``."""
    if token and len(token) > 8:
        return text.replace(token, "<HIBID_TOKEN redacted>")
    return text


def _redact_cookies(cookies: dict, text: str) -> str:
    """Replace any cookie value that appears verbatim in text."""
    for v in cookies.values():
        if v and len(v) > 4:
            text = text.replace(v, "<cookie redacted>")
    return text


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def _is_valid_graphql(resp) -> bool:
    """True if response looks like a real GraphQL JSON body."""
    if resp is None:
        return False
    if getattr(resp, "status_code", 0) != 200:
        return False
    ct = (resp.headers.get("content-type") or "") if hasattr(resp, "headers") else ""
    if "json" not in ct and "graphql" not in ct:
        return False
    try:
        body = resp.json()
    except Exception:
        return False
    return "data" in body or "errors" in body


# ---------------------------------------------------------------------------
# Auth strategies
# ---------------------------------------------------------------------------


def _try_anon(session, payload: dict[str, Any]):
    """Anonymous POST — no Authorization, no cookies."""
    try:
        return session.post(GRAPHQL_URL, json=payload, timeout=REQUEST_TIMEOUT)
    except Exception as exc:
        logger.debug("Anonymous request error: %s", exc)
        return None


def _try_cookie_seeded(session, auction_id: int, payload: dict[str, Any]):
    """GET catalog page first to acquire cookies, then POST."""
    catalog_url = CATALOG_URL_TEMPLATE.format(auction_id=auction_id)
    try:
        seed_resp = session.get(catalog_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if seed_resp.status_code >= 400:
            logger.debug("Catalog seed GET returned %s", seed_resp.status_code)
            return None
    except Exception as exc:
        logger.debug("Catalog seed GET error: %s", exc)
        return None

    post_headers = {
        "Origin": "https://encoreauctions.hibid.com",
        "Referer": catalog_url,
    }
    try:
        return session.post(
            GRAPHQL_URL,
            json=payload,
            headers=post_headers,
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as exc:
        logger.debug("Cookie-seeded POST error: %s", exc)
        return None


def _try_bearer(session, token: str, payload: dict[str, Any]):
    """POST with Authorization: Bearer {token}."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        return session.post(
            GRAPHQL_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
        )
    except Exception as exc:
        safe_msg = _redact_token(token, str(exc))
        logger.debug("Bearer POST error: %s", safe_msg)
        return None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


_PAGE_LENGTHS = [500, 200, 100]


def _build_payload(auction_id: int, page_number: int, page_length: int) -> dict:
    return {
        "operationName": "LotSearchLotOnly",
        "variables": {
            "auctionId": auction_id,
            "pageNumber": page_number,
            "pageLength": page_length,
        },
        "query": LOT_SEARCH_QUERY,
    }


def _paged_results(resp) -> Optional[dict]:
    """Pull the {totalCount, results, ...} dict out of a successful response."""
    try:
        body = resp.json()
    except Exception:
        return None
    lot_search = (body.get("data") or {}).get("lotSearch") or {}
    paged = lot_search.get("pagedResults")
    return paged if isinstance(paged, dict) else None


def _negotiate_page_length(
    session, auction_id: int, auth_fn: Callable
) -> tuple[int, dict]:
    """Try 500 → 200 → 100 until one returns a valid page-1 response."""
    for page_length in _PAGE_LENGTHS:
        payload = _build_payload(auction_id, 1, page_length)
        resp = auth_fn(session, payload)
        if not _is_valid_graphql(resp):
            continue
        paged = _paged_results(resp)
        if paged is None:
            continue
        logger.info("Page length %d accepted by API.", page_length)
        return page_length, paged
    raise RuntimeError(
        f"All page lengths ({_PAGE_LENGTHS}) rejected or returned invalid data."
    )


def _fetch_auction_name(session, auction_id: int) -> str:
    """Best-effort lookup of the human-readable auction name."""
    try:
        resp = session.post(
            GRAPHQL_URL,
            json={
                "operationName": "AuctionInfo",
                "variables": {"id": auction_id},
                "query": AUCTION_INFO_QUERY,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if not _is_valid_graphql(resp):
            return f"Auction {auction_id}"
        body = resp.json()
        auction = (body.get("data") or {}).get("auction") or {}
        return auction.get("eventName") or f"Auction {auction_id}"
    except Exception:
        return f"Auction {auction_id}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _make_session():
    """Create a curl_cffi session impersonating a real Chrome TLS handshake."""
    return cffi_requests.Session(impersonate=IMPERSONATE)


def fetch_all_lots(auction_id: int) -> tuple[str, list[dict[str, Any]]]:
    """
    Fetch all lots for ``auction_id`` using the 3-tier auth strategy.

    Returns:
        (auction_name, items_list)

    Raises:
        RuntimeError if all auth strategies fail or pagination errors out.
    """
    token: Optional[str] = os.environ.get("HIBID_TOKEN") or None

    with _make_session() as session:
        # Probe auth strategies in priority order
        def anon_fn(s, payload):
            return _try_anon(s, payload)

        def cookie_fn(s, payload):
            return _try_cookie_seeded(s, auction_id, payload)

        def bearer_fn(s, payload):
            if not token:
                return None
            return _try_bearer(s, token, payload)

        chosen_fn: Optional[Callable] = None
        chosen_name: Optional[str] = None

        for fn, name in [
            (anon_fn, "anonymous"),
            (cookie_fn, "cookie-seeded"),
            (bearer_fn, "JWT bearer"),
        ]:
            logger.info("Trying auth strategy: %s", name)
            probe_payload = _build_payload(auction_id, 1, _PAGE_LENGTHS[0])
            resp = fn(session, probe_payload)
            if _is_valid_graphql(resp) and _paged_results(resp) is not None:
                chosen_fn = fn
                chosen_name = name
                logger.info("Auth strategy succeeded: %s", name)
                break
            status = getattr(resp, "status_code", "no response") if resp is not None else "no response"
            logger.warning("Auth strategy %s failed (status: %s).", name, status)

        if chosen_fn is None:
            raise RuntimeError(
                f"All auth strategies failed (anonymous, cookie-seeded, JWT bearer) "
                f"for auction {auction_id}. If HIBID_TOKEN is set, check that it is "
                f"valid and not expired."
            )

        # Determine page length + fetch page 1
        page_length, first_page = _negotiate_page_length(session, auction_id, chosen_fn)
        total_count: int = first_page.get("totalCount") or 0
        results: list[dict] = list(first_page.get("results") or [])

        # Best-effort auction name lookup
        auction_name = _fetch_auction_name(session, auction_id)

        logger.info(
            "Auction %d: %s — %d total lots (page length: %d, auth: %s)",
            auction_id,
            auction_name,
            total_count,
            page_length,
            chosen_name,
        )

        all_items: list[dict[str, Any]] = list(results)
        page_number = 2
        while (page_number - 1) * page_length < total_count:
            time.sleep(RATE_LIMIT_SLEEP)
            payload = _build_payload(auction_id, page_number, page_length)
            resp = chosen_fn(session, payload)
            if not _is_valid_graphql(resp):
                status = getattr(resp, "status_code", "no response") if resp is not None else "no response"
                raise RuntimeError(f"Page {page_number} fetch failed (status: {status}).")
            paged = _paged_results(resp)
            if paged is None:
                raise RuntimeError(f"Page {page_number} returned no pagedResults.")
            page_results = paged.get("results") or []
            all_items.extend(page_results)

            logger.info(
                "Fetched page %d/%d (%d items so far)",
                page_number,
                -(-total_count // page_length),
                len(all_items),
            )
            page_number += 1

        return auction_name, all_items
