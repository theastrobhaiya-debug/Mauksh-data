import json
import os
from datetime import datetime, timezone
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SIGNS = [
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
]

HOROSCOPE_FILE = "Horoscope.json"

# --------------------------------------------------
# Read the previous horoscope
# --------------------------------------------------

try:
    with open(HOROSCOPE_FILE, "r", encoding="utf-8") as f:
        previous = json.load(f)
except Exception:
    previous = {}

previous_text = json.dumps(
    previous,
    ensure_ascii=False,
    indent=2
)

today = datetime.now(timezone.utc).strftime("%d %B %Y")

# --------------------------------------------------
# Prompt
# --------------------------------------------------

prompt = f"""
You are the lead Vedic astrologer and daily horoscope writer for Mauksh.

TODAY:
{today}

Create a completely fresh DAILY HOROSCOPE for all 12 zodiac signs.

ASTROLOGY REQUIREMENTS
----------------------
Use Vedic / sidereal astrology.

Before writing, research the actual planetary positions and important
transits applicable to today.

Pay attention to relevant factors such as:
- Moon sign and movement
- Sun
- Mercury
- Venus
- Mars
- Jupiter
- Saturn
- Rahu and Ketu
- Retrogrades
- Important conjunctions/aspects
- Nakshatra influences when relevant

Do NOT simply write generic Western-style zodiac predictions.

Each sign must be interpreted according to how today's actual
sidereal planetary situation affects that sign.

WRITING STYLE
-------------
Write in natural, polished Hinglish.

The tone should feel like a knowledgeable human astrologer speaking
directly to the reader.

Do NOT sound robotic.

Do NOT use the same prediction for multiple signs.

Do NOT force every sign into the same story.

Some signs may have a stronger career day.
Another may have relationship developments.
Another may need financial caution.
Another may experience mental restlessness.
Another may have a productive or lucky window.

The differences must come from the astrology.

IMPORTANT ANTI-REPETITION RULE
------------------------------
Below is the previous Horoscope.json.

Study it carefully.

Do NOT copy its sentences, phrases, structure of ideas, or dominant
themes.

Today's horoscope must feel meaningfully different from yesterday.

If yesterday focused on:
- patience
- communication
- unexpected expenses
- emotional distance
- taking things slowly

then do NOT simply rewrite those same ideas using different words.

Instead, find new manifestations of today's planetary transits.

Previous horoscope:
{previous_text}

CONTENT
-------
For every zodiac sign include:

1. Energy
2. Career
3. Love
4. Money
5. Advice
6. Mauksh Truth

Keep each sign detailed enough to be genuinely useful.

The "Mauksh Truth" should be a short, memorable insight that feels
specific to that sign's situation today.

Avoid:
- fearmongering
- guaranteed predictions
- death/accident predictions
- medical claims
- extreme financial claims
- repetitive motivational filler
- generic statements that could apply equally to every sign

HTML FORMAT
-----------
Each sign must be returned as ONE HTML string.

Use this structure:

<h3>♈ Aries</h3>
<p>🔥 Energy: ...</p>
<p>💼 Career: ...</p>
<p>❤️ Love: ...</p>
<p>💰 Money: ...</p>
<p>🧘 Advice: ...</p>
<p class="truth">⚡ Mauksh Truth: ...</p>

Use the correct zodiac emoji and name for every sign.

JSON FORMAT
-----------
Return ONLY valid JSON.

Do NOT use Markdown.
Do NOT use ```json.
Do NOT add explanations outside the JSON.

The JSON must contain exactly these keys:

{{
  "date": "{today}",
  "aries": "...",
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

FINAL QUALITY CHECK
-------------------
Before returning the JSON, internally verify:

1. Exactly 12 zodiac signs are present.
2. Every sign has all six sections.
3. Every sign is materially different from the others.
4. Today's predictions are based on today's Vedic/sidereal transits.
5. The previous horoscope has NOT simply been paraphrased.
6. The HTML is valid.
7. The output is valid JSON.
8. The writing sounds human and natural.
"""

# --------------------------------------------------
# Generate
# --------------------------------------------------

response = client.responses.create(
    model="gpt-5.1",
    tools=[{"type": "web_search"}],
    input=prompt
)

text = response.output_text.strip()

# Remove accidental Markdown fences
if text.startswith("```"):
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

# --------------------------------------------------
# Validate JSON
# --------------------------------------------------

data = json.loads(text)

required_keys = ["date"] + SIGNS

if set(data.keys()) != set(required_keys):
    raise ValueError(
        "Generated JSON does not contain exactly the required fields."
    )

for sign in SIGNS:

    if not isinstance(data[sign], str):
        raise ValueError(f"{sign} horoscope is not a string.")

    if len(data[sign].strip()) < 150:
        raise ValueError(
            f"{sign} horoscope is too short."
        )

    required_sections = [
        "Energy:",
        "Career:",
        "Love:",
        "Money:",
        "Advice:",
        "Mauksh Truth:"
    ]

    for section in required_sections:
        if section not in data[sign]:
            raise ValueError(
                f"{sign} is missing section: {section}"
            )

# --------------------------------------------------
# Final safety check
# --------------------------------------------------

# Make sure we never accidentally destroy the existing
# horoscope with an empty/broken response.

if len(data) != 13:
    raise ValueError("Unexpected number of JSON fields.")

# --------------------------------------------------
# Write only after ALL validation passes
# --------------------------------------------------

with open(HOROSCOPE_FILE, "w", encoding="utf-8") as f:
    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=2
    )

print(
    f"Successfully generated and validated Horoscope.json for {today}"
)