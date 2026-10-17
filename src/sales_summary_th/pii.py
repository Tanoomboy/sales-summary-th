"""PII guard: drop columns that look personal and mask personal values in the rest.

Detects: customer names (by header, or Thai/English name titles), Thai phone numbers,
bank account numbers, 13-digit Thai ID numbers, e-mail addresses.
This is a best-effort safety net, not a guarantee. Always look at your data first.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MASK = "[ซ่อน]"

# header keywords (normalised: lower-case, no spaces/_/-)
_PII_HEADER_WORDS = [
    "ชื่อลูกค้า", "ลูกค้า", "ชื่อผู้ซื้อ", "ผู้ซื้อ", "ชื่อผู้รับ", "ผู้รับ", "ชื่อเล่น", "นามสกุล", "ชื่อจริง",
    "ชื่อ-นามสกุล", "ชื่อนามสกุล", "ชื่อ", "customer", "client", "buyer", "recipient", "fullname",
    "firstname", "lastname", "name",
    "เบอร์", "โทร", "มือถือ", "phone", "tel", "mobile", "contact",
    "บัญชี", "เลขบัญชี", "account", "bank", "ธนาคาร", "พร้อมเพย์", "promptpay",
    "บัตรประชาชน", "เลขบัตร", "idcard", "citizen", "nationalid",
    "email", "อีเมล", "อีเมล์", "ที่อยู่", "address", "lineid", "ไอดีไลน์",
]
# headers that contain a PII word but are NOT personal
_SAFE_HEADERS = {"ชื่อสินค้า", "ชื่อรายการ", "ชื่อเมนู", "ชื่อสาขา", "ชื่อร้าน", "productname", "itemname",
                 "branchname", "storename", "shopname", "ชื่อช่องทาง", "channelname"}

_RX = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    # 13-digit Thai ID: 1-2345-67890-12-3 or 1234567890123
    "id_card": re.compile(r"(?<!\d)\d[\s-]?\d{4}[\s-]?\d{5}[\s-]?\d{2}[\s-]?\d(?!\d)"),
    # Thai mobile: 06/08/09 + 8 digits, or +66 6/8/9 + 8 digits; landline 02-07 + 7 digits
    "phone": re.compile(
        r"(?<![\d])(?:(?:\+?66[\s-]?|0)[689](?:[\s-]?\d){8}|0[2-7](?:[\s-]?\d){7})(?![\d])"),
    # bank account: typical xxx-x-xxxxx-x, or 10-12 digits written with dashes/spaces
    "bank": re.compile(r"(?<![\d])(?:\d{3}[\s-]\d[\s-]\d{5}[\s-]\d|\d{3}[\s-]\d{3}[\s-]\d{3,4}|\d{10,12})(?![\d])"),
    # names with a title
    "name": re.compile(
        r"(?:นางสาว|นาง(?!ฟ้า|เงือก|พญา)|นาย(?!หน้า|ก|ทุน|จ้าง)|น\.ส\.|ด\.ช\.|ด\.ญ\.|คุณ(?!ภาพ|ค่า|สมบัติ|ประโยชน์))"
        r"\s*[ก-๙A-Za-z]{2,}(?:\s+[ก-๙A-Za-z]{2,})?"
        r"|\b(?:Mr|Mrs|Ms|Miss|Khun)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"),
}
_LABELS = {"email": "อีเมล", "id_card": "เลขบัตรประชาชน", "phone": "เบอร์โทร", "bank": "เลขบัญชี",
           "name": "ชื่อคน"}


def _norm(h: str) -> str:
    return re.sub(r"[\s_\-\.()]+", "", (h or "").strip().lower())


def is_pii_header(header: str) -> bool:
    n = _norm(header)
    if not n or n in _SAFE_HEADERS:
        return False
    return any(w.replace("-", "") in n for w in _PII_HEADER_WORDS)


def find_pii(value: str) -> list[str]:
    """Return list of PII kinds found in a string."""
    if not value:
        return []
    kinds = []
    for kind, rx in _RX.items():
        if rx.search(value):
            kinds.append(kind)
    return kinds


def mask_value(value: str) -> tuple[str, list[str]]:
    kinds = []
    out = value
    for kind, rx in _RX.items():  # order matters: email/id before phone/bank
        new = rx.sub(MASK, out)
        if new != out:
            kinds.append(kind)
            out = new
    return out, kinds


@dataclass
class PiiReport:
    dropped_columns: list[str] = field(default_factory=list)
    masked: dict[str, dict[str, int]] = field(default_factory=dict)  # column -> kind -> count

    @property
    def found(self) -> bool:
        return bool(self.dropped_columns or self.masked)

    def warnings(self) -> list[str]:
        msgs = []
        if self.dropped_columns:
            cols = ", ".join(f"'{c}'" for c in self.dropped_columns)
            msgs.append(f"⚠️ พบคอลัมน์ที่น่าจะเป็นข้อมูลส่วนตัว ตัดออกแล้ว ไม่นำมาใช้: {cols}")
        for col, kinds in self.masked.items():
            parts = ", ".join(f"{_LABELS[k]} {n} จุด" for k, n in kinds.items())
            msgs.append(f"⚠️ คอลัมน์ '{col}' มีข้อมูลที่ดูเหมือน {parts} ปิดบังเป็น {MASK} แล้ว")
        return msgs


def clean_rows(headers: list[str], rows: list[dict[str, str]], protected: set[str] | None = None):
    """Drop PII columns and mask PII-looking values.

    protected: headers used as numeric/date columns (never dropped; not masked because
    masking a number would corrupt it, e.g. amount 1234567890 is not a phone).
    Returns (new_headers, new_rows, report).
    """
    protected = protected or set()
    report = PiiReport()
    keep = []
    for h in headers:
        if h not in protected and is_pii_header(h):
            report.dropped_columns.append(h)
        else:
            keep.append(h)
    new_rows = []
    for r in rows:
        nr = {}
        for h in keep:
            v = r.get(h, "")
            if h not in protected and v:
                v2, kinds = mask_value(v)
                if kinds:
                    col = report.masked.setdefault(h, {})
                    for k in kinds:
                        col[k] = col.get(k, 0) + 1
                v = v2
            nr[h] = v
        new_rows.append(nr)
    return keep, new_rows, report
