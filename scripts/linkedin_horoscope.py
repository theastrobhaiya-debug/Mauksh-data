
import json
import os
import re
import requests

from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI


# ============================================================
# MAUKSH DAILY CAREER HOROSCOPE — LINKEDIN
# ============================================================

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ)
DATE_TEXT = TODAY.strftime("%d %B %Y")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BUFFER_TOKEN = os.environ["MAUKSH_CAREER_BUFFER_TOKEN"]

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
BUFFER_URL = "https://api.buffer.com"

HISTORY_PATH = os.getenv(
    "MAUKSH_CAREER_HISTORY",
    "mauksh_linkedin_career_history.json",
)

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

SIGN_NAMES = [sign for sign, _ in SIGNS]


# ============================================================
# JSON RESPONSE PARSER
# ============================================================

def parse_json_response(raw):
    raw = raw.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "OpenAI did not return valid JSON. "
            f"Response excerpt: {raw[:500]}"
        ) from exc


# ============================================================
# CAREER HISTORY
# ============================================================

def load_recent_history():
    if not os.path.exists(HISTORY_PATH):
        return []

    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as file:
            history = json.load(file)

        if not isinstance(history, list):
            return []

        return history[-30:]

    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Could not read career horoscope history. "
            "Fix the history file before publishing."
        ) from exc


def save_history(post_text):
    history = load_recent_history()

    # Keep only one successful record per publication date.
    history = [
        item for item in history
        if item.get("date") != DATE_TEXT
    ]

    history.append({
        "date": DATE_TEXT,
        "post": post_text,
    })

    history = history[-30:]

    directory = os.path.dirname(
        os.path.abspath(HISTORY_PATH)
    )
    os.makedirs(directory, exist_ok=True)

    temporary_path = HISTORY_PATH + ".tmp"

    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_path, HISTORY_PATH)


# ============================================================
# STAGE 1 — OPENAI VEDIC TRANSIT INTERPRETATION
# ============================================================

def analyze_vedic_transits(history):
    history_text = json.dumps(
        history,
        ensure_ascii=False,
    )

    prompt = f"""
You are an experienced practitioner of traditional
Vedic sidereal astrology.

DATE: {DATE_TEXT}
REFERENCE TIME: 12:00 PM Indian Standard Time
ZODIAC: Sidereal
AYANAMSHA: Lahiri

Determine and interpret the planetary transit picture
for the specified date using your own existing knowledge.

Do not use external tools, Python libraries, or an ephemeris.

IMPORTANT ACCURACY REQUIREMENTS:

- Estimate the positions of the Sun, Moon, Mars, Mercury,
  Jupiter, Venus, Saturn, Rahu and Ketu.
- Do not pretend that estimates are verified astronomical data.
- If you cannot confidently determine a planetary sign,
  degree, nakshatra or motion, mark it uncertain.
- Never invent a precise degree or astronomical event
  merely to fill a field.
- Distinguish actual planetary positions from astrological
  interpretation.
- Do not invent a conjunction, aspect, sign ingress or
  retrograde station.
- Use the standard sidereal zodiac and Lahiri framework
  as the intended interpretive system.

CAREER ANALYSIS FOR ALL 12 SIGNS:

Treat each zodiac sign as the ascendant and use whole-sign
houses.

Consider the following traditional house significations:

10th house: career, status, authority and professional action.
6th house: employment, competition, service and disputes.
11th house: gains, professional networks and ambitions.
2nd house: income, resources and financial stability.

Consider the relevant house lords, planetary placements,
traditional aspects, conjunctions and retrograde effects
only when you can reasonably support the interpretation.

For each sign, identify:
- Relevant career houses and their lords.
- The strongest plausible career theme.
- A concrete professional situation.
- A possible development or complication.
- The uncertainty or limitations of the interpretation.

Avoid assigning stereotypical predictions to signs.

HISTORICAL POSTS — AVOID REPEATING THEIR SCENARIOS:
{history_text}

Return ONLY valid JSON in this structure:

{{
  "date": "{DATE_TEXT}",
  "reference_time": "12:00 IST",
  "zodiac": "Sidereal",
  "ayanamsha": "Lahiri",
  "transits": [
    {{
      "planet": "Sun",
      "sign": null,
      "degree": null,
      "motion": "uncertain",
      "confidence": "estimated"
    }}
  ],
  "career_analysis": [
    {{
      "sign": "ARIES",
      "houses_activated": [],
      "astrological_factors": [],
      "career_theme": "",
      "specific_scenario": "",
      "possible_outcome": ""
    }}
  ]
}}

Include all nine grahas and exactly 12 career-analysis entries
in this order:
{json.dumps(SIGN_NAMES)}

Use null or uncertainty labels rather than inventing facts.
Do not include the final LinkedIn post in this response.
"""

    print("Stage 1: Asking OpenAI to interpret Vedic transits...")

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    data = parse_json_response(response.output_text)

    if len(data.get("transits", [])) != 9:
        raise ValueError(
            "Transit analysis did not return nine grahas."
        )

    analysis = data.get("career_analysis", [])

    if len(analysis) != 12:
        raise ValueError(
            "Transit analysis did not return 12 signs."
        )

    for index, item in enumerate(analysis):
        if str(item.get("sign", "")).upper() != SIGN_NAMES[index]:
            raise ValueError(
                f"Transit analysis has incorrect sign order "
                f"at position {index + 1}."
            )

    print("Transit interpretation completed.")
    return data


# ============================================================
# STAGE 2 — GENERATE LINKEDIN CAREER HOROSCOPE
# ============================================================

def generate_horoscopes(transit_data, history):
    prompt = f"""
You are the official Vedic astrology career prediction
writer for Mauksh's LinkedIn Page.

PUBLICATION DATE: {DATE_TEXT}

Use this OpenAI-generated transit analysis:
{json.dumps(transit_data, ensure_ascii=False, indent=2)}

PREVIOUSLY PUBLISHED POSTS:
{json.dumps(history, ensure_ascii=False, indent=2)}

YOUR TASK:

Write a genuinely predictive Daily Career Horoscope
for all 12 zodiac signs.

This is not a generic career advice post.

Every prediction should describe a specific, plausible
professional development informed by the supplied analysis.

CAREER THEMES MAY INCLUDE:

- Hiring and interview decisions
- A manager reviewing a proposal
- A delayed approval or payment
- A dispute over responsibilities or credit
- A difficult client negotiation
- Contract revisions or deadline changes
- A project being challenged or returned for revision
- Competition for a role or responsibility
- A business pricing or cash-flow decision
- A referral from a professional contact
- Scrutiny from senior management
- A change in authority or reporting structure
- An accountability issue
- A commercial decision that needs reconsideration
- Recognition accompanied by additional responsibility
- A technical assessment or selection process

These are examples, not a checklist.

SPECIFICITY RULES:

1. Give every sign a distinct central professional event.

2. Include concrete circumstances, such as a client questioning
   a deadline, a manager reviewing a proposal, or an approval
   requiring another round of documentation.

3. Explain what might happen, not merely what the reader
   should do.

4. Avoid predictions that could apply to almost any person.

5. Use the supplied career analysis as the foundation.
   Do not invent additional transits or planetary placements.

6. Do not force a positive outcome for every sign.
   Include plausible obstacles, delays, mixed outcomes
   and constructive developments.

7. Compare the underlying scenarios with the previous posts.
   Reject recycled events even when the wording is different.

8. Do not automatically assign promotions to Capricorn,
   leadership to Aries, communication to Gemini, recognition
   to Leo, or office politics to Scorpio.

9. Do not repeatedly use vague phrases such as:
   "New opportunities are coming."
   "Your hard work will pay off."
   "Recognition may come your way."
   "Focus on your goals."
   "Success is within reach."

10. Do not invent precise employers, names, salaries,
    guaranteed promotions or guaranteed business outcomes.

11. Do not present astrological interpretations as certainty.
    Use measured predictive language where appropriate.

LINKEDIN FORMAT:

Mauksh Daily Career Horoscope
{DATE_TEXT}

♈ Aries: [prediction]

♉ Taurus: [prediction]

♊ Gemini: [prediction]

♋ Cancer: [prediction]

♌ Leo: [prediction]

♍ Virgo: [prediction]

♎ Libra: [prediction]

♏ Scorpio: [prediction]

♐ Sagittarius: [prediction]

♑ Capricorn: [prediction]

♒ Aquarius: [prediction]

♓ Pisces: [prediction]

WRITING STYLE:

- English only.
- One or two concise sentences per sign.
- Career and professional life only.
- No love, health, family or general lifestyle content.
- No planetary names or explanations in the final post.
- No hashtags, introductory paragraphs or conclusion.
- No additional emojis beyond the zodiac symbols.
- Avoid identical sentence structures across signs.
- Keep the post professional and suitable for LinkedIn.
- Do not add Markdown formatting.

Return ONLY valid JSON in this structure:

{{
  "horoscopes": [
    {{
      "sign": "ARIES",
      "text": "A specific career prediction."
    }}
  ]
}}

Include exactly 12 signs in the required order.
"""

    print("Stage 2: Generating 12 career predictions...")

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    data = parse_json_response(response.output_text)
    horoscopes = data.get("horoscopes", [])

    if not isinstance(horoscopes, list) or len(horoscopes) != 12:
        raise ValueError(
            "OpenAI did not return exactly 12 horoscopes."
        )

    for index, item in enumerate(horoscopes):
        expected_sign = SIGN_NAMES[index]

        if not isinstance(item, dict):
            raise ValueError("Invalid horoscope entry.")

        if str(item.get("sign", "")).upper() != expected_sign:
            raise ValueError(
                f"Expected {expected_sign} at position "
                f"{index + 1}."
            )

        text = str(item.get("text", "")).strip()

        if not text:
            raise ValueError(
                f"{expected_sign} has an empty prediction."
            )

        if not text.endswith((".", "!", "?")):
            raise ValueError(
                f"{expected_sign} prediction is incomplete."
            )

        item["sign"] = expected_sign
        item["text"] = text

    post_text = format_linkedin_post(horoscopes)

    print("Generated and validated all 12 predictions.")
    print("\n" + "=" * 60)
    print(post_text)
    print("=" * 60)

    return post_text


# ============================================================
# FORMAT LINKEDIN POST
# ============================================================

def format_linkedin_post(horoscopes):
    lines = [
        "Mauksh Daily Career Horoscope",
        DATE_TEXT,
        "",
    ]

    symbols = dict(SIGNS)

    for item in horoscopes:
        sign = item["sign"]
        symbol = symbols[sign]

        lines.append(
            f"{symbol} {sign.title()}: {item['text']}"
        )
        lines.append("")

    return "\n".join(lines).strip()


# ============================================================
# BUFFER GRAPHQL HELPER
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
            "Buffer returned an invalid JSON response."
        ) from exc

    if result.get("errors"):
        raise RuntimeError(
            "Buffer GraphQL error: "
            + json.dumps(result["errors"], ensure_ascii=False)
        )

    return result.get("data", {})


# ============================================================
# FIND LINKEDIN CHANNEL
# ============================================================

def get_linkedin_channel_id():
    organizations_query = """
    query GetOrganizations {
        account {
            organizations {
                id
                name
            }
        }
    }
    """

    data = buffer_graphql(organizations_query)

    organizations = (
        data.get("account", {}).get("organizations", [])
    )

    if not organizations:
        raise RuntimeError(
            "No Buffer organizations found."
        )

    matching_channels = []

    channels_query = """
    query GetChannels($organizationId: OrganizationId!) {
        channels(input: { organizationId: $organizationId }) {
            id
            name
            displayName
            service
        }
    }
    """

    for organization in organizations:
        channel_data = buffer_graphql(
            channels_query,
            {"organizationId": organization["id"]},
        )

        for channel in channel_data.get("channels", []):
            service = str(
                channel.get("service", "")
            ).lower()

            if service in ("linkedin", "linked_in"):
                matching_channels.append({
                    **channel,
                    "organization": organization.get("name"),
                })

    # Optional explicit channel selection for accounts with
    # multiple LinkedIn profiles or Pages.
    requested_channel_id = os.getenv(
        "BUFFER_LINKEDIN_CHANNEL_ID"
    )

    if requested_channel_id:
        matches = [
            channel for channel in matching_channels
            if channel["id"] == requested_channel_id
        ]

        if len(matches) != 1:
            raise RuntimeError(
                "BUFFER_LINKEDIN_CHANNEL_ID does not match "
                "a discovered LinkedIn channel."
            )

        selected = matches[0]

    else:
        if len(matching_channels) != 1:
            details = [
                {
                    "id": c["id"],
                    "name": c.get("name"),
                    "displayName": c.get("displayName"),
                    "organization": c.get("organization"),
                }
                for c in matching_channels
            ]

            raise RuntimeError(
                "Expected exactly one LinkedIn channel. "
                f"Found {len(matching_channels)}: "
                f"{json.dumps(details, ensure_ascii=False)}. "
                "Set BUFFER_LINKEDIN_CHANNEL_ID to select "
                "the intended LinkedIn Page."
            )

        selected = matching_channels[0]

    print(
        "LinkedIn channel:",
        selected.get("displayName")
        or selected.get("name"),
    )

    print("Channel ID:", selected["id"])

    return selected["id"]


# ============================================================
# CREATE LINKEDIN POST
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

    print("Submitting career horoscope to Buffer...")

    data = buffer_graphql(mutation, variables)
    result = data.get("createPost", {})

    if result.get("message"):
        raise RuntimeError(
            "Buffer could not create the post: "
            + result["message"]
        )

    post = result.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            "Buffer did not return a post ID: "
            + json.dumps(data, ensure_ascii=False)
        )

    print("\n" + "=" * 60)
    print("BUFFER POST CREATED")
    print("=" * 60)
    print("Post ID:", post["id"])
    print("Due At:", post.get("dueAt"))
    print("\nPOST TEXT:\n")
    print(post_text)
    print("=" * 60)

    return post


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("MAUKSH DAILY CAREER HOROSCOPE — LINKEDIN")
    print("Date:", DATE_TEXT)
    print("Model:", OPENAI_MODEL)
    print("=" * 60)

    # Read history before generation.
    history = load_recent_history()

    # Ask OpenAI to estimate and interpret Vedic transits.
    transit_data = analyze_vedic_transits(history)

    # Generate the actual LinkedIn post.
    post_text = generate_horoscopes(
        transit_data,
        history,
    )

    # Preview mode never publishes.
    if os.getenv("PREVIEW_ONLY", "false").lower() == "true":
        print("\nPREVIEW ONLY: Nothing was sent to Buffer.")
        return

    # Publish the post.
    post = publish_to_linkedin(post_text)

    # Save only after Buffer confirms creation of a post ID.
    save_history(post_text)

    print("\nWorkflow finished.")
    print("Buffer Post ID:", post["id"])
    print("Career horoscope submitted successfully.")


if __name__ == "__main__":
    main()
