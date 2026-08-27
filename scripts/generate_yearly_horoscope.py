import json
import os
from datetime import datetime, timezone
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SIGNS = [
    "aries","taurus","gemini","cancer","leo","virgo",
    "libra","scorpio","sagittarius","capricorn","aquarius","pisces"
]

OUTPUT = "Horoscope3.json"

year = datetime.now(timezone.utc).year + 1

previous = {}
try:
    with open(OUTPUT, "r", encoding="utf-8") as f:
        previous = json.load(f)
except Exception:
    pass

prompt = f"""
You are the senior Vedic astrologer for Mauksh.

Create a detailed YEARLY Vedic horoscope for {year}
for all 12 zodiac signs.

Use Vedic sidereal astrology.

Research the major planetary movements throughout {year}.

Analyze:
- Jupiter's movement and major aspects
- Saturn's movement
- Rahu and Ketu
- Saturn/Jupiter retrogrades
- Mercury retrogrades
- Venus/Mars retrogrades when applicable
- Eclipses
- Major conjunctions
- Important sign changes
- Important nakshatra influences

Do NOT write a generic Western horoscope.

Each zodiac sign must have its own astrological storyline.

Include timing throughout the year:
- January–March
- April–June
- July–September
- October–December

Previous yearly horoscope:
{json.dumps(previous, ensure_ascii=False)}

Do not paraphrase it.

Write natural, insightful Hinglish.

For every sign include:

<h3>♈ Aries – {year}</h3>
<p>🔥 Year Theme: ...</p>
<p>💼 Career: ...</p>
<p>❤️ Love: ...</p>
<p>💰 Money: ...</p>
<p>📅 Jan–Mar: ...</p>
<p>📅 Apr–Jun: ...</p>
<p>📅 Jul–Sep: ...</p>
<p>📅 Oct–Dec: ...</p>
<p>🧘 Advice: ...</p>
<p class="truth">⚡ Mauksh Truth: ...</p>

Make every sign substantially different.

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
    raise ValueError("Invalid yearly horoscope structure")

for sign in SIGNS:
    if len(data[sign].strip()) < 300:
        raise ValueError(f"{sign} yearly horoscope is too short")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Yearly horoscope generated: {year}")
