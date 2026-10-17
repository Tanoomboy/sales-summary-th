"""Command line: sales-summary FILE [options]"""
from __future__ import annotations

import argparse
import csv
import sys
from importlib import resources
from pathlib import Path

from . import __version__
from .loader import parse_date
from .summary import InputError, load, render, render_lines, summarize


def _sample_path() -> Path:
    return Path(str(resources.files("sales_summary_th") / "data" / "sample_sales.csv"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sales-summary",
        description="สรุปยอดขายทั้งวันเป็น 5 บรรทัด จากไฟล์ CSV/Excel (ตัวเลขคำนวณด้วยโค้ด ไม่ต้องใช้ AI)")
    p.add_argument("file", nargs="?", help="ไฟล์ยอดขาย .csv หรือ .xlsx")
    p.add_argument("--demo", action="store_true", help="ลองกับข้อมูลตัวอย่างที่มากับโปรแกรม")
    p.add_argument("--date", help="วันที่จะสรุป (ค่าเริ่มต้น = วันล่าสุดในไฟล์) เช่น 2026-10-17")
    p.add_argument("--compare", help="วันที่ใช้เทียบ (ค่าเริ่มต้น = วันก่อนหน้าในไฟล์)")
    p.add_argument("--branch", help="สรุปเฉพาะสาขานี้")
    p.add_argument("--channel", help="สรุปเฉพาะช่องทางนี้")
    p.add_argument("--out", help="บันทึกผลสรุปเป็นไฟล์ .txt ด้วย")
    p.add_argument("--clean-csv", help="บันทึกตารางที่ตัดข้อมูลส่วนตัวแล้วเป็น CSV (ไว้วางในแชต AI)")
    p.add_argument("--ai", action="store_true",
                   help="(ไม่บังคับ) ให้ AI เรียบเรียงข้อ 5 ต้องตั้ง SALES_SUMMARY_API_KEY หรือ OPENAI_API_KEY")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Thai text on Windows consoles
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    if args.demo:
        path, title = _sample_path(), "ข้อมูลตัวอย่าง"
    elif args.file:
        path, title = Path(args.file.strip('"')), None
    else:
        build_parser().print_help()
        print("\nตัวอย่าง:  sales-summary ยอดขาย.csv      หรือลองก่อน:  sales-summary --demo")
        return 2
    if not path.exists():
        print(f"ไม่พบไฟล์: {path}", file=sys.stderr)
        return 2
    try:
        day = parse_date(args.date) if args.date else None
        cmp = parse_date(args.compare) if args.compare else None
        if (args.date and not day) or (args.compare and not cmp):
            raise InputError("อ่านวันที่ที่พิมพ์ไม่ได้ ใช้รูปแบบ 2026-10-17 หรือ 17/10/2026")
        ds = load(path, branch=args.branch, channel=args.channel)
        s = summarize(ds, day=day, compare=cmp)
    except InputError as e:
        print(f"ผิดพลาด: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"ผิดพลาด: {e}", file=sys.stderr)
        return 1

    note = None
    if args.ai:
        from .ai import polish_action
        s.action, note = polish_action(render_lines(s), s.action)

    text = render(s, title=title)
    if note:
        text += f"\n({note})"
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8-sig")
        print(f"\nบันทึกผลไว้ที่: {args.out}")
    if args.clean_csv:
        with open(args.clean_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=ds.clean_headers)
            w.writeheader()
            w.writerows(ds.clean_rows)
        print(f"บันทึกตารางที่ตัดข้อมูลส่วนตัวแล้วไว้ที่: {args.clean_csv}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
