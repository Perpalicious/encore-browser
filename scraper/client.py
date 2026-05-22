"""
HiBid GraphQL HTTP client with 3-tier auth strategy:
  1. Anonymous — no Authorization header, no cookies.
  2. Cookie-seeded — GET catalog page first to acquire session cookies,
     then POST with those cookies.
  3. JWT bearer — read HIBID_TOKEN from .env, pass as Authorization: Bearer.

Any error message or log line that might touch the token replaces it with the
literal string <HIBID_TOKEN redacted>. Cookies are similarly redacted.

Never logs, prints, or persists the token value.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRAPHQL_URL = "https://encoreauctions.hibid.com/graphql"
CATALOG_URL_TEMPLATE = "https://encoreauctions.hibid.com/catalog/{auction_id}"

RATE_LIMIT_SLEEP = 0.25  # 250 ms between requests

# Headers common to all requests
_BASE_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ---------------------------------------------------------------------------
# GraphQL query (verbatim from spec)
# ---------------------------------------------------------------------------

LOT_SEARCH_QUERY = """
query LotSearchLotOnly($auctionId: Int!, $pageNumber: Int!, $pageLength: Int!, $searchText: String, $filter: LotSearchFilter) {
  lotSearch(auctionId: $auctionId, pageNumber: $pageNumber, pageLength: $pageLength, searchText: $searchText, filter: $filter) {
    totalCount
    auctionName
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
""".strip()

# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------


def _redact_token(token: Optional[str], text: str) -> str:
    """Replace occurrences of token in text with <HIBID_TOKEN redacted>."""
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
# Auth strategies
# ---------------------------------------------------------------------------


def _try_anon(
    client: httpx.Client, payload: dict[str, Any]
) -> Optional[httpx.Response]:
    """Attempt an anonymous POST (no auth, no cookies)."""
    try:
        resp = client.post(GRAPHQL_URL, json=payload, headers=_BASE_HEADERS)
        return resp
    except Exception as exc:
        logger.debug("Anonymous request error: %s", exc)
        return None


def _try_cookie_seeded(
    client: httpx.Client, auction_id: int, payload: dict[str, Any], token: Optional[str]
) -> Optional[httpx.Response]:
    """
    GET the catalog page to seed session cookies, then POST.
    """
    catalog_url = CATALOG_URL_TEMPLATE.format(auction_id=auction_id)
    seed_headers = {
        **_BASE_HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Origin": "https://encoreauctions.hibid.com",
        "Referer": catalog_url,
    }
    try:
        seed_resp = client.get(catalog_url, headers=seed_headers, follow_redirects=True)
        if seed_resp.status_code >= 400:
            logger.debug(
                "Catalog seed GET returned %s", seed_resp.status_code
            )
            return None
    except Exception as exc:
        logger.debug("Catalog seed GET error: %s", exc)
        return None

    post_headers = {
        **_BASE_HEADERS,
        "Origin": "https://encoreauctions.hibid.com",
        "Referer": catalog_url,
    }
    try:
        resp = client.post(GRAPHQL_URL, json=payload, headers=post_headers)
        return resp
    except Exception as exc:
        logger.debug("Cookie-seeded POST error: %s", exc)
        return None


def _try_bearer(
    client: httpx.Client, token: str, payload: dict[str, Any]
) -> Optional[httpx.Response]:
    """POST with Authorization: Bearer {token}."""
    headers = {
        **_BASE_HEADERS,
        # Token passed in memory only; never logged
        "Authorization": f"Bearer {token}",
    }
    try:
        resp = client.post(GRAPHQL_URL, json=payload, headers=headers)
        return resp
    except Exception as exc:
        # Redact token from any error message
        safe_msg = _redact_token(token, str(exc))
        logger.debug("Bearer POST error: %s", safe_msg)
        return None


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def _is_valid_graphql(resp: Optional[httpx.Response]) -> bool:
    """Return True if the response looks like valid GraphQL JSON (not a CF page)."""
    if resp is None:
        return False
    if resp.status_code != 200:
        return False
    ct = resp.headers.get("content-type", "")
    if "json" not in ct and "graphql" not in ct:
        return False
    try:
        body = resp.json()
    except Exception:
        return False
    return "data" in body or "errors" in body


# ---------------------------------------------------------------------------
# Page-length negotiation
# ---------------------------------------------------------------------------

_PAGE_LENGTHS = [500, 200, 100]


def _negotiate_page_length(
    client: httpx.Client,
    auction_id: int,
    auth_fn,
) -> tuple[int, dict[str, Any]]:
    """
    Try page lengths 500 → 200 → 100 until one works.
    Returns (page_length, first_page_data).
    Raises RuntimeError if none work.
    """
    for page_length in _PAGE_LENGTHS:
        payload = _build_payload(auction_id, 1, page_length)
        resp = auth_fn(client, payload)
        if not _is_valid_graphql(resp):
            continue
        body = resp.json()
        lot_search = (body.get("data") or {}).get("lotSearch")
        if lot_search is None:
            continue
        logger.info("Page length %d accepted by API.", page_length)
        return page_length, lot_search
    raise RuntimeError(
        f"All page lengths ({_PAGE_LENGTHS}) rejected or returned invalid data."
    )


def _build_payload(auction_id: int, page_number: int, page_length: int) -> dict:
    return {
        "operationName": "LotSearchLotOnly",
        "variables": {
            "auctionId": auction_id,
            "pageNumber": page_number,
            "pageLength": page_length,
            "searchText": "",
            "filter": {},
        },
        "query": LOT_SEARCH_QUERY,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_all_lots(auction_id: int) -> tuple[str, list[dict[str, Any]]]:
    """
    Fetch all lots for the given auction_id using the 3-tier auth strategy.

    Returns:
        (auction_name, items_list)

    Raises:
        RuntimeError if all auth strategies fail.
    """
    token: Optional[str] = os.environ.get("HIBID_TOKEN") or None

    with httpx.Client(timeout=30.0) as client:
        # Build the auth function in priority order
        def _auth_fn_anon(c: httpx.Client, payload: dict) -> Optional[httpx.Response]:
            return _try_anon(c, payload)

        def _auth_fn_cookie(c: httpx.Client, payload: dict) -> Optional[httpx.Response]:
            return _try_cookie_seeded(c, auction_id, payload, token)

        def _auth_fn_bearer(c: httpx.Client, payload: dict) -> Optional[httpx.Response]:
            if not token:
                return None
            return _try_bearer(c, token, payload)

        # Probe each strategy on page 1
        chosen_fn = None
        chosen_name = None

        for fn, name in [
            (_auth_fn_anon, "anonymous"),
            (_auth_fn_cookie, "cookie-seeded"),
            (_auth_fn_bearer, "JWT bearer"),
        ]:
            logger.info("Trying auth strategy: %s", name)
            probe_payload = _build_payload(auction_id, 1, _PAGE_LENGTHS[0])
            resp = fn(client, probe_payload)
            if _is_valid_graphql(resp):
                chosen_fn = fn
                chosen_name = name
                logger.info("Auth strategy succeeded: %s", name)
                break
            status = resp.status_code if resp is not None else "no response"
            logger.warning("Auth strategy %s failed (status: %s).", name, status)

        if chosen_fn is None:
            # Build a safe error message
            strategies = "anonymous, cookie-seeded, JWT bearer"
            msg = (
                f"All auth strategies failed ({strategies}) for auction {auction_id}. "
                "If HIBID_TOKEN is set, check that it is valid and not expired."
            )
            raise RuntimeError(msg)

        # Negotiate page length and get first page
        page_length, first_page = _negotiate_page_length(client, auction_id, chosen_fn)

        total_count: int = first_page.get("totalCount") or 0
        auction_name: str = first_page.get("auctionName") or ""
        results: list[dict] = first_page.get("results") or []

        logger.info(
            "Auction %d: %s — %d total lots (page length: %d)",
            auction_id,
            auction_name,
            total_count,
            page_length,
        )

        all_items: list[dict[str, Any]] = list(results)

        # Paginate
        page_number = 2
        while (page_number - 1) * page_length < total_count:
            time.sleep(RATE_LIMIT_SLEEP)
            payload = _build_payload(auction_id, page_number, page_length)
            resp = chosen_fn(client, payload)
            if not _is_valid_graphql(resp):
                status = resp.status_code if resp is not None else "no response"
                msg = f"Page {page_number} fetch failed (status: {status})."
                raise RuntimeError(msg)

            body = resp.json()
            lot_search = (body.get("data") or {}).get("lotSearch") or {}
            page_results = lot_search.get("results") or []
            all_items.extend(page_results)

            logger.info(
                "Fetched page %d/%d (%d items so far)",
                page_number,
                -(-total_count // page_length),  # ceiling division
                len(all_items),
            )
            page_number += 1

        return auction_name, all_items
