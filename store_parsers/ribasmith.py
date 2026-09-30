from __future__ import annotations

import json
import time
from urllib.parse import quote_plus

from matcher_core import PRICE_BASIS
from .base import BaseStoreParser


class RibaSmithParser(BaseStoreParser):
    """Riba Smith search adapter.

    Fetch the search page's Next.js/RSC data without a deployment-specific
    Next-Action ID. Products may be nested in the page's ``initialData`` or
    returned directly as:

        {"ok": true, "productos": [{...}, ...], "marcas": [...], "keywords": [...]}

    This parser deliberately isolates that transport/shape from the rest of the
    price robot and returns the same normalized product dictionary as every
    other store adapter.
    """

    store_id = "ribasmith"
    display_name = "Riba Smith"

    SEARCH_URL = "https://www.ribasmith.com/search"
    MAX_PAGES = 1

    @property
    def max_pages(self) -> int:
        return self.MAX_PAGES

    def _headers(self):
        h = super()._headers()
        h.update({
            "accept": "text/x-component,*/*;q=0.9",
            "referer": "https://www.ribasmith.com/",
            # Request the full Flight response. A router prefetch can return
            # only a loading shell, without the search page's product data.
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
    def _extract_payload(cls, text: str) -> dict:
        """Find products in direct JSON or nested Flight component props.

        Flight record IDs and component nesting change between deployments;
        neither is part of the product schema we depend on.
        """
        def find_products(value):
            if isinstance(value, dict):
                if isinstance(value.get("productos"), list):
                    return value
                # Prefer the search page's data over other component props.
                if "initialData" in value:
                    found = find_products(value["initialData"])
                    if found is not None:
                        return found
                children = value.values()
            elif isinstance(value, list):
                children = value
            else:
                return None
            for child in children:
                found = find_products(child)
                if found is not None:
                    return found
            return None

        try:
            found = find_products(json.loads(str(text)))
            if found is not None:
                return found
        except json.JSONDecodeError:
            pass

        for raw_line in str(text).splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            _, payload = line.split(":", 1)
            payload = payload.strip()
            if not payload.startswith(("{", "[")):
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            found = find_products(obj)
            if found is not None:
                return found

        return {}

    def _normalize_product(self, product: dict) -> dict | None:
        name = str(product.get("nombre") or product.get("detalle") or "").strip()
        sku = str(product.get("sku") or product.get("item") or product.get("id") or "").strip()
        if not name or not sku:
            return None

        # Riba's response exposes all useful price forms directly. ``precio`` /
        # ``precio_base`` are the stable shelf/list values; ``preciofinal`` and
        # ``precio_calculo`` represent what should actually be paid now.
        regular = self._as_float(product.get("precio_base"))
        if regular is None:
            regular = self._as_float(product.get("precio"))

        final = self._as_float(product.get("preciofinal"))
        if final is None:
            final = self._as_float(product.get("precio_calculo"))
        if final is None:
            final = self._as_float(product.get("preciooferta"))
        if final is None:
            final = regular
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

        attrs = {
            "size": product.get("size"),
            "brand": product.get("marca"),
            "detail": product.get("detalle"),
            "pack": product.get("pack"),
            "inventory": product.get("inv"),
            "weighted sku": product.get("skupeso"),
        }
        attrs = {k: v for k, v in attrs.items() if v not in (None, "")}

        # A stable per-product path was not present in the supplied payload, so
        # link to the search result that produced this candidate for auditing.
        url = f"{self.SEARCH_URL}?q={quote_plus(name)}"

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

        params = {"q": query}
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
                payload = self._extract_payload(r.text)
                if payload.get("ok") is False:
                    raise RuntimeError("Riba Smith search reported a failure")
                products = payload.get("productos") or []
                items = [x for x in (self._normalize_product(p) for p in products) if x]

                if not items and products:
                    raise RuntimeError("Riba Smith response contained products but none could be normalized")
                if not payload:
                    raise RuntimeError("Could not find the Riba Smith 'productos' payload in the response")

                return {"items": items, "has_more": False}

            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(0.75 * (2 ** attempt))

        raise RuntimeError(f"Riba Smith request failed for {query!r}: {last_error}")
