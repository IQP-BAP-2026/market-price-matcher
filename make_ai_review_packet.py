from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

STOPWORDS = {
    'de','del','la','el','los','las','y','en','con','para','por','caja','bolsa','paquete','pack',
    'unidad','unidades','unid','uds','und','bap','empaque','marca','marcas','sabor','sabores',
    'variado','variada','variados','variadas','surtido','surtida','surtidos','surtidas','aprox',
    'kg','kgs','kilo','kilos','g','gr','gramos','lb','lbs','oz','ml','l','lt','litro','litros','x'
}


def norm(value: Any) -> str:
    s = '' if value is None else str(value)
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def tokens(value: Any) -> set[str]:
    out = set()
    for w in norm(value).split():
        if w in STOPWORDS or len(w) <= 1:
            continue
        if len(w) > 4 and w.endswith('s') and w != 'arroz':
            w = w[:-1]
        out.add(w)
    return out


def fnum(value: Any) -> float | None:
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            v = float(value)
            return v if math.isfinite(v) else None
        except Exception:
            return None
    try:
        return float(str(value).replace('$','').replace(',','').strip())
    except Exception:
        return None


def compact_context(product: dict[str, Any], max_chars: int = 180) -> str:
    parts = []
    for key in ('linea', 'familia', 'subfamilia'):
        v = product.get(key)
        if v and norm(v) not in {norm(x) for x in parts}:
            parts.append(str(v).strip())

    desc = str(product.get('description') or '').strip()
    if desc:
        # Only keep description when it adds words not already in the target name/categories.
        base = ' '.join([str(product.get('name') or '')] + parts)
        extra = tokens(desc) - tokens(base)
        if extra:
            parts.append(desc)

    text = ' | '.join(parts)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + '…'
    return text


def candidate_rank(target_name: str, target_qty: float | None, row: dict[str, Any]) -> float:
    name = str(row.get('candidate_name') or '')
    overlap = len(tokens(target_name) & tokens(name)) / max(1, len(tokens(target_name)))
    size_score = 0.0
    kg = row.get('kg')
    if target_qty and kg and target_qty > 0 and kg > 0:
        ratio = kg / target_qty
        size_score = max(0.0, 1.0 - abs(math.log(ratio)) / 3.0)
    # Name overlap dominates; size helps prefer comparable retail packs.
    return overlap * 3.0 + size_score


def main() -> None:
    ap = argparse.ArgumentParser(
        description='Create a compact AI review packet from a price-robot performance workbook.'
    )
    ap.add_argument('input', type=Path, help='Performance analysis .xlsx')
    ap.add_argument('-o', '--output', type=Path, default=Path('ai_review_packet.jsonl'))
    ap.add_argument('--store', default='super99', help='Store name to use if Candidates has no Store column.')
    ap.add_argument('--max-candidates', type=int, default=12,
                    help='Maximum candidates per product (default 12). Use 0 for all candidates.')
    ap.add_argument('--all-candidates', action='store_true', help='Include all candidate rows.')
    args = ap.parse_args()

    wb = load_workbook(args.input, read_only=True, data_only=True)
    if 'Product Analysis' not in wb.sheetnames or 'Candidates' not in wb.sheetnames:
        raise ValueError('Workbook must contain Product Analysis and Candidates sheets.')

    pws = wb['Product Analysis']
    cws = wb['Candidates']

    ph = [c.value for c in next(pws.iter_rows(min_row=1, max_row=1))]
    pi = {str(h): i for i, h in enumerate(ph) if h is not None}

    def pget(row, *names):
        for n in names:
            if n in pi:
                return row[pi[n]]
        return None

    products: dict[Any, dict[str, Any]] = {}
    code_to_row: dict[str, Any] = {}

    for row in pws.iter_rows(min_row=2, values_only=True):
        spreadsheet_row = pget(row, 'Spreadsheet Row')
        code = pget(row, 'Código de producto')
        name = pget(row, 'Nombre del producto')
        if spreadsheet_row is None or not name:
            continue
        product = {
            'row': spreadsheet_row,
            'code': '' if code is None else str(code).strip(),
            'name': str(name).strip(),
            'qty': fnum(pget(row, 'Target Quantity kg', 'Unidad de Peso en KG')),
            'current': fnum(pget(row, 'Current BAP Price')),
            'linea': pget(row, 'Linea de producto'),
            'familia': pget(row, 'Familia de productos'),
            'subfamilia': pget(row, 'Sub-familia de Productos'),
            'description': pget(row, 'Descripción del producto'),
        }
        product['ctx'] = compact_context(product)
        products[spreadsheet_row] = product
        if product['code']:
            code_to_row[product['code']] = spreadsheet_row

    ch = [c.value for c in next(cws.iter_rows(min_row=1, max_row=1))]
    ci = {str(h): i for i, h in enumerate(ch) if h is not None}

    def cget(row, *names):
        for n in names:
            if n in ci:
                return row[ci[n]]
        return None

    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for idx, row in enumerate(cws.iter_rows(min_row=2, values_only=True), start=2):
        spreadsheet_row = cget(row, 'Spreadsheet Row')
        if spreadsheet_row not in products:
            code = cget(row, 'Código de producto')
            spreadsheet_row = code_to_row.get('' if code is None else str(code).strip())
        if spreadsheet_row not in products:
            continue

        chosen = fnum(cget(row, 'Chosen Price'))
        kg = fnum(cget(row, 'Normalized kg', 'Candidate Unit kg'))
        ppkg = fnum(cget(row, 'Price / kg'))
        if ppkg is None and chosen is not None and kg and kg > 0:
            ppkg = chosen / kg

        store = cget(row, 'Store', 'Store Name') or args.store
        cid = cget(row, 'SKU')
        if cid in (None, ''):
            cid = f'r{idx}'

        cand = {
            'store': str(store).strip(),
            'id': str(cid).strip(),
            'candidate_name': str(cget(row, 'Candidate Product') or '').strip(),
            'kg': kg,
            'price': chosen,
            'ppkg': ppkg,
        }
        if not cand['candidate_name']:
            continue
        grouped[spreadsheet_row].append(cand)

    max_candidates = 0 if args.all_candidates else max(0, args.max_candidates)

    schema = {
        'schema': 'bap-ai-review-v1',
        'product_fields': {
            'id': 'product code (or spreadsheet row fallback)',
            'n': 'BAP target product name',
            'q': 'target quantity in kg; project rule 1 L = 1 kg',
            'cur': 'current BAP price',
            'ctx': 'short product context/category/description when useful',
            'c': 'candidate arrays: [store, candidate_id, candidate_name, normalized_kg, chosen_price, price_per_kg]'
        },
        'review_goal': (
            'For each product, independently decide which candidates are representative everyday matches. '
            'Reject specialty/subtype mismatches and implausible price/size outliers. For varied targets, accept '
            'a reasonable range within the category. Compute representative market price/kg, then BAP estimate '
            '= market price/kg * target kg * 0.20, plus percent difference vs current BAP price.'
        )
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    product_count = 0
    candidate_count = 0
    with args.output.open('w', encoding='utf-8') as f:
        f.write(json.dumps(schema, ensure_ascii=False, separators=(',', ':')) + '\n')
        for spreadsheet_row, p in products.items():
            cands = grouped.get(spreadsheet_row, [])
            # De-duplicate exact same store/name/size/price entries.
            unique = {}
            for c in cands:
                key = (norm(c['store']), norm(c['candidate_name']), round(c['kg'], 4) if c['kg'] else None,
                       round(c['price'], 4) if c['price'] is not None else None)
                unique.setdefault(key, c)
            cands = list(unique.values())

            if max_candidates and len(cands) > max_candidates:
                ranked = sorted(
                    cands,
                    key=lambda c: candidate_rank(p['name'], p['qty'], c),
                    reverse=True,
                )
                # Keep strongest matches but preserve one cheap and one expensive plausible candidate for price sanity.
                selected = ranked[:max_candidates]
                selected_ids = {id(x) for x in selected}
                priced = [x for x in cands if x['ppkg'] is not None and x['ppkg'] > 0]
                extremes = []
                if priced:
                    extremes = [min(priced, key=lambda x: x['ppkg']), max(priced, key=lambda x: x['ppkg'])]
                for e in extremes:
                    if id(e) not in selected_ids:
                        # Replace the lowest-ranked selection rather than exceed the cap.
                        selected[-1] = e
                        selected_ids.add(id(e))
                cands = selected

            pid = p['code'] or f'row:{spreadsheet_row}'
            obj = {
                'id': pid,
                'n': p['name'],
                'q': round(p['qty'], 6) if p['qty'] is not None else None,
                'cur': round(p['current'], 4) if p['current'] is not None else None,
                'ctx': p['ctx'] or None,
                'c': [
                    [
                        c['store'], c['id'], c['candidate_name'],
                        round(c['kg'], 6) if c['kg'] is not None else None,
                        round(c['price'], 4) if c['price'] is not None else None,
                        round(c['ppkg'], 4) if c['ppkg'] is not None else None,
                    ]
                    for c in cands
                ]
            }
            f.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n')
            product_count += 1
            candidate_count += len(cands)

    wb.close()
    print(f'Wrote {args.output}')
    print(f'Products: {product_count:,}')
    print(f'Candidates included: {candidate_count:,}')
    print(f'Max candidates/product: {"ALL" if max_candidates == 0 else max_candidates}')


if __name__ == '__main__':
    main()
