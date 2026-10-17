import csv
import datetime as dt
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from sales_summary_th import cli, pii
from sales_summary_th.loader import map_columns, parse_date, parse_hour, parse_number
from sales_summary_th.summary import fmt_pct, load, render, render_lines, summarize

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "src/sales_summary_th/data/sample_sales.csv"
PII_SAMPLE = ROOT / "examples/ข้อมูลตัวอย่าง-มีข้อมูลส่วนตัว.csv"


def write_csv(rows, header):
    fd, p = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return p


class TestParsing(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(parse_date("2026-10-20"), dt.date(2026, 10, 20))
        self.assertEqual(parse_date("20/10/2026"), dt.date(2026, 10, 20))
        self.assertEqual(parse_date("20/10/2569"), dt.date(2026, 10, 20))  # พ.ศ.
        self.assertEqual(parse_date("20-10-69"), dt.date(2026, 10, 20))
        self.assertIsNone(parse_date("ไม่ใช่วันที่"))

    def test_numbers(self):
        self.assertEqual(parse_number("1,234.50"), 1234.5)
        self.assertEqual(parse_number("฿ 500"), 500)
        self.assertEqual(parse_number("(40)"), -40)
        self.assertEqual(parse_number("\u221240"), -40)
        self.assertIsNone(parse_number("abc"))

    def test_hour(self):
        self.assertEqual(parse_hour("14:05"), 14)
        self.assertEqual(parse_hour("2026-10-20 09:30:00"), 9)
        self.assertIsNone(parse_hour(""))

    def test_columns_th_en(self):
        m = map_columns(["วันที่", "เวลา", "ชื่อสินค้า", "จำนวน", "ยอดขาย (บาท)", "สาขา"])
        self.assertEqual(m["product"], "ชื่อสินค้า")
        self.assertEqual(m["amount"], "ยอดขาย (บาท)")
        m = map_columns(["Date", "Product", "Qty", "Amount", "Channel"])
        self.assertEqual(set(m), {"date", "product", "qty", "amount", "channel"})


class TestSampleNumbers(unittest.TestCase):
    """Independent re-calculation of the sample with plain csv sums."""

    def setUp(self):
        self.s = summarize(load(SAMPLE))
        with open(SAMPLE, encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))

    def _sum(self, day, product=None):
        return sum(float(r["ยอดขาย"]) for r in self.rows
                   if r["วันที่"] == day and (product is None or r["สินค้า"] == product))

    def test_totals(self):
        self.assertEqual(self.s.today, dt.date(2026, 10, 20))
        self.assertEqual(self.s.total, self._sum("2026-10-20"))
        self.assertEqual(self.s.total, 48200)
        self.assertEqual(self.s.total_prev, 43000)

    def test_lines(self):
        lines = render_lines(self.s)
        self.assertEqual(lines[0], "1. ยอดรวม: 48,200 บ. เทียบเมื่อวาน +5,200 บ. (+12.1%)")
        self.assertEqual(lines[1], "2. 3 ตัวขายดี: ชาไทย 15,000 บ. · ลาเต้ 12,000 บ. · โกโก้ 9,900 บ.")
        self.assertEqual(lines[2], "3. ตกหนักสุด: ขนมปัง \u22121,400 บ. (\u221235%) เทียบเมื่อวาน")
        self.assertEqual(lines[3], "4. ผิดปกติ: 14:00–15:00 ยอด 0")
        self.assertTrue(lines[4].startswith("5. พรุ่งนี้ควรทำ: "))
        self.assertIn("ตรวจตัวเลขกับข้อมูลจริงก่อนใช้งาน", render(self.s))


class TestAnomalies(unittest.TestCase):
    H = ["date", "time", "product", "qty", "amount"]

    def test_none_found_and_no_yesterday(self):
        p = write_csv([["2026-10-20", "09:00", "A", 1, 100], ["2026-10-20", "10:00", "B", 2, 50]], self.H)
        s = summarize(load(p))
        lines = render_lines(s)
        self.assertIn("ข้อมูลไม่พอ", lines[0])
        self.assertIn("ข้อมูลไม่พอ", lines[2])
        self.assertEqual(lines[3], "4. ผิดปกติ: ไม่พบ")
        self.assertIn("มีสินค้าแค่ 2 รายการ", lines[1])

    def test_negative_duplicate_zero(self):
        rows = [["2026-10-19", "09:00", "A", 1, 100],
                ["2026-10-20", "09:00", "A", 1, 100],
                ["2026-10-20", "09:00", "A", 1, 100],   # duplicate
                ["2026-10-20", "12:00", "B", -1, -30],  # negative
                ]
        s = summarize(load(write_csv(rows, self.H)))
        self.assertEqual(s.negative_rows, [5])
        self.assertEqual(s.duplicate_groups, [[3, 4]])
        self.assertEqual(s.zero_hours, [(10, 12)])
        l4 = render_lines(s)[3]
        self.assertIn("10:00–12:00 ยอด 0", l4)
        self.assertIn("ตัวเลขติดลบ 1 รายการ", l4)
        self.assertIn("รายการซ้ำ 1 ชุด", l4)
        self.assertIn("แถวติดลบ: 5", render(s))

    def test_product_disappeared_is_drop(self):
        rows = [["2026-10-19", "", "A", 1, 100], ["2026-10-19", "", "B", 1, 300],
                ["2026-10-20", "", "A", 1, 150]]
        s = summarize(load(write_csv(rows, self.H)))
        self.assertEqual(s.drop[0], "B")
        self.assertIn("(\u2212100%)", render_lines(s)[2])

    def test_price_times_qty(self):
        p = write_csv([["2026-10-20", "A", 3, 20]], ["date", "product", "qty", "price"])
        self.assertEqual(summarize(load(p)).total, 60)

    def test_branch_filter(self):
        p = write_csv([["2026-10-20", "A", 100, "X"], ["2026-10-20", "A", 50, "Y"]],
                      ["date", "product", "amount", "branch"])
        self.assertEqual(summarize(load(p, branch="Y")).total, 50)

    def test_pct(self):
        self.assertEqual(fmt_pct(12.093), "+12.1%")
        self.assertEqual(fmt_pct(-35.0), "\u221235%")
        self.assertEqual(fmt_pct(None), "ไม่มีฐานเทียบ")


class TestPII(unittest.TestCase):
    def test_headers(self):
        for h in ["ชื่อลูกค้า", "เบอร์โทร", "Customer Name", "phone", "เลขบัญชี", "Email"]:
            self.assertTrue(pii.is_pii_header(h), h)
        for h in ["ชื่อสินค้า", "สินค้า", "ยอดขาย", "สาขา", "ช่องทางออนไลน์", "product_name"]:
            self.assertFalse(pii.is_pii_header(h), h)

    def test_values(self):
        cases = {
            "โทร 081-234-5678": "phone", "0898765432": "phone", "+66 91 234 5678": "phone",
            "02-123-4567": "phone", "บัญชี 123-4-56789-0": "bank", "1-2345-67890-12-3": "id_card",
            "a.b@example.com": "email", "คุณสมชาย": "name", "นางสาว มานี": "name", "Mr. John Smith": "name",
        }
        for v, kind in cases.items():
            masked, kinds = pii.mask_value(v)
            self.assertIn(kind, kinds, v)
            self.assertIn(pii.MASK, masked, v)
        for safe in ["ชาไทย", "ขนมปังคุณภาพดี", "เค้กนางฟ้า", "ลาเต้ 2 แก้ว", "โปร 99 บาท"]:
            self.assertEqual(pii.mask_value(safe), (safe, []), safe)

    def test_pii_file(self):
        ds = load(PII_SAMPLE)
        self.assertEqual(ds.pii_report.dropped_columns, ["ชื่อลูกค้า", "เบอร์โทร"])
        self.assertNotIn("ชื่อลูกค้า", ds.clean_headers)
        text = render(summarize(ds))
        for secret in ["สมชาย", "0812345678", "081-234-5678", "123-4-56789-0", "0861112222",
                       "test@example.com", "วีระ"]:
            self.assertNotIn(secret, text)
            self.assertFalse(any(secret in v for r in ds.clean_rows for v in r.values()), secret)
        self.assertIn("ข้อมูลส่วนตัว", text)
        self.assertEqual(summarize(ds).total, 390)


class TestCLI(unittest.TestCase):
    def test_demo_runs_without_key(self):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), redirect_stdout(buf):
            code = cli.main(["--demo", "--ai"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("ข้อมูลตัวอย่าง", out)
        self.assertIn("ไม่ได้ตั้ง API key", out)

    def test_ai_reply_with_new_numbers_rejected(self):
        from sales_summary_th import ai
        fake = io.BytesIO('{"choices":[{"message":{"content":"เพิ่มยอดเป็น 99,999 บาท"}}]}'.encode())
        fake.__enter__ = lambda *a: fake
        fake.__exit__ = lambda *a: None
        with mock.patch.dict(os.environ, {"SALES_SUMMARY_API_KEY": "sk-test-SECRET"}), \
                mock.patch("urllib.request.urlopen", return_value=fake):
            action, note = ai.polish_action(["1. ยอดรวม: 100 บ."], "fallback")
        self.assertEqual(action, "fallback")
        self.assertNotIn("SECRET", note)  # key never echoed

    def test_excel(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["วันที่", "สินค้า", "ยอดขาย"])
        ws.append([dt.datetime(2026, 10, 20), "ชาไทย", 120])
        ws.append([dt.datetime(2026, 10, 20), "ลาเต้", 60])
        p = tempfile.mktemp(suffix=".xlsx")
        wb.save(p)
        self.assertEqual(summarize(load(p)).total, 180)

    def test_missing_file(self):
        self.assertEqual(cli.main(["/nope/none.csv"]), 2)


if __name__ == "__main__":
    unittest.main()
