
import os
import re
import json
import argparse
import logging
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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")

BUFFER_TOKEN = os.getenv("BUFFER_X_ACCESS_TOKEN")
BUFFER_CHANNEL_NAME = os.getenv("BUFFER_X_CHANNEL_NAME", "").strip()

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

log = logging.getLogger("famous-numerology")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

if not BUFFER_TOKEN:
    raise RuntimeError("Missing BUFFER_X_ACCESS_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# HISTORY MANAGEMENT
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
    temp_file = HISTORY_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    temp_file.replace(HISTORY_FILE)


# =========================================================
# NUMEROLOGY CALCULATIONS
# =========================================================

def digit_sum(number):
    return sum(int(x) for x in str(number))


def reduce_number(number):
    while number > 9:
        number = digit_sum(number)
    return number


def calculate_mulank(dob):
    day = dob.day
    return {
        "compound": day,
        "reduced": reduce_number(day)
    }


def calculate_bhagyank(dob):
    total = sum(int(x) for x in dob.strftime("%d%m%Y"))

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
# OPENAI RESPONSES API
# =========================================================

def ask_openai(prompt):
    response = client.responses.create(
        model=OPENAI_MODEL,
        tools=[
            {"type": "web_search"}
        ],
        input=prompt,
        text={
            "format": {
                "type": "json_object"
            }
        }
    )

    output = response.output_text.strip()

    # Handle accidental Markdown wrappers.
    output = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        output
    )

    return json.loads(output)


# =========================================================
# DISCOVER FAMOUS INDIAN PERSONALITIES
# =========================================================

def discover_people():
    date_text = TODAY.strftime("%d %B")
    
    prompt = f"""
You are a meticulous researcher specialising in Indian
public figures and Indian numerology.

Today's date in India is {date_text} {TODAY.year}.

Find famous Indian personalities whose actual Gregorian
date of birth is {date_text}.

STRICT REQUIREMENTS:

1. Only Indian personalities.
2. Only people who are currently alive.
3. Maximum {MAX_PEOPLE} people.
4. Prioritise widely recognised people from different
   fields: cinema, sports, business, politics, literature,
   music, science and public life.
5. Never invent a birthday.
6. Never infer a birth date from an unreliable website.
7. Verify the exact day, month and year of birth using
   at least TWO independent reliable sources.
8. Verify that each person is currently alive using
   current information.
9. Do not include someone whose living status is uncertain.
10. Do not include people with conflicting birth dates.
11. The sources must have HTTPS URLs.
12. Prefer reputable newspapers, official biographies,
    government sources, established publications and
    verified institutional profiles.
13. Do not use Wikipedia as the only source.
14. Do not call anyone a celebrity.

Return valid JSON only:

{{
  "people": [
    {{
      "name": "Full name",
      "date_of_birth": "YYYY-MM-DD",
      "field": "Profession",
      "is_alive": true,
      "birthday_matches_today": true,
      "living_status_evidence": "Short explanation",
      "sources": [
        {{
          "title": "Source title",
          "url": "https://...",
          "supports": "Exact date of birth"
        }},
        {{
          "title": "Source title",
          "url": "https://...",
          "supports": "Exact date of birth"
        }},
        {{
          "title": "Source title",
          "url": "https://...",
          "supports": "Current living status"
        }}
      ],
      "documented_life_milestones": [
        "A verified achievement or important life event",
        "Another verified achievement"
      ]
    }}
  ]
}}

IMPORTANT:
Return an empty people array if no qualifying person
can be verified. Never fill the list with guesses.

Research the actual date, not the next famous birthday.
"""

    result = ask_openai(prompt)

    people = []

    for person in result.get("people", []):

        try:
            dob = date.fromisoformat(person["date_of_birth"])
        except (ValueError, KeyError, TypeError):
            continue

        if (dob.month, dob.day) != (TODAY.month, TODAY.day):
            continue

        if person.get("is_alive") is not True:
            continue

        if person.get("birthday_matches_today") is not True:
            continue

        sources = person.get("sources", [])

        valid_sources = []

        for source in sources:
            url = source.get("url", "")

            try:
                parsed = urlparse(url)
                if parsed.scheme == "https" and parsed.netloc:
                    valid_sources.append(source)
            except Exception:
                continue

        unique_urls = {
            source["url"].lower().rstrip("/")
            for source in valid_sources
        }

        # Require two independent source URLs.
        if len(unique_urls) < 2:
            log.warning(
                "Skipping %s: fewer than two valid sources",
                person.get("name")
            )
            continue

        person["sources"] = valid_sources
        person["dob"] = dob

        people.append(person)

        if len(people) >= MAX_PEOPLE:
            break

    return people


# =========================================================
# GENERATE NUMEROLOGY THREAD
# =========================================================

def generate_thread(people):

    calculated_people = []

    for person in people:

        dob = person["dob"]

        mulank = calculate_mulank(dob)
        bhagyank = calculate_bhagyank(dob)
        personal_year = calculate_personal_year(
            dob,
            FORECAST_YEAR
        )

        calculated_people.append({
            "name": person["name"],
            "field": person["field"],
            "date_of_birth": dob.isoformat(),
            "mulank": mulank,
            "bhagyank": bhagyank,
            "personal_year": personal_year,
            "milestones": person.get(
                "documented_life_milestones", []
            ),
            "sources": person["sources"]
        })

    prompt = f"""
You are an excellent Indian numerology researcher
and analytical writer creating an X thread.

Today's date: {TODAY.isoformat()}
Forecast year: {FORECAST_YEAR}

PERSON DATA:
{json.dumps(calculated_people, ensure_ascii=False, indent=2)}

YOUR TASK:

Create one opening birthday post followed by EXACTLY
three individual analysis posts for every person.

THREAD STRUCTURE:

POST 1: MAIN BIRTHDAY GREETING

Wish all verified people a happy birthday first.

Mention their names and professions.

Keep the greeting natural, warm and professional.

POST 2: MULANK ANALYSIS

For each person, explain:
- Their Mulank.
- Original compound birth-day number.
- The traditional Indian numerological interpretation.
- How the interpretation relates to documented aspects
  of their personality or career.

Do not pretend that numerology proves their personality.

POST 3: BHAGYANK ANALYSIS

For each person, explain:
- Their Bhagyank.
- Original compound total.
- Its traditional numerological interpretation.
- Connect it analytically to their documented
  achievements, career choices or life milestones.

Do not invent events or psychological facts.

POST 4: PERSONAL YEAR ANALYSIS

For each person, explain:
- Their Personal Year for {FORECAST_YEAR}.
- Its traditional numerological meaning.
- What themes it symbolically represents.
- A thoughtful interpretation of the year ahead.

This is an interpretive forecast, not a guaranteed prediction.

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
11. No guaranteed outcomes.
12. No generic repetitive descriptions.
13. Avoid repeating the same sentence structure.
14. Keep the analysis specific to each person.
15. Never invent biographical milestones.
16. Use the supplied calculations exactly.
17. Do not calculate or alter numbers yourself.
18. Do not put URLs in the posts.
19. Make every post readable as a standalone X post.

IMPORTANT:
There must be exactly one opening post and exactly
three posts per person.

Return valid JSON only:

{{
  "opening_post": "Birthday greeting",
  "analyses": [
    {{
      "name": "Person name",
      "mulank_post": "Analysis",
      "bhagyank_post": "Analysis",
      "personal_year_post": "Analysis"
    }}
  ]
}}
"""

    result = ask_openai(prompt)

    opening = result.get("opening_post", "").strip()
    analyses = result.get("analyses", [])

    if not opening:
        raise ValueError("Missing opening birthday post")

    if len(analyses) != len(people):
        raise ValueError("Incorrect number of individual analyses")

    posts = [opening]

    for person, analysis in zip(people, analyses):

        if analysis.get("name", "").strip().lower() != \
                person["name"].strip().lower():
            raise ValueError("Person order/name mismatch")

        individual_posts = [
            analysis.get("mulank_post", "").strip(),
            analysis.get("bhagyank_post", "").strip(),
            analysis.get("personal_year_post", "").strip()
        ]

        if not all(individual_posts):
            raise ValueError(
                f"Incomplete analysis for {person['name']}"
            )

        posts.extend(individual_posts)

    for index, post in enumerate(posts, start=1):

        if len(post) > MAX_POST_LENGTH:
            raise ValueError(
                f"Post {index} exceeds {MAX_POST_LENGTH} characters: "
                f"{len(post)} characters"
            )

    return posts


# =========================================================
# BUFFER API
# =========================================================

def buffer_request(query):
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


def discover_x_channel():

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
            "No Buffer organizations found"
        )

    channels = []

    for organization in organizations:

        query = """
        query GetChannels {
            channels(input: {
                organizationId: "%s"
            }) {
                id
                name
                displayName
                service
                isQueuePaused
            }
        }
        """ % organization["id"]

        result = buffer_request(query)

        channels.extend(result.get("channels", []))

    x_channels = [
        channel for channel in channels
        if channel.get("service", "").lower() == "twitter"
    ]

    if BUFFER_CHANNEL_NAME:
        x_channels = [
            channel for channel in x_channels
            if BUFFER_CHANNEL_NAME.lower() in (
                channel.get("name", "").lower()
            )
            or BUFFER_CHANNEL_NAME.lower() in (
                channel.get("displayName", "").lower()
            )
        ]

    if len(x_channels) == 0:
        raise RuntimeError("No matching X channel found")

    if len(x_channels) > 1:
        names = [
            channel.get("name")
            for channel in x_channels
        ]
        raise RuntimeError(
            f"Multiple X channels found: {names}. "
            "Set BUFFER_X_CHANNEL_NAME."
        )

    channel = x_channels[0]

    if channel.get("isQueuePaused"):
        raise RuntimeError("The selected Buffer X queue is paused")

    log.info(
        "Selected Buffer X channel: %s",
        channel.get("name")
    )

    return channel["id"]


def publish_thread(posts, channel_id):

    # Buffer requires the root post in both locations.
    thread_items = [
        {"text": post}
        for post in posts
    ]

    variables = {
        "input": {
            "channelId": channel_id,
            "text": posts[0],
            "schedulingType": "automatic",
            "mode": "shareNow",
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
        raise RuntimeError(str(data["errors"]))

    result = (
        data.get("data", {})
        .get("createPost", {})
    )

    if "message" in result:
        raise RuntimeError(result["message"])

    post = result.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            f"Buffer did not confirm post creation: {data}"
        )

    return post


# =========================================================
# MAIN EXECUTION
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate and republish today's thread"
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate and save the thread without publishing"
    )

    args = parser.parse_args()

    history = load_history()

    if not args.force:

        if history.get("status") == "submitted_to_buffer":
            log.info("Today's thread was already submitted.")
            return

        if history.get("status") == "publishing":
            log.warning(
                "Previous execution stopped during publishing. "
                "Check Buffer manually before using --force."
            )
            return

    log.info(
        "Starting famous Indian birthday research for %s",
        TODAY
    )

    # Step 1: Discover and verify people.
    people = discover_people()

    if not people:

        history["status"] = "no_verified_people"
        history["people"] = []
        save_history(history)

        log.info(
            "No qualifying living Indian personalities "
            "with verified birthdays found today."
        )
        return

    # Step 2: Calculate numbers and generate analysis.
    posts = generate_thread(people)

    # Step 3: Save the generated thread.
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
    history["generated_at"] = datetime.now(TZ).isoformat()

    if args.preview:

        history["status"] = "preview"
        save_history(history)

        print("\n" + "=" * 55)
        print("PREVIEW - NOT PUBLISHED")
        print("=" * 55)

        for index, post in enumerate(posts, start=1):
            print(f"\nPOST {index} ({len(post)} characters)")
            print(post)

        print("\n" + "=" * 55)
        return

    # Step 4: Resolve Buffer channel.
    channel_id = discover_x_channel()

    # Step 5: Mark publishing before sending.
    # This prevents automatic duplicate submissions after
    # an interrupted execution.
    history["status"] = "publishing"
    save_history(history)

    # Step 6: Submit the entire thread as one Buffer post.
    result = publish_thread(posts, channel_id)

    # Step 7: Only mark successful after Buffer confirmation.
    history["status"] = "submitted_to_buffer"
    history["buffer_post_id"] = result["id"]
    history["buffer_status"] = result.get("status")
    history["submitted_at"] = datetime.now(TZ).isoformat()

    save_history(history)

    log.info("Thread successfully submitted to Buffer.")
    log.info("Buffer post ID: %s", result["id"])
    log.info("Thread posts: %s", len(posts))

    for index, post in enumerate(posts, start=1):
        log.info(
            "Post %s: %s characters",
            index,
            len(post)
        )


if __name__ == "__main__":
    main()
