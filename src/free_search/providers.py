"""Search provider implementations with a unified output contract."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB guard against runaway responses


class ProviderError(Exception):
    """Base class for provider failures."""


class AuthError(ProviderError):
    """Raised when provider credentials are missing or rejected."""


class NetworkError(ProviderError):
    """Raised when upstream networking fails."""


class RateLimitError(ProviderError):
    """Raised when provider reports rate limiting."""


class QuotaExceededError(ProviderError):
    """Raised when provider quota has been exhausted."""


class ParseError(ProviderError):
    """Raised when an upstream response cannot be parsed safely."""


class UpstreamError(ProviderError):
    """Raised for non-recoverable upstream API errors."""


@dataclass(slots=True)
class SearchItem:
    """Unified search result item."""

    title: str
    url: str
    snippet: str
    source: str
    rank: int


class BaseProvider:
    """Base provider contract for search services."""

    name = "base"

    def __init__(
        self,
        *,
        config: dict[str, Any],
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.enabled = bool(config.get("enabled", True))
        self.timeout = int(config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        self.min_interval_seconds = float(config.get("min_interval_seconds", 0.0))
        self._last_request_ts = 0.0

    def is_enabled(self) -> bool:
        return self.enabled

    def maybe_sleep_for_rate_limit(self) -> float:
        if self.min_interval_seconds <= 0:
            return 0.0
        now = time.time()
        elapsed = now - self._last_request_ts
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            logger.debug("Provider %s sleeping %.2fs for pacing", self.name, remaining)
            time.sleep(remaining)
            return remaining
        return 0.0

    def _mark_request(self) -> None:
        self._last_request_ts = time.time()

    @staticmethod
    def _http_error_detail(response: requests.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                for key in ("error", "message", "detail"):
                    value = payload.get(key)
                    if value:
                        return str(value)
        except ValueError:
            pass
        text = (response.text or "").strip()
        if text:
            return text[:180]
        return ""

    @staticmethod
    def _guard_response_size(response: requests.Response) -> None:
        """Raise ParseError if the response body exceeds MAX_RESPONSE_BYTES."""
        cl = response.headers.get("content-length")
        if cl:
            try:
                if int(cl) > MAX_RESPONSE_BYTES:
                    raise ParseError(
                        f"Response content-length {cl} bytes exceeds {MAX_RESPONSE_BYTES} limit"
                    )
            except ValueError:
                pass
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ParseError(
                f"Response body {len(response.content)} bytes exceeds {MAX_RESPONSE_BYTES} limit"
            )

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        raise NotImplementedError


class BraveProvider(BaseProvider):
    name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    @staticmethod
    def _api_key_candidates(api_key: str) -> list[str]:
        key = api_key.strip()
        if not key:
            return []
        candidates = [key]
        if key.startswith("BSA"):
            candidates.append(f"BSa{key[3:]}")
        elif key.startswith("BSa"):
            candidates.append(f"BSA{key[3:]}")
        deduped: list[str] = []
        for candidate in candidates:
            if candidate not in deduped:
                deduped.append(candidate)
        return deduped

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        api_key = (self.config.get("api_key") or "").strip()
        if not api_key:
            raise AuthError("Brave API key missing")

        self.maybe_sleep_for_rate_limit()
        params = {"q": query, "count": max_results}
        key_candidates = self._api_key_candidates(api_key)
        if not key_candidates:
            raise AuthError("Brave API key missing")

        response: requests.Response | None = None
        for index, candidate in enumerate(key_candidates):
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": candidate,
            }
            logger.debug(
                "Brave request: query=%r max_results=%s attempt=%s",
                query,
                max_results,
                index + 1,
            )
            try:
                response = self.session.get(
                    self.endpoint,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                raise NetworkError(f"Brave request failed: {exc}") from exc
            finally:
                self._mark_request()

            if response.status_code not in (401, 403):
                break
            if index + 1 < len(key_candidates):
                logger.warning(
                    "Brave auth failed with current key format; retrying with alternate prefix"
                )

        if response is None:
            raise UpstreamError("Brave request did not receive a response")

        if response.status_code in (401, 403):
            detail = self._http_error_detail(response)
            raise AuthError(
                f"Brave auth failed: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )
        if response.status_code == 429:
            raise RateLimitError("Brave rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"Brave server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            detail = self._http_error_detail(response)
            raise UpstreamError(
                f"Brave request rejected: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )

        self._guard_response_size(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ParseError("Brave returned non-JSON response") from exc

        web = payload.get("web", {})
        raw_results = web.get("results", [])
        items: list[SearchItem] = []
        for idx, row in enumerate(raw_results[:max_results], start=1):
            title = (row.get("title") or "").strip()
            url = (row.get("url") or "").strip()
            snippet = (row.get("description") or "").strip()
            if not (title and url):
                continue
            items.append(
                SearchItem(title=title, url=url, snippet=snippet, source=self.name, rank=idx)
            )
        logger.info("Brave returned %s results for query=%r", len(items), query)
        return items


class TavilyProvider(BaseProvider):
    name = "tavily"
    endpoint = "https://api.tavily.com/search"

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        api_key = (self.config.get("api_key") or "").strip()
        if not api_key:
            raise AuthError("Tavily API key missing")

        self.maybe_sleep_for_rate_limit()
        body = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "search_depth": self.config.get("search_depth", "basic"),
        }

        try:
            logger.debug("Tavily request: query=%r max_results=%s", query, max_results)
            response = self.session.post(self.endpoint, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise NetworkError(f"Tavily request failed: {exc}") from exc
        finally:
            self._mark_request()

        if response.status_code in (401, 403):
            detail = self._http_error_detail(response)
            raise AuthError(
                f"Tavily auth failed: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )
        if response.status_code == 429:
            raise RateLimitError("Tavily rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"Tavily server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            detail = self._http_error_detail(response)
            raise UpstreamError(
                f"Tavily request rejected: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )

        self._guard_response_size(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ParseError("Tavily returned non-JSON response") from exc

        raw_results = payload.get("results", [])
        items: list[SearchItem] = []
        for idx, row in enumerate(raw_results[:max_results], start=1):
            title = (row.get("title") or "").strip()
            url = (row.get("url") or "").strip()
            snippet = (row.get("content") or "").strip()
            if not (title and url):
                continue
            items.append(
                SearchItem(title=title, url=url, snippet=snippet, source=self.name, rank=idx)
            )
        logger.info("Tavily returned %s results for query=%r", len(items), query)
        return items


class DuckDuckGoProvider(BaseProvider):
    name = "duckduckgo"
    endpoint = "https://duckduckgo.com/html/"

    @staticmethod
    def _extract_target_url(href: str) -> str:
        raw_href = href.strip()
        if not raw_href:
            return ""
        if raw_href.startswith("//"):
            raw_href = f"https:{raw_href}"

        parsed = urlparse(raw_href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            if target:
                return unquote(target).strip()
        return raw_href

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        self.maybe_sleep_for_rate_limit()
        params = {"q": query}
        headers = {"User-Agent": DEFAULT_USER_AGENT}

        try:
            logger.debug("DuckDuckGo HTML request: query=%r max_results=%s", query, max_results)
            response = self.session.get(
                self.endpoint, params=params, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise NetworkError(f"DuckDuckGo request failed: {exc}") from exc
        finally:
            self._mark_request()

        if response.status_code == 429:
            raise RateLimitError("DuckDuckGo rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"DuckDuckGo server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            detail = self._http_error_detail(response)
            raise UpstreamError(
                f"DuckDuckGo request rejected: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )

        self._guard_response_size(response)
        soup = BeautifulSoup(response.text, "html.parser")
        node_selectors = (
            "div.result",
            "article[data-testid='result']",
            "li[data-layout='organic']",
            "div.results_links",
        )
        nodes: list[Any] = []
        for selector in node_selectors:
            nodes.extend(soup.select(selector))

        items: list[SearchItem] = []
        seen_urls: set[str] = set()
        rank = 0
        for node in nodes:
            link = (
                node.select_one("a.result__a")
                or node.select_one("a[data-testid='result-title-a']")
                or node.select_one("h2 a[href]")
            )
            if not link:
                continue
            href = self._extract_target_url(link.get("href") or "")
            title = link.get_text(" ", strip=True)
            snippet_node = (
                node.select_one("a.result__snippet")
                or node.select_one(".result__snippet")
                or node.select_one("[data-result='snippet']")
                or node.select_one("[data-testid='result-snippet']")
            )
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            if not (title and href) or href in seen_urls:
                continue
            seen_urls.add(href)
            rank += 1
            items.append(
                SearchItem(title=title, url=href, snippet=snippet, source=self.name, rank=rank)
            )
            if rank >= max_results:
                break

        # Return empty list (not an error) — router will continue to next provider
        if not items:
            logger.info("DuckDuckGo HTML returned no results for query=%r", query)
        else:
            logger.info("DuckDuckGo HTML returned %s results for query=%r", len(items), query)
        return items


class SerperProvider(BaseProvider):
    name = "serper"
    endpoint = "https://google.serper.dev/search"

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        api_key = (self.config.get("api_key") or "").strip()
        if not api_key:
            raise AuthError("Serper API key missing")

        self.maybe_sleep_for_rate_limit()
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        body = {"q": query, "num": max_results}

        try:
            logger.debug("Serper request: query=%r max_results=%s", query, max_results)
            response = self.session.post(
                self.endpoint, headers=headers, json=body, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise NetworkError(f"Serper request failed: {exc}") from exc
        finally:
            self._mark_request()

        if response.status_code in (401, 403):
            detail = self._http_error_detail(response)
            raise AuthError(
                f"Serper auth failed: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )
        if response.status_code == 429:
            raise RateLimitError("Serper rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"Serper server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            detail = self._http_error_detail(response)
            raise UpstreamError(
                f"Serper request rejected: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )

        self._guard_response_size(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ParseError("Serper returned non-JSON response") from exc

        raw_results = payload.get("organic", [])
        items: list[SearchItem] = []
        for idx, row in enumerate(raw_results[:max_results], start=1):
            title = (row.get("title") or "").strip()
            url = (row.get("link") or "").strip()
            snippet = (row.get("snippet") or "").strip()
            if not (title and url):
                continue
            items.append(
                SearchItem(title=title, url=url, snippet=snippet, source=self.name, rank=idx)
            )
        logger.info("Serper returned %s results for query=%r", len(items), query)
        return items


class SearchApiProvider(BaseProvider):
    name = "searchapi"
    endpoint = "https://www.searchapi.io/api/v1/search"

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        api_key = (self.config.get("api_key") or "").strip()
        if not api_key:
            raise AuthError("SearchApi API key missing")

        self.maybe_sleep_for_rate_limit()
        params = {
            "engine": self.config.get("engine", "google"),
            "q": query,
            "num": max_results,
        }
        # Use Bearer token header only — avoids leaking key in query string / server logs
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            logger.debug("SearchApi request: query=%r max_results=%s", query, max_results)
            response = self.session.get(
                self.endpoint, params=params, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise NetworkError(f"SearchApi request failed: {exc}") from exc
        finally:
            self._mark_request()

        if response.status_code in (401, 403):
            detail = self._http_error_detail(response)
            raise AuthError(
                f"SearchApi auth failed: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )
        if response.status_code == 429:
            raise RateLimitError("SearchApi rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"SearchApi server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            detail = self._http_error_detail(response)
            raise UpstreamError(
                f"SearchApi request rejected: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )

        self._guard_response_size(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ParseError("SearchApi returned non-JSON response") from exc

        raw_results = payload.get("organic_results", []) or payload.get("results", [])
        items: list[SearchItem] = []
        for idx, row in enumerate(raw_results[:max_results], start=1):
            title = (row.get("title") or "").strip()
            url = (row.get("link") or row.get("url") or "").strip()
            snippet = (row.get("snippet") or row.get("description") or "").strip()
            if not (title and url):
                continue
            items.append(
                SearchItem(title=title, url=url, snippet=snippet, source=self.name, rank=idx)
            )
        logger.info("SearchApi returned %s results for query=%r", len(items), query)
        return items


class DuckDuckGoInstantProvider(BaseProvider):
    name = "duckduckgo_instant"
    endpoint = "https://api.duckduckgo.com/"

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        self.maybe_sleep_for_rate_limit()
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        headers = {"User-Agent": DEFAULT_USER_AGENT}

        try:
            logger.debug(
                "DuckDuckGo Instant request: query=%r max_results=%s", query, max_results
            )
            response = self.session.get(
                self.endpoint, params=params, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise NetworkError(f"DuckDuckGo Instant request failed: {exc}") from exc
        finally:
            self._mark_request()

        if response.status_code == 429:
            raise RateLimitError("DuckDuckGo Instant rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"DuckDuckGo Instant server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            detail = self._http_error_detail(response)
            raise UpstreamError(
                f"DuckDuckGo Instant request rejected: HTTP {response.status_code}"
                + (f" ({detail})" if detail else "")
            )

        self._guard_response_size(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ParseError("DuckDuckGo Instant returned non-JSON response") from exc

        flattened: list[tuple[str, str]] = []
        abstract_text = (payload.get("AbstractText") or "").strip()
        abstract_url = (payload.get("AbstractURL") or "").strip()
        if abstract_text and abstract_url:
            flattened.append((abstract_text, abstract_url))

        def _collect(rows: list[dict[str, Any]]) -> None:
            for row in rows:
                if "Topics" in row and isinstance(row.get("Topics"), list):
                    _collect(row["Topics"])
                    continue
                text = (row.get("Text") or "").strip()
                url = (row.get("FirstURL") or "").strip()
                if text and url:
                    flattened.append((text, url))

        _collect(payload.get("Results", []))
        _collect(payload.get("RelatedTopics", []))

        items: list[SearchItem] = []
        seen_urls: set[str] = set()
        for text, url in flattened:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = text.split(" - ", 1)[0].strip() or text[:80]
            items.append(
                SearchItem(
                    title=title, url=url, snippet=text, source=self.name, rank=len(items) + 1
                )
            )
            if len(items) >= max_results:
                break

        logger.info("DuckDuckGo Instant returned %s results for query=%r", len(items), query)
        return items


class YaCyProvider(BaseProvider):
    name = "yacy"
    endpoint = "http://localhost:8090/yacysearch.json"

    def search(self, query: str, *, max_results: int) -> list[SearchItem]:
        endpoint = self.config.get("endpoint") or self.endpoint

        self.maybe_sleep_for_rate_limit()
        params = {
            "query": query,
            "maximumRecords": max_results,
            "startRecord": 0,
            "resource": self.config.get("resource", "global"),
        }

        try:
            response = self.session.get(endpoint, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise NetworkError(f"YaCy request failed: {exc}") from exc
        finally:
            self._mark_request()

        if response.status_code in (401, 403):
            raise AuthError(f"YaCy auth failed: HTTP {response.status_code}")
        if response.status_code == 429:
            raise RateLimitError("YaCy rate limited")
        if response.status_code >= 500:
            raise UpstreamError(f"YaCy server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise UpstreamError(f"YaCy request rejected: HTTP {response.status_code}")

        self._guard_response_size(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ParseError("YaCy returned non-JSON response") from exc

        raw_items: list[dict[str, Any]] = []
        channels = payload.get("channels")
        if isinstance(channels, list):
            for channel in channels:
                if isinstance(channel, dict) and isinstance(channel.get("items"), list):
                    raw_items.extend(channel["items"])
        if not raw_items and isinstance(payload.get("items"), list):
            raw_items = payload["items"]

        items: list[SearchItem] = []
        for idx, row in enumerate(raw_items[:max_results], start=1):
            title = (row.get("title") or "").strip()
            url = (row.get("link") or row.get("url") or "").strip()
            snippet = (row.get("description") or row.get("snippet") or "").strip()
            if not (title and url):
                continue
            items.append(
                SearchItem(title=title, url=url, snippet=snippet, source=self.name, rank=idx)
            )
        return items


PROVIDER_REGISTRY = {
    BraveProvider.name: BraveProvider,
    TavilyProvider.name: TavilyProvider,
    DuckDuckGoProvider.name: DuckDuckGoProvider,
    DuckDuckGoInstantProvider.name: DuckDuckGoInstantProvider,
    SearchApiProvider.name: SearchApiProvider,
    YaCyProvider.name: YaCyProvider,
    SerperProvider.name: SerperProvider,
}
