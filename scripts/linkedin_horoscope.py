
import os
import json
import re
import base64
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

# GitHub repository history
HISTORY_PATH = "data/linkedin_history.json"
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")
GITHUB_TOKEN = os.getenv("GH_HISTORY_TOKEN", "")

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

SIGN_NAMES = [s[0] for s in SIGNS]
SYMBOLS = dict(SIGNS)


# ============================================================
# GITHUB HISTORY API
# ============================================================

def github_headers():
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GH_HISTORY_TOKEN is missing. Configure it in "
            "GitHub Actions so horoscope history persists."
        )

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url():
    if not GITHUB_REPOSITORY or "/" not in GITHUB_REPOSITORY:
        raise RuntimeError(
            "GITHUB_REPOSITORY is missing or invalid. "
            "Run this script inside GitHub Actions or configure it."
        )

    return (
        "https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{HISTORY_PATH}"
    )


def load_history():
    """
    Read the history file from the repository.
    A 404 means the file has not been created yet.
    """

    response = requests.get(
        github_file_url(),
        headers=github_headers(),
        params={"ref": os.getenv("GITHUB_REF_NAME", "main")},
        timeout=30,
    )

    if response.status_code == 404:
        print("History file not found; starting with empty history.")
        return [], None

    if response.status_code != 200:
        raise RuntimeError(
            f"GitHub history read failed: "
            f"{response.status_code} {response.text[:500]}"
        )

    result = response.json()

    if result.get("encoding") != "base64":
        raise RuntimeError("Unexpected GitHub history encoding.")

    try:
        content = base64.b64decode(result["content"]).decode("utf-8")
        history = json.loads(content)
    except (ValueError, KeyError) as exc:
        raise RuntimeError(
            "History file is not valid JSON. Fix it before publishing."
        ) from exc

    if not isinstance(history, list):
        raise RuntimeError("History JSON must contain a list.")

    print(f"Loaded {len(history)} history records from GitHub.")
    return history[-30:], result.get("sha")


def save_history(history, existing_sha=None):
    """
    Create or update the history file in GitHub.
    Requires repository Contents: write permission.
    """

    directory_url = (
        "https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/data"
    )

    # Ensure the data directory exists by creating the file itself.
    # GitHub creates intermediate paths automatically for file writes.

    content = json.dumps(
        history[-30:],
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("ascii")

    payload = {
        "message": f"Update LinkedIn career horoscope history: {DATE_TEXT}",
        "content": encoded_content,
        "branch": os.getenv("GITHUB_REF_NAME", "main"),
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
            f"GitHub history write failed: "
            f"{response.status_code} {response.text[:1000]}"
        )

    print("LinkedIn history successfully committed to GitHub.")


# ============================================================
# JSON PARSER
# ============================================================

def parse_json(raw):
    raw = raw.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "OpenAI returned invalid JSON: " + raw[:500]
        ) from exc


# ============================================================
# STAGE 1: OPENAI VEDIC TRANSIT ESTIMATION
# ============================================================

def analyze_transits(history):
    prompt = f"""
You are an expert in traditional Vedic sidereal astrology.

Date: {DATE_TEXT}
Reference time: 12:00 PM India Standard Time
Zodiac: Sidereal
Ayanamsha: Lahiri

Determine the planetary transit picture for this date using
your existing knowledge. Do not use external tools or libraries.

Analyze Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn,
Rahu and Ketu.

IMPORTANT:
- Estimate planetary positions only when reasonably confident.
- Do not claim you verified astronomical calculations.
- Use null for uncertain degrees or positions.
- Do not invent conjunctions, aspects, sign ingresses,
  nakshatras or retrograde changes.
- Distinguish estimated positions from interpretation.
- If you cannot reliably determine the current sign of a
  planet, explicitly mark it uncertain.

For all 12 signs, treat each sign as the ascendant and use
whole-sign houses.

Career factors:
- 10th house and lord: career, authority and status.
- 6th house and lord: employment, competition and disputes.
- 11th house and lord: gains, networks and ambitions.
- 2nd house and lord: income and resources.

Consider traditional Vedic planetary aspects and house lords
only when you can reasonably support the interpretation.

For each sign, identify a specific possible professional
event, its astrological rationale and a possible outcome.

Previous LinkedIn posts. Avoid repeating their central
professional scenarios:
{json.dumps(history, ensure_ascii=False)}

Return ONLY JSON:

{{
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

Include exactly nine planets and all 12 signs in this order:
{json.dumps(SIGN_NAMES)}

Do not write the final LinkedIn post here.
"""

    print("Stage 1: Estimating Vedic transits with OpenAI...")

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    data = parse_json(response.output_text)

    if len(data.get("transits", [])) != 9:
        raise ValueError("Expected nine planetary entries.")

    analysis = data.get("career_analysis", [])

    if len(analysis) != 12:
        raise ValueError("Expected career analysis for 12 signs.")

    for i, item in enumerate(analysis):
        if str(item.get("sign", "")).upper() != SIGN_NAMES[i]:
            raise ValueError(
                f"Incorrect career-analysis order at {SIGN_NAMES[i]}."
            )

    return data


# ============================================================
# STAGE 2: WRITE THE LINKEDIN HOROSCOPE
# ============================================================

def generate_linkedin_post(transits, history):
    prompt = f"""
You are the official Vedic astrology career prediction
writer for Mauksh's LinkedIn Page.

Publication date: {DATE_TEXT}

TRANSIT AND CAREER ANALYSIS:
{json.dumps(transits, ensure_ascii=False, indent=2)}

PREVIOUSLY PUBLISHED POSTS:
{json.dumps(history, ensure_ascii=False, indent=2)}

Write a Daily Career Horoscope for all 12 signs.

CORE REQUIREMENT:
Write specific predictions about plausible professional
developments, not generic career advice.

GOOD EXAMPLE:
"A client may challenge a previously agreed delivery date,
forcing a review of project scope before the next milestone."

BAD EXAMPLE:
"Communication will be important today."

The example is illustrative. Do not reuse its scenario.

PREDICTION RULES:

1. Give each sign a distinct central professional event.
2. Ground predictions in the supplied career analysis.
3. Do not invent new planetary positions or astrological facts.
4. Avoid semantic repetition across signs and historical posts.
5. Do not make every prediction about promotions, success,
   recognition, opportunities or changing jobs.
6. Cover varied professional situations, including hiring,
   interviews, client negotiations, delayed approvals,
   commercial decisions, workplace disputes, deadlines,
   accountability, professional reputation, leadership,
   contracts and project reviews.
7. These are possible themes, not a checklist.
8. Include constructive, neutral and challenging possibilities.
9. Use cautious predictive language; do not guarantee outcomes.
10. Avoid vague motivational clichés.
11. Do not invent names, salaries, employers or precise events.
12. Do not discuss love, health, family or lifestyle.
13. Do not mention planets or explain astrology in the final post.
14. English only. No hashtags or extra emojis.
15. Keep the writing natural, concise and professional.

FORMAT EXACTLY:

Mauksh Daily Career Horoscope
{DATE_TEXT}

♈ Aries: prediction

♉ Taurus: prediction

♊ Gemini: prediction

♋ Cancer: prediction

♌ Leo: prediction

♍ Virgo: prediction

♎ Libra: prediction

♏ Scorpio: prediction

♐ Sagittarius: prediction

♑ Capricorn: prediction

♒ Aquarius: prediction

♓ Pisces: prediction

Each prediction must contain 18–30 words and be one or
two complete sentences. Every sign must have a prediction.

Return ONLY valid JSON:

{{
  "horoscopes": [
    {{
      "sign": "ARIES",
      "text": "Specific career prediction."
    }}
  ]
}}

Include all signs in the required order:
{json.dumps(SIGN_NAMES)}
"""

    print("Stage 2: Writing 12 distinct career predictions...")

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )

    data = parse_json(response.output_text)
    horoscopes = data.get("horoscopes", [])

    if not isinstance(horoscopes, list) or len(horoscopes) != 12:
        raise ValueError("Expected exactly 12 horoscope entries.")

    lines = [
        "Mauksh Daily Career Horoscope",
        DATE_TEXT,
        "",
    ]

    for index, item in enumerate(horoscopes):
        expected_sign = SIGN_NAMES[index]

        if not isinstance(item, dict):
            raise ValueError("Invalid horoscope entry.")

        if str(item.get("sign", "")).upper() != expected_sign:
            raise ValueError(
                f"Expected {expected_sign} at position {index + 1}."
            )

        text = str(item.get("text", "")).strip()
        word_count = len(text.split())

        if not 18 <= word_count <= 30:
            raise ValueError(
                f"{expected_sign} has {word_count} words; "
                "expected 18–30. Nothing was published."
            )

        if not text.endswith((".", "!", "?")):
            raise ValueError(
                f"{expected_sign} prediction is incomplete."
            )

        lines.append(
            f"{SYMBOLS[expected_sign]} "
            f"{expected_sign.title()}: {text}"
        )
        lines.append("")

    post_text = "\n".join(lines).strip()

    # Buffer and LinkedIn have content-size constraints.
    if len(post_text) > 3000:
        raise ValueError(
            f"LinkedIn post has {len(post_text)} characters; "
            "reduce the horoscope lengths."
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
            + json.dumps(result["errors"], ensure_ascii=False)
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

    data = buffer_graphql(organization_query)
    organizations = data.get("account", {}).get("organizations", [])

    if not organizations:
        raise RuntimeError("No Buffer organizations found.")

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
            {"organizationId": organization["id"]},
        )

        for channel in result.get("channels", []):
            if str(channel.get("service", "")).lower() in (
                "linkedin",
                "linked_in",
            ):
                channels_found.append(channel)

    requested_id = os.getenv("BUFFER_LINKEDIN_CHANNEL_ID")

    if requested_id:
        selected = [
            c for c in channels_found
            if c["id"] == requested_id
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
                    "id": c["id"],
                    "name": c.get("name"),
                    "displayName": c.get("displayName"),
                }
                for c in channels_found
            ]

            raise RuntimeError(
                "Expected exactly one LinkedIn channel. "
                "Found: "
                + json.dumps(available, ensure_ascii=False)
                + ". Configure BUFFER_LINKEDIN_CHANNEL_ID."
            )

        channel = channels_found[0]

    print(
        "LinkedIn channel:",
        channel.get("displayName") or channel.get("name"),
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

    print("Publishing to Buffer...")

    data = buffer_graphql(mutation, variables)
    result = data.get("createPost", {})

    if result.get("message"):
        raise RuntimeError(
            "Buffer could not create post: " + result["message"]
        )

    post = result.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            "Buffer did not return a post ID: "
            + json.dumps(data, ensure_ascii=False)
        )

    print("Buffer post created:", post["id"])
    print("Due at:", post.get("dueAt"))

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

    # Read persistent history from GitHub.
    history, history_sha = load_history()

    # Estimate and interpret Vedic transits with OpenAI.
    transit_data = analyze_transits(history)

    # Generate the finished LinkedIn post.
    post_text = generate_linkedin_post(
        transit_data,
        history,
    )

    print("\n" + "=" * 60)
    print("GENERATED LINKEDIN POST")
    print("=" * 60)
    print(post_text)
    print("=" * 60)

    if os.getenv("PREVIEW_ONLY", "false").lower() == "true":
        print("PREVIEW_ONLY enabled. Nothing was published.")
        return

    # Publish first.
    post = publish_to_linkedin(post_text)

    # Record only after Buffer returns a post ID.
    record = {
        "date": DATE_TEXT,
        "post_id": post["id"],
        "post": post_text,
    }

    # Avoid duplicate history records for the same date.
    history = [
        item for item in history
        if item.get("date") != DATE_TEXT
    ]

    history.append(record)
    history = history[-30:]

    # Commit history to GitHub.
    save_history(history, history_sha)

    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETED")
    print("LinkedIn horoscope submitted to Buffer.")
    print("History saved to:", HISTORY_PATH)
    print("Buffer Post ID:", post["id"])
    print("=" * 60)


if __name__ == "__main__":
    main()
