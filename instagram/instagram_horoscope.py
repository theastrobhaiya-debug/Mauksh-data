import json
import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SIGNS = [
    ("aries", "♈", "Aries"),
    ("taurus", "♉", "Taurus"),
    ("gemini", "♊", "Gemini"),
    ("cancer", "♋", "Cancer"),
    ("leo", "♌", "Leo"),
    ("virgo", "♍", "Virgo"),
    ("libra", "♎", "Libra"),
    ("scorpio", "♏", "Scorpio"),
    ("sagittarius", "♐", "Sagittarius"),
    ("capricorn", "♑", "Capricorn"),
    ("aquarius", "♒", "Aquarius"),
    ("pisces", "♓", "Pisces"),
]

today = datetime.now().strftime("%d %B %Y")

prompt = f"""
You are the Vedic astrologer for Mauksh.

Create today's DAILY HOROSCOPE for:
{today}

IMPORTANT:
This is for an Instagram audience in India.

ASTROLOGY:
Use Vedic astrology, not Western astrology.

Use:
- Sidereal zodiac
- Lahiri ayanamsa
- Current planetary positions
- Sun
- Moon
- Mars
- Mercury
- Jupiter
- Venus
- Saturn
- Rahu
- Ketu
- Current retrogrades
- Important conjunctions
- Important aspects
- Moon movement
- Nakshatra influence where relevant

First reason about the actual planetary/transit situation for today.

Then interpret those transits separately for all 12 zodiac signs.

Do NOT create generic horoscope content.

The prediction for Aries must genuinely differ from Taurus.
Do not simply change the zodiac name while keeping the same prediction.

LANGUAGE:
Write in natural Indian Hinglish.

Use Roman Hindi mixed naturally with English.

Example tone:
"Aaj work front par ek important conversation ho sakti hai.
Aapko apni baat clearly rakhni hogi, lekin unnecessary argument avoid karein."

Do NOT use overly Sanskritized Hindi.

Do NOT sound like AI.

Do NOT use repetitive motivational phrases.

CONTENT FOR EACH SIGN:

1. Overall
2. Career
3. Love
4. Money
5. Advice
6. Mauksh Truth

Keep each sign concise enough for Instagram.

Each sign should be approximately 70–110 words.

"Mauksh Truth" must be a short, memorable and specific insight.

Avoid:
- fearmongering
- death predictions
- accident predictions
- medical claims
- guaranteed financial results
- guaranteed marriage/divorce claims
- generic filler

OUTPUT:

Return ONLY valid JSON.

Use exactly this structure:

{{
  "date": "{today}",
  "transit_summary": "...",
  "aries": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "taurus": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "gemini": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "cancer": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "leo": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "virgo": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "libra": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "scorpio": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "sagittarius": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "capricorn": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "aquarius": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }},
  "pisces": {{
      "overall": "...",
      "career": "...",
      "love": "...",
      "money": "...",
      "advice": "...",
      "mauksh_truth": "..."
  }}
}}

Before returning, verify:
- Exactly 12 signs
- No missing sections
- No duplicated predictions
- Predictions are based on today's Vedic transits
- Natural Hinglish
- Valid JSON only
"""

response = client.responses.create(
    model="gpt-5.6",
    tools=[{"type": "web_search"}],
    input=prompt,
)

text = response.output_text.strip()

if text.startswith("```"):
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

data = json.loads(text)

required = ["date", "transit_summary"] + [x[0] for x in SIGNS]

for key in required:
    if key not in data:
        raise ValueError(f"Missing key: {key}")

sections = [
    "overall",
    "career",
    "love",
    "money",
    "advice",
    "mauksh_truth",
]

for slug, _, _ in SIGNS:
    for section in sections:
        value = data[slug].get(section)

        if not value:
            raise ValueError(
                f"Missing {section} for {slug}"
            )

output_file = OUTPUT_DIR / "daily_horoscope.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=2,
    )

print(f"Generated: {output_file}")
