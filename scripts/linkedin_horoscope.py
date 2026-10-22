
import os
import json
import requests
import swisseph as swe

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from openai import OpenAI


# ============================================================
# MAUKSH DAILY CAREER HOROSCOPE
# Actual Vedic transits + OpenAI interpretation + Buffer
# ============================================================

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BUFFER_TOKEN = os.environ["MAUKSH_CAREER_BUFFER_TOKEN"]

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
BUFFER_URL = "https://api.buffer.com"

TZ = ZoneInfo("Asia/Kolkata")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# DATE AND REFERENCE TIME
# ============================================================

now = datetime.now(TZ)
today = now.strftime("%d %B %Y")

# Use a consistent reference time for daily predictions.
# All planetary positions are calculated for 12 noon IST.
reference_time = datetime.combine(
    now.date(),
    time(12, 0),
    tzinfo=TZ
)

utc_time = reference_time.astimezone(timezone.utc)

julian_day = swe.julday(
    utc_time.year,
    utc_time.month,
    utc_time.day,
    (
        utc_time.hour
        + utc_time.minute / 60
        + utc_time.second / 3600
    )
)

print("=" * 60)
print("MAUKSH DAILY CAREER HOROSCOPE")
print("Date:", today)
print("Transit reference:", reference_time.isoformat())
print("=" * 60)


# ============================================================
# VEDIC TRANSIT CALCULATION
# Swiss Ephemeris + Lahiri sidereal zodiac
# ============================================================

swe.set_sid_mode(swe.SIDM_LAHIRI)

FLAGS = (
    swe.FLG_SWIEPH
    | swe.FLG_SIDEREAL
    | swe.FLG_SPEED
)

SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}


def calculate_position(planet_id):
    result, ret_flags = swe.calc_ut(
        julian_day,
        planet_id,
        FLAGS
    )

    longitude = result[0] % 360
    speed = result[3]

    sign_index = int(longitude // 30)
    degree_in_sign = longitude % 30

    return {
        "sign": SIGNS[sign_index],
        "degree": round(degree_in_sign, 4),
        "longitude": round(longitude, 4),
        "retrograde": speed < 0,
        "daily_motion_degrees": round(speed, 6),
    }


transits = {}

for planet_name, planet_id in PLANETS.items():
    transits[planet_name] = calculate_position(planet_id)

# Ketu is exactly opposite the selected Rahu node.
rahu_longitude = transits["Rahu"]["longitude"]
ketu_longitude = (rahu_longitude + 180) % 360

ketu_sign_index = int(ketu_longitude // 30)

transits["Ketu"] = {
    "sign": SIGNS[ketu_sign_index],
    "degree": round(ketu_longitude % 30, 4),
    "longitude": round(ketu_longitude, 4),
    "retrograde": True,
    "daily_motion_degrees": None,
}

# Calculate the Moon's nakshatra using 27 equal divisions.
moon_longitude = transits["Moon"]["longitude"]
nakshatra_number = int(moon_longitude / (360 / 27))

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika",
    "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha",
    "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati",
    "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha",
    "Shravana", "Dhanishtha", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

moon_nakshatra = NAKSHATRAS[nakshatra_number]

print("\nCALCULATED SIDEREAL TRANSITS")
print("-" * 60)

for planet, data in transits.items():
    motion = (
        "Retrograde"
        if data["retrograde"]
        else "Direct"
    )

    print(
        f"{planet:8} "
        f"{data['sign']:12} "
        f"{data['degree']:7.3f}° "
        f"{motion}"
    )

print("Moon Nakshatra:", moon_nakshatra)

transit_context = {
    "date": today,
    "timezone": "Asia/Kolkata",
    "reference_time": reference_time.isoformat(),
    "zodiac": "Sidereal",
    "ayanamsha": "Lahiri",
    "node_method": "Mean lunar node",
    "moon_nakshatra": moon_nakshatra,
    "planetary_positions": transits,
}


# ============================================================
# OPENAI — TRANSIT-BASED HOROSCOPE GENERATION
# ============================================================

prompt = f"""
You are the lead Vedic astrologer and editorial writer
for Mauksh.

Create a daily career horoscope for LinkedIn using the
VERIFIED PLANETARY POSITION DATA provided below.

DATE: {today}

ASTROLOGICAL SYSTEM:
Vedic astrology, sidereal zodiac, Lahiri ayanamsha.
Reference time: 12 noon, Asia/Kolkata.

ACTUAL TRANSIT DATA:
{json.dumps(transit_context, indent=2)}

NON-NEGOTIABLE RULE:
Use the supplied planetary positions as the astronomical
source of truth. Do not invent different positions,
sign ingresses, conjunctions, or retrograde status.

Do not claim you have verified an ephemeris independently.
The positions have already been calculated.

YOUR TASK:

Produce twelve genuinely distinct, career-specific
predictions derived from the supplied transits.

STEP 1 — ASTROLOGICAL REASONING

Treat each of the twelve zodiac signs in turn as the
ascendant and use whole-sign houses.

For each sign:
1. Determine which signs occupy its 2nd, 3rd, 6th,
   7th, 10th and 11th houses.
2. Identify which supplied transiting planets occupy
   or aspect those houses.
3. Apply classical Parashari graha drishti:
   all planets aspect the 7th house from themselves;
   Mars additionally aspects the 4th and 8th;
   Jupiter additionally aspects the 5th and 9th;
   Saturn additionally aspects the 3rd and 10th.
4. Consider the transiting planet's nature, sign dignity,
   conjunctions, house placement and relevant interactions.
5. Prioritize the strongest defensible career implication
   instead of listing every possible interpretation.

Do not confuse sign-based general predictions with
individual birth-chart analysis. You do not have each
reader's natal chart, natal Moon, dashas or birth details.

STEP 2 — SPECIFIC CAREER OUTCOMES

Translate the astrological factors into a plausible,
specific professional situation.

Possible outcomes include:
- A manager scrutinizing unfinished deliverables.
- A negotiation over payment, compensation or contract terms.
- Delays in approvals or decisions from senior management.
- Pressure from competitors or a demanding workload.
- A client relationship requiring clearer boundaries.
- A communication error affecting a project.
- A need to document decisions or review contractual details.
- A professional connection helping resolve a bottleneck.
- Greater responsibility without immediate recognition.
- Reassessment of a role, business strategy or career direction.
- Foreign-client, technology or online-business developments.
- A period of lower visibility or behind-the-scenes work.

These are examples, not predictions to copy automatically.
Choose a scenario only when the actual transits support it.

Do not invent specific meetings, job offers, promotions,
dismissals or financial gains without sufficient astrological
justification.

STEP 3 — ELIMINATE GENERIC AND REPETITIVE WRITING

Before drafting, internally map all twelve signs to:
- Their strongest relevant transit.
- The career house involved.
- The likely professional implication.
- One practical, sign-specific prediction.

Compare all twelve predictions before returning them.

Each prediction must differ in its principal astrological
rationale and professional implication, not merely its wording.

Do not repeatedly predict:
- Promotion or recognition.
- New opportunities.
- Job changes.
- Hard work paying off.
- Communication problems.
- Delays followed by success.

Do not assign a different generic career-advice sentence
to each sign.

Avoid motivational filler, vague statements, false certainty,
and unsupported claims about today's events.

A challenging transit may indicate friction or caution.
A favorable transit may support a constructive development.
Do not force every sign into a positive prediction.

If the transits do not support a dramatic event, describe
a specific, proportionate professional tendency instead.

STEP 4 — DAILY NOVELTY

Make the predictions specific to the supplied planetary
configuration for {today}.

Do not rely on familiar horoscope templates.
Do not claim that predictions differ from previous days
unless historical posts have actually been supplied for
comparison.

Use different sentence structures and professional contexts.
Keep the tone grounded, clear and credible.

STEP 5 — EXACT OUTPUT FORMAT

Mauksh Daily Career Horoscope
{today}

♈ Aries: Prediction

♉ Taurus: Prediction

♊ Gemini: Prediction

♋ Cancer: Prediction

♌ Leo: Prediction

♍ Virgo: Prediction

♎ Libra: Prediction

♏ Scorpio: Prediction

♐ Sagittarius: Prediction

♑ Capricorn: Prediction

♒ Aquarius: Prediction

♓ Pisces: Prediction

FORMATTING RULES:
- English only.
- One or two concise sentences per sign.
- Career and professional life only.
- No hashtags.
- No introductory paragraph or conclusion.
- No explanations of the calculations.
- No additional emojis.
- Preserve the exact title, date and sign order.

FINAL AUDIT:
Check that all twelve signs are present, the house placements
are correct, the transit rationale is defensible, and the
predictions are not interchangeable.

Return only the finished LinkedIn post.
"""

print("\nGenerating horoscope with OpenAI...")

response = client.responses.create(
    model=OPENAI_MODEL,
    input=prompt
)

post_text = (response.output_text or "").strip()

if not post_text:
    print("\nOPENAI RETURNED AN EMPTY TEXT RESPONSE")
    print(response.model_dump_json(indent=2))
    raise RuntimeError(
        "OpenAI returned no horoscope text. "
        "Inspect the response details above."
    )

if response.status != "completed":
    raise RuntimeError(
        f"OpenAI response did not complete: {response.status}"
    )

print("\nHOROSCOPE GENERATED")
print("=" * 60)
print(post_text)
print("=" * 60)


# ============================================================
# BUFFER API HELPERS
# ============================================================

headers = {
    "Authorization": f"Bearer {BUFFER_TOKEN}",
    "Content-Type": "application/json",
}


def buffer_graphql(query, variables=None):
    payload = {"query": query}

    if variables is not None:
        payload["variables"] = variables

    result = requests.post(
        BUFFER_URL,
        headers=headers,
        json=payload,
        timeout=45,
    )

    if result.status_code != 200:
        raise RuntimeError(
            f"Buffer HTTP error {result.status_code}: "
            f"{result.text}"
        )

    try:
        data = result.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Buffer returned invalid JSON: {result.text}"
        ) from exc

    if data.get("errors"):
        raise RuntimeError(
            "Buffer GraphQL error: "
            + json.dumps(data["errors"], indent=2)
        )

    return data


# ============================================================
# STEP 1 — GET ORGANIZATION
# ============================================================

print("\nGetting Buffer organization...")

organization_query = """
query GetOrganizations {
    account {
        organizations {
            id
            name
        }
    }
}
"""

organization_data = buffer_graphql(
    organization_query
)

organizations = (
    organization_data.get("data", {})
    .get("account", {})
    .get("organizations", [])
)

if not organizations:
    raise RuntimeError(
        "No Buffer organization found for this API token."
    )

organization = organizations[0]
organization_id = organization["id"]

print("Organization:", organization.get("name"))
print("Organization ID:", organization_id)


# ============================================================
# STEP 2 — GET CHANNELS AND SELECT LINKEDIN
# ============================================================

print("\nGetting Buffer channels...")

channels_query = f"""
query GetChannels {{
    channels(
        input: {{
            organizationId: "{organization_id}"
        }}
    ) {{
        id
        name
        displayName
        service
    }}
}}
"""

channels_data = buffer_graphql(channels_query)

channels = (
    channels_data.get("data", {})
    .get("channels", [])
)

if not channels:
    raise RuntimeError(
        "No Buffer channels were returned."
    )

print("\nAvailable Buffer channels:")

for item in channels:
    print(
        "-",
        item.get("displayName"),
        "|",
        item.get("service"),
        "|",
        item.get("id"),
    )

# Do not accidentally publish to another social network.
linkedin_channels = [
    item
    for item in channels
    if "linkedin" in " ".join([
        str(item.get("service") or ""),
        str(item.get("name") or ""),
        str(item.get("displayName") or ""),
    ]).lower()
]

if not linkedin_channels:
    raise RuntimeError(
        "No LinkedIn channel was found. "
        "Check the channel list and connect your LinkedIn "
        "Page to Buffer before publishing."
    )

# Prefer an explicitly named Mauksh LinkedIn Page if several
# LinkedIn channels are connected.
mauksh_channels = [
    item for item in linkedin_channels
    if "mauksh" in " ".join([
        str(item.get("name") or ""),
        str(item.get("displayName") or ""),
    ]).lower()
]

if len(mauksh_channels) == 1:
    channel = mauksh_channels[0]
elif len(linkedin_channels) == 1:
    channel = linkedin_channels[0]
else:
    raise RuntimeError(
        "Multiple LinkedIn channels were found. "
        "Configure an explicit channel ID to avoid "
        "publishing to the wrong Page."
    )

channel_id = channel["id"]

print("\nSelected LinkedIn channel:")
print("Name:", channel.get("name"))
print("Display name:", channel.get("displayName"))
print("Channel ID:", channel_id)


# ============================================================
# STEP 3 — CREATE BUFFER POST
# ============================================================

print("\nSubmitting horoscope to Buffer...")

create_post_query = """
mutation CreatePost($input: CreatePostInput!) {
    createPost(input: $input) {
        ... on PostActionSuccess {
            post {
                id
                text
                dueAt
            }
        }
        ... on MutationError {
            message
        }
    }
}
"""

variables = {
    "input": {
        "text": post_text,
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "shareNow",
    }
}

create_post_data = buffer_graphql(
    create_post_query,
    variables,
).get("data", {}).get("createPost")

if not create_post_data:
    raise RuntimeError(
        "Unexpected Buffer response: "
        + json.dumps(create_post_data)
    )

if create_post_data.get("message"):
    raise RuntimeError(
        "Buffer rejected the post: "
        + create_post_data["message"]
    )

post = create_post_data.get("post")

if not post:
    raise RuntimeError(
        "Buffer did not return a post ID."
    )


# ============================================================
# SUCCESS
# ============================================================

print("\n" + "=" * 60)
print("SUCCESS — HOROSCOPE ADDED TO BUFFER")
print("=" * 60)

print("Date:", today)
print("Channel:", channel.get("displayName"))
print("Buffer Post ID:", post.get("id"))
print("Buffer Due At:", post.get("dueAt"))

print("\nFINAL LINKEDIN POST")
print("-" * 60)
print(post_text)
print("-" * 60)

# Close the Swiss Ephemeris resources.
swe.close()
