from __future__ import annotations

import json
import time
from urllib.parse import quote

from matcher_core import PRICE_BASIS
from .base import BaseStoreParser


class ReyParser(BaseStoreParser):
    """Supermercados Rey search adapter.

    The supplied ``smrey.com/search?name=...&_rsc=...`` response is a Next.js
    Flight/RSC stream. Product records are self-contained JSON lines whose
    ``__typename`` is ``CatalogProductModel``.
    """

    store_id = "rey"
    display_name = "El Rey"

    SEARCH_URL = "https://www.smrey.com/search"
    BASE_URL = "https://www.smrey.com"
    MAX_PAGES = 1
    # _rsc is a cache-busting/flight parameter in Next.js. The captured value
    # supplied by the user works as a request shape; product search itself is
    # controlled by the ``name`` query parameter.
    RSC_TOKEN = "1e0s3"

    @property
    def max_pages(self) -> int:
        return self.MAX_PAGES

    def _headers(self):
        h = super()._headers()
        h.update({
            "accept": "text/x-component,*/*;q=0.9",
            "referer": "https://www.smrey.com/",
            "rsc": "1",
        })
        return h

    @staticmethod
    def _as_float(value):
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _extract_products(cls, text: str) -> list[dict]:
        """Extract CatalogProductModel objects from a Next Flight stream."""
        products: list[dict] = []
        seen: set[str] = set()

        for raw_line in str(text).splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            _, payload = line.split(":", 1)
            payload = payload.strip()
            if not payload.startswith("{"):
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if not isinstance(obj, dict):
                continue
            if obj.get("__typename") != "CatalogProductModel":
                continue
            sku = str(obj.get("sku") or "").strip()
            name = str(obj.get("name") or "").strip()
            if not sku or not name or sku in seen:
                continue
            seen.add(sku)
            products.append(obj)

        return products

    def _normalize_product(self, product: dict) -> dict | None:
        name = str(product.get("name") or "").strip()
        sku = str(product.get("sku") or "").strip()
        if not name or not sku:
            return None

        final = self._as_float(product.get("price"))
        regular = self._as_float(product.get("previousPrice"))
        if regular is None:
            regular = self._as_float(product.get("priceBeforeTaxes"))
        if regular is None:
            regular = final
        if final is None:
            final = regular

        # ``previousPrice`` is only useful as a list price when it is actually
        # above the live price. Otherwise treat current price as regular too.
        if regular is not None and final is not None and regular < final:
            regular = final

        if PRICE_BASIS == "regular":
            chosen = regular if regular is not None else final
            basis = "regular" if regular is not None else "final fallback"
        else:
            chosen = final if final is not None else regular
            basis = "final" if final is not None else "regular fallback"

        discount_percent = None
        if regular and final is not None and regular > 0 and final < regular:
            discount_percent = (regular - final) / regular * 100.0

        attrs = {
            "brand": product.get("brand"),
            "unit": product.get("unit"),
            # Only expose sub-unit metadata as audit context. Quantity parsing
            # should prefer the product title because the captured response has
            # at least one inconsistent subQty field (e.g. a 9gr title with a
            # subQty value of 0.3).
            "sub unit": product.get("subUnit"),
            "sub quantity": product.get("subQty"),
            "stock": product.get("stock"),
            "available": product.get("isAvailable"),
        }
        attrs = {k: v for k, v in attrs.items() if v not in (None, "")}

        slug = str(product.get("slug") or "").strip()
        url = f"{self.BASE_URL}/product/{quote(slug)}" if slug else f"{self.SEARCH_URL}?name={quote(name)}"

        return {
            "store": self.store_id,
            "store_name": self.display_name,
            "sku": sku,
            "name": name,
            "url": url,
            "attrs": attrs,
            "regular_price": regular,
            "final_price": final,
            "price": chosen,
            "price_basis": basis,
            "discount_percent": discount_percent,
            "currency": "USD",
        }

    def _fetch_page(self, query: str, page: int) -> dict:
        if page != 1:
            return {"items": [], "has_more": False}

        params = {"name": query, "_rsc": self.RSC_TOKEN}
        last_error = None

        for attempt in range(self.max_retries):
            try:
                r = self._session().get(
                    self.SEARCH_URL,
                    params=params,
                    timeout=self.timeout_seconds,
                )

                if r.status_code == 429:
                    last_error = RuntimeError("HTTP 429 rate limited")
                    time.sleep(max(0.5, 1.5 * (2 ** attempt)))
                    continue
                if 500 <= r.status_code < 600:
                    last_error = RuntimeError(f"HTTP {r.status_code}")
                    time.sleep(0.75 * (2 ** attempt))
                    continue

                r.raise_for_status()
                products = self._extract_products(r.text)
                if not products:
                    raise RuntimeError("Could not find CatalogProductModel rows in Rey response")

                # Preserve Rey's availability signal where present. If the site
                # returns an out-of-stock record, keep it out of the pricing set.
                products = [p for p in products if p.get("isAvailable") is not False]
                items = [x for x in (self._normalize_product(p) for p in products) if x]
                return {"items": items, "has_more": False}

            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(0.75 * (2 ** attempt))

        raise RuntimeError(f"El Rey request failed for {query!r}: {last_error}")
