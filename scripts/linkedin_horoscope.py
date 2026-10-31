
import os
import json
import re
import base64
import requests
import swisseph as swe

from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI


# ============================================================
# MAUKSH DAILY CAREER HOROSCOPE — LINKEDIN
# FULL AUTOMATED VERSION
# ============================================================

TZ = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

TODAY = datetime.now(TZ)
DATE_TEXT = TODAY.strftime("%d %B %Y")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BUFFER_TOKEN = os.environ["MAUKSH_CAREER_BUFFER_TOKEN"]

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5-mini"
)

BUFFER_URL = "https://api.buffer.com"

# GitHub history
HISTORY_PATH = "data/linkedin_history.json"

GITHUB_REPOSITORY = os.getenv(
    "GITHUB_REPOSITORY",
    ""
)

GITHUB_TOKEN = os.getenv(
    "GH_HISTORY_TOKEN",
    ""
)

GITHUB_BRANCH = os.getenv(
    "GITHUB_REF_NAME",
    "main"
)

# Preview mode prevents publishing.
PREVIEW_ONLY = (
    os.getenv("PREVIEW_ONLY", "false").lower() == "true"
)

# Mean or true lunar node.
RAHU_NODE_MODE = os.getenv(
    "RAHU_NODE_MODE",
    "mean"
).lower()

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# ZODIAC SIGNS
# ============================================================

SIGNS = [
    ("ARIES", "♈"),
    ("TAURUS", "♉"),
    ("GEMINI", "♊"),
    ("CANCER", "♋"),
    ("LEO", "♌"),
    ("VIRGO", "♍"),
    ("LIBRA", "♎"),
    ("SCORPIO", "♏"),
    ("SAGITTARIUS", "♐"),
    ("CAPRICORN", "♑"),
    ("AQUARIUS", "♒"),
    ("PISCES", "♓"),
]

SIGN_NAMES = [item[0] for item in SIGNS]
SYMBOLS = dict(SIGNS)

SIGN_NAMES_FULL = [
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


# ============================================================
# TRADITIONAL VEDIC SIGN LORDS
# ============================================================

SIGN_LORDS = {
    "ARIES": "Mars",
    "TAURUS": "Venus",
    "GEMINI": "Mercury",
    "CANCER": "Moon",
    "LEO": "Sun",
    "VIRGO": "Mercury",
    "LIBRA": "Venus",
    "SCORPIO": "Mars",
    "SAGITTARIUS": "Jupiter",
    "CAPRICORN": "Saturn",
    "AQUARIUS": "Saturn",
    "PISCES": "Jupiter",
}


# ============================================================
# PLANETARY EPHEMERIS SETTINGS
# ============================================================

PLANET_BODIES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
}

# Traditional Parashari planetary aspects.
# Rahu and Ketu are deliberately excluded.
ASPECTS = {
    "Sun": [7],
    "Moon": [7],
    "Mars": [4, 7, 8],
    "Mercury": [7],
    "Jupiter": [5, 7, 9],
    "Venus": [7],
    "Saturn": [3, 7, 10],
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def get_ordinal(number):

    suffix = "th"

    if number % 100 not in (11, 12, 13):
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(number % 10, "th")

    return f"{number}{suffix}"


def get_sign_and_degree(longitude):

    longitude = longitude % 360

    sign_index = int(longitude // 30)
    degree = longitude % 30

    return (
        SIGN_NAMES_FULL[sign_index],
        round(degree, 4),
        sign_index,
    )


def get_motion(speed):

    if abs(speed) < 0.0001:
        return "stationary"

    return (
        "retrograde"
        if speed < 0
        else "direct"
    )


def parse_json(raw):

    raw = raw.strip()

    if raw.startswith("```"):
        raw = re.sub(
            r"^```(?:json)?\s*",
            "",
            raw
        )

        raw = re.sub(
            r"\s*```$",
            "",
            raw
        )

    try:
        return json.loads(raw)

    except json.JSONDecodeError as exc:

        raise ValueError(
            "OpenAI returned invalid JSON: "
            + raw[:1000]
        ) from exc


# ============================================================
# GITHUB HISTORY API
# ============================================================

def github_headers():

    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GH_HISTORY_TOKEN is missing."
        )

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url():

    if (
        not GITHUB_REPOSITORY
        or "/" not in GITHUB_REPOSITORY
    ):
        raise RuntimeError(
            "GITHUB_REPOSITORY is missing or invalid."
        )

    return (
        "https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{HISTORY_PATH}"
    )


def load_history():

    print("Loading LinkedIn history from GitHub...")

    response = requests.get(
        github_file_url(),
        headers=github_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=30,
    )

    if response.status_code == 404:

        print(
            "History file not found. "
            "Starting with empty history."
        )

        return [], None

    if response.status_code != 200:

        raise RuntimeError(
            "GitHub history read failed: "
            f"{response.status_code} "
            f"{response.text[:1000]}"
        )

    result = response.json()

    if result.get("encoding") != "base64":
        raise RuntimeError(
            "Unexpected GitHub history encoding."
        )

    try:

        content = base64.b64decode(
            result["content"]
        ).decode("utf-8")

        history = json.loads(content)

    except (ValueError, KeyError) as exc:

        raise RuntimeError(
            "History file contains invalid JSON."
        ) from exc

    if not isinstance(history, list):
        raise RuntimeError(
            "GitHub history must contain a JSON list."
        )

    print(
        f"Loaded {len(history)} history records."
    )

    return history[-30:], result.get("sha")


def save_history(history, existing_sha=None):

    print("Saving history to GitHub...")

    content = json.dumps(
        history[-30:],
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("ascii")

    payload = {
        "message": (
            "Update LinkedIn career horoscope history: "
            + DATE_TEXT
        ),
        "content": encoded_content,
        "branch": GITHUB_BRANCH,
    }

    if existing_sha:
        payload["sha"] = existing_sha

    response = requests.put(
        github_file_url(),
        headers=github_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 201):

        raise RuntimeError(
            "GitHub history write failed: "
            f"{response.status_code} "
            f"{response.text[:1000]}"
        )

    print(
        "LinkedIn history successfully committed."
    )


# ============================================================
# STAGE 1A: CALCULATE REAL PLANETARY POSITIONS
# ============================================================

def calculate_transits():

    print(
        "\nCalculating Lahiri sidereal planetary positions..."
    )

    if RAHU_NODE_MODE not in ("mean", "true"):
        raise ValueError(
            "RAHU_NODE_MODE must be mean or true."
        )

    # Set Lahiri ayanamsha.
    swe.set_sid_mode(
        swe.SIDM_LAHIRI,
        0,
        0
    )

    # Reference time: 12 PM IST.
    reference_time = datetime(
        TODAY.year,
        TODAY.month,
        TODAY.day,
        12,
        0,
        0,
        tzinfo=TZ
    )

    utc_time = reference_time.astimezone(UTC)

    utc_hour = (
        utc_time.hour
        + utc_time.minute / 60
        + utc_time.second / 3600
    )

    jd = swe.julday(
        utc_time.year,
        utc_time.month,
        utc_time.day,
        utc_hour,
        swe.GREG_CAL
    )

    # Moshier ephemeris calculation.
    # Does not require external ephemeris data files.
    flags = (
        swe.FLG_MOSEPH
        | swe.FLG_SIDEREAL
        | swe.FLG_SPEED
    )

    ayanamsha = swe.get_ayanamsa_ut(jd)

    transits = []
    raw_positions = {}

    # Seven classical planets.
    for planet, body in PLANET_BODIES.items():

        xx, retflag = swe.calc_ut(
            jd,
            body,
            flags
        )

        longitude = xx[0] % 360
        speed = xx[3]

        sign, degree, sign_index = (
            get_sign_and_degree(longitude)
        )

        raw_positions[planet] = {
            "longitude": longitude,
            "speed": speed,
            "sign_index": sign_index,
        }

        transits.append({
            "planet": planet,
            "sign": sign,
            "degree": degree,
            "longitude": round(longitude, 6),
            "daily_speed": round(speed, 6),
            "motion": get_motion(speed),
            "confidence": "ephemeris_calculated",
        })

    # Rahu calculation.
    node_body = (
        swe.TRUE_NODE
        if RAHU_NODE_MODE == "true"
        else swe.MEAN_NODE
    )

    xx, retflag = swe.calc_ut(
        jd,
        node_body,
        flags
    )

    rahu_longitude = xx[0] % 360
    rahu_speed = xx[3]

    # Ketu is exactly opposite Rahu.
    ketu_longitude = (
        rahu_longitude + 180
    ) % 360

    rahu_sign, rahu_degree, rahu_sign_index = (
        get_sign_and_degree(rahu_longitude)
    )

    ketu_sign, ketu_degree, ketu_sign_index = (
        get_sign_and_degree(ketu_longitude)
    )

    raw_positions["Rahu"] = {
        "longitude": rahu_longitude,
        "speed": rahu_speed,
        "sign_index": rahu_sign_index,
    }

    raw_positions["Ketu"] = {
        "longitude": ketu_longitude,
        "speed": rahu_speed,
        "sign_index": ketu_sign_index,
    }

    transits.extend([
        {
            "planet": "Rahu",
            "sign": rahu_sign,
            "degree": rahu_degree,
            "longitude": round(
                rahu_longitude, 6
            ),
            "daily_speed": round(
                rahu_speed, 6
            ),
            "motion": get_motion(rahu_speed),
            "confidence": "ephemeris_calculated",
            "node_type": RAHU_NODE_MODE,
        },
        {
            "planet": "Ketu",
            "sign": ketu_sign,
            "degree": ketu_degree,
            "longitude": round(
                ketu_longitude, 6
            ),
            "daily_speed": round(
                rahu_speed, 6
            ),
            "motion": get_motion(rahu_speed),
            "confidence": "calculated_opposite_of_rahu",
            "node_type": RAHU_NODE_MODE,
        },
    ])

    print(
        "Lahiri Ayanamsha:",
        round(ayanamsha, 6)
    )

    for item in transits:

        print(
            f'{item["planet"]:10} '
            f'{item["sign"]:12} '
            f'{item["degree"]:8} '
            f'{item["motion"]}'
        )

    return {
        "date": DATE_TEXT,
        "reference_time": "12:00 PM IST",
        "utc_time": utc_time.isoformat(),
        "zodiac": "Sidereal",
        "ayanamsha": "Lahiri",
        "ayanamsha_value": round(
            ayanamsha, 6
        ),
        "ephemeris": "Swiss Ephemeris Moshier",
        "node_method": RAHU_NODE_MODE,
        "transits": transits,
        "raw_positions": raw_positions,
    }


# ============================================================
# STAGE 1B: WHOLE-SIGN HOUSE ANALYSIS
# ============================================================

def build_sign_context(transit_data):

    positions = transit_data["raw_positions"]

    contexts = []

    for asc_index, asc_sign in enumerate(SIGN_NAMES):

        house_positions = []
        aspects_received = []
        houses_activated = set()

        # Planetary house placements.
        for planet, position in positions.items():

            planet_sign = position["sign_index"]

            house = (
                (planet_sign - asc_index) % 12
            ) + 1

            house_positions.append({
                "planet": planet,
                "house": house,
                "house_ordinal": get_ordinal(house),
                "sign": SIGN_NAMES_FULL[
                    planet_sign
                ],
            })

            houses_activated.add(house)

            # Traditional aspects from seven planets only.
            for aspect_number in ASPECTS.get(
                planet, []
            ):

                target_sign_index = (
                    planet_sign + aspect_number - 1
                ) % 12

                target_house = (
                    (
                        target_sign_index - asc_index
                    ) % 12
                ) + 1

                aspects_received.append({
                    "planet": planet,
                    "aspect": aspect_number,
                    "target_house": target_house,
                    "target_sign": SIGN_NAMES_FULL[
                        target_sign_index
                    ],
                })

                houses_activated.add(target_house)

        # Career-relevant house lords.
        career_lords = []

        for house in [2, 6, 10, 11]:

            house_sign_index = (
                asc_index + house - 1
            ) % 12

            house_sign = SIGN_NAMES[
                house_sign_index
            ]

            lord = SIGN_LORDS[house_sign]

            lord_position = positions[lord]

            lord_transit_house = (
                (
                    lord_position["sign_index"]
                    - asc_index
                ) % 12
            ) + 1

            career_lords.append({
                "house": house,
                "house_sign": SIGN_NAMES_FULL[
                    house_sign_index
                ],
                "lord": lord,
                "lord_transit_sign": SIGN_NAMES_FULL[
                    lord_position["sign_index"]
                ],
                "lord_transit_house": (
                    lord_transit_house
                ),
            })

        contexts.append({
            "sign": asc_sign,
            "ascendant_sign": asc_sign,
            "houses_activated": sorted(
                houses_activated
            ),
            "transit_house_positions": (
                house_positions
            ),
            "aspects_received": aspects_received,
            "career_house_lords": career_lords,
        })

    return contexts


# ============================================================
# STAGE 1C: OPENAI VEDIC CAREER INTERPRETATION
# ============================================================

def analyze_transits(history):

    transit_data = calculate_transits()

    sign_contexts = build_sign_context(
        transit_data
    )

    prompt = f"""
You are an expert in traditional Vedic sidereal astrology.

The planetary positions below have been calculated
using Swiss Ephemeris and Lahiri Ayanamsha.

These are the astronomical inputs.
NEVER recalculate, change or guess their positions.

CALCULATED TRANSITS:
{json.dumps(transit_data, ensure_ascii=False, indent=2)}

WHOLE-SIGN HOUSE CONTEXT:
{json.dumps(sign_contexts, ensure_ascii=False, indent=2)}

PREVIOUSLY PUBLISHED CAREER SCENARIOS:
{json.dumps(history, ensure_ascii=False, indent=2)}

==================================================
YOUR TASK
==================================================

Interpret the calculated transits for all 12 signs,
treating each sign as the ascendant.

Use whole-sign houses.

Career factors:

2nd house: income, financial resources and speech.
6th house: employment, workload, colleagues,
competition and workplace disputes.
10th house: profession, career, authority and status.
11th house: gains, professional networks and ambitions.

Consider house lords, their transit placements and
the supplied planetary aspects.

Traditional Parashari aspects:

Sun, Moon, Mercury, Venus: 7th aspect.
Mars: 4th, 7th and 8th aspects.
Jupiter: 5th, 7th and 9th aspects.
Saturn: 3rd, 7th and 10th aspects.

Do not invent aspects for Rahu and Ketu.

Do not invent conjunctions, yogas or planetary facts.

==================================================
PROFESSIONAL SCENARIO GENERATION
==================================================

For every zodiac sign:

1. Identify the most relevant career houses.
2. Identify the planetary factors supporting the reading.
3. Translate these factors into a realistic
   professional situation.
4. Identify what could trigger that situation.
5. Describe the likely professional development.
6. Identify the possible practical outcome.

Think about actual situations:

- A client revising commercial terms.
- An employer delaying a hiring decision.
- A manager questioning a project deadline.
- A payment being held pending approval.
- A colleague disputing responsibility.
- An urgent assignment arriving unexpectedly.
- A project being reassigned.
- A business proposal requiring revision.
- An interview being rescheduled.
- A supplier changing delivery commitments.
- A performance review raising a difficult issue.
- A customer requesting a refund or modification.

These are examples only.

Create different scenarios when supported by
the astrological factors.

Do not write generic career themes.

Do not guarantee outcomes.

Do not make all predictions positive.

Do not assume every reader is employed.

Include different professional situations for
employees, job seekers, business owners and freelancers.

==================================================
UNIQUENESS
==================================================

Every sign must have a different central scenario.

Avoid repeating the same scenario with different wording.

Avoid repeating the main situations in the historical posts.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

{{
  "career_analysis": [
    {{
      "sign": "ARIES",
      "houses_activated": [],
      "astrological_factors": [],
      "career_theme": "",
      "real_world_trigger": "",
      "specific_scenario": "",
      "likely_professional_development": "",
      "possible_outcome": ""
    }}
  ]
}}

Include exactly 12 signs in this order:

{json.dumps(SIGN_NAMES)}

Keep every analysis specific and grounded in
the supplied calculated planetary data.
"""

    print(
        "\nStage 1: Interpreting calculated Vedic transits..."
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    data = parse_json(response.output_text)

    analysis = data.get(
        "career_analysis",
        []
    )

    if (
        not isinstance(analysis, list)
        or len(analysis) != 12
    ):
        raise ValueError(
            "Expected exactly 12 career analyses."
        )

    for index, item in enumerate(analysis):

        if (
            str(item.get("sign", "")).upper()
            != SIGN_NAMES[index]
        ):
            raise ValueError(
                "Incorrect career analysis order: "
                + SIGN_NAMES[index]
            )

        required_fields = [
            "specific_scenario",
            "real_world_trigger",
            "likely_professional_development",
            "possible_outcome",
        ]

        for field in required_fields:

            if not str(item.get(field, "")).strip():
                raise ValueError(
                    f"{SIGN_NAMES[index]} missing {field}."
                )

    transit_data["career_analysis"] = analysis

    return transit_data


# ============================================================
# STAGE 2: RELATABLE LINKEDIN HOROSCOPE WRITER
# ============================================================

def generate_linkedin_post(transit_data, history):

    prompt = f"""
You are the official daily career horoscope writer
for Mauksh's LinkedIn Page.

Publication date: {DATE_TEXT}

Your responsibility is to write specific,
relatable professional predictions for all
12 zodiac signs.

TRANSIT AND CAREER ANALYSIS:
{json.dumps(transit_data, ensure_ascii=False, indent=2)}

PREVIOUSLY PUBLISHED POSTS:
{json.dumps(history, ensure_ascii=False, indent=2)}

==================================================
CORE WRITING PHILOSOPHY
==================================================

Do NOT write traditional generic horoscopes.

Write predictions that describe situations
people actually encounter in their professional lives.

The reader should think:

"This is something that could genuinely happen
in my workplace, business or professional life."

A prediction must describe a recognisable event,
not simply an emotion, quality or general possibility.

==================================================
WHAT TO WRITE ABOUT
==================================================

EMPLOYEES:

- A manager asking for an explanation about delayed work.
- An unexpected change in project responsibilities.
- A colleague disagreeing with their approach.
- Being asked to handle an urgent assignment.
- A pending appraisal or performance discussion.
- Discovering an error in previously submitted work.
- A meeting where an important decision is postponed.
- Receiving feedback requiring project revisions.
- A team member failing to complete their responsibility.
- Being asked to take ownership of unfinished work.

JOB SEEKERS:

- Receiving an interview call after a long wait.
- An employer requesting additional documents.
- A postponed interview or delayed hiring decision.
- Negotiating salary expectations.
- Getting feedback after an interview.
- Hearing about an opening through a professional contact.

BUSINESS OWNERS AND FREELANCERS:

- A client delaying payment.
- A customer negotiating the quoted price.
- An order requiring urgent attention.
- A supplier changing delivery commitments.
- A potential client asking for a revised proposal.
- A project getting delayed because of pending approval.
- A customer returning with a modification request.
- A business expense requiring reconsideration.

MANAGERS AND LEADERS:

- Handling disagreement between team members.
- Defending a business decision.
- Reviewing an employee's performance.
- Taking responsibility for a delayed project.
- Prioritising between two urgent assignments.

These are examples, not a checklist.

Generate scenarios appropriate to the supplied
astrological analysis.

==================================================
PREDICTION CONSTRUCTION
==================================================

Each prediction must include:

1. A specific professional situation.
2. A realistic development or interaction.
3. A possible consequence or response.

Example:

"An important client may question a previously
agreed project cost, requiring you to justify
your pricing before the deal moves forward."

Another example:

"You may receive feedback on work submitted
earlier, with a request to correct something
you believed was already finalised."

Do not copy these examples.

==================================================
STRICTLY AVOID
==================================================

Never use standalone statements such as:

- New opportunities are coming.
- Success is on the way.
- Career growth is indicated.
- Communication will be important.
- Stay focused on your goals.
- Hard work will bring rewards.
- Your efforts will be recognised.
- Be careful about workplace politics.
- A new beginning is possible.
- Financial growth is indicated.
- Your leadership skills will shine.
- Challenges will make you stronger.

Do not use motivational language to fill space.

==================================================
ASTROLOGICAL DISCIPLINE
==================================================

1. Use only the supplied transit analysis.
2. Do not invent new planetary positions.
3. Do not invent new yogas or aspects.
4. Do not explain astrology in the final post.
5. Do not mention planets in the final predictions.
6. Do not force positive predictions for every sign.
7. Use cautious predictive language.
8. Keep the scenario relevant to the astrological factors.

==================================================
VARIETY AND UNIQUENESS
==================================================

1. Every sign must have a different central event.
2. Do not repeat the same event using synonyms.
3. Do not make all predictions about promotions.
4. Do not make all predictions about job changes.
5. Include business and freelance scenarios.
6. Avoid repeating previously published scenarios.
7. Do not assume every reader is employed.

==================================================
LANGUAGE AND LENGTH
==================================================

- English only.
- Natural conversational professional English.
- 18–30 words per prediction.
- One or two complete sentences.
- Cautious language: may, might, could.
- No guaranteed outcomes.
- No planet names.
- No hashtags.
- No additional emojis.
- No generic opening or closing paragraph.

==================================================
FINAL QUALITY CHECK
==================================================

Before returning JSON, internally verify:

1. Can the reader imagine the actual situation?
2. Does the prediction describe an identifiable event?
3. Is there a realistic development or consequence?
4. Is it distinct from the other 11 predictions?
5. Is it supported by the career analysis?
6. Does it avoid generic horoscope language?
7. Does it contain 18–30 words?

Rewrite any prediction that fails.

==================================================
OUTPUT FORMAT
==================================================

Return ONLY valid JSON.

{{
  "horoscopes": [
    {{
      "sign": "ARIES",
      "text": "Specific professional prediction."
    }}
  ]
}}

Include exactly 12 signs in this order:

{json.dumps(SIGN_NAMES)}

Do not include explanations outside JSON.
"""

    print(
        "\nStage 2: Generating relatable career predictions..."
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    data = parse_json(response.output_text)

    horoscopes = data.get(
        "horoscopes",
        []
    )

    if (
        not isinstance(horoscopes, list)
        or len(horoscopes) != 12
    ):
        raise ValueError(
            "Expected exactly 12 horoscope entries."
        )

    lines = [
        "Mauksh Daily Career Horoscope",
        DATE_TEXT,
        "",
    ]

    forbidden_phrases = [
        "new opportunities are coming",
        "success is on the way",
        "career growth is indicated",
        "communication will be important",
        "stay focused on your goals",
        "hard work will bring rewards",
        "your efforts will be recognised",
        "a new beginning is possible",
        "challenges will make you stronger",
    ]

    for index, item in enumerate(horoscopes):

        expected_sign = SIGN_NAMES[index]

        if not isinstance(item, dict):
            raise ValueError(
                "Invalid horoscope entry."
            )

        if (
            str(item.get("sign", "")).upper()
            != expected_sign
        ):
            raise ValueError(
                f"Expected {expected_sign} at "
                f"position {index + 1}."
            )

        text = str(
            item.get("text", "")
        ).strip()

        word_count = len(text.split())

        if not 18 <= word_count <= 30:
            raise ValueError(
                f"{expected_sign} has {word_count} words. "
                "Expected 18–30."
            )

        if not text.endswith((".", "!", "?")):
            raise ValueError(
                f"{expected_sign} prediction is incomplete."
            )

        lower_text = text.lower()

        for phrase in forbidden_phrases:

            if phrase in lower_text:
                raise ValueError(
                    f"Generic prediction detected for "
                    f"{expected_sign}: {phrase}"
                )

        if re.search(
            r"#|[\U0001F300-\U0001FAFF]",
            text
        ):
            raise ValueError(
                f"Unexpected hashtag or emoji in {expected_sign}."
            )

        lines.append(
            f"{SYMBOLS[expected_sign]} "
            f"{expected_sign.title()}: {text}"
        )

        lines.append("")

    post_text = "\n".join(lines).strip()

    if len(post_text) > 3000:
        raise ValueError(
            f"LinkedIn post contains {len(post_text)} characters."
        )

    return post_text


# ============================================================
# BUFFER GRAPHQL
# ============================================================

def buffer_graphql(query, variables=None):

    response = requests.post(
        BUFFER_URL,
        headers={
            "Authorization": f"Bearer {BUFFER_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "variables": variables or {},
        },
        timeout=60,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"Buffer HTTP error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    try:

        result = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "Buffer returned invalid JSON."
        ) from exc

    if result.get("errors"):

        raise RuntimeError(
            "Buffer GraphQL error: "
            + json.dumps(
                result["errors"],
                ensure_ascii=False
            )
        )

    return result.get("data", {})


# ============================================================
# FIND LINKEDIN CHANNEL
# ============================================================

def get_linkedin_channel_id():

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

    data = buffer_graphql(
        organization_query
    )

    organizations = (
        data.get("account", {})
        .get("organizations", [])
    )

    if not organizations:
        raise RuntimeError(
            "No Buffer organizations found."
        )

    channel_query = """
    query GetChannels($organizationId: OrganizationId!) {
      channels(input: { organizationId: $organizationId }) {
        id
        name
        displayName
        service
      }
    }
    """

    channels_found = []

    for organization in organizations:

        result = buffer_graphql(
            channel_query,
            {
                "organizationId": organization["id"]
            }
        )

        for channel in result.get(
            "channels",
            []
        ):

            if str(
                channel.get("service", "")
            ).lower() in (
                "linkedin",
                "linked_in",
            ):

                channels_found.append(channel)

    requested_id = os.getenv(
        "BUFFER_LINKEDIN_CHANNEL_ID"
    )

    if requested_id:

        selected = [
            channel
            for channel in channels_found
            if channel["id"] == requested_id
        ]

        if len(selected) != 1:

            raise RuntimeError(
                "Configured LinkedIn channel ID was not found."
            )

        channel = selected[0]

    else:

        if len(channels_found) != 1:

            available = [
                {
                    "id": channel["id"],
                    "name": channel.get("name"),
                    "displayName": channel.get("displayName"),
                }
                for channel in channels_found
            ]

            raise RuntimeError(
                "Expected exactly one LinkedIn channel. "
                "Found: "
                + json.dumps(
                    available,
                    ensure_ascii=False
                )
                + ". Configure BUFFER_LINKEDIN_CHANNEL_ID."
            )

        channel = channels_found[0]

    print(
        "LinkedIn channel:",
        channel.get("displayName")
        or channel.get("name")
    )

    return channel["id"]


# ============================================================
# PUBLISH LINKEDIN POST THROUGH BUFFER
# ============================================================

def publish_to_linkedin(post_text):

    channel_id = get_linkedin_channel_id()

    mutation = """
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

    print("\nPublishing to Buffer...")

    data = buffer_graphql(
        mutation,
        variables
    )

    result = data.get(
        "createPost",
        {}
    )

    if result.get("message"):

        raise RuntimeError(
            "Buffer could not create post: "
            + result["message"]
        )

    post = result.get("post")

    if not post or not post.get("id"):

        raise RuntimeError(
            "Buffer did not return a post ID: "
            + json.dumps(
                data,
                ensure_ascii=False
            )
        )

    print(
        "Buffer post created:",
        post["id"]
    )

    print(
        "Due at:",
        post.get("dueAt")
    )

    return post


# ============================================================
# MAIN WORKFLOW
# ============================================================

def main():

    print("=" * 65)
    print("MAUKSH DAILY CAREER HOROSCOPE — LINKEDIN")
    print("Publication date:", DATE_TEXT)
    print("Model:", OPENAI_MODEL)
    print("Ayanamsha: Lahiri")
    print("Rahu mode:", RAHU_NODE_MODE)
    print("Preview only:", PREVIEW_ONLY)
    print("=" * 65)

    # 1. Load historical posts.
    history, history_sha = load_history()

    # 2. Calculate planetary transits and analyse
    #    career houses for all twelve ascendants.
    transit_data = analyze_transits(history)

    # 3. Generate relatable daily predictions.
    post_text = generate_linkedin_post(
        transit_data,
        history
    )

    # 4. Print the finished post.
    print("\n" + "=" * 65)
    print("GENERATED LINKEDIN POST")
    print("=" * 65)
    print(post_text)
    print("=" * 65)

    # 5. Preview mode stops before Buffer publishing.
    if PREVIEW_ONLY:

        print(
            "\nPREVIEW_ONLY enabled. "
            "Nothing was published."
        )

        return

    # 6. Publish to LinkedIn through Buffer.
    post = publish_to_linkedin(post_text)

    # 7. Record history only after Buffer
    #    confirms that a post was created.
    record = {
        "date": DATE_TEXT,
        "post_id": post["id"],
        "post": post_text,
        "transits": transit_data["transits"],
    }

    # Avoid duplicate history records for same date.
    history = [
        item
        for item in history
        if item.get("date") != DATE_TEXT
    ]

    history.append(record)

    history = history[-30:]

    # 8. Save history in GitHub.
    save_history(
        history,
        history_sha
    )

    print("\n" + "=" * 65)
    print("WORKFLOW COMPLETED")
    print("LinkedIn horoscope submitted to Buffer.")
    print("History saved to:", HISTORY_PATH)
    print("Buffer Post ID:", post["id"])
    print("=" * 65)


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print("\nWORKFLOW FAILED")
        print(type(exc).__name__ + ":", str(exc))

        raise
