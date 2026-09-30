from __future__ import annotations

import json
import time
from urllib.parse import quote

from matcher_core import PRICE_BASIS
from .base import BaseStoreParser


class SuperXtraParser(BaseStoreParser):
    store_id = "superxtra"
    display_name = "Super Xtra"

    BASE_URL = "https://www.superxtra.com"
    # The provided VTEX runtime response contains 30 productSearch results.
    # We intentionally use one runtime page for now; adding VTEX pagination later
    # only requires changing this parser, not the matching/orchestration code.
    MAX_PAGES = 1
    PICK_RUNTIME = (
        "appsEtag,blocks,blocksTree,components,contentMap,extensions,messages,"
        "page,pages,query,queryData,route,runtimeMeta,settings"
    )

    @property
    def max_pages(self) -> int:
        return self.MAX_PAGES

    def _headers(self):
        h = super()._headers()
        h.update({
            "accept": "application/json,text/plain,*/*",
            "referer": "https://www.superxtra.com/",
        })
        return h

    @staticmethod
    def _offer_for_product(product: dict) -> dict:
        # Prefer the default seller and a SKU that is actually available.
        best = None
        for item in product.get("items") or []:
            for seller in item.get("sellers") or []:
                offer = seller.get("commertialOffer") or {}
                price = offer.get("Price")
                qty = offer.get("AvailableQuantity")
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                available = True
                try:
                    available = float(qty) > 0
                except (TypeError, ValueError):
                    pass
                candidate = (seller.get("sellerDefault") is True, available, item, seller, offer)
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
        return {} if best is None else {"item": best[2], "seller": best[3], "offer": best[4]}

    @staticmethod
    def _product_attrs(product: dict, item: dict) -> dict[str, object]:
        attrs: dict[str, object] = {}
        for prop in product.get("properties") or []:
            name = str(prop.get("name", "")).strip().lower()
            vals = prop.get("values")
            if name and vals:
                attrs[name] = ", ".join(map(str, vals)) if isinstance(vals, list) else vals
        for attr in item.get("attributes") or []:
            name = str(attr.get("name", "")).strip().lower()
            if name:
                attrs[name] = attr.get("value")
        # Include SKU variation text because some VTEX products put size there.
        for var in item.get("variations") or []:
            name = str(var.get("name", "")).strip().lower()
            vals = var.get("values")
            if name and vals:
                attrs[name] = ", ".join(map(str, vals)) if isinstance(vals, list) else vals
        if item.get("measurementUnit"):
            attrs["measurement unit"] = item.get("measurementUnit")
        if item.get("unitMultiplier") not in (None, ""):
            attrs["unit multiplier"] = item.get("unitMultiplier")
        return attrs

    def _normalize_product(self, product: dict) -> dict | None:
        choice = self._offer_for_product(product)
        if not choice:
            return None
        item = choice["item"]
        offer = choice["offer"]
        name = str(item.get("nameComplete") or product.get("productName") or item.get("name") or "").strip()
        sku = str(item.get("itemId") or product.get("productId") or "").strip()
        if not name or not sku:
            return None

        regular = offer.get("ListPrice")
        final = offer.get("Price")
        try:
            regular = float(regular) if regular is not None else None
        except (TypeError, ValueError):
            regular = None
        try:
            final = float(final) if final is not None else None
        except (TypeError, ValueError):
            final = None

        if regular is None:
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

        link = product.get("link") or ""
        if link and str(link).startswith("/"):
            link = self.BASE_URL + str(link)

        return {
            "store": self.store_id,
            "store_name": self.display_name,
            "sku": sku,
            "name": name,
            "url": link,
            "attrs": self._product_attrs(product, item),
            "regular_price": regular,
            "final_price": final,
            "price": chosen,
            "price_basis": basis,
            "discount_percent": discount_percent,
            "currency": "USD",
        }

    @staticmethod
    def _extract_product_search(runtime: dict) -> list[dict]:
        for entry in runtime.get("queryData") or []:
            data = entry.get("data")
            if not data:
                continue
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    continue
            if isinstance(data, dict) and "productSearch" in data:
                return (data.get("productSearch") or {}).get("products") or []
        return []

    def _fetch_page(self, query: str, page: int) -> dict:
        if page != 1:
            return {"items": [], "has_more": False}

        # This matches the runtime URL supplied by the user. Using it keeps the
        # Xtra-specific transport isolated in this parser and makes replacement
        # with a lower-level VTEX endpoint straightforward later.
        slug = quote(str(query).strip(), safe="")
        url = f"{self.BASE_URL}/{slug}"
        params = {
            "_q": query,
            "map": "ft",
            "__pickRuntime": self.PICK_RUNTIME,
            "__device": "phone",
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                r = self._session().get(url, params=params, timeout=self.timeout_seconds)
                if r.status_code == 429:
                    time.sleep(max(0.5, 1.5 * (2 ** attempt)))
                    last_error = RuntimeError("HTTP 429 rate limited")
                    continue
                if 500 <= r.status_code < 600:
                    last_error = RuntimeError(f"HTTP {r.status_code}")
                    time.sleep(0.75 * (2 ** attempt))
                    continue
                r.raise_for_status()
                runtime = r.json()
                products = self._extract_product_search(runtime)
                items = [x for x in (self._normalize_product(p) for p in products) if x]
                return {"items": items, "has_more": False}
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(0.75 * (2 ** attempt))
        raise RuntimeError(f"SuperXtra request failed for {query!r}: {last_error}")
