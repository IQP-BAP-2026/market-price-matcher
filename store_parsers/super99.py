from __future__ import annotations

import json
import time
from pathlib import Path

from matcher_core import PRICE_BASIS
from .base import BaseStoreParser


class Super99Parser(BaseStoreParser):
    store_id = "super99"
    display_name = "Super 99"

    ENDPOINT = "https://catalog-service.adobe.io/graphql"
    RESULTS_PER_PAGE = 20
    MAX_PAGES = 2
    REQUEST_DELAY_SECONDS = 0.05

    HEADERS = {
        "accept": "*/*",
        "content-type": "application/json",
        "magento-environment-id": "62e34917-8244-4ca2-869c-5c4958a4ec04",
        "magento-store-code": "super99",
        "magento-store-view-code": "brisas_del_golf",
        "magento-website-code": "super99",
        "origin": "https://www.super99.com",
        "referer": "https://www.super99.com/",
        "x-api-key": "search_gql",
    }

    QUERY = r"""
    query quickSearch(
        $phrase: String!
        $pageSize: Int = 20
        $currentPage: Int = 1
        $filter: [SearchClauseInput!]
        $sort: [ProductSearchSortInput!]
        $context: QueryContextInput
    ) {
        productSearch(
            phrase: $phrase
            page_size: $pageSize
            current_page: $currentPage
            filter: $filter
            sort: $sort
            context: $context
        ) {
            items {
                product {
                    sku
                    name
                    canonical_url
                    price_range {
                        minimum_price {
                            regular_price { value currency }
                            final_price { value currency }
                            discount { percent_off amount_off }
                        }
                    }
                }
                productView { name attributes { name value } }
            }
            page_info { current_page page_size total_pages }
            total_count
        }
    }
    """

    @property
    def max_pages(self) -> int:
        return self.MAX_PAGES

    def _headers(self):
        h = super()._headers()
        h.update(self.HEADERS)
        return h

    @staticmethod
    def _read_price(minimum: dict, key: str):
        try:
            p = minimum[key]
            return float(p["value"]), str(p.get("currency", "USD"))
        except Exception:
            return None, ""

    def _normalize_item(self, entry: dict) -> dict | None:
        product = entry.get("product") or {}
        sku = str(product.get("sku", "")).strip()
        name = str(product.get("name", "")).strip()
        if not sku or not name:
            return None

        attrs = {}
        for a in (entry.get("productView") or {}).get("attributes") or []:
            key = str(a.get("name", "")).strip().lower()
            if key:
                attrs[key] = a.get("value")

        try:
            minimum = product["price_range"]["minimum_price"]
        except Exception:
            minimum = {}

        regular, c1 = self._read_price(minimum, "regular_price")
        final, c2 = self._read_price(minimum, "final_price")
        currency = c2 or c1 or "USD"

        discount_percent = None
        try:
            d = minimum.get("discount") or {}
            if d.get("percent_off") is not None:
                discount_percent = float(d["percent_off"])
        except Exception:
            pass

        if PRICE_BASIS == "regular":
            chosen = regular if regular is not None else final
            basis = "regular" if regular is not None else "final fallback"
        else:
            chosen = final if final is not None else regular
            basis = "final" if final is not None else "regular fallback"

        return {
            "store": self.store_id,
            "store_name": self.display_name,
            "sku": sku,
            "name": name,
            "url": product.get("canonical_url") or "",
            "attrs": attrs,
            "regular_price": regular,
            "final_price": final,
            "price": chosen,
            "price_basis": basis,
            "discount_percent": discount_percent,
            "currency": currency,
        }

    def _fetch_page(self, query: str, page: int) -> dict:
        payload = {
            "query": self.QUERY,
            "variables": {
                "phrase": query,
                "pageSize": self.RESULTS_PER_PAGE,
                "currentPage": page,
                "filter": [
                    {"attribute": "visibility", "in": ["Search", "Catalog, Search"]},
                    {"attribute": "inStock", "eq": "true"},
                ],
                "context": {
                    "customerGroup": "b6589fc6ab0dc82cf12099d1c2d40ab994e8410c",
                    "userViewHistory": [],
                },
            },
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                r = self._session().post(self.ENDPOINT, json=payload, timeout=self.timeout_seconds)
                if r.status_code == 429:
                    time.sleep(max(0.5, 1.5 * (2 ** attempt)))
                    last_error = RuntimeError("HTTP 429 rate limited")
                    continue
                if 500 <= r.status_code < 600:
                    last_error = RuntimeError(f"HTTP {r.status_code}")
                    time.sleep(0.75 * (2 ** attempt))
                    continue
                r.raise_for_status()
                body = r.json()
                if body.get("errors"):
                    raise RuntimeError(json.dumps(body["errors"], ensure_ascii=False))
                raw = body["data"]["productSearch"]
                items = [x for x in (self._normalize_item(e) for e in raw.get("items") or []) if x]
                page_info = raw.get("page_info") or {}
                total_pages = int(page_info.get("total_pages") or 1)
                if self.REQUEST_DELAY_SECONDS:
                    time.sleep(self.REQUEST_DELAY_SECONDS)
                return {"items": items, "has_more": page < total_pages}
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(0.75 * (2 ** attempt))
        raise RuntimeError(f"Super99 request failed for {query!r}, page {page}: {last_error}")
