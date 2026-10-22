
import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI


# ============================================================
# MAUKSH — DAILY LINKEDIN CAREER HOROSCOPE
# Fresh generation every run; no history or GitHub API
# ============================================================

TIMEZONE = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TIMEZONE)
DATE_TEXT = TODAY.strftime("%d %B %Y")
DATE_ISO = TODAY.strftime("%Y-%m-%d")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BUFFER_TOKEN = os.getenv("MAUKSH_CAREER_BUFFER_TOKEN")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_LINKEDIN_CHANNEL_ID")
PREVIEW_ONLY = os.getenv("PREVIEW_ONLY", "true").lower() in {
    "1", "true", "yes", "y"
}

BUFFER_API_URL = "https://api.buffer.com"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY.")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# OPENAI HELPER
# ============================================================

def ask_openai(prompt, max_output_tokens=4000):
    """Generate text using OpenAI."""
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        max_output_tokens=max_output_tokens,
    )

    result = response.output_text.strip()

    if not result:
        raise RuntimeError("OpenAI returned an empty response.")

    return result


# ============================================================
# STAGE 1 — ESTIMATE VEDIC SIDEREAL TRANSITS
# ============================================================

def analyze_transits():
    """
    Ask OpenAI to estimate Vedic sidereal transits for today's date.
    No external ephemeris or history is used.
    """

    prompt = f"""
You are a careful researcher of traditional Vedic astrology.

DATE: {DATE_TEXT}
DATE IN ISO FORMAT: {DATE_ISO}
REFERENCE TIMEZONE: Asia/Kolkata
ZODIAC: Sidereal Vedic astrology
AYANAMSHA: Lahiri

Estimate the planetary positions relevant to a Vedic career horoscope
for this date. Use your learned astronomical knowledge to estimate the
positions. Do not claim that you consulted a live ephemeris.

Consider these nine grahas:
Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu and Ketu.

Return ONLY valid JSON using this structure:

{{
  "date": "{DATE_ISO}",
  "method": "OpenAI-based sidereal transit estimates; not ephemeris verified",
  "transits": {{
    "Sun": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Moon": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Mars": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Mercury": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Jupiter": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Venus": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Saturn": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Rahu": {{"sign": "sign name", "degree": "approximate degree or unknown"}},
    "Ketu": {{"sign": "sign name", "degree": "approximate degree or unknown"}}
  }},
  "career_themes": [
    "A concise general career theme",
    "A concise communication or business theme",
    "A concise caution or opportunity"
  ],
  "uncertainties": [
    "List any planetary placements you are not confident about"
  ]
}}

Rules:
- Use sidereal signs, not tropical zodiac signs.
- Rahu and Ketu must be opposite each other.
- Do not invent precise degrees if you are unsure; use "unknown".
- Do not fabricate an eclipse, retrograde, conjunction or exact aspect.
- Separate estimates from verified facts.
- Interpret the transits as symbolic astrological themes, not guaranteed events.
- Keep the JSON valid. Do not include Markdown fences.
"""

    raw = ask_openai(prompt, max_output_tokens=2500)

    # Be tolerant if the model accidentally wraps JSON in code fences.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not parse OpenAI transit JSON: {exc}\nResponse:\n{raw}"
        ) from exc

    logging.info("Transit estimates generated for %s.", DATE_TEXT)
    logging.info("Estimated transits: %s", json.dumps(
        data.get("transits", {}),
        ensure_ascii=False
    ))

    return data


# ============================================================
# STAGE 2 — GENERATE THE LINKEDIN POST
# ============================================================

def generate_linkedin_post(transit_data):
    """Generate a new career horoscope for all 12 Moon signs."""

    transit_json = json.dumps(
        transit_data,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
You are the editorial writer for Mauksh's daily Vedic career horoscope
on LinkedIn. Write a fresh, practical, insightful post for today.

DATE: {DATE_TEXT}
ASTROLOGICAL FRAMEWORK: Vedic sidereal astrology
SIGNS: Interpret each sign as the reader's Chandra Rashi (Moon sign).

OPENAI-ESTIMATED TRANSIT DATA:
{transit_json}

REQUIREMENTS:

1. Begin with exactly:
Mauksh Daily Career Horoscope
{DATE_TEXT}

2. Include all 12 signs exactly once, in this order:
♈ Aries
♉ Taurus
♊ Gemini
♋ Cancer
♌ Leo
♍ Virgo
♎ Libra
♏ Scorpio
♐ Sagittarius
♑ Capricorn
♒ Aquarius
♓ Pisces

3. Format each line like this:
♈ Aries: [career guidance]

4. Give each sign 18–28 words. Keep each prediction focused and
meaningfully different from the others.

5. Make predictions specific to work and professional life, such as:
- interviews, applications and job searches
- workplace communication and office dynamics
- leadership, visibility and recognition
- business, clients, sales and negotiations
- money decisions related to work
- deadlines, focus, planning and execution
- career changes, networking and collaboration

6. Connect the guidance to the supplied transit themes when relevant.
Do not pretend that every planet directly affects every sign in the
same way. Do not invent house placements because individual birth charts
were not supplied.

7. Give practical advice, not vague statements such as:
"Good things are coming", "Trust the universe", or "Stay positive".

8. Avoid absolute promises, fear-based predictions, guaranteed
promotions, guaranteed money, guaranteed job offers or claims of
certain failure.

9. Do not repeat the same advice across multiple signs. Vary sentence
structure and the professional situations discussed.

10. Use natural, professional English suitable for LinkedIn.
Avoid excessive emojis, hashtags inside the predictions, and
unnecessarily mystical language.

11. After the 12 predictions, add a short practical closing line.
Then add 3–5 relevant hashtags, including #Mauksh and
#CareerHoroscope.

12. Do not add a long explanation of the astrology methodology.
Do not output JSON or Markdown tables.

Important: the transit positions are OpenAI-generated estimates,
not independently verified astronomical calculations. Do not describe
them as verified or make claims of exact astronomical precision.

Return only the finished LinkedIn post.
"""

    post = ask_openai(prompt, max_output_tokens=2500)

    if "Mauksh Daily Career Horoscope" not in post:
        raise RuntimeError("Generated post is missing its required heading.")

    # Basic validation: require every zodiac sign to appear.
    required_signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn",
        "Aquarius", "Pisces",
    ]

    missing = [sign for sign in required_signs if sign not in post]

    if missing:
        raise RuntimeError(
            "Generated post is missing zodiac signs: "
            + ", ".join(missing)
        )

    logging.info("LinkedIn post generated successfully.")
    return post


# ============================================================
# BUFFER API
# ============================================================

def buffer_graphql(query, variables=None):
    """Send a GraphQL request to Buffer."""
    if not BUFFER_TOKEN:
        raise RuntimeError(
            "Missing MAUKSH_CAREER_BUFFER_TOKEN."
        )

    response = requests.post(
        BUFFER_API_URL,
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

    response.raise_for_status()
    payload = response.json()

    if payload.get("errors"):
        raise RuntimeError(
            "Buffer API error: "
            + json.dumps(payload["errors"], ensure_ascii=False)
        )

    return payload.get("data", {})


def publish_to_linkedin(post_text):
    """Publish the generated post to the configured Buffer channel."""

    if not BUFFER_CHANNEL_ID:
        raise RuntimeError(
            "Missing BUFFER_LINKEDIN_CHANNEL_ID. "
            "Add your LinkedIn channel ID as a GitHub Actions "
            "variable or environment variable."
        )

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on Post {
          id
          text
        }
        ... on UserError {
          message
        }
      }
    }
    """

    variables = {
        "input": {
            "channelId": BUFFER_CHANNEL_ID,
            "text": post_text,
            "schedulingType": "automatic",
            "mode": "shareNow",
        }
    }

    data = buffer_graphql(mutation, variables)
    result = data.get("createPost")

    if not result:
        raise RuntimeError(
            "Buffer did not return a createPost result: "
            + json.dumps(data, ensure_ascii=False)
        )

    if result.get("message") and not result.get("id"):
        raise RuntimeError(
            "Buffer could not create the post: "
            + str(result["message"])
        )

    if not result.get("id"):
        raise RuntimeError(
            "Buffer response did not include a post ID: "
            + json.dumps(result, ensure_ascii=False)
        )

    logging.info("Buffer accepted the post. Post ID: %s", result["id"])
    return result


# ============================================================
# MAIN
# ============================================================

def main():
    logging.info("Starting Mauksh Daily Career Horoscope.")
    logging.info("Date: %s", DATE_TEXT)
    logging.info("Model: %s", OPENAI_MODEL)
    logging.info("Preview only: %s", PREVIEW_ONLY)

    # No history is loaded or saved.
    transit_data = analyze_transits()
    post_text = generate_linkedin_post(transit_data)

    print("\n" + "=" * 65)
    print(post_text)
    print("=" * 65 + "\n")

    if PREVIEW_ONLY:
        logging.info(
            "PREVIEW_ONLY is enabled. Post was generated but not published."
        )
        return

    result = publish_to_linkedin(post_text)
    logging.info("Publishing request completed. ID: %s", result["id"])


if __name__ == "__main__":
    main()
