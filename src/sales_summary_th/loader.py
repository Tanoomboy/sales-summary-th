"""Read CSV / Excel files and map columns (Thai or English headers)."""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

# canonical field -> header aliases (lower-case, spaces removed)
ALIASES = {
    "date": ["date", "day", "วันที่", "วัน", "วันที่ขาย", "orderdate", "saledate", "วันเดือนปี",
             "datetime", "timestamp", "วันที่เวลา", "วันเวลา"],
    "time": ["time", "เวลา", "เวลาขาย", "hour", "ชั่วโมง"],
    "product": ["product", "item", "productname", "itemname", "menu", "sku", "สินค้า", "ชื่อสินค้า",
                "รายการ", "รายการสินค้า", "เมนู"],
    "qty": ["qty", "quantity", "units", "จำนวน", "จำนวนชิ้น", "ชิ้น", "จำนวนที่ขาย", "หน่วย"],
    "amount": ["amount", "total", "sales", "revenue", "net", "netsales", "ยอด", "ยอดขาย", "ยอดเงิน",
               "ราคารวม", "รวม", "รวมเงิน", "ยอดสุทธิ", "บาท"],
    "price": ["price", "unitprice", "ราคา", "ราคาต่อหน่วย", "ราคาต่อชิ้น"],
    "branch": ["branch", "store", "shop", "location", "สาขา", "ร้าน"],
    "channel": ["channel", "platform", "ช่องทาง", "ช่องทางขาย", "แพลตฟอร์ม"],
}


def _norm_header(h: str) -> str:
    return re.sub(r"[\s_\-\.()]+", "", (h or "").strip().lower())


def map_columns(headers: list[str]) -> dict[str, str]:
    """Return {canonical: original_header} for headers we recognise."""
    mapping: dict[str, str] = {}
    normed = {h: _norm_header(h) for h in headers}
    for canon, aliases in ALIASES.items():
        # exact alias first, then "starts with alias" (e.g. "ยอดขาย(บาท)")
        for h, n in normed.items():
            if h in mapping.values():
                continue
            if n in aliases:
                mapping[canon] = h
                break
        else:
            for h, n in normed.items():
                if h in mapping.values():
                    continue
                if any(n.startswith(a) for a in aliases if len(a) >= 3):
                    mapping[canon] = h
                    break
    return mapping


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp874", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_table(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (headers, rows) where every cell is a string."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return _read_excel(path)
    if suffix == ".xls":
        raise ValueError("ไฟล์ .xls รุ่นเก่ายังไม่รองรับ กรุณาบันทึกเป็น .xlsx หรือ .csv ก่อน")
    text = _decode(path.read_bytes())
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = list(r) + [""] * (len(headers) - len(r))
        out.append({h: (r[i] or "").strip() for i, h in enumerate(headers)})
    return headers, out


def _cell_to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        if v.time() == dt.time(0, 0):
            return v.date().isoformat()
        return v.isoformat(sep=" ")
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _read_excel(path: Path):
    try:
        import openpyxl
    except ImportError as e:  # pragma: no cover
        raise ValueError("ต้องติดตั้ง openpyxl เพื่ออ่าน Excel: pip install openpyxl") from e
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [[_cell_to_str(c) for c in r] for r in ws.iter_rows(values_only=True)]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = list(r) + [""] * (len(headers) - len(r))
        out.append({h: r[i] for i, h in enumerate(headers)})
    return headers, out


# ---------- value parsing ----------

def parse_number(s: str) -> float | None:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1]
    t = t.replace("฿", "").replace("บาท", "").replace("บ.", "").replace(",", "").replace(" ", "")
    t = t.replace("\u2212", "-")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


_DATE_PATTERNS = [
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})"), "ymd"),
    (re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})"), "ymd"),
    (re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"), "dmy"),
    (re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})(?!\d)"), "dmy2"),
]


def parse_date(s: str) -> dt.date | None:
    """Accept 2026-10-17, 17/10/2026, 17/10/2569 (พ.ศ.), 17-10-69. Day-first for slashes."""
    t = (s or "").strip()
    for rx, kind in _DATE_PATTERNS:
        m = rx.match(t)
        if not m:
            continue
        a, b, c = (int(x) for x in m.groups())
        if kind == "ymd":
            y, mo, d = a, b, c
        elif kind == "dmy":
            d, mo, y = a, b, c
        else:
            d, mo, y = a, b, c
            y = y + 2500 if y >= 40 else y + 2000  # 69 -> 2569 (พ.ศ.), 26 -> 2026
        if y > 2400:  # Buddhist Era
            y -= 543
        try:
            return dt.date(y, mo, d)
        except ValueError:
            return None
    return None


_TIME_RX = re.compile(r"(?:^|[\sT])(\d{1,2})[:.](\d{2})(?::\d{2})?")


def parse_hour(s: str) -> int | None:
    t = (s or "").strip()
    if not t:
        return None
    m = _TIME_RX.search(" " + t)
    if m:
        h = int(m.group(1))
        return h if 0 <= h <= 23 else None
    if t.isdigit() and 0 <= int(t) <= 23:
        return int(t)
    return None


@dataclass
class Sale:
    row: int            # 1-based row number in the file (header = row 1)
    date: dt.date
    hour: int | None
    product: str
    qty: float | None
    amount: float
    branch: str = ""
    channel: str = ""
    raw_key: tuple = field(default=(), repr=False)


@dataclass
class LoadResult:
    sales: list[Sale]
    mapping: dict[str, str]
    skipped_rows: list[int]
    warnings: list[str]
