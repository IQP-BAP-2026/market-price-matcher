"""Stream the large, values-only Candidates sheet without millions of Cell objects."""
from io import BytesIO
import math
from pathlib import Path
import re
import tempfile
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from openpyxl.utils import get_column_letter


def prepare_candidates(ws, table, style_sheet):
    """Keep only a width/style sample in the otherwise normal workbook.

    `table` is a results_format.Table: Spanish headers, rows converted on the fly, number formats and
    the columns to hide."""
    from results_format import finish_columns
    ws.append(table.headers)
    for row in table[:149]:
        ws.append(row)
    style_sheet(ws)
    finish_columns(ws, table)
    for col, fmt in enumerate(table.formats, 1):
        ws.cell(2, col).number_format = fmt


def save_with_candidates(wb, destination, rows, progress=None, sheet="Candidatos"):
    """Preserve normal-sheet styles/hooks; stream candidate XML into the XLSX ZIP.

    The staging file is replaced only after a successful save, so an export
    failure cannot truncate an existing results workbook.
    """
    destination = Path(destination)
    ws = wb[sheet]
    columns = [get_column_letter(i) for i in range(1, ws.max_column + 1)]
    styles = [ws.cell(2, i).style_id for i in range(1, len(columns) + 1)]
    sheet_path = f"xl/worksheets/sheet{wb.sheetnames.index(sheet) + 1}.xml"
    template = BytesIO()
    wb.save(template)
    extent = f"A1:{columns[-1]}{len(rows) + 1}"
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".xlsx.tmp", delete=False) as temp:
        staging = Path(temp.name)
    try:
        with ZipFile(template) as source, ZipFile(staging, "w", ZIP_DEFLATED, compresslevel=1, allowZip64=True) as target:
            for info in source.infolist():
                if info.filename != sheet_path:
                    target.writestr(info.filename, source.read(info.filename))
                    continue
                xml = source.read(sheet_path).decode("utf-8")
                prefix, data = xml.split("<sheetData>", 1)
                data, suffix = data.split("</sheetData>", 1)
                header = re.search(r"<row\b.*?</row>", data, re.S).group(0)
                prefix = re.sub(r'<dimension ref="[^"]+"', f'<dimension ref="{extent}"', prefix)
                # keep the filter's columns (hidden columns may be left out of it); extend it to every row
                suffix = re.sub(r'<autoFilter ref="([A-Z]+)1:([A-Z]+)\d+"',
                                lambda m: f'<autoFilter ref="{m[1]}1:{m[2]}{len(rows) + 1}"', suffix)
                with target.open(sheet_path, "w", force_zip64=True) as stream:
                    stream.write((prefix + "<sheetData>" + header).encode("utf-8"))
                    batch = []
                    for row_number, row in enumerate(rows, 2):
                        cells = []
                        for col, style, value in zip(columns, styles, row):
                            if value is None:
                                continue
                            ref = f'{col}{row_number}'
                            attr = f' r="{ref}"' + (f' s="{style}"' if style else '')
                            if isinstance(value, bool):
                                cell = f'<c{attr} t="b"><v>{int(value)}</v></c>'
                            elif isinstance(value, (int, float)):
                                if not math.isfinite(value):
                                    continue
                                cell = f'<c{attr} t="n"><v>{value:.16g}</v></c>'
                            elif isinstance(value, str):
                                text = escape(value[:32767]).replace("\r", "&#13;")
                                cell = f'<c{attr} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'
                            else:
                                raise TypeError(f"Unsupported candidate value: {type(value).__name__}")
                            cells.append(cell)
                        batch.append(f'<row r="{row_number}">' + ''.join(cells) + '</row>')
                        if len(batch) >= 1000:
                            stream.write(''.join(batch).encode("utf-8"))
                            batch.clear()
                        if progress and (row_number - 1) % 50000 == 0:
                            progress(row_number - 1, len(rows))
                    stream.write((''.join(batch) + "</sheetData>" + suffix).encode("utf-8"))
        staging.replace(destination)
    finally:
        staging.unlink(missing_ok=True)
