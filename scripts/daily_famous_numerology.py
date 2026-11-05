
import os
import json
import re
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI

# ============================================================
# MAUKSH BIRTHDAY NUMEROLOGY — EDITORIAL EDITION
# ============================================================

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ).date()
FORECAST_YEAR = TODAY.year + 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")

BUFFER_TOKEN = (
    os.getenv("BUFFER_X_ACCESS_TOKEN")
    or os.getenv("BUFFER_ACCESS_TOKEN")
)

BUFFER_API = "https://api.buffer.com"

BUFFER_X_CHANNEL_NAME = os.getenv("BUFFER_X_CHANNEL_NAME", "")

HISTORY_DIR = Path("data/famous_numerology")
HISTORY_FILE = HISTORY_DIR / f"{TODAY.isoformat()}.json"

MAX_PEOPLE = 4
MAX_TWEET_LENGTH = 275
MAX_THREAD_POSTS = 3

# ============================================================
# INITIALIZATION
# ============================================================

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing")

if not BUFFER_TOKEN:
    raise RuntimeError(
        "BUFFER_X_ACCESS_TOKEN or BUFFER_ACCESS_TOKEN is missing"
    )

client = OpenAI(api_key=OPENAI_API_KEY)

# ============================================================
# HISTORY MANAGEMENT
# ============================================================

def load_history():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    if not HISTORY_FILE.exists():
        return {
            "date": TODAY.isoformat(),
            "people": {}
        }

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "people" not in data:
            data["people"] = {}

        return data

    except (json.JSONDecodeError, OSError):
        print("WARNING: History file unreadable. Starting fresh.")
        return {
            "date": TODAY.isoformat(),
            "people": {}
        }


def save_history(history):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = HISTORY_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    temp_file.replace(HISTORY_FILE)


def person_key(person):
    raw = (
        person["name"].strip().lower()
        + "|"
        + person["dob"]
    )

    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ============================================================
# BUFFER GRAPHQL
# ============================================================

def buffer_request(query, variables=None):
    response = requests.post(
        BUFFER_API,
        headers={
            "Authorization": f"Bearer {BUFFER_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "query": query,
            "variables": variables or {}
        },
        timeout=40
    )

    response.raise_for_status()

    result = response.json()

    if result.get("errors"):
        raise RuntimeError(
            "Buffer GraphQL error: "
            + json.dumps(result["errors"])
        )

    return result.get("data", {})


def get_buffer_x_channel():

    organizations_query = """
    query {
        account {
            organizations {
                id
                name
            }
        }
    }
    """

    data = buffer_request(organizations_query)

    organizations = (
        data.get("account", {}).get("organizations", [])
    )

    if not organizations:
        raise RuntimeError("No Buffer organization found")

    all_channels = []

    channels_query = """
    query GetChannels($organizationId: OrganizationId!) {
        channels(input: {organizationId: $organizationId}) {
            id
            name
            displayName
            service
            isQueuePaused
            isLocked
        }
    }
    """

    for organization in organizations:

        result = buffer_request(
            channels_query,
            {"organizationId": organization["id"]}
        )

        all_channels.extend(
            result.get("channels", [])
        )

    x_channels = [
        channel for channel in all_channels
        if channel.get("service", "").lower() == "twitter"
        and not channel.get("isLocked", False)
    ]

    if BUFFER_X_CHANNEL_NAME:
        matching = [
            channel for channel in x_channels
            if BUFFER_X_CHANNEL_NAME.lower()
            in (
                channel.get("name", "")
                + " "
                + channel.get("displayName", "")
            ).lower()
        ]

        if matching:
            x_channels = matching

    if not x_channels:
        raise RuntimeError("No available X channel found in Buffer")

    if len(x_channels) > 1:
        raise RuntimeError(
            "Multiple X channels found. Set BUFFER_X_CHANNEL_NAME "
            "to select the correct channel."
        )

    channel = x_channels[0]

    if channel.get("isQueuePaused"):
        raise RuntimeError(
            "Your Buffer X queue is paused. Unpause it before publishing."
        )

    print(
        f"Using Buffer X channel: "
        f"{channel.get('name') or channel.get('displayName')}"
    )

    return channel["id"]


# ============================================================
# RESEARCH: FAMOUS INDIAN PERSONALITIES
# ============================================================

def research_birthdays():

    prompt = f"""
You are a professional research assistant for Mauksh.

TODAY: {TODAY.strftime("%d %B %Y")}
COUNTRY: India

Find up to {MAX_PEOPLE} famous Indian personalities whose
birthday is TODAY.

STRICT RULES:

1. Include only people who are alive as of today.
2. Include only Indian personalities.
3. They must be genuinely famous and publicly recognised.
4. Verify their exact date of birth.
5. DOB must match today's day and month.
6. Use at least TWO independent HTTPS sources per person.
7. Prefer authoritative biographies, reputable newspapers,
   official profiles and established publications.
8. Never guess a birth date.
9. Do not include fictional characters.
10. Do not include someone whose current living status
    cannot be reasonably verified.
11. Do not invent career achievements.
12. If no suitable person can be verified, return an empty list.

Return ONLY valid JSON in this structure:

{{
  "people": [
    {{
      "name": "Full name",
      "dob": "YYYY-MM-DD",
      "profession": "Profession",
      "known_for": "Brief description",
      "career_milestones": [
        "Verified milestone 1",
        "Verified milestone 2"
      ],
      "sources": [
        {{
          "title": "Source title",
          "url": "https://..."
        }},
        {{
          "title": "Source title",
          "url": "https://..."
        }}
      ],
      "alive_verified": true
    }}
  ]
}}

Return no commentary outside JSON.
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        tools=[{"type": "web_search"}],
        input=prompt
    )

    output = response.output_text.strip()

    output = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        output,
        flags=re.IGNORECASE
    )

    try:
        result = json.loads(output)
    except json.JSONDecodeError:
        raise RuntimeError(
            "Birthday research did not return valid JSON:\n"
            + output[:2000]
        )

    people = result.get("people", [])

    verified = []

    for person in people:

        try:
            dob = datetime.strptime(
                person["dob"], "%Y-%m-%d"
            ).date()
        except (ValueError, KeyError, TypeError):
            continue

        if dob.month != TODAY.month or dob.day != TODAY.day:
            continue

        if person.get("alive_verified") is not True:
            continue

        sources = person.get("sources", [])

        valid_sources = [
            source for source in sources
            if isinstance(source, dict)
            and source.get("url", "").startswith("https://")
            and source.get("title")
        ]

        if len(valid_sources) < 2:
            continue

        if not person.get("career_milestones"):
            continue

        if not person.get("name"):
            continue

        person["sources"] = valid_sources[:3]
        verified.append(person)

    # Remove duplicate names
    unique = {}

    for person in verified:
        unique[person["name"].strip().lower()] = person

    return list(unique.values())[:MAX_PEOPLE]


# ============================================================
# NUMEROLOGY CALCULATIONS
# ============================================================

def reduce_number(number):
    while number > 9:
        number = sum(int(digit) for digit in str(number))

    return number


def calculate_mulank(dob):
    return reduce_number(dob.day)


def calculate_bhagyank(dob):
    total = sum(int(digit) for digit in dob.strftime("%Y%m%d"))

    reduced = reduce_number(total)

    return {
        "compound": total,
        "reduced": reduced
    }


def calculate_personal_year(dob, year):

    total = (
        sum(int(digit) for digit in str(dob.day))
        + sum(int(digit) for digit in str(dob.month))
        + sum(int(digit) for digit in str(year))
    )

    return reduce_number(total)


def numerology_data(person):

    dob = datetime.strptime(
        person["dob"], "%Y-%m-%d"
    ).date()

    mulank = calculate_mulank(dob)
    bhagyank = calculate_bhagyank(dob)

    personal_year = calculate_personal_year(
        dob,
        FORECAST_YEAR
    )

    return {
        "dob": dob.isoformat(),
        "mulank": mulank,
        "bhagyank_compound": bhagyank["compound"],
        "bhagyank_reduced": bhagyank["reduced"],
        "personal_year": personal_year,
        "forecast_year": FORECAST_YEAR
    }


# ============================================================
# EDITORIAL THREAD GENERATION
# ============================================================

def generate_thread(person):

    numbers = numerology_data(person)

    prompt = f"""
You are the senior editorial writer for MAUKSH.

Create a premium, intelligent, minimal X birthday numerology thread.

SUBJECT:
{json.dumps(person, ensure_ascii=False)}

NUMEROLOGY:
{json.dumps(numbers)}

TODAY:
{TODAY.strftime("%d %B %Y")}

FORECAST YEAR:
{FORECAST_YEAR}

CREATE EXACTLY THREE POSTS.

POST 1 — BIRTHDAY + MULANK

Must begin exactly:

Happy Birthday, {person['name']}!

Then explain their Mulank and its traditional numerological
association.

Keep it personal, readable and interesting.

POST 2 — BHAGYANK + LIFE JOURNEY

Explain the Bhagyank, including its compound number
when relevant.

Connect the traditional interpretation to one or two
REAL, documented milestones from the person's life.

Do not claim that numerology caused their success.

POST 3 — UPCOMING PERSONAL YEAR

Explain their Personal Year {FORECAST_YEAR}.

Describe the traditional numerological themes of that number.

Give a thoughtful, balanced interpretation.

Do not make guaranteed predictions about their future.

EDITORIAL STYLE:

- Magazine-quality writing.
- Minimal and sophisticated.
- Natural English.
- Short, clean sentences.
- No emojis.
- No hashtags.
- No decorative Unicode characters.
- No unnecessary headings.
- No repetitive introductions.
- No exaggerated spiritual claims.
- No generic AI phrases.
- No clickbait.
- No forced connections between numbers and achievements.
- No repeated disclaimers.
- No claims of scientific validity.
- Use the actual verified career milestones provided.
- Explain numerology as a traditional interpretive system.
- Every post must be independently readable.
- Maximum {MAX_TWEET_LENGTH} characters per post.
- Exactly three posts.
- Do not include source URLs inside the posts.

IMPORTANT:

Use only the supplied numerological calculations.
Do not recalculate or change the numbers.

Return ONLY JSON:

{{
  "posts": [
    "First post",
    "Second post",
    "Third post"
  ]
}}
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    output = response.output_text.strip()

    output = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        output,
        flags=re.IGNORECASE
    )

    try:
        result = json.loads(output)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"Invalid thread JSON for {person['name']}:\n"
            + output[:1500]
        )

    posts = result.get("posts", [])

    if len(posts) != MAX_THREAD_POSTS:
        raise RuntimeError(
            f"Expected exactly 3 posts for {person['name']}"
        )

    cleaned = []

    for index, post in enumerate(posts):

        post = post.strip()

        if not post:
            raise RuntimeError("Empty thread post")

        if len(post) > MAX_TWEET_LENGTH:
            raise RuntimeError(
                f"Post {index + 1} for {person['name']} "
                f"is too long: {len(post)} characters"
            )

        if index == 0 and not post.startswith(
            f"Happy Birthday, {person['name']}!"
        ):
            raise RuntimeError(
                "First post does not start with the required birthday greeting"
            )

        cleaned.append(post)

    return {
        "posts": cleaned,
        "numbers": numbers
    }


# ============================================================
# BUFFER THREAD PUBLISHING
# ============================================================

def publish_thread(channel_id, posts):

    mutation = """
    mutation CreateBirthdayThread($input: CreatePostInput!) {
        createPost(input: $input) {
            ... on PostActionSuccess {
                post {
                    id
                    status
                    text
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
            "text": posts[0],
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "metadata": {
                "twitter": {
                    "thread": [
                        {"text": post}
                        for post in posts
                    ]
                }
            }
        }
    }

    result = buffer_request(
        mutation,
        variables
    )

    action = result.get("createPost", {})

    post = action.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            "Buffer did not confirm thread creation: "
            + json.dumps(action)
        )

    return post


# ============================================================
# MAIN AUTOMATION
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Mauksh Birthday Numerology"
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate threads without publishing"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass previous publishing history"
    )

    args = parser.parse_args()

    print("=" * 55)
    print("MAUKSH BIRTHDAY NUMEROLOGY")
    print("EDITORIAL EDITION")
    print("=" * 55)

    print("Date:", TODAY)
    print("Forecast year:", FORECAST_YEAR)
    print("Model:", OPENAI_MODEL)
    print("Preview:", args.preview)

    history = load_history()

    print("\nSearching for verified birthdays...")

    people = research_birthdays()

    if not people:
        print("No verified living Indian birthdays found today.")

        history["last_run_status"] = "no_verified_people"
        save_history(history)

        return

    print(f"\nFound {len(people)} eligible personalities.")

    channel_id = None

    for person in people:

        name = person["name"]
        key = person_key(person)

        existing = history["people"].get(key, {})

        if (
            existing.get("status") == "submitted_to_buffer"
            and not args.force
        ):
            print(f"\nSkipping already published: {name}")
            continue

        print("\n" + "-" * 50)
        print("PERSON:", name)
        print("DOB:", person["dob"])

        try:

            generated = generate_thread(person)

            posts = generated["posts"]

            print("\nNUMEROLOGY:")
            print(json.dumps(
                generated["numbers"],
                indent=2
            ))

            print("\nGENERATED THREAD:")

            for index, post in enumerate(posts, 1):
                print(f"\nPOST {index} ({len(post)} chars)")
                print(post)

            if args.preview:
                print("\nPREVIEW ONLY. Not publishing.")

                history["people"][key] = {
                    "name": name,
                    "dob": person["dob"],
                    "status": "preview_generated",
                    "posts": posts,
                    "numbers": generated["numbers"],
                    "sources": person["sources"]
                }

                save_history(history)
                continue

            if channel_id is None:
                channel_id = get_buffer_x_channel()

            # Save a pending state before sending.
            # This makes interrupted runs visible for manual checking.
            history["people"][key] = {
                "name": name,
                "dob": person["dob"],
                "status": "publishing",
                "posts": posts,
                "numbers": generated["numbers"],
                "sources": person["sources"]
            }

            save_history(history)

            result = publish_thread(
                channel_id,
                posts
            )

            history["people"][key] = {
                "name": name,
                "dob": person["dob"],
                "status": "submitted_to_buffer",
                "buffer_post_id": result["id"],
                "buffer_status": result.get("status"),
                "posts": posts,
                "numbers": generated["numbers"],
                "sources": person["sources"]
            }

            save_history(history)

            print("\nSUCCESS: Thread submitted to Buffer.")
            print("Buffer post ID:", result["id"])

        except Exception as error:

            print(f"\nERROR for {name}: {error}")

            history["people"][key] = {
                "name": name,
                "dob": person["dob"],
                "status": "failed",
                "error": str(error)
            }

            save_history(history)

    history["last_run_status"] = "completed"
    history["last_run_at"] = datetime.now(TZ).isoformat()

    save_history(history)

    print("\n" + "=" * 55)
    print("MAUKSH AUTOMATION FINISHED")
    print("=" * 55)


if __name__ == "__main__":
    main()
