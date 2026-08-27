import json
import os
from datetime import datetime, timezone
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
]

today = datetime.now(timezone.utc).strftime("%d %B %Y")

prompt = f"""
You are the daily Vedic astrology writer for Mauksh.

Generate a fresh DAILY horoscope for {today} for all 12 zodiac signs.

IMPORTANT:
- Use Vedic/sidereal astrology.
- Base the interpretation on the actual planetary transits applicable to today.
- Do not repeat generic horoscope themes.
- Every zodiac sign must have a distinctly different interpretation.
- Write natural Hinglish, like a knowledgeable human astrologer.
- Make predictions practical, specific and believable.
- Cover Energy, Career, Love, Money and Advice.
- Add a short "Mauksh Truth" that feels insightful and human.
- Avoid fearmongering and absolute claims.
- Do not mention that you are an AI.
- Return ONLY valid JSON.
- Do not use Markdown code fences.

The JSON must have exactly this structure:

{{
  "date": "{today}",
  "aries": "<h3>♈ Aries</h3><p>🔥 Energy: ...</p><p>💼 Career: ...</p><p>❤️ Love: ...</p><p>💰 Money: ...</p><p>🧘 Advice: ...</p><p class=\\"truth\\">⚡ Mauksh Truth: ...</p>",
  "taurus": "...",
  "gemini": "...",
  "cancer": "...",
  "leo": "...",
  "virgo": "...",
  "libra": "...",
  "scorpio": "...",
  "sagittarius": "...",
  "capricorn": "...",
  "aquarius": "...",
  "pisces": "..."
}}

Before returning the JSON, internally check that:
1. All 12 signs are present.
2. No sign has copied wording from another sign.
3. The horoscope is substantially different from yesterday's themes.
4. The HTML is valid.
"""

response = client.responses.create(
    model="gpt-5.1",
    tools=[{"type": "web_search"}],
    input=prompt
)

text = response.output_text.strip()

if text.startswith("```"):
    text = text.replace("```json", "").replace("```", "").strip()

data = json.loads(text)

required = ["date"] + SIGNS

if sorted(data.keys()) != sorted(required):
    raise ValueError("Horoscope JSON does not contain exactly the required fields.")

for sign in SIGNS:
    if not isinstance(data[sign], str) or len(data[sign]) < 100:
        raise ValueError(f"Invalid horoscope for {sign}")

with open("Horoscope.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Successfully generated Horoscope.json for {today}")
