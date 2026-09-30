"""Shared header-based current-price input for comparison and human review."""
import csv
import math
from pathlib import Path


def product_code(value):
    if value is None:
        return ""
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value).strip()


def money(value):
    try:
        if isinstance(value, bool):
            return None
        result = float(str(value).replace("$", "").replace(",", "").strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def read_current_rows(path):
    """Read Salesforce CSV/XLSX or legacy BAP headers; never infer price by position.

    Preserve source columns and add canonical BAP names for existing consumers.
    IDs are PricebookEntry IDs from the input, never product codes or product IDs.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            headers = next(reader, [])
            values = list(reader)
    else:
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            iterator = wb.active.iter_rows(values_only=True)
            headers = next(iterator, ())
            values = list(iterator)
        finally:
            wb.close()
    headers = [str(h or "").strip() for h in headers]
    if len(set(h.casefold() for h in headers if h)) != len([h for h in headers if h]):
        raise ValueError("Duplicate column headers in current-prices file.")
    fields = {h.casefold(): h for h in headers}
    code_field = fields.get("productcode") or fields.get("código de producto")
    price_field = fields.get("unitprice") or fields.get("precio de lista")
    if not code_field or not price_field:
        raise ValueError("Current prices require ProductCode and UnitPrice headers (legacy Código de producto / Precio de lista also supported).")
    name_field = fields.get("name") or fields.get("nombre del producto")
    id_field = fields.get("id")
    rows, codes, ids = [], set(), set()
    for row_number, values_row in enumerate(values, start=2):
        if not any(value not in (None, "") for value in values_row):
            continue
        row = dict(zip(headers, values_row))
        key = product_code(row.get(code_field))
        if not key:
            raise ValueError(f"Current-prices row {row_number} is missing ProductCode.")
        if key in codes:
            raise ValueError(f"Multiple current-price entries for ProductCode {key}. Filter the input to one pricebook entry per product.")
        codes.add(key)
        identifier = str(row.get(id_field) or "").strip()
        if identifier and identifier in ids:
            raise ValueError(f"Duplicate Salesforce Id in current prices: {identifier}")
        if identifier:
            ids.add(identifier)
        raw_price = row.get(price_field)
        price = money(raw_price)
        if raw_price not in (None, "") and (price is None or price < 0):
            raise ValueError(f"Invalid UnitPrice for ProductCode {key}: {raw_price}")
        row.update({"Código de producto": key, "Nombre del producto": row.get(name_field),
                    "Precio de lista": price, "Id": identifier})
        rows.append(row)
    return rows


def read_current_prices(path):
    return {row["Código de producto"]: row["Precio de lista"] for row in read_current_rows(path)
            if row["Precio de lista"] is not None}
