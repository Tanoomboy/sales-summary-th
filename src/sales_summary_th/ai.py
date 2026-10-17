"""OPTIONAL: ask an LLM to rephrase line 5 ("พรุ่งนี้ควรทำ"). Off unless --ai is given.

Only the already-computed 5-line summary is sent (no raw rows, no customer data).
The reply is rejected if it contains any number that is not already in the summary,
so the AI can never invent figures. Any error -> keep the rule-based action.

Env vars (never printed):
  SALES_SUMMARY_API_KEY  (or OPENAI_API_KEY)
  SALES_SUMMARY_API_BASE default https://api.openai.com/v1 (any OpenAI-compatible API)
  SALES_SUMMARY_MODEL    default gpt-4o-mini
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

PROMPT = (
    "คุณเป็นผู้ช่วยร้านค้าขนาดเล็ก ด้านล่างคือสรุปยอดขายที่คำนวณด้วยโปรแกรมแล้ว (ตัวเลขถูกต้อง)\n"
    "เขียน 'สิ่งที่ควรทำพรุ่งนี้' 1 ข้อ ภาษาไทย สั้น ทำได้จริง ไม่เกิน 1 ประโยค อิงจากข้อ 1-4\n"
    "ห้ามใส่ตัวเลขใหม่ที่ไม่มีในสรุป ห้ามเดา ตอบเฉพาะประโยคนั้น ไม่ต้องมีเลขข้อหรือคำนำ\n\n"
)


def api_key() -> str | None:
    return os.environ.get("SALES_SUMMARY_API_KEY") or os.environ.get("OPENAI_API_KEY") or None


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(text)}


def polish_action(summary_lines: list[str], fallback: str, timeout: float = 20.0) -> tuple[str, str]:
    """Return (action, note). note explains what happened (for the user), never the key."""
    key = api_key()
    if not key:
        return fallback, "ไม่ได้ตั้ง API key จึงใช้คำแนะนำแบบกฎ (ไม่ใช้ AI)"
    base = os.environ.get("SALES_SUMMARY_API_BASE", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("SALES_SUMMARY_MODEL", "gpt-4o-mini")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT + "\n".join(summary_lines[:4])}],
        "temperature": 0.3,
        "max_tokens": 120,
    }
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip().splitlines()[0].strip()
        text = re.sub(r"^(5\.|พรุ่งนี้ควรทำ\s*:?)\s*", "", text).strip()
    except Exception as e:  # network, auth, format... never leak the key
        return fallback, f"เรียก AI ไม่สำเร็จ ({type(e).__name__}) จึงใช้คำแนะนำแบบกฎแทน"
    if not text:
        return fallback, "AI ตอบว่าง จึงใช้คำแนะนำแบบกฎแทน"
    new_nums = _numbers(text) - _numbers("\n".join(summary_lines))
    if new_nums:
        return fallback, "AI ใส่ตัวเลขที่ไม่มีในข้อมูล จึงไม่ใช้คำตอบนั้น (ใช้คำแนะนำแบบกฎแทน)"
    return text, f"ข้อ 5 เรียบเรียงโดย AI ({model}) ตัวเลขทั้งหมดยังมาจากโปรแกรม"
