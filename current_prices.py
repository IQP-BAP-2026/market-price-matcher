"""Shared header-based current-price input for comparison and human review.

The current-prices file is the Salesforce price book download. It can be .xlsx, .xls, .csv (any encoding,
"," or ";") or an HTML "Excel" export (see table_files), its header row doesn't have to be the first row,
and it may have any number of extra columns: only the columns below are read. Salesforce keeps one
row per product and price book, so a product can appear several times; only rows of BAP's price book
(STANDARD_PRICEBOOK_ID, in the Pricebook2Id column) are used.
"""
from pathlib import Path

from table_files import is_spreadsheet, load_book, read_text_table, to_number  # noqa: F401  (re-exported)

# BAP's price book in Salesforce. Rows of any other price book are ignored.
STANDARD_PRICEBOOK_ID = "01s41000004hcm1AAA"

# The columns that are read, each under the names it can have (compared without accents, case, spaces
# or punctuation, so "Product Code", "PRODUCTCODE" and "Código de producto" all match).
COLUMN_NAMES = {
    "code": ("ProductCode", "Product Code", "Código de producto", "Codigo del producto", "Código"),
    "price": ("UnitPrice", "Unit Price", "List Price", "Precio de lista", "Precio unitario", "Precio"),
    "id": ("Id", "Price Book Entry ID", "PricebookEntryId", "Pricebook Entry Id"),
    "pricebook": ("Pricebook2Id", "Pricebook2 Id", "Price Book ID", "PricebookId", "Price Book: ID"),
    "name": ("Name", "Product Name", "Nombre del producto", "Nombre"),
}


def _key(text):
    import re
    import unicodedata
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", text)


_ALIASES = {field: [_key(n) for n in names] for field, names in COLUMN_NAMES.items()}


def _columns(headers):
    """{field: column index} for the fields found in a header row. Exact names are matched before the
    shorter fallbacks ("Precio", "Nombre"), and one column is never used for two fields."""
    keys = [_key(h) for h in headers]
    found, used = {}, set()
    for field, aliases in _ALIASES.items():
        for alias in aliases:
            index = next((i for i, k in enumerate(keys) if k == alias and i not in used), None)
            if index is not None:
                found[field] = index
                used.add(index)
                break
    return found


def _same_salesforce_id(value, wanted):
    """Salesforce Ids come in a 15-character and an 18-character form (the 18 adds a checksum)."""
    value, wanted = str(value or "").strip(), str(wanted or "").strip()
    if not value or not wanted:
        return False
    return value == wanted or value[:15] == wanted[:15] and (len(value) == 15 or len(wanted) == 15)


def _read_table(path, max_header_row=30):
    """(headers, data rows, decimal_comma) from the sheet whose header row has the code and price columns."""
    book = load_book(path)
    try:
        best = None
        for name in book.sheetnames:
            sheet = book[name]
            rows = sheet.iter_rows(values_only=True)
            for number, row in enumerate(rows, start=1):
                if number > max_header_row:
                    break
                columns = _columns(row)
                if "code" in columns and "price" in columns:
                    data = [list(r) for r in rows]
                    return list(row), data, getattr(sheet, "decimal_comma", False)
                if best is None and number == 1:
                    best = list(row)
        return best or [], [], False
    finally:
        book.close()


def product_code(value):
    if value is None:
        return ""
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value).strip()


def money(value, decimal_comma=False):
    """A price from a cell: 5.02, "$5.02", "1,234.50" — or, with decimal_comma (Spanish-format CSV),
    "5,02" and "1.234,50"."""
    return to_number(value, decimal_comma)


def read_current_rows(path, pricebook_id=STANDARD_PRICEBOOK_ID):
    """The current price of each product in BAP's price book, from a Salesforce download.

    Each row is {"Código de producto", "Nombre del producto", "Precio de lista", "Id", "Pricebook2Id"}
    (plus "ProductCode"/"UnitPrice"/"Name" copies). Ids are PricebookEntry Ids from the input, never
    product codes. Prices are never taken by column position."""
    headers, values, decimal_comma = _read_table(Path(path))
    columns = _columns(headers)
    if "code" not in columns or "price" not in columns:
        raise ValueError("Current prices require ProductCode and UnitPrice headers "
                         "(legacy Código de producto / Precio de lista also supported).")

    def get(row, field):
        index = columns.get(field)
        return row[index] if index is not None and index < len(row) else None

    rows, codes, ids = [], set(), set()
    skipped_other_books = 0
    for row_number, values_row in enumerate(values, start=2):
        if not any(value not in (None, "") for value in values_row):
            continue
        if "pricebook" in columns and not _same_salesforce_id(get(values_row, "pricebook"), pricebook_id):
            skipped_other_books += 1
            continue
        key = product_code(get(values_row, "code"))
        if not key:
            raise ValueError(f"Current-prices row {row_number} is missing ProductCode.")
        if key in codes:
            raise ValueError(f"Multiple current-price entries for ProductCode {key}"
                             + (f" in price book {pricebook_id}." if "pricebook" in columns else
                                ". Download the price book with the Pricebook2Id column, or filter the file "
                                "to one price-book entry per product."))
        codes.add(key)
        identifier = str(get(values_row, "id") or "").strip()
        if identifier and identifier in ids:
            raise ValueError(f"Duplicate Salesforce Id in current prices: {identifier}")
        if identifier:
            ids.add(identifier)
        raw_price = get(values_row, "price")
        price = money(raw_price, decimal_comma)
        if raw_price not in (None, "") and (price is None or price < 0):
            raise ValueError(f"Invalid UnitPrice for ProductCode {key}: {raw_price}")
        name = get(values_row, "name")
        rows.append({"Código de producto": key, "Nombre del producto": name, "Precio de lista": price,
                     "Id": identifier, "Pricebook2Id": str(get(values_row, "pricebook") or "").strip(),
                     "ProductCode": key, "Name": name, "UnitPrice": price})
    if "pricebook" in columns and not rows and skipped_other_books:
        raise ValueError(f"No rows of price book {pricebook_id} were found in the current-prices file "
                         f"(Pricebook2Id column).")
    return rows


def read_current_prices(path):
    return {row["Código de producto"]: row["Precio de lista"] for row in read_current_rows(path)
            if row["Precio de lista"] is not None}


# ---------------------------------------------------------------------------
# Required columns — checked before a search starts (window and command line)
# ---------------------------------------------------------------------------
# Every column of the products sheet that the matcher reads.
PRODUCT_REQUIRED_COLUMNS = (
    "Código de producto", "Nombre del producto", "Unidad de Peso en KG", "Sub-familia de Productos",
    "Linea de producto", "Familia de productos", "Descripción del producto", "Grupo de Productos",
    "Categoria RepTrim",
)
# Current prices must be the Salesforce pricebook download: the reviewed
# prices are exported by Salesforce Id, so a file without the Id column (like the old BAP current_prices.xlsx)
# is refused. (Salesforce name, older BAP name) — either name is accepted for code and price.
CURRENT_REQUIRED_COLUMNS = (("ProductCode", "Código de producto"), ("Id",), ("UnitPrice", "Precio de lista"))


def _norm(value):
    from matcher_core import normalize
    return normalize(value)


def product_columns_missing(path):
    """Required columns missing from the products workbook ([] = fine). The robot reads the sheet/header row
    that has the most of them (a MASTER-yyyy sheet first), like it does when searching."""
    import re
    wanted = {_norm(c): c for c in PRODUCT_REQUIRED_COLUMNS}
    wb = load_book(path)   # .xlsx, .xls, .csv or HTML export
    try:
        names = [s for s in wb.sheetnames if re.fullmatch(r"MASTER-\d{4}", s, re.I)]
        names += [s for s in wb.sheetnames if s not in names]
        best = set()
        for name in names:
            for row in wb[name].iter_rows(max_row=30, values_only=True):
                found = {_norm(v) for v in row if v not in (None, "")} & set(wanted)
                if len(found) > len(best):
                    best = found
            if len(best) == len(wanted):
                break
    finally:
        wb.close()
    return [wanted[k] for k in wanted if k not in best]


def current_prices_columns_missing(path):
    """Required columns missing from the current-prices file ([] = fine), as 'ProductCode / Código de producto'.
    The header row is found the same way the prices are read (any row near the top, any extra columns)."""
    headers, _rows, _comma = _read_table(Path(path))
    columns = _columns(headers)
    needed = (("code", "ProductCode / Código de producto"), ("id", "Id"), ("price", "UnitPrice / Precio de lista"))
    return [label for field, label in needed if field not in columns]
