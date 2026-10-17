# sales-summary-th · สรุปยอดขายทั้งวัน ในนาทีเดียว

โปรแกรมเล็ก ๆ ฟรี (MIT) เปิดไฟล์ยอดขาย **CSV หรือ Excel** แล้วสรุปให้ **5 บรรทัด** ภาษาไทย:

1. ยอดรวม เทียบเมื่อวาน (+/− บาท และ %)
2. 3 ตัวขายดี
3. ตัวที่ยอดตกหนักสุด
4. ความผิดปกติ (ช่วงเวลาที่ยอดเป็น 0, ตัวเลขติดลบ, รายการซ้ำ) หรือ "ไม่พบ"
5. พรุ่งนี้ควรทำอะไร 1 อย่าง

**ตัวเลขทุกตัวคำนวณด้วยโค้ด ไม่ได้ให้ AI เดา** ใช้งานได้ครบโดยไม่ต้องมี API key และไม่ต้องต่ออินเทอร์เน็ต (หลังติดตั้ง)
ถ้าในไฟล์มีชื่อลูกค้า เบอร์โทร เลขบัญชี อีเมล หรือเลขบัตรประชาชน โปรแกรมจะตัดออกหรือปิดบังให้ และเตือนก่อนเสมอ

> ไม่อยากติดตั้งอะไรเลย? ใช้ไฟล์ [prompt-th.md](prompt-th.md) คัดลอกไปวางใน ChatGPT / Gemini / Claude ได้ทันที

---

## ติดตั้ง 3 ขั้น

**1) ติดตั้ง Python** (ทำครั้งเดียว ถ้ามีแล้วข้ามได้)
- Windows: โหลดจาก https://www.python.org/downloads/ ตอนติดตั้ง **ติ๊กช่อง "Add python.exe to PATH"** ก่อนกด Install
- Mac: โหลดจากลิงก์เดียวกัน แล้วติดตั้งตามปกติ

**2) ติดตั้งโปรแกรม** เปิด Command Prompt (Windows) หรือ Terminal (Mac) แล้ววางคำสั่งนี้ กด Enter

Windows:
```
py -m pip install https://github.com/Tanoomboy/sales-summary-th/archive/refs/heads/main.zip
```
Mac:
```
python3 -m pip install https://github.com/Tanoomboy/sales-summary-th/archive/refs/heads/main.zip
```

**3) ลองกับข้อมูลตัวอย่าง**

Windows:
```
py -m sales_summary_th --demo
```
Mac:
```
python3 -m sales_summary_th --demo
```
ถ้าเห็นสรุป 5 บรรทัด แปลว่าพร้อมใช้แล้ว

## ใช้กับไฟล์ของคุณ

พิมพ์คำสั่ง เว้นวรรค แล้ว **ลากไฟล์ยอดขายมาวางในหน้าต่าง** (จะได้ที่อยู่ไฟล์อัตโนมัติ) กด Enter

```
py -m sales_summary_th ยอดขาย.csv
```
(Mac ใช้ `python3` แทน `py` · หรือพิมพ์สั้น ๆ ว่า `sales-summary ยอดขาย.csv` ก็ได้ถ้าเครื่องหาเจอ)

ไฟล์ควรมีหัวคอลัมน์ประมาณนี้ (ไทยหรืออังกฤษก็ได้ ลำดับไม่สำคัญ):

| ต้องมี | ไม่บังคับ |
|---|---|
| วันที่ (date), สินค้า (product), ยอดขาย (amount) | เวลา (time), จำนวน (qty), ราคา (price), สาขา (branch), ช่องทาง (channel) |

- ใส่ข้อมูล **วันนี้และเมื่อวาน** ไว้ในไฟล์เดียวกันได้เลย โปรแกรมสรุปวันล่าสุดและเทียบกับวันก่อนหน้าให้เอง
- วันที่ใช้ได้ทั้ง `2026-10-20`, `20/10/2026` หรือ `20/10/2569` (พ.ศ.)
- ไม่มีคอลัมน์ยอดขาย แต่มี ราคา + จำนวน ก็ได้ (โปรแกรมคูณให้)
- ไม่มีคอลัมน์เวลา ก็ได้ แต่จะตรวจ "ช่วงเวลายอด 0" ไม่ได้

ตัวเลือกที่ใช้บ่อย:

| คำสั่งเสริม | ทำอะไร |
|---|---|
| `--out สรุป.txt` | บันทึกผลเป็นไฟล์ไว้ส่งต่อ |
| `--date 2026-10-20` | เลือกวันที่จะสรุป |
| `--compare 2026-10-13` | เลือกวันที่ใช้เทียบ (เช่น วันเดียวกันของสัปดาห์ก่อน) |
| `--branch "สาขา 1"` / `--channel เดลิเวอรี` | สรุปเฉพาะสาขา/ช่องทาง |
| `--clean-csv ปลอดภัย.csv` | บันทึกตารางที่ตัดข้อมูลส่วนตัวแล้ว ไว้วางในแชต AI |

**Windows แบบไม่พิมพ์คำสั่ง:** ดาวน์โหลดไฟล์ [windows/summarize.bat](windows/summarize.bat) แล้ว **ลากไฟล์ยอดขายไปวางบนไฟล์ .bat** ผลจะขึ้นบนจอ และบันทึกเป็น `ชื่อไฟล์-summary.txt` ไว้ข้าง ๆ

## ตัวอย่างผลลัพธ์ (ข้อมูลตัวอย่าง ตัวเลขสมมติทั้งหมด)

```
สรุปยอดขาย 2026-10-20 (264 รายการ) · ข้อมูลตัวอย่าง
1. ยอดรวม: 48,200 บ. เทียบเมื่อวาน +5,200 บ. (+12.1%)
2. 3 ตัวขายดี: ชาไทย 15,000 บ. · ลาเต้ 12,000 บ. · โกโก้ 9,900 บ.
3. ตกหนักสุด: ขนมปัง −1,400 บ. (−35%) เทียบเมื่อวาน
4. ผิดปกติ: 14:00–15:00 ยอด 0
5. พรุ่งนี้ควรทำ: เช็กว่าช่วง 14:00–15:00 ทำไมไม่มียอด (ร้านปิด ของหมด หรือระบบขัดข้อง) แล้วแก้ก่อนเปิดร้าน
ตรวจตัวเลขกับข้อมูลจริงก่อนใช้งาน
```

ไฟล์ตัวอย่างอยู่ในโฟลเดอร์ [examples/](examples/) (ทุกไฟล์เป็น **ข้อมูลตัวอย่าง** ชื่อและเบอร์ในไฟล์เป็นของปลอม)

## เรื่องข้อมูลส่วนตัว

- คอลัมน์ที่ชื่อเหมือน ชื่อลูกค้า / เบอร์โทร / เลขบัญชี / อีเมล / ที่อยู่ / เลขบัตร จะถูก **ตัดทิ้ง** ไม่นำมาใช้
- ข้อความในคอลัมน์อื่นที่ดูเหมือนเบอร์โทรไทย เลขบัญชี เลขบัตร 13 หลัก อีเมล หรือชื่อที่มีคำนำหน้า (คุณ/นาย/นาง/นางสาว) จะถูกแทนด้วย `[ซ่อน]`
- โปรแกรมทำงานในเครื่องคุณ ไม่ส่งข้อมูลไปไหน (ยกเว้นเปิดโหมด `--ai` เอง ซึ่งส่งแค่สรุปตัวเลข 4 บรรทัด ไม่ส่งตาราง)
- การตรวจนี้เป็นตัวช่วย ไม่ได้รับประกัน 100% ควรดูข้อมูลของคุณเองก่อนแชร์ทุกครั้ง

## (ไม่บังคับ) ให้ AI ช่วยเรียบเรียงข้อ 5

ถ้ามี API key ของ OpenAI หรือบริการที่ใช้รูปแบบเดียวกัน ตั้งค่าแล้วเติม `--ai`:
```
set SALES_SUMMARY_API_KEY=ใส่คีย์ของคุณ          (Windows)
export SALES_SUMMARY_API_KEY=ใส่คีย์ของคุณ       (Mac)
py -m sales_summary_th ยอดขาย.csv --ai
```
AI แก้ได้แค่ข้อความข้อ 5 ตัวเลขยังมาจากโปรแกรม ถ้า AI ใส่ตัวเลขที่ไม่มีในข้อมูล โปรแกรมจะไม่ใช้คำตอบนั้น
ตั้ง `SALES_SUMMARY_API_BASE` และ `SALES_SUMMARY_MODEL` ได้ถ้าใช้บริการอื่น อย่าใส่คีย์ลงในไฟล์ที่แชร์หรืออัปโหลด

## แก้ปัญหาที่เจอบ่อย

- **`py` / `python3` is not recognized**: ติดตั้ง Python ใหม่ และติ๊ก "Add python.exe to PATH"
- **Mac ขึ้น `externally-managed-environment`**: ใช้ Python จาก python.org หรือเติม `--user` ท้ายคำสั่งติดตั้ง
- **หาคอลัมน์ไม่เจอ**: เปลี่ยนหัวคอลัมน์ให้เป็น วันที่ / สินค้า / ยอดขาย
- **ไฟล์ .xls รุ่นเก่า**: เปิดใน Excel แล้ว Save As เป็น .xlsx หรือ .csv
- **อัปเดตเป็นเวอร์ชันใหม่**: รันคำสั่งติดตั้งขั้นที่ 2 ซ้ำ โดยเติม `--upgrade`

---

## English

`sales-summary-th` turns a day of sales (CSV/XLSX) into a 5-line Thai summary: total vs. previous day,
top 3 products, biggest drop, anomalies (zero-sales hours, negative values, duplicate rows), and one
action for tomorrow. All numbers are computed deterministically in Python; no API key is needed.
An optional `--ai` flag lets an OpenAI-compatible model rephrase line 5 only (replies that introduce new
numbers are rejected). A PII guard drops name/phone/account columns and masks Thai phone numbers, bank
account numbers, Thai ID numbers, e-mails and titled names in other columns.

```
pip install https://github.com/Tanoomboy/sales-summary-th/archive/refs/heads/main.zip
sales-summary --demo
sales-summary sales.csv [--date YYYY-MM-DD] [--compare YYYY-MM-DD] [--branch X] [--out summary.txt]
```

Development: `pip install -e .` then `python -m unittest discover -s tests`.
Recognised headers: date/วันที่, time/เวลา, product/สินค้า, qty/จำนวน, amount/ยอดขาย, price/ราคา,
branch/สาขา, channel/ช่องทาง. Python 3.9+. License: MIT.
