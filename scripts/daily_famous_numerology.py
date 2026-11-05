
import os
import re
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import requests
from openai import OpenAI


# =========================================================
# CONFIGURATION
# =========================================================

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ).date()
FORECAST_YEAR = TODAY.year + 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = (
    os.getenv("OPENAI_MODEL", "").strip()
    or "gpt-5-mini"
)

BUFFER_TOKEN = os.getenv("BUFFER_X_ACCESS_TOKEN")

BUFFER_URL = "https://api.buffer.com"

MAX_PEOPLE = 4
MAX_POST_LENGTH = 275

BASE_DIR = Path(__file__).resolve().parents[1]

HISTORY_DIR = BASE_DIR / "data" / "famous_numerology"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = HISTORY_DIR / f"{TODAY.isoformat()}.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("daily-numerology")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# JSON HELPERS
# =========================================================

def parse_json_output(output):

    output = output.strip()

    output = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        output
    )

    try:
        return json.loads(output)

    except json.JSONDecodeError:

        start = output.find("{")
        end = output.rfind("}")

        if start == -1 or end == -1:
            raise ValueError("Invalid JSON from OpenAI")

        return json.loads(output[start:end + 1])


# =========================================================
# OPENAI RESPONSES API
# =========================================================

def ask_openai(prompt, use_web_search=False):

    args = {
        "model": OPENAI_MODEL,
        "input": prompt
    }

    if use_web_search:

        args["tools"] = [
            {
                "type": "web_search",
                "search_context_size": "high"
            }
        ]

    else:

        args["text"] = {
            "format": {
                "type": "json_object"
            }
        }

    response = client.responses.create(**args)

    if not response.output_text:
        raise RuntimeError("OpenAI returned empty output")

    return parse_json_output(response.output_text)


# =========================================================
# HISTORY
# =========================================================

def load_history():

    if not HISTORY_FILE.exists():

        return {
            "date": TODAY.isoformat(),
            "status": "new",
            "people": [],
            "thread": [],
            "buffer_post_id": None
        }

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(data):

    temp = HISTORY_FILE.with_suffix(".tmp")

    with open(temp, "w", encoding="utf-8") as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

    temp.replace(HISTORY_FILE)


# =========================================================
# NUMEROLOGY
# =========================================================

def digit_sum(number):
    return sum(int(x) for x in str(number))


def reduce_number(number):

    while number > 9:
        number = digit_sum(number)

    return number


def calculate_mulank(dob):

    return {
        "compound": dob.day,
        "reduced": reduce_number(dob.day)
    }


def calculate_bhagyank(dob):

    total = sum(
        int(x) for x in dob.strftime("%d%m%Y")
    )

    return {
        "compound": total,
        "reduced": reduce_number(total)
    }


def calculate_personal_year(dob, year):

    total = (
        digit_sum(dob.day)
        + digit_sum(dob.month)
        + digit_sum(year)
    )

    return {
        "compound": total,
        "reduced": reduce_number(total),
        "year": year
    }


# =========================================================
# BIRTHDAY RESEARCH
# =========================================================

def discover_people():

    birthday = TODAY.strftime("%d %B")

    prompt = f"""
You are a professional researcher specialising in
famous Indian public personalities.

Today's date is {birthday} {TODAY.year}.

Find famous Indian personalities whose actual Gregorian
birthday is {birthday}.

STRICT REQUIREMENTS:

1. Only Indian personalities.
2. Only people who are currently alive.
3. Maximum {MAX_PEOPLE} people.
4. Include different fields where possible:
   cinema, sports, business, politics, literature,
   music, science and public life.
5. Verify exact date of birth using at least TWO
   independent reliable sources.
6. Verify that the person is currently alive.
7. Exclude uncertain or conflicting information.
8. Never invent birthdays or achievements.
9. Do not use Wikipedia as the only source.
10. Prefer official biographies, established newspapers,
    institutional websites and reputable publications.
11. Use HTTPS URLs.
12. Do not use the word celebrity.

Return JSON only:

{{
  "people": [
    {{
      "name": "Full name",
      "date_of_birth": "YYYY-MM-DD",
      "field": "Profession",
      "is_alive": true,
      "birthday_matches_today": true,
      "living_status_evidence": "Explanation",
      "sources": [
        {{
          "title": "Source title",
          "url": "https://example.com",
          "supports": "Date of birth"
        }},
        {{
          "title": "Source title",
          "url": "https://example.org",
          "supports": "Date of birth"
        }},
        {{
          "title": "Source title",
          "url": "https://example.net",
          "supports": "Living status"
        }}
      ],
      "documented_life_milestones": [
        "Verified achievement",
        "Verified milestone"
      ]
    }}
  ]
}}

Return an empty people array if no qualifying
personality can be verified.

Never guess.
"""

    result = ask_openai(
        prompt,
        use_web_search=True
    )

    people = []
    seen = set()

    for person in result.get("people", []):

        try:
            dob = date.fromisoformat(
                person["date_of_birth"]
            )
        except (ValueError, KeyError, TypeError):
            continue

        if (dob.day, dob.month) != (
            TODAY.day, TODAY.month
        ):
            continue

        if person.get("is_alive") is not True:
            continue

        if person.get("birthday_matches_today") is not True:
            continue

        name = person.get("name", "").strip()

        if not name or name.lower() in seen:
            continue

        sources = person.get("sources", [])
        valid_sources = []

        for source in sources:

            try:
                parsed = urlparse(source.get("url", ""))

                if (
                    parsed.scheme == "https"
                    and parsed.netloc
                ):
                    valid_sources.append(source)

            except Exception:
                continue

        # Require two different source domains.

        domains = {
            urlparse(s["url"]).netloc.lower()
            for s in valid_sources
        }

        if len(domains) < 2:
            log.warning("Skipping %s: insufficient sources", name)
            continue

        person["sources"] = valid_sources
        person["dob"] = dob

        people.append(person)
        seen.add(name.lower())

        if len(people) >= MAX_PEOPLE:
            break

    return people


# =========================================================
# NUMEROLOGY ANALYSIS
# =========================================================

def generate_thread(people):

    calculated = []

    for person in people:

        dob = person["dob"]

        calculated.append({

            "name": person["name"],
            "field": person["field"],
            "date_of_birth": dob.isoformat(),

            "mulank": calculate_mulank(dob),

            "bhagyank": calculate_bhagyank(dob),

            "personal_year": calculate_personal_year(
                dob,
                FORECAST_YEAR
            ),

            "milestones": person.get(
                "documented_life_milestones", []
            ),

            "sources": person["sources"]
        })

    prompt = f"""
You are an analytical Indian numerology writer.

Today's date: {TODAY.isoformat()}
Forecast year: {FORECAST_YEAR}

PERSON DATA:

{json.dumps(calculated, ensure_ascii=False, indent=2)}

Create an X thread.

STRUCTURE:

POST 1:
Wish all personalities happy birthday FIRST.
Mention their names and professions.

POST 2:
For EACH person, explain:
- Mulank.
- Original compound birth-day number.
- Traditional numerological meaning.
- Analytical connection with documented career
  or personality-related public evidence.

POST 3:
For EACH person, explain:
- Bhagyank.
- Original compound total.
- Traditional interpretation.
- Connection with documented life milestones.

POST 4:
For EACH person, explain:
- Personal Year for {FORECAST_YEAR}.
- Traditional meaning.
- Symbolic themes.
- Thoughtful interpretation of the year ahead.

WRITING RULES:

1. Maximum 275 characters per post.
2. English only.
3. No emojis.
4. No hashtags.
5. No decorative symbols.
6. No Markdown.
7. No marketing language.
8. Never mention The Astro Bhaiya.
9. Never use the word celebrity.
10. No exaggerated claims.
11. No guaranteed predictions.
12. Avoid repetitive writing.
13. Do not invent achievements.
14. Use supplied calculations exactly.
15. Do not change any numbers.
16. Do not include URLs.
17. Clearly distinguish numerological interpretation
    from documented biographical facts.
18. Make each post specific and interesting.

Return valid JSON only:

{{
  "opening_post": "Birthday greeting",
  "analyses": [
    {{
      "name": "Person name",
      "mulank_post": "Mulank analysis",
      "bhagyank_post": "Bhagyank analysis",
      "personal_year_post": "Personal year analysis"
    }}
  ]
}}

There must be exactly three analysis posts per person.
"""

    result = ask_openai(
        prompt,
        use_web_search=False
    )

    opening = result.get("opening_post", "").strip()
    analyses = result.get("analyses", [])

    if not opening:
        raise ValueError("Missing birthday greeting")

    if len(analyses) != len(people):
        raise ValueError("Analysis count mismatch")

    posts = [opening]

    for person, analysis in zip(people, analyses):

        if (
            analysis.get("name", "").strip().lower()
            != person["name"].strip().lower()
        ):
            raise ValueError("Person name mismatch")

        individual = [

            analysis.get("mulank_post", "").strip(),

            analysis.get("bhagyank_post", "").strip(),

            analysis.get("personal_year_post", "").strip()

        ]

        if not all(individual):
            raise ValueError(
                f"Incomplete analysis for {person['name']}"
            )

        posts.extend(individual)

    for i, post in enumerate(posts, start=1):

        if len(post) > MAX_POST_LENGTH:
            raise ValueError(
                f"Post {i} has {len(post)} characters. "
                f"Maximum is {MAX_POST_LENGTH}."
            )

    return posts


# =========================================================
# BUFFER API
# =========================================================

def buffer_request(query):

    if not BUFFER_TOKEN:
        raise RuntimeError(
            "Missing BUFFER_X_ACCESS_TOKEN"
        )

    response = requests.post(

        BUFFER_URL,

        headers={
            "Authorization": f"Bearer {BUFFER_TOKEN}",
            "Content-Type": "application/json"
        },

        json={"query": query},

        timeout=45
    )

    response.raise_for_status()

    data = response.json()

    if data.get("errors"):

        raise RuntimeError(
            f"Buffer GraphQL error: {data['errors']}"
        )

    return data.get("data", {})


# =========================================================
# AUTOMATIC ACCOUNT AND X CHANNEL DETECTION
# =========================================================

def discover_x_channel():

    log.info("Connecting to your Buffer account...")

    # One account: get its organizations.

    account_query = """
    query {
        account {
            organizations {
                id
                name
            }
        }
    }
    """

    data = buffer_request(account_query)

    organizations = (
        data.get("account", {}).get("organizations", [])
    )

    if not organizations:
        raise RuntimeError(
            "No organization found in your Buffer account"
        )

    # Use the first organization automatically.

    organization = organizations[0]

    log.info(
        "Using Buffer organization: %s",
        organization["name"]
    )

    # Insert organization ID as a GraphQL string.
    # This avoids the previous ID! / OrganizationId!
    # variable type mismatch entirely.

    organization_id = json.dumps(organization["id"])

    channels_query = f"""
    query {{
        channels(input: {{
            organizationId: {organization_id}
        }}) {{
            id
            name
            displayName
            service
            isQueuePaused
        }}
    }}
    """

    channel_data = buffer_request(channels_query)

    channels = channel_data.get("channels", [])

    # Find X channel.

    x_channels = [
        channel for channel in channels
        if channel.get("service", "").lower() == "twitter"
    ]

    if not x_channels:
        raise RuntimeError(
            "No X/Twitter channel connected to this organization"
        )

    if len(x_channels) > 1:
        raise RuntimeError(
            "More than one X channel found. "
            "Please disconnect the unwanted channel "
            "or select one explicitly."
        )

    channel = x_channels[0]

    if channel.get("isQueuePaused"):
        raise RuntimeError(
            "Your Buffer X queue is paused"
        )

    log.info(
        "X channel detected: %s",
        channel.get("displayName") or channel.get("name")
    )

    return channel["id"]


# =========================================================
# PUBLISH THREAD
# =========================================================

def publish_thread(posts, channel_id):

    if not posts:
        raise ValueError("No posts to publish")

    # Every post, including the opening post,
    # must be inside the thread array.

    thread_items = [
        {"text": post}
        for post in posts
    ]

    variables = {

        "input": {

            "channelId": channel_id,

            "text": posts[0],

            "schedulingType": "automatic",

            "mode": "addToQueue",

            "metadata": {

                "twitter": {

                    "thread": thread_items

                }

            }
        }
    }

    mutation = """
    mutation CreateThread($input: CreatePostInput!) {

        createPost(input: $input) {

            ... on PostActionSuccess {
                post {
                    id
                    text
                    status
                    dueAt
                }
            }

            ... on MutationError {
                message
            }
        }
    }
    """

    response = requests.post(

        BUFFER_URL,

        headers={
            "Authorization": f"Bearer {BUFFER_TOKEN}",
            "Content-Type": "application/json"
        },

        json={
            "query": mutation,
            "variables": variables
        },

        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            f"Buffer publishing error: {data['errors']}"
        )

    result = (
        data.get("data", {}).get("createPost", {})
    )

    if result.get("message"):
        raise RuntimeError(result["message"])

    post = result.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            f"Buffer did not confirm thread creation: {data}"
        )

    return post


# =========================================================
# MAIN EXECUTION
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--preview",
        action="store_true"
    )

    parser.add_argument(
        "--force",
        action="store_true"
    )

    args = parser.parse_args()

    history = load_history()

    # Duplicate protection.

    if not args.force:

        if history.get("status") == "submitted_to_buffer":

            log.info(
                "Today's thread already submitted. Exiting."
            )

            return

        if history.get("status") == "publishing":

            raise RuntimeError(
                "Previous publishing attempt is unresolved. "
                "Check Buffer before using --force."
            )

    log.info(
        "Starting birthday research: %s",
        TODAY
    )

    # STEP 1: RESEARCH

    people = discover_people()

    if not people:

        history["status"] = "no_verified_people"
        history["people"] = []

        save_history(history)

        log.info(
            "No qualifying living Indian personalities found."
        )

        return

    log.info(
        "Verified candidates: %s",
        len(people)
    )

    # STEP 2: ANALYSIS

    posts = generate_thread(people)

    # STEP 3: SAVE DATA

    history["people"] = [

        {

            "name": person["name"],

            "date_of_birth": person["dob"].isoformat(),

            "field": person["field"],

            "sources": person["sources"],

            "mulank": calculate_mulank(person["dob"]),

            "bhagyank": calculate_bhagyank(person["dob"]),

            "personal_year": calculate_personal_year(
                person["dob"],
                FORECAST_YEAR
            )

        }

        for person in people
    ]

    history["thread"] = posts

    history["generated_at"] = (
        datetime.now(TZ).isoformat()
    )

    # STEP 4: PREVIEW

    if args.preview:

        history["status"] = "preview"

        save_history(history)

        print("\n" + "=" * 55)
        print("DAILY FAMOUS INDIAN NUMEROLOGY")
        print("PREVIEW - NOT PUBLISHED")
        print("=" * 55)

        for index, post in enumerate(posts, start=1):

            print(
                f"\nPOST {index} "
                f"({len(post)} characters)"
            )

            print(post)

        print("\n" + "=" * 55)

        return

    # STEP 5: DETECT BUFFER CHANNEL

    channel_id = discover_x_channel()

    # STEP 6: SAVE PUBLISHING STATUS

    history["status"] = "publishing"

    save_history(history)

    # STEP 7: PUBLISH

    result = publish_thread(
        posts,
        channel_id
    )

    # STEP 8: CONFIRM SUCCESS

    history["status"] = "submitted_to_buffer"

    history["buffer_post_id"] = result["id"]

    history["buffer_status"] = result.get("status")

    history["submitted_at"] = (
        datetime.now(TZ).isoformat()
    )

    save_history(history)

    log.info(
        "Successfully submitted thread to Buffer."
    )

    log.info(
        "Buffer post ID: %s",
        result["id"]
    )

    log.info(
        "Total posts: %s",
        len(posts)
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:
        main()

    except Exception:

        log.exception(
            "Daily numerology execution failed"
        )

        raise
