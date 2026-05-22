"""
Unit tests for scraper/client.py — mocks curl_cffi to confirm the 3-tier auth
selection, pagination, and redaction logic without making any network calls.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scraper import client


# ---------------------------------------------------------------------------
# Fake curl_cffi response
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code: int = 200, body: dict | None = None,
                 content_type: str = "application/json; charset=utf-8"):
        self.status_code = status_code
        self._body = body or {}
        self.headers = {"content-type": content_type}

    def json(self):
        return self._body


def _paged(results: list[dict], total: int, page_number: int, page_length: int) -> dict:
    return {
        "data": {
            "lotSearch": {
                "pagedResults": {
                    "pageLength": page_length,
                    "pageNumber": page_number,
                    "totalCount": total,
                    "filteredCount": total,
                    "results": results,
                }
            }
        }
    }


def _auction(name: str = "TEST AUCTION") -> dict:
    return {"data": {"auction": {"id": 1, "eventName": name}}}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidGraphql:
    def test_valid_200_with_data(self):
        resp = FakeResponse(200, {"data": {"foo": 1}})
        assert client._is_valid_graphql(resp) is True

    def test_valid_200_with_errors(self):
        resp = FakeResponse(200, {"errors": [{"message": "bad"}]})
        assert client._is_valid_graphql(resp) is True

    def test_invalid_403(self):
        resp = FakeResponse(403, content_type="text/html")
        assert client._is_valid_graphql(resp) is False

    def test_invalid_html_content_type(self):
        resp = FakeResponse(200, {"data": {}}, content_type="text/html")
        assert client._is_valid_graphql(resp) is False

    def test_none_response(self):
        assert client._is_valid_graphql(None) is False


class TestAnonAuthHappyPath:
    """Anonymous strategy succeeds → no further auth attempts; pagination runs."""

    def test_two_page_fetch(self, monkeypatch):
        monkeypatch.delenv("HIBID_TOKEN", raising=False)

        page1 = _paged([{"id": 1, "lotNumber": "1"}, {"id": 2, "lotNumber": "2"}], total=3, page_number=1, page_length=2)
        page2 = _paged([{"id": 3, "lotNumber": "3"}], total=3, page_number=2, page_length=2)
        auction = _auction("TEST")

        # Sequence of POST responses:
        # 1) probe (anon, page 1, length 500) - SUCCESS (sets chosen_fn)
        # 2) negotiate first try at length 500 - SUCCESS
        # 3) auction-info POST (eventName lookup)
        # 4) page 2
        # We patch length list so we don't have to provide 3 negotiations
        monkeypatch.setattr(client, "_PAGE_LENGTHS", [2])

        post_responses = [
            FakeResponse(200, page1),   # probe at page_length=2
            FakeResponse(200, page1),   # negotiation reuse
            FakeResponse(200, auction), # _fetch_auction_name
            FakeResponse(200, page2),   # page 2
        ]
        fake_session = MagicMock()
        fake_session.__enter__.return_value = fake_session
        fake_session.__exit__.return_value = False
        fake_session.post.side_effect = post_responses

        monkeypatch.setattr(client, "_make_session", lambda: fake_session)
        # Speed up: skip rate-limit sleep
        monkeypatch.setattr(client.time, "sleep", lambda _s: None)

        name, items = client.fetch_all_lots(741675)
        assert name == "TEST"
        assert [i["id"] for i in items] == [1, 2, 3]


class TestFallbackToBearer:
    """Anon + cookie-seeded both blocked (403); JWT bearer succeeds."""

    def test_bearer_used_when_anon_and_cookie_403(self, monkeypatch):
        monkeypatch.setenv("HIBID_TOKEN", "fake.jwt.token.value-LONG-ENOUGH")
        monkeypatch.setattr(client, "_PAGE_LENGTHS", [2])

        page1 = _paged([{"id": 9, "lotNumber": "9"}], total=1, page_number=1, page_length=2)
        auction = _auction("BEARER OK")

        fake_session = MagicMock()
        fake_session.__enter__.return_value = fake_session
        fake_session.__exit__.return_value = False
        # GET (cookie-seed catalog) returns 403; POSTs:
        fake_session.get.return_value = FakeResponse(403, content_type="text/html")
        fake_session.post.side_effect = [
            FakeResponse(403, content_type="text/html"),  # anon probe
            FakeResponse(200, page1),                     # bearer probe → success
            FakeResponse(200, page1),                     # negotiation
            FakeResponse(200, auction),                   # auction-info
        ]
        monkeypatch.setattr(client, "_make_session", lambda: fake_session)
        monkeypatch.setattr(client.time, "sleep", lambda _s: None)

        name, items = client.fetch_all_lots(741675)
        assert name == "BEARER OK"
        assert items[0]["id"] == 9
        # Confirm the bearer header was actually sent
        bearer_call = [
            c for c in fake_session.post.call_args_list
            if c.kwargs.get("headers", {}).get("Authorization", "").startswith("Bearer ")
        ]
        assert bearer_call, "Bearer Authorization header was never sent"


class TestAllAuthFails:
    def test_runtime_error_when_all_strategies_fail(self, monkeypatch):
        monkeypatch.setenv("HIBID_TOKEN", "fake.jwt.token.value-LONG-ENOUGH")
        monkeypatch.setattr(client, "_PAGE_LENGTHS", [2])

        fake_session = MagicMock()
        fake_session.__enter__.return_value = fake_session
        fake_session.__exit__.return_value = False
        fake_session.get.return_value = FakeResponse(403, content_type="text/html")
        fake_session.post.return_value = FakeResponse(403, content_type="text/html")
        monkeypatch.setattr(client, "_make_session", lambda: fake_session)

        with pytest.raises(RuntimeError, match="All auth strategies failed"):
            client.fetch_all_lots(741675)


class TestRedactionStillWorks:
    """The redaction helpers are still exported and effective after the rewrite."""

    def test_token_redacted(self):
        token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.FAKE.SIG"
        msg = f"oh no: {token} leaked"
        out = client._redact_token(token, msg)
        assert token not in out
        assert "<HIBID_TOKEN redacted>" in out

    def test_short_token_not_redacted(self):
        out = client._redact_token("abc", "see abc here")
        assert "abc" in out
