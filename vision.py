import os
import io
import time
import base64
import requests
from PIL import Image

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

def _compress_image(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((768, 768))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def scan_fridge_and_make_recipe(image_bytes: bytes, user_profile: str = "") -> dict:
    if not GEMINI_KEY:
        return {"ok": False, "text": "⚠️ GEMINI_API_KEY არ არის მითითებული."}

    try:
        b64_img = _compress_image(image_bytes)
    except Exception:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")

    prompt = f"""შენ ხარ FitChef AI — პროფესიონალი ნუტრიციოლოგი და შეფ-მზარეული.
მომხმარებლის პროფილი: {user_profile}

დააკვირდი ამ ფოტოს და ერთიანად შეასრულე ორი დავალება გამართული, ბუნებრივი ქართული ენით — უცხოური სიტყვებისა და კალკების გარეშე (მაგ. გამოიყენე „ოსპი“ და არა „ლინზა“, HTML ტეგების გარეშე):
1. **მაცივარში აღმოჩენილი პროდუქტები:** მოკლე სიით ჩამოთვალე რას ხედავ ფოტოზე.
2. **რეკომენდებული ჯანსაღი რეცეპტი:** ამ პროდუქტებისა და მომხმარებლის მიზნის მიხედვით შეადგინე ერთი ჯანსაღი, გემრიელი კერძი (კერძის სახელი, ინგრედიენტები გრამობით, კალორიულობა კკალ-ში და მომზადების 3-4 მოკლე ნაბიჯი).
3. პასუხის ბოლო ხაზზე აუცილებლად დაწერე ზუსტად ასეთი შემაჯამებელი ხაზი:
PLAN_ITEM: [Meal] კვება - XXX კკალ: კერძის მოკლე აღწერა
"""

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 2500
        }
    }

    models = ["gemini-2.5-flash-lite", "gemini-flash-lite-latest", "gemini-flash-latest"]
    last_status = ""
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}"
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                plan_item = ""
                clean_lines = []
                for line in raw.splitlines():
                    if line.strip().startswith("PLAN_ITEM:"):
                        plan_item = line.split("PLAN_ITEM:", 1)[1].strip()
                    else:
                        clean_lines.append(line)
                return {
                    "ok": True,
                    "text": "\n".join(clean_lines).strip(),
                    "plan_item": plan_item
                }
            last_status = str(r.status_code)
            if r.status_code == 429:
                time.sleep(1.5)
        except Exception as e:
            last_status = str(e)

    if last_status == "429":
        return {"ok": False, "text": "⏳ API-ს წუთობრივი ლიმიტი დროებით გადატვირთულია. დაელოდეთ 15-20 წამს და დააჭირეთ ღილაკს თავიდან."}
    return {"ok": False, "text": f"⚠️ ფოტოს დამუშავება ვერ მოხერხდა ({last_status})."}
