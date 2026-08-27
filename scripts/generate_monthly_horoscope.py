import json
import os
from datetime import datetime, timezone
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SIGNS = [
    "aries","taurus","gemini","cancer","leo","virgo",
    "libra","scorpio","sagittarius","capricorn","aquarius","pisces"
]

OUTPUT = "Horoscope2.json"

now = datetime.now(timezone.utc)
month = now.strftime("%B %Y")

previous = {}
try:
    with open(OUTPUT, "r", encoding="utf-8") as f:
        previous = json.load(f)
except Exception:
    pass

prompt = f"""
You are the senior Vedic astrologer for Mauksh.

Create the MONTHLY Vedic horoscope for {month} for all 12 zodiac signs.

Use Vedic sidereal astrology and research the actual planetary
transits for the entire month.

Analyze:
- Sun
- Moon
- Mercury
- Venus
- Mars
- Jupiter
- Saturn
- Rahu
- Ketu
- Retrogrades
- Eclipses if applicable
- Major conjunctions/aspects
- Important nakshatra changes when relevant

Do not create generic zodiac content.

For each sign, interpret the transits specifically for that sign.

Every sign must feel different.

Previous monthly horoscope:
{json.dumps(previous, ensure_ascii=False)}

Do not simply rewrite the previous month.

Write natural, human Hinglish.

For every sign include:

<h3>♈ Aries – {month}</h3>
<p>🔥 Theme: ...</p>
<p>💼 Career: ...</p>
<p>❤️ Love: ...</p>
<p>💰 Money: ...</p>
<p>📅 Important Period: ...</p>
<p>🧘 Advice: ...</p>
<p class="truth">⚡ Mauksh Truth: ...</p>

Important Period should mention useful parts of the month
such as early/mid/late month when astrologically relevant.

Return ONLY valid JSON.

Required keys:
date, aries, taurus, gemini, cancer, leo, virgo,
libra, scorpio, sagittarius, capricorn, aquarius, pisces
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

if set(data.keys()) != set(required):
    raise ValueError("Invalid monthly horoscope structure")

for sign in SIGNS:
    if len(data[sign].strip()) < 200:
        raise ValueError(f"{sign} horoscope is too short")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Monthly horoscope generated: {month}")
