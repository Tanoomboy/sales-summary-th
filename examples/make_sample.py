"""สร้างข้อมูลตัวอย่าง (ข้อมูลตัวอย่าง / EXAMPLE DATA, ตัวเลขสมมติทั้งหมด)."""
import csv
import random
from pathlib import Path

PRICE = {"ชาไทย": 50, "ลาเต้": 60, "โกโก้": 55, "อเมริกาโน่": 50, "ขนมปัง": 40, "ชาเขียว": 50}
DAYS = {
    "2026-10-19": {"ชาไทย": 260, "ลาเต้": 190, "โกโก้": 150, "อเมริกาโน่": 90, "ขนมปัง": 100, "ชาเขียว": 37},
    "2026-10-20": {"ชาไทย": 300, "ลาเต้": 200, "โกโก้": 180, "อเมริกาโน่": 100, "ขนมปัง": 65, "ชาเขียว": 74},
}
rng = random.Random(20261020)
rows = []
for day, cups in DAYS.items():
    hours = [h for h in range(8, 20) if not (day == "2026-10-20" and h == 14)]
    for product, total_qty in cups.items():
        left = total_qty
        while left > 0:
            q = min(left, rng.randint(1, 6))
            left -= q
            h = rng.choice(hours)
            rows.append([day, f"{h:02d}:{rng.randint(0, 59):02d}", rng.choice(["สาขา 1", "สาขา 2"]),
                         rng.choice(["หน้าร้าน", "หน้าร้าน", "เดลิเวอรี"]), product, q, q * PRICE[product]])
rows.sort(key=lambda r: (r[0], r[1]))
out = Path(__file__).resolve().parents[1] / "src/sales_summary_th/data/sample_sales.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["วันที่", "เวลา", "สาขา", "ช่องทาง", "สินค้า", "จำนวน", "ยอดขาย"])
    # de-duplicate accidental identical rows so the sample has no "duplicates"
    seen = set()
    for r in rows:
        while tuple(r) in seen:
            r[1] = f"{r[1][:3]}{(int(r[1][3:]) + 1) % 60:02d}"
        seen.add(tuple(r))
        w.writerow(r)
print(out, len(rows))
