
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
# 1. CONFIGURATION
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

# Keep a safety margin below X's character limit.
TARGET_LENGTH = 240
MAX_POST_LENGTH = 275

BASE_DIR = Path(__file__).resolve().parents[1]

HISTORY_DIR = (
    BASE_DIR / "data" / "famous_numerology"
)

HISTORY_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = (
    HISTORY_DIR / f"{TODAY.isoformat()}.json"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("daily-numerology")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# 2. JSON HELPERS
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
            raise ValueError(
                "OpenAI did not return valid JSON"
            )

        return json.loads(
            output[start:end + 1]
        )


# =========================================================
# 3. OPENAI RESPONSES API
# =========================================================

def ask_openai(prompt, use_web_search=False):

    args = {
        "model": OPENAI_MODEL,
        "input": prompt
    }

    if use_web_search:

        # Web search and JSON mode are deliberately
        # kept separate to avoid API incompatibility.

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

    output = response.output_text

    if not output:
        raise RuntimeError(
            "OpenAI returned an empty response"
        )

    return parse_json_output(output)


# =========================================================
# 4. HISTORY MANAGEMENT
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
# 5. NUMEROLOGY CALCULATIONS
# =========================================================

def digit_sum(number):

    return sum(
        int(x) for x in str(number)
    )


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
# 6. BIRTHDAY RESEARCH
# =========================================================

def discover_people():

    birthday = TODAY.strftime("%d %B")

    prompt = f"""
You are a professional researcher specialising in
famous Indian public personalities.

Today's Indian date is {birthday} {TODAY.year}.

Find famous Indian personalities whose actual Gregorian
birthday is {birthday}.

STRICT REQUIREMENTS:

1. Only Indian personalities.
2. Only people currently alive.
3. Maximum {MAX_PEOPLE} people.
4. Prioritise widely recognised people from:
   cinema, sports, business, politics, literature,
   music, science and public life.
5. Verify exact date of birth with at least TWO
   independent reliable sources.
6. Check current living status using recent information.
7. Exclude uncertain or conflicting information.
8. Never invent birthdays.
9. Never invent achievements.
10. Do not use Wikipedia as the only source.
11. Prefer official biographies, reputable newspapers,
    established publications and institutional websites.
12. Use HTTPS source URLs.
13. Do not use the word celebrity.
14. Do not include people born on another date.
15. Include actual birth year, not just day and month.

Return JSON only:

{{
  "people": [
    {{
      "name": "Full name",
      "date_of_birth": "YYYY-MM-DD",
      "field": "Profession",
      "is_alive": true,
      "birthday_matches_today": true,
      "living_status_evidence": "Recent evidence",
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
        "Another verified achievement"
      ]
    }}
  ]
}}

Return an empty people array if no qualifying
personality can be verified.

Never guess.
"""

    log.info(
        "Researching birthdays for %s",
        birthday
    )

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

        # Verify actual birthday.

        if (dob.day, dob.month) != (
            TODAY.day,
            TODAY.month
        ):
            continue

        if person.get("is_alive") is not True:
            continue

        if person.get("birthday_matches_today") is not True:
            continue

        name = person.get("name", "").strip()

        if not name:
            continue

        if name.lower() in seen_names:
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

        # Require independent source domains.

        domains = {
            urlparse(s["url"]).netloc.lower()
            for s in valid_sources
        }

        if len(domains) < 2:

            log.warning(
                "Skipping %s: insufficient independent sources",
                name
            )

            continue

        person["sources"] = valid_sources
        person["dob"] = dob

        people.append(person)
        seen_names.add(name.lower())

        if len(people) >= MAX_PEOPLE:
            break

    log.info(
        "Qualifying personalities found: %s",
        len(people)
    )

    return people


# =========================================================
# 7. AUTOMATIC POST SHORTENING
# =========================================================

def shorten_posts(posts):

    log.info(
        "Automatically shortening posts to fit X limits..."
    )

    prompt = f"""
You are an expert editor for X.

Rewrite the following posts to a maximum of
{TARGET_LENGTH} characters EACH.

IMPORTANT RULES:

1. Preserve every person's name.
2. Preserve all numerology numbers exactly.
3. Preserve Mulank, Bhagyank and Personal Year.
4. Preserve the main analytical insight.
5. Preserve important documented facts.
6. Never invent facts.
7. Do not change the meaning.
8. Do not combine separate posts.
9. Keep the original order.
10. English only.
11. No emojis.
12. No hashtags.
13. No decorative symbols.
14. Keep the writing natural and analytical.
15. Aim for 220-240 characters, never exceed 240.

POSTS:

{json.dumps(posts, ensure_ascii=False, indent=2)}

Return JSON only:

{{
    "posts": [
        "Shortened post 1",
        "Shortened post 2"
    ]
}}
"""

    result = ask_openai(
        prompt,
        use_web_search=False
    )

    shortened = result.get("posts", [])

    if len(shortened) != len(posts):

        raise ValueError(
            "Post shortening count mismatch"
        )

    shortened = [
        post.strip()
        for post in shortened
    ]

    for index, post in enumerate(shortened, start=1):

        if not post:
            raise ValueError(
                f"Empty shortened post: {index}"
            )

    return shortened


def validate_and_shorten(posts):

    # First pass: automatic shortening.

    if any(
        len(post) > TARGET_LENGTH
        for post in posts
    ):

        posts = shorten_posts(posts)

    # Second pass: check whether shortening succeeded.

    if any(
        len(post) > MAX_POST_LENGTH
        for post in posts
    ):

        log.warning(
            "Some posts still exceed the maximum. "
            "Running one more shortening pass."
        )

        posts = shorten_posts(posts)

    # Final strict validation.

    for index, post in enumerate(posts, start=1):

        if len(post) > MAX_POST_LENGTH:

            raise ValueError(
                f"Post {index} has {len(post)} characters. "
                f"Maximum is {MAX_POST_LENGTH}."
            )

    return posts


# =========================================================
# 8. GENERATE NUMEROLOGY THREAD
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
                "documented_life_milestones",
                []
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

Create one birthday greeting followed by EXACTLY
three analysis posts per person.

THREAD STRUCTURE:

POST 1: BIRTHDAY GREETING

Wish all verified people happy birthday FIRST.

Mention their names and professions.

Make it warm and professional.

POST 2: MULANK ANALYSIS

For each person explain:

- Their Mulank.
- Original compound birth-day number.
- Traditional numerological interpretation.
- Analytical connection with documented public
  career milestones or achievements.

POST 3: BHAGYANK ANALYSIS

For each person explain:

- Their Bhagyank.
- Original compound total.
- Traditional interpretation.
- Connection with documented life milestones.

POST 4: PERSONAL YEAR ANALYSIS

For each person explain:

- Personal Year for {FORECAST_YEAR}.
- Traditional numerological meaning.
- Symbolic themes of the year.
- Thoughtful interpretation of the year ahead.

WRITING RULES:

1. Maximum 240 characters per post.
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
12. Avoid repetitive sentence structures.
13. Never invent achievements.
14. Use supplied calculations exactly.
15. Do not alter numbers.
16. No URLs in posts.
17. Clearly distinguish traditional numerology
    from documented biographical facts.
18. Make every analysis interesting and specific.

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

There must be exactly one opening post
and exactly three posts per person.
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
        raise ValueError(
            "Missing birthday greeting"
        )

    if len(analyses) != len(people):

        raise ValueError(
            "Incorrect number of individual analyses"
        )

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
                f"Incomplete analysis for {person['name']}"
            )

        posts.extend(individual_posts)

    # Automatic character correction.

    posts = validate_and_shorten(posts)

    log.info(
        "Generated %s posts successfully",
        len(posts)
    )

    return posts


# =========================================================
# 9. BUFFER GRAPHQL REQUEST
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

        json={
            "query": query
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
# 10. AUTOMATIC BUFFER ACCOUNT DETECTION
# =========================================================

def discover_x_channel():

    log.info(
        "Connecting to Buffer..."
    )

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
            "No Buffer organization found"
        )

    # Automatically select the first organization.

    organization = organizations[0]

    log.info(
        "Buffer organization: %s",
        organization["name"]
    )

    # JSON string escaping makes this safe to insert
    # into the GraphQL query.

    organization_id = json.dumps(
        organization["id"]
    )

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

    channel_data = buffer_request(
        channels_query
    )

    channels = channel_data.get(
        "channels", []
    )

    x_channels = [

        channel for channel in channels

        if channel.get(
            "service", ""
        ).lower() == "twitter"

    ]

    if not x_channels:

        raise RuntimeError(
            "No X channel found in your Buffer organization"
        )

    if len(x_channels) > 1:

        raise RuntimeError(
            "Multiple X channels found. "
            "Please check your Buffer organization."
        )

    channel = x_channels[0]

    if channel.get("isQueuePaused"):

        raise RuntimeError(
            "Your Buffer X queue is paused"
        )

    log.info(
        "Connected X channel: %s",
        channel.get("displayName") or channel.get("name")
    )

    return channel["id"]


# =========================================================
# 11. PUBLISH THREAD TO BUFFER
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

            "mode": "addToQueue",

            "metadata": {

                "twitter": {

                    "thread": thread_items

                }

            }

        }

    }

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
        data.get("data", {}).get(
            "createPost", {}
        )
    )

    if result.get("message"):

        raise RuntimeError(
            result["message"]
        )

    post = result.get("post")

    if not post or not post.get("id"):

        raise RuntimeError(
            f"Buffer did not confirm submission: {data}"
        )

    return post


# =========================================================
# 12. MAIN EXECUTION
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate preview without Buffer publishing"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate and republish today's thread"
    )

    args = parser.parse_args()

    history = load_history()

    # Duplicate protection.

    if not args.force:

        if history.get("status") == "submitted_to_buffer":

            log.info(
                "Today's thread already submitted."
            )

            return

        if history.get("status") == "publishing":

            raise RuntimeError(
                "Previous publishing attempt unresolved. "
                "Check Buffer before using --force."
            )

    log.info(
        "Starting Daily Famous Indian Numerology"
    )

    log.info(
        "Date: %s",
        TODAY
    )

    log.info(
        "Forecast year: %s",
        FORECAST_YEAR
    )

    # STEP 1: BIRTHDAY RESEARCH

    people = discover_people()

    if not people:

        history["status"] = "no_verified_people"
        history["people"] = []

        save_history(history)

        log.info(
            "No qualifying birthdays found today."
        )

        return

    # STEP 2: NUMEROLOGY ANALYSIS

    posts = generate_thread(people)

    # STEP 3: SAVE RESEARCH AND CONTENT

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

        print("\n" + "=" * 60)
        print("DAILY FAMOUS INDIAN NUMEROLOGY")
        print("PREVIEW - NOT PUBLISHED")
        print("=" * 60)

        for index, post in enumerate(
            posts,
            start=1
        ):

            print(
                f"\nPOST {index} "
                f"({len(post)} characters)"
            )

            print(post)

        print("\n" + "=" * 60)

        log.info(
            "Preview completed successfully."
        )

        return

    # STEP 5: BUFFER CHANNEL DETECTION

    channel_id = discover_x_channel()

    # STEP 6: MARK PUBLISHING

    history["status"] = "publishing"

    save_history(history)

    # STEP 7: BUFFER SUBMISSION

    result = publish_thread(
        posts,
        channel_id
    )

    # STEP 8: CONFIRMATION

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
        "Total thread posts: %s",
        len(posts)
    )


# =========================================================
# 13. ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        main()

    except Exception:

        log.exception(
            "Daily numerology execution failed"
        )

        raise
