

import os

import json

import re

import hashlib

from pathlib import Path

from datetime import datetime

from zoneinfo import ZoneInfo

import requests

from openai import OpenAI

# =========================================================

# MAUKSH — DAILY FAMOUS PERSONALITY NUMEROLOGY

# Editorial Edition

# =========================================================

TZ = ZoneInfo("Asia/Kolkata")

TODAY = datetime.now(TZ).date()

FORECAST_YEAR = TODAY.year + 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

BUFFER_TOKEN = (

    os.getenv("BUFFER_X_ACCESS_TOKEN")

    or os.getenv("BUFFER_ACCESS_TOKEN")

)

BUFFER_X_CHANNEL_NAME = os.getenv("BUFFER_X_CHANNEL_NAME", "")

BUFFER_API = "https://api.buffer.com"

HISTORY_DIR = Path("data/famous_numerology")

HISTORY_FILE = HISTORY_DIR / f"{TODAY.isoformat()}.json"

MAX_PEOPLE = 4

MAX_POSTS = 3

MAX_CHARS = 275

SUCCESS_STATUSES = {

    "submitted_to_buffer",

    "published",

    "sent",

    "scheduled"

}

if not OPENAI_API_KEY:

    raise RuntimeError("OPENAI_API_KEY missing")

if not BUFFER_TOKEN:

    raise RuntimeError("BUFFER_X_ACCESS_TOKEN missing")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================================================

# HISTORY

# =========================================================

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

    except Exception as e:

        raise RuntimeError(f"Cannot read history: {e}")

def save_history(history):

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    temp = HISTORY_FILE.with_suffix(".tmp")

    with open(temp, "w", encoding="utf-8") as f:

        json.dump(history, f, indent=2, ensure_ascii=False)

    temp.replace(HISTORY_FILE)

def person_key(person):

    raw = (

        person["name"].strip().lower()

        + "|"

        + person["dob"]

    )

    return hashlib.sha256(

        raw.encode("utf-8")

    ).hexdigest()[:16]

# =========================================================

# OPENAI JSON EXTRACTION

# =========================================================

def extract_json(output):

    output = output.strip()

    output = re.sub(

        r"^```(?:json)?\s*|\s*```$",

        "",

        output,

        flags=re.IGNORECASE

    )

    return json.loads(output)

# =========================================================

# BUFFER GRAPHQL

# =========================================================

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

        timeout=45

    )

    response.raise_for_status()

    result = response.json()

    if result.get("errors"):

        raise RuntimeError(

            json.dumps(result["errors"], ensure_ascii=False)

        )

    return result.get("data", {})

def get_x_channel():

    organization_query = """

    query {

        account {

            organizations {

                id

                name

            }

        }

    }

    """

    data = buffer_request(organization_query)

    organizations = (

        data.get("account", {}).get("organizations", [])

    )

    if not organizations:

        raise RuntimeError("No Buffer organization found")

    channel_query = """

    query GetChannels($organizationId: OrganizationId!) {

        channels(input: {organizationId: $organizationId}) {

            id

            name

            displayName

            service

            isLocked

        }

    }

    """

    channels = []

    for organization in organizations:

        result = buffer_request(

            channel_query,

            {"organizationId": organization["id"]}

        )

        channels.extend(result.get("channels", []))

    x_channels = [

        c for c in channels

        if (c.get("service") or "").lower() in (

            "twitter", "x"

        )

        and not c.get("isLocked", False)

    ]

    if BUFFER_X_CHANNEL_NAME:

        matching = [

            c for c in x_channels

            if BUFFER_X_CHANNEL_NAME.lower()

            in (

                (c.get("name") or "")

                + " "

                + (c.get("displayName") or "")

            ).lower()

        ]

        x_channels = matching

    if not x_channels:

        raise RuntimeError("No matching X channel found in Buffer")

    if len(x_channels) > 1:

        raise RuntimeError(

            "Multiple X channels found. Set BUFFER_X_CHANNEL_NAME."

        )

    channel = x_channels[0]

    print(

        "Buffer channel:",

        channel.get("displayName") or channel.get("name")

    )

    return channel["id"]

# =========================================================

# BIRTHDAY RESEARCH

# =========================================================

def research_birthdays():

    prompt = f"""

You are a professional research assistant for MAUKSH.

Find up to {MAX_PEOPLE} famous Indian personalities

whose birthday is today.

TODAY: {TODAY.strftime("%d %B %Y")}

STRICT REQUIREMENTS:

1. Only living people.

2. Only Indian personalities.

3. Must be genuinely famous and publicly recognised.

4. Exact date of birth must be verified.

5. Birthday must match today's day and month.

6. Use at least TWO independent reliable sources.

7. Prefer official biographies and established publications.

8. Do not guess dates of birth.

9. Do not include deceased personalities.

10. Do not invent achievements.

11. Exclude people whose living status cannot be verified.

12. Return an empty list if no suitable people are found.

Include a variety of fields where possible:

sports, business, entertainment, literature and public life.

Return ONLY JSON:

{{

  "people": [

    {{

      "name": "Full name",

      "dob": "YYYY-MM-DD",

      "profession": "Profession",

      "known_for": "Short description",

      "career_milestones": [

        "Verified achievement",

        "Verified achievement"

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

"""

    response = client.responses.create(

        model=OPENAI_MODEL,

        tools=[{"type": "web_search"}],

        input=prompt

    )

    result = extract_json(response.output_text)

    verified = []

    seen = set()

    for person in result.get("people", []):

        try:

            dob = datetime.strptime(

                person["dob"], "%Y-%m-%d"

            ).date()

        except (ValueError, KeyError, TypeError):

            continue

        if (dob.day, dob.month) != (TODAY.day, TODAY.month):

            continue

        if dob > TODAY:

            continue

        if person.get("alive_verified") is not True:

            continue

        sources = person.get("sources", [])

        valid_sources = [

            s for s in sources

            if isinstance(s, dict)

            and s.get("title")

            and s.get("url", "").startswith("https://")

        ]

        if len(valid_sources) < 2:

            continue

        if not person.get("career_milestones"):

            continue

        name = person.get("name", "").strip()

        if not name or name.lower() in seen:

            continue

        seen.add(name.lower())

        person["sources"] = valid_sources[:3]

        verified.append(person)

    return verified[:MAX_PEOPLE]

# =========================================================

# NUMEROLOGY

# =========================================================

def reduce_number(number):

    while number > 9:

        number = sum(int(x) for x in str(number))

    return number

def calculate_mulank(dob):

    return reduce_number(dob.day)

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

        sum(int(x) for x in str(dob.day))

        + sum(int(x) for x in str(dob.month))

        + sum(int(x) for x in str(year))

    )

    return reduce_number(total)

def get_numbers(person):

    dob = datetime.strptime(

        person["dob"], "%Y-%m-%d"

    ).date()

    bhagyank = calculate_bhagyank(dob)

    return {

        "mulank": calculate_mulank(dob),

        "bhagyank_compound": bhagyank["compound"],

        "bhagyank_reduced": bhagyank["reduced"],

        "personal_year": calculate_personal_year(

            dob, FORECAST_YEAR

        ),

        "forecast_year": FORECAST_YEAR

    }

# =========================================================

# EDITORIAL THREAD GENERATION

# =========================================================

def generate_thread(person):

    numbers = get_numbers(person)

    prompt = f"""

You are the senior editorial writer of MAUKSH.

Create an intelligent, premium, minimal birthday

numerology thread for X.

PERSON:

{json.dumps(person, ensure_ascii=False)}

CALCULATED NUMBERS:

{json.dumps(numbers)}

TODAY:

{TODAY.strftime("%d %B %Y")}

EXACTLY THREE POSTS.

POST 1 — BIRTHDAY AND MULANK

Start exactly with:

Happy Birthday, {person['name']}!

Explain their Mulank and its traditional association.

Make the opening interesting and personal.

POST 2 — BHAGYANK AND LIFE JOURNEY

Explain their Bhagyank and compound number.

Connect its traditional numerological interpretation

to one or two actual career milestones.

Do not claim numerology caused their achievements.

POST 3 — UPCOMING PERSONAL YEAR

Explain their personal year for {FORECAST_YEAR}.

Describe the traditional themes associated with the number.

Offer a thoughtful interpretation without guaranteed predictions.

WRITING STYLE:

- Editorial magazine style.

- Short, elegant paragraphs.

- Natural English.

- Minimal and sophisticated.

- No emojis.

- No hashtags.

- No decorative characters.

- No unnecessary headings.

- No repetitive disclaimers.

- No generic AI phrases.

- No clickbait.

- No exaggerated claims.

- No forced connections.

- No fabricated facts.

- Do not repeat the birthday greeting.

- No source URLs in posts.

- Maximum {MAX_CHARS} characters per post.

- Explain numerology as a traditional interpretive system.

- Each post should provide a distinct piece of information.

Do not change the supplied calculations.

Return ONLY JSON:

{{

  "posts": [

    "Post one",

    "Post two",

    "Post three"

  ]

}}

"""

    response = client.responses.create(

        model=OPENAI_MODEL,

        input=prompt

    )

    result = extract_json(response.output_text)

    posts = result.get("posts", [])

    if len(posts) != MAX_POSTS:

        raise ValueError("Thread must contain exactly 3 posts")

    for index, post in enumerate(posts):

        post = post.strip()

        if not post:

            raise ValueError("Empty post generated")

        if len(post) > MAX_CHARS:

            raise ValueError(

                f"Post {index + 1} exceeds {MAX_CHARS} characters"

            )

        if index == 0 and not post.startswith(

            f"Happy Birthday, {person['name']}!"

        ):

            raise ValueError("Birthday greeting missing")

        posts[index] = post

    return {

        "posts": posts,

        "numbers": numbers

    }

# =========================================================

# PUBLISH THREAD THROUGH BUFFER

# =========================================================

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

            "mode": "shareNow",

            "metadata": {

                "twitter": {

                    "thread": [

                        {"text": p} for p in posts

                    ]

                }

            }

        }

    }

    data = buffer_request(mutation, variables)

    action = data.get("createPost", {})

    post = action.get("post")

    if not post or not post.get("id"):

        raise RuntimeError(

            "Buffer did not confirm publishing: "

            + json.dumps(action)

        )

    return post

# =========================================================

# MAIN

# =========================================================

def main():

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--preview", action="store_true")

    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    print("=" * 55)

    print("MAUKSH BIRTHDAY NUMEROLOGY")

    print("EDITORIAL EDITION")

    print("=" * 55)

    print("Date:", TODAY)

    print("Forecast:", FORECAST_YEAR)

    print("Model:", OPENAI_MODEL)

    history = load_history()

    print("\nResearching today's birthdays...")

    people = research_birthdays()

    if not people:

        print("No verified birthdays found.")

        history["last_run_status"] = "no_verified_people"

        save_history(history)

        return

    print("Found:", len(people))

    channel_id = None

    for person in people:

        name = person["name"]

        key = person_key(person)

        previous = history["people"].get(key, {})

        previous_status = previous.get("status")

        if previous_status == "publishing" and not args.force:

            print(

                f"SKIPPING {name}: Previous publishing attempt "

                "has an uncertain outcome. Check Buffer manually."

            )

            continue

        if previous_status in SUCCESS_STATUSES and not args.force:

            print(f"Already processed: {name}")

            continue

        print("\n" + "-" * 50)

        print(name)

        print(person["dob"])

        try:

            generated = generate_thread(person)

            posts = generated["posts"]

            print("\nNUMEROLOGY")

            print(json.dumps(

                generated["numbers"],

                indent=2

            ))

            for i, post in enumerate(posts, 1):

                print(f"\nPOST {i} ({len(post)} characters)")

                print(post)

            if args.preview:

                history["people"][key] = {

                    "name": name,

                    "dob": person["dob"],

                    "status": "preview_generated",

                    "posts": posts,

                    "numbers": generated["numbers"],

                    "sources": person["sources"]

                }

                save_history(history)

                print("\nPREVIEW ONLY")

                continue

            if channel_id is None:

                channel_id = get_x_channel()

            # Save pending state before API submission.

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

            print("\nSUCCESS:", name)

            print("Buffer ID:", result["id"])

        except Exception as e:

            print("\nERROR:", name, str(e))

            history["people"][key] = {

                "name": name,

                "dob": person["dob"],

                "status": "failed",

                "error": str(e)

            }

            save_history(history)

    history["last_run_status"] = "completed"

    history["last_run_at"] = datetime.now(TZ).isoformat()

    save_history(history)

    print("\nMAUKSH AUTOMATION COMPLETE")

if __name__ == "__main__":

    main()