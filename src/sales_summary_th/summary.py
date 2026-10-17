"""Deterministic sales summary. Every number here is computed by code."""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import pii
from .loader import Sale, map_columns, parse_date, parse_hour, parse_number, read_table

MINUS = "\u2212"  # − (looks nicer than "-" in Thai text)
CHECK_LINE = "ตรวจตัวเลขกับข้อมูลจริงก่อนใช้งาน"


class InputError(ValueError):
    """A problem with the user's file, explained in Thai."""


# ---------------- formatting ----------------

def fmt_money(v: float) -> str:
    v = round(v, 2)
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:,.2f}"


def fmt_signed_money(v: float) -> str:
    sign = "+" if v > 0 else (MINUS if v < 0 else "±")
    return f"{sign}{fmt_money(abs(v))}"


def fmt_pct(p: float | None) -> str:
    if p is None:
        return "ไม่มีฐานเทียบ"
    p = round(p, 1)
    sign = "+" if p > 0 else (MINUS if p < 0 else "±")
    s = f"{abs(p):.1f}".rstrip("0").rstrip(".")
    return f"{sign}{s}%"


def pct_change(new: float, old: float) -> float | None:
    if old == 0:
        return None
    return (new - old) / abs(old) * 100.0


# ---------------- loading ----------------

@dataclass
class Dataset:
    sales: list[Sale]
    mapping: dict[str, str]
    pii_report: pii.PiiReport
    skipped_rows: list[int]
    clean_headers: list[str]
    clean_rows: list[dict[str, str]]


def load(path: str | Path, branch: str | None = None, channel: str | None = None) -> Dataset:
    headers, rows = read_table(path)
    if not headers:
        raise InputError("ไฟล์ว่าง หรืออ่านไม่ได้")
    mapping = map_columns(headers)
    missing = [c for c in ("date", "product") if c not in mapping]
    if "amount" not in mapping and not ("price" in mapping and "qty" in mapping):
        missing.append("amount")
    if missing:
        th = {"date": "วันที่ (date)", "product": "สินค้า (product)", "amount": "ยอดขาย (amount)"}
        raise InputError(
            "หาคอลัมน์ไม่เจอ: " + ", ".join(th[m] for m in missing)
            + f"\nคอลัมน์ในไฟล์: {', '.join(headers)}"
            + "\nตั้งชื่อหัวคอลัมน์เป็น เช่น วันที่, เวลา, สินค้า, จำนวน, ยอดขาย, สาขา")

    protected = {mapping[k] for k in ("date", "time", "qty", "amount", "price") if k in mapping}
    # product/branch/channel are needed, so they are masked (not dropped) if they contain PII
    keep_cols = {mapping[k] for k in ("product", "branch", "channel") if k in mapping}
    clean_headers, clean_rows, report = pii.clean_rows(headers, rows, protected=protected)
    # never drop a column we need for the summary; re-add it masked
    for h in list(report.dropped_columns):
        if h in keep_cols:
            report.dropped_columns.remove(h)

    sales: list[Sale] = []
    skipped: list[int] = []
    for i, (raw, r) in enumerate(zip(rows, clean_rows), start=2):
        d = parse_date(raw.get(mapping["date"], ""))
        amount = parse_number(raw.get(mapping["amount"], "")) if "amount" in mapping else None
        qty = parse_number(raw.get(mapping["qty"], "")) if "qty" in mapping else None
        if amount is None and "price" in mapping and qty is not None:
            price = parse_number(raw.get(mapping["price"], ""))
            amount = price * qty if price is not None else None
        product = r.get(mapping["product"], "").strip() if mapping["product"] in r else \
            pii.mask_value(raw.get(mapping["product"], ""))[0].strip()
        if d is None or amount is None or not product:
            skipped.append(i)
            continue
        hour = None
        if "time" in mapping:
            hour = parse_hour(raw.get(mapping["time"], ""))
        else:
            hour = parse_hour(raw.get(mapping["date"], "")[10:])
        b = r.get(mapping["branch"], "") if "branch" in mapping else ""
        c = r.get(mapping["channel"], "") if "channel" in mapping else ""
        if branch and b.strip().lower() != branch.strip().lower():
            continue
        if channel and c.strip().lower() != channel.strip().lower():
            continue
        # duplicate key uses the ORIGINAL row (in memory only, never printed)
        key = tuple((raw.get(h, "") or "").strip() for h in headers)
        sales.append(Sale(row=i, date=d, hour=hour, product=product, qty=qty, amount=amount,
                          branch=b, channel=c, raw_key=key))
    if not sales:
        raise InputError("ไม่พบแถวที่อ่านได้ (ตรวจรูปแบบวันที่/ตัวเลข หรือชื่อสาขา/ช่องทางที่กรอง)")
    return Dataset(sales, mapping, report, skipped, clean_headers, clean_rows)


# ---------------- analysis ----------------

@dataclass
class Summary:
    today: dt.date
    compare_day: dt.date | None
    total: float
    total_prev: float | None
    top3: list[tuple[str, float]]
    drop: tuple[str, float, float, float | None] | None  # product, prev, now, pct
    zero_hours: list[tuple[int, int]]  # ranges [start, end) with 0 sales
    negative_rows: list[int]
    duplicate_groups: list[list[int]]
    duplicate_extra_amount: float
    action: str
    warnings: list[str] = field(default_factory=list)
    recheck: list[str] = field(default_factory=list)
    rows_today: int = 0
    has_time: bool = False


def _ranges(hours: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for h in sorted(hours):
        if out and out[-1][1] == h:
            out[-1] = (out[-1][0], h + 1)
        else:
            out.append((h, h + 1))
    return out


def rule_based_action(s: "Summary") -> str:
    """Pick ONE concrete action for tomorrow from what the numbers show (no AI)."""
    if s.negative_rows or s.duplicate_groups:
        what = []
        if s.negative_rows:
            what.append("รายการติดลบ")
        if s.duplicate_groups:
            what.append("รายการซ้ำ")
        return f"เช็ก{'และ'.join(what)}กับบิล/ระบบขายก่อนปิดยอด แล้วแก้ให้ถูก"
    if s.zero_hours:
        a, b = s.zero_hours[0]
        return f"เช็กว่าช่วง {a:02d}:00–{b:02d}:00 ทำไมไม่มียอด (ร้านปิด ของหมด หรือระบบขัดข้อง) แล้วแก้ก่อนเปิดร้าน"
    if s.drop and s.drop[3] is not None and s.drop[3] <= -20:
        return (f"หาสาเหตุที่ {s.drop[0]} ยอดตก (ของหมด/ราคา/ที่วาง) แล้ววางให้เห็นชัดขึ้นหรือจัดโปรเล็ก ๆ")
    if s.top3:
        return f"เตรียมสต็อก {s.top3[0][0]} ให้พอ เพราะขายดีที่สุดวันนี้"
    return "บันทึกยอดให้ครบทุกรายการ แล้วสรุปใหม่พรุ่งนี้"


def summarize(ds: Dataset, day: dt.date | None = None, compare: dt.date | None = None) -> Summary:
    by_day: dict[dt.date, list[Sale]] = defaultdict(list)
    for s in ds.sales:
        by_day[s.date].append(s)
    days = sorted(by_day)
    today = day or days[-1]
    if today not in by_day:
        raise InputError(f"ไม่มีข้อมูลของวันที่ {today.isoformat()} ในไฟล์")
    if compare is None:
        earlier = [d for d in days if d < today]
        compare = earlier[-1] if earlier else None
    elif compare not in by_day:
        raise InputError(f"ไม่มีข้อมูลของวันที่ {compare.isoformat()} ในไฟล์")

    cur = by_day[today]
    prev = by_day.get(compare, []) if compare else []
    total = sum(s.amount for s in cur)
    total_prev = sum(s.amount for s in prev) if compare else None

    per = Counter()
    for s in cur:
        per[s.product] += s.amount
    top3 = sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))[:3]

    drop = None
    if compare:
        per_prev = Counter()
        for s in prev:
            per_prev[s.product] += s.amount
        worst = None
        for p in sorted(set(per_prev) | set(per)):
            diff = per.get(p, 0.0) - per_prev.get(p, 0.0)
            if diff < 0 and (worst is None or diff < worst[0]):
                worst = (diff, p)
        if worst:
            p = worst[1]
            drop = (p, per_prev.get(p, 0.0), per.get(p, 0.0), pct_change(per.get(p, 0.0), per_prev.get(p, 0.0)))

    # anomalies
    hours = [s.hour for s in cur if s.hour is not None]
    zero_hours: list[tuple[int, int]] = []
    if hours:
        hourly = Counter()
        for s in cur:
            if s.hour is not None:
                hourly[s.hour] += s.amount
        zero = [h for h in range(min(hours), max(hours) + 1) if abs(hourly.get(h, 0.0)) < 1e-9]
        zero_hours = _ranges(zero)
    negative_rows = [s.row for s in cur if s.amount < 0 or (s.qty is not None and s.qty < 0)]
    groups: dict[tuple, list[Sale]] = defaultdict(list)
    for s in cur:
        groups[s.raw_key].append(s)
    dup_groups = [[x.row for x in g] for g in groups.values() if len(g) > 1]
    dup_extra = sum(x.amount for g in groups.values() if len(g) > 1 for x in g[1:])

    summ = Summary(today=today, compare_day=compare, total=total, total_prev=total_prev, top3=top3,
                   drop=drop, zero_hours=zero_hours, negative_rows=negative_rows,
                   duplicate_groups=sorted(dup_groups), duplicate_extra_amount=dup_extra, action="",
                   rows_today=len(cur), has_time=bool(hours))
    summ.action = rule_based_action(summ)

    summ.warnings = ds.pii_report.warnings()
    if ds.skipped_rows:
        rs = ", ".join(map(str, ds.skipped_rows[:10])) + (" ..." if len(ds.skipped_rows) > 10 else "")
        summ.warnings.append(f"⚠️ ข้ามแถวที่อ่านวันที่/ยอด/สินค้าไม่ได้ {len(ds.skipped_rows)} แถว (แถว {rs})")
    if summ.negative_rows:
        summ.recheck.append("แถวติดลบ: " + ", ".join(map(str, summ.negative_rows)))
    if summ.duplicate_groups:
        summ.recheck.append("แถวซ้ำ: " + " · ".join("=".join(map(str, g)) for g in summ.duplicate_groups)
                            + f" (ถ้าบันทึกซ้ำจริง ยอดรวมจะลดลง {fmt_money(summ.duplicate_extra_amount)} บ.)")
    if ds.skipped_rows:
        summ.recheck.append("แถวที่ถูกข้าม: " + ", ".join(map(str, ds.skipped_rows[:10])))
    return summ


# ---------------- rendering ----------------

def _day_label(today: dt.date, other: dt.date) -> str:
    if (today - other).days == 1:
        return "เมื่อวาน"
    return f"วันที่ {other.isoformat()}"


def render_lines(s: Summary) -> list[str]:
    # 1
    if s.compare_day is None:
        l1 = f"1. ยอดรวม: {fmt_money(s.total)} บ. เทียบเมื่อวาน: ข้อมูลไม่พอ (ไม่มีข้อมูลวันก่อนหน้าในไฟล์)"
    else:
        diff = s.total - s.total_prev
        l1 = (f"1. ยอดรวม: {fmt_money(s.total)} บ. เทียบ{_day_label(s.today, s.compare_day)} "
              f"{fmt_signed_money(diff)} บ. ({fmt_pct(pct_change(s.total, s.total_prev))})")
    # 2
    l2 = "2. 3 ตัวขายดี: " + " · ".join(f"{p} {fmt_money(v)} บ." for p, v in s.top3)
    if len(s.top3) < 3:
        l2 += f" (มีสินค้าแค่ {len(s.top3)} รายการ)"
    # 3
    if s.compare_day is None:
        l3 = "3. ตกหนักสุด: ข้อมูลไม่พอ (ไม่มีข้อมูลวันก่อนหน้า)"
    elif s.drop is None:
        l3 = "3. ตกหนักสุด: ไม่มีสินค้าที่ยอดลดลง"
    else:
        p, old, new, pc = s.drop
        l3 = f"3. ตกหนักสุด: {p} {fmt_signed_money(new - old)} บ. ({fmt_pct(pc)}) เทียบ{_day_label(s.today, s.compare_day)}"
    # 4
    items = []
    for a, b in s.zero_hours:
        items.append(f"{a:02d}:00–{b:02d}:00 ยอด 0")
    if s.negative_rows:
        items.append(f"ตัวเลขติดลบ {len(s.negative_rows)} รายการ")
    if s.duplicate_groups:
        items.append(f"รายการซ้ำ {len(s.duplicate_groups)} ชุด")
    l4 = "4. ผิดปกติ: " + (" · ".join(items) if items else "ไม่พบ")
    if not s.has_time:
        l4 += " (ไม่มีคอลัมน์เวลา จึงไม่ได้ตรวจช่วงเวลายอด 0)"
    # 5
    l5 = f"5. พรุ่งนี้ควรทำ: {s.action}"
    return [l1, l2, l3, l4, l5]


def render(s: Summary, title: str | None = None) -> str:
    out = []
    if s.warnings:
        out.extend(s.warnings)
        out.append("")
    head = f"สรุปยอดขาย {s.today.isoformat()} ({s.rows_today} รายการ)"
    if title:
        head += f" · {title}"
    out.append(head)
    out.extend(render_lines(s))
    check = CHECK_LINE
    if s.recheck:
        check += " · ควรตรวจซ้ำ: " + " | ".join(s.recheck)
    out.append(check)
    return "\n".join(out)
