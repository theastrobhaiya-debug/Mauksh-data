
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
    or "gpt-6-astra"
)

BUFFER_TOKEN = os.getenv("BUFFER_X_ACCESS_TOKEN")
BUFFER_CHANNEL_NAME = os.getenv(
    "BUFFER_X_CHANNEL_NAME", ""
).strip()

BUFFER_URL = "https://api.buffer.com"

MAX_PEOPLE = 4
MAX_POST_LENGTH = 275

BASE_DIR = Path(__file__).resolve().parents[1]

HISTORY_DIR = (
    BASE_DIR / "data" / "famous_numerology"
)

HISTORY_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = HISTORY_DIR / f"{TODAY.isoformat()}.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("daily-numerology")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

if not BUFFER_TOKEN:
    raise RuntimeError("Missing BUFFER_X_ACCESS_TOKEN")

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

        # Recover a JSON object if the model adds
        # unwanted text around it.
        start = output.find("{")
        end = output.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                "Model did not return a valid JSON object"
            )

        return json.loads(output[start:end + 1])


# =========================================================
# OPENAI API
# =========================================================

def ask_openai(prompt, use_web_search=False):

    request_args = {
        "model": OPENAI_MODEL,
        "input": prompt
    }

    if use_web_search:

        # IMPORTANT:
        # Do not combine web_search with JSON mode.
        # Ask for JSON in the prompt and parse the result.

        request_args["tools"] = [
            {
                "type": "web_search",
                "search_context_size": "high"
            }
        ]

    else:

        # JSON mode is used only for requests without
        # web search.

        request_args["text"] = {
            "format": {
                "type": "json_object"
            }
        }

    response = client.responses.create(**request_args)

    output = response.output_text

    if not output:
        raise ValueError("OpenAI returned an empty response")

    return parse_json_output(output)


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

    with open(
        HISTORY_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_history(data):

    temp_file = HISTORY_FILE.with_suffix(".tmp")

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

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
# DISCOVER FAMOUS INDIAN PERSONALITIES
# =========================================================

def discover_people():

    date_text = TODAY.strftime("%d %B")

    prompt = f"""
You are a professional researcher specialising in
Indian public figures and traditional numerology.

Today's Indian date is {date_text} {TODAY.year}.

Find famous Indian personalities whose actual Gregorian
birthday is {date_text}.

STRICT RESEARCH RULES:

1. Only Indian personalities.
2. Only people who are alive today.
3. Maximum {MAX_PEOPLE} people.
4. Prioritise widely recognised people across:
   cinema, sports, business, politics, literature,
   music, science and public life.
5. Never invent a birthday.
6. Verify the complete date of birth using at least
   TWO independent reliable sources.
7. Check current living status using recent information.
8. Exclude anyone whose living status is uncertain.
9. Exclude people with conflicting birth dates.
10. Do not use Wikipedia as the only source.
11. Use HTTPS source URLs.
12. Prefer official biographies, reputable newspapers,
    institutional profiles and established publications.
13. Do not use the word celebrity.
14. Do not include people born on a different date.

Return JSON only, with this structure:

{{
  "people": [
    {{
      "name": "Full name",
      "date_of_birth": "YYYY-MM-DD",
      "field": "Profession",
      "is_alive": true,
      "birthday_matches_today": true,
      "living_status_evidence": "Evidence",
      "sources": [
        {{
          "title": "Source title",
          "url": "https://example.com",
          "supports": "Date of birth"
        }},
        {{
          "title": "Source title",
          "url": "https://example.com",
          "supports": "Date of birth"
        }},
        {{
          "title": "Source title",
          "url": "https://example.com",
          "supports": "Living status"
        }}
      ],
      "documented_life_milestones": [
        "Verified achievement",
        "Another verified achievement"
      ]
    }}
  ]
}}

If no qualifying personality can be verified,
return an empty people array.

Do not fill the list with guesses.
"""

    result = ask_openai(
        prompt,
        use_web_search=True
    )

    people = []
    seen_names = set()

    for person in result.get("people", []):

        try:
            dob = date.fromisoformat(
                person["date_of_birth"]
            )
        except (ValueError, KeyError, TypeError):
            continue

        if (dob.month, dob.day) != (
            TODAY.month, TODAY.day
        ):
            continue

        if person.get("is_alive") is not True:
            continue

        if person.get("birthday_matches_today") is not True:
            continue

        name = person.get("name", "").strip()

        if not name or name.lower() in seen_names:
            continue

        sources = person.get("sources", [])
        valid_sources = []

        for source in sources:

            url = source.get("url", "")

            try:
                parsed = urlparse(url)

                if (
                    parsed.scheme == "https"
                    and parsed.netloc
                ):
                    valid_sources.append(source)

            except Exception:
                continue

        unique_urls = {
            s["url"].lower().rstrip("/")
            for s in valid_sources
        }

        if len(unique_urls) < 2:

            log.warning(
                "Skipping %s: insufficient sources",
                name
            )

            continue

        person["sources"] = valid_sources
        person["dob"] = dob

        people.append(person)
        seen_names.add(name.lower())

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

        calculated_people.append({

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
You are an excellent Indian numerology analyst
and analytical writer creating an X thread.

Today's date: {TODAY.isoformat()}
Forecast year: {FORECAST_YEAR}

PERSON DATA:

{json.dumps(calculated_people, ensure_ascii=False, indent=2)}

Create one opening birthday greeting followed by
exactly THREE individual analysis posts per person.

THREAD STRUCTURE:

POST 1: BIRTHDAY GREETING

Wish all verified people happy birthday FIRST.

Mention their names and professions.

Keep it warm, natural and professional.

POST 2: MULANK ANALYSIS

For each person:

- Explain their Mulank.
- Include the original compound birth-day number.
- Explain its traditional numerological meaning.
- Connect the interpretation analytically to
  documented aspects of their career or life.

POST 3: BHAGYANK ANALYSIS

For each person:

- Explain their Bhagyank.
- Include the original compound total.
- Explain its traditional numerological meaning.
- Connect it to documented career achievements
  or life milestones.

Do not invent biographical events.

POST 4: PERSONAL YEAR

For each person:

- Explain their Personal Year for {FORECAST_YEAR}.
- Explain its traditional numerological meaning.
- Describe the symbolic themes of the year.
- Give a thoughtful interpretation.

This is an interpretive forecast, not a guarantee.

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
13. Avoid repeating sentence structures.
14. Be specific to each person.
15. Never invent milestones.
16. Use supplied calculations exactly.
17. Do not alter the numbers.
18. Do not include URLs in posts.
19. Each post must be readable independently.

IMPORTANT:

Return valid JSON only.

There must be exactly one opening post and
exactly three analysis posts per person.

Use this JSON structure:

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
"""

    result = ask_openai(
        prompt,
        use_web_search=False
    )

    opening = result.get(
        "opening_post", ""
    ).strip()

    analyses = result.get("analyses", [])

    if not opening:
        raise ValueError("Missing opening post")

    if len(analyses) != len(people):
        raise ValueError("Analysis count mismatch")

    posts = [opening]

    for person, analysis in zip(people, analyses):

        if (
            analysis.get("name", "").strip().lower()
            != person["name"].strip().lower()
        ):
            raise ValueError(
                f"Person mismatch: {person['name']}"
            )

        individual_posts = [

            analysis.get(
                "mulank_post", ""
            ).strip(),

            analysis.get(
                "bhagyank_post", ""
            ).strip(),

            analysis.get(
                "personal_year_post", ""
            ).strip()
        ]

        if not all(individual_posts):

            raise ValueError(
                f"Incomplete analysis: {person['name']}"
            )

        posts.extend(individual_posts)

    for index, post in enumerate(posts, start=1):

        if len(post) > MAX_POST_LENGTH:

            raise ValueError(
                f"Post {index} exceeds character limit: "
                f"{len(post)} characters"
            )

    return posts


# =========================================================
# BUFFER GRAPHQL
# =========================================================

def buffer_request(query, variables=None):

    response = requests.post(

        BUFFER_URL,

        headers={
            "Authorization": f"Bearer {BUFFER_TOKEN}",
            "Content-Type": "application/json"
        },

        json={
            "query": query,
            "variables": variables or {}
        },

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
# FIND X CHANNEL
# =========================================================

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
        data.get("account", {}).get(
            "organizations", []
        )
    )

    if not organizations:
        raise RuntimeError(
            "No Buffer organizations found"
        )

    channels = []

    for organization in organizations:

        query = """
        query GetChannels($organizationId: ID!) {
            channels(input: {
                organizationId: $organizationId
            }) {
                id
                name
                displayName
                service
                isQueuePaused
            }
        }
        """

        result = buffer_request(
            query,
            {
                "organizationId": organization["id"]
            }
        )

        channels.extend(
            result.get("channels", [])
        )

    x_channels = [

        channel for channel in channels

        if channel.get(
            "service", ""
        ).lower() == "twitter"

    ]

    if BUFFER_CHANNEL_NAME:

        x_channels = [

            channel for channel in x_channels

            if BUFFER_CHANNEL_NAME.lower()
            in channel.get("name", "").lower()

            or BUFFER_CHANNEL_NAME.lower()
            in channel.get("displayName", "").lower()

        ]

    if not x_channels:

        raise RuntimeError(
            "No matching X channel found in Buffer"
        )

    if len(x_channels) > 1:

        raise RuntimeError(
            "Multiple X channels found. "
            "Set BUFFER_X_CHANNEL_NAME in GitHub Variables."
        )

    channel = x_channels[0]

    if channel.get("isQueuePaused"):

        raise RuntimeError(
            "The selected Buffer X queue is paused"
        )

    log.info(
        "Selected X channel: %s",
        channel.get("name")
    )

    return channel["id"]


# =========================================================
# PUBLISH X THREAD
# =========================================================

def publish_thread(posts, channel_id):

    thread_items = [
        {"text": post}
        for post in posts
    ]

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

    data = buffer_request(
        mutation,
        variables
    )

    result = data.get("createPost", {})

    if result.get("message"):

        raise RuntimeError(
            result["message"]
        )

    post = result.get("post")

    if not post or not post.get("id"):

        raise RuntimeError(
            "Buffer did not confirm thread creation"
        )

    return post


# =========================================================
# MAIN
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true"
    )

    parser.add_argument(
        "--preview",
        action="store_true"
    )

    args = parser.parse_args()

    history = load_history()

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
        "Starting birthday research for %s",
        TODAY
    )

    # STEP 1: FIND PEOPLE

    people = discover_people()

    if not people:

        history["status"] = "no_verified_people"
        history["people"] = []

        save_history(history)

        log.info(
            "No qualifying birthdays found today."
        )

        return

    log.info(
        "Found %s verified candidates",
        len(people)
    )

    # STEP 2: GENERATE THREAD

    posts = generate_thread(people)

    # STEP 3: SAVE HISTORY

    history["people"] = [

        {

            "name": person["name"],

            "date_of_birth": person["dob"].isoformat(),

            "field": person["field"],

            "sources": person["sources"],

            "mulank": calculate_mulank(
                person["dob"]
            ),

            "bhagyank": calculate_bhagyank(
                person["dob"]
            ),

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

    # STEP 4: PREVIEW MODE

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

    # STEP 5: FIND BUFFER CHANNEL

    channel_id = discover_x_channel()

    # STEP 6: MARK BEFORE PUBLISHING

    history["status"] = "publishing"

    save_history(history)

    # STEP 7: PUBLISH

    result = publish_thread(
        posts,
        channel_id
    )

    # STEP 8: CONFIRM

    history["status"] = "submitted_to_buffer"

    history["buffer_post_id"] = result["id"]

    history["buffer_status"] = result.get("status")

    history["submitted_at"] = (
        datetime.now(TZ).isoformat()
    )

    save_history(history)

    log.info(
        "Successfully submitted thread to Buffer"
    )

    log.info(
        "Buffer ID: %s",
        result["id"]
    )

    log.info(
        "Total thread posts: %s",
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
