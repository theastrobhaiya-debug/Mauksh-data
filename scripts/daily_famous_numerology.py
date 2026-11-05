

import os

import sys

import json

import re

import argparse

import requests

from pathlib import Path

from datetime import datetime

from zoneinfo import ZoneInfo

from openai import OpenAI

# =========================================================

# SETTINGS

# =========================================================

TZ = ZoneInfo("Asia/Kolkata")

TODAY = datetime.now(TZ).date()

TODAY_STR = TODAY.isoformat()

FORECAST_YEAR = TODAY.year + 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-5-mini"

BUFFER_TOKEN = os.getenv("BUFFER_X_ACCESS_TOKEN", "").strip()

BUFFER_API_URL = "https://api.buffer.com"

MAX_POST_LENGTH = 275

TARGET_POST_LENGTH = 240

BASE_DIR = Path(__file__).resolve().parent.parent

HISTORY_DIR = BASE_DIR / "data" / "famous_numerology"

HISTORY_FILE = HISTORY_DIR / f"{TODAY_STR}.json"

HISTORY_DIR.mkdir(parents=True, exist_ok=True)

if not OPENAI_API_KEY:

    raise RuntimeError("OPENAI_API_KEY is missing.")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================================================

# BASIC FUNCTIONS

# =========================================================

def log(message):

    print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] {message}")

def clean_text(text):

    text = str(text or "")

    text = text.replace("\n", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()

def load_history():

    if not HISTORY_FILE.exists():

        return {}

    try:

        return json.loads(

            HISTORY_FILE.read_text(encoding="utf-8")

        )

    except Exception:

        return {}

def save_history(history):

    HISTORY_FILE.write_text(

        json.dumps(history, indent=2, ensure_ascii=False),

        encoding="utf-8"

    )

def extract_json(text):

    text = str(text or "").strip()

    text = re.sub(

        r"^```(?:json)?\s*",

        "",

        text,

        flags=re.IGNORECASE

    )

    text = re.sub(r"\s*```$", "", text)

    try:

        return json.loads(text)

    except json.JSONDecodeError:

        pass

    start = text.find("{")

    end = text.rfind("}")

    if start != -1 and end > start:

        return json.loads(text[start:end + 1])

    raise ValueError("Could not read JSON returned by OpenAI.")

# =========================================================

# NUMEROLOGY CALCULATIONS

# =========================================================

def digit_sum(number):

    return sum(int(x) for x in str(number))

def reduce_number(number):

    while number > 9:

        number = digit_sum(number)

    return number

def calculate_numerology(day, month, year):

    mulank_compound = day

    mulank_reduced = reduce_number(mulank_compound)

    dob = f"{day:02d}{month:02d}{year}"

    bhagyank_compound = digit_sum(dob)

    bhagyank_reduced = reduce_number(bhagyank_compound)

    personal_year = f"{day:02d}{month:02d}{FORECAST_YEAR}"

    personal_year_compound = digit_sum(personal_year)

    personal_year_reduced = reduce_number(personal_year_compound)

    return {

        "mulank_compound": mulank_compound,

        "mulank_reduced": mulank_reduced,

        "bhagyank_compound": bhagyank_compound,

        "bhagyank_reduced": bhagyank_reduced,

        "personal_year_compound": personal_year_compound,

        "personal_year_reduced": personal_year_reduced

    }

# =========================================================

# OPENAI

# =========================================================

def ask_openai(prompt, use_web_search=False):

    params = {

        "model": OPENAI_MODEL,

        "input": prompt

    }

    if use_web_search:

        params["tools"] = [

            {"type": "web_search"}

        ]

    else:

        params["text"] = {

            "format": {

                "type": "json_object"

            }

        }

    response = client.responses.create(**params)

    return response.output_text

# =========================================================

# FIND TODAY'S BIRTHDAYS

# =========================================================

def research_people():

    prompt = f"""

Today's date in India is {TODAY_STR}.

Find famous Indian personalities whose birthday is today.

I want people from different fields, such as sports,

business, cinema, literature, science, public life and arts.

Follow these rules carefully:

1. Include only Indian personalities.

2. Include only people who are alive today.

3. Their birthday must match today's exact day and month.

4. Verify their date of birth through reliable sources.

5. Use at least two independent sources for each person.

6. Verify that each person is currently alive.

7. Prefer established newspapers, official websites,

   institutions and reliable biographies.

8. Do not depend only on Wikipedia.

9. Do not guess dates or achievements.

10. Do not include someone if their birth date or

    living status cannot be verified.

11. Avoid including several people from the same field

    when there are other suitable personalities.

Return valid JSON in this format:

{{

  "people": [

    {{

      "name": "Full name",

      "date_of_birth": "YYYY-MM-DD",

      "profession": "Profession",

      "verified_alive": true,

      "life_summary": "Short factual summary of their career.",

      "notable_facts": [

        "Verified achievement or milestone",

        "Another verified achievement"

      ],

      "sources": [

        {{

          "title": "Source title",

          "url": "https://example.com",

          "supports": "What this source confirms"

        }},

        {{

          "title": "Second source",

          "url": "https://example.com",

          "supports": "What this source confirms"

        }}

      ]

    }}

  ]

}}

If nobody can be verified, return an empty people array.

Do not invent information.

"""

    log("Checking today's birthdays...")

    raw = ask_openai(prompt, use_web_search=True)

    data = extract_json(raw)

    people = data.get("people", [])

    verified = []

    seen = set()

    for person in people:

        try:

            dob = datetime.strptime(

                person["date_of_birth"],

                "%Y-%m-%d"

            ).date()

            if dob.day != TODAY.day or dob.month != TODAY.month:

                continue

            if dob >= TODAY:

                continue

            if not person.get("verified_alive"):

                continue

            sources = person.get("sources", [])

            valid_sources = [

                source for source in sources

                if str(source.get("url", "")).startswith("https://")

            ]

            if len(valid_sources) < 2:

                continue

            name = clean_text(person.get("name"))

            if not name:

                continue

            if name.lower() in seen:

                continue

            seen.add(name.lower())

            person["name"] = name

            person["sources"] = valid_sources

            person["date_of_birth"] = dob.isoformat()

            verified.append(person)

        except (ValueError, TypeError, KeyError):

            continue

    log(f"Found {len(verified)} verified personalities.")

    return verified

# =========================================================

# WRITE FIVE POSTS FOR EACH PERSON

# =========================================================

def create_posts(person, numbers):

    prompt = f"""

Write a natural five-post X thread about this person.

Name: {person["name"]}

Profession: {person.get("profession", "")}

Date of birth: {person["date_of_birth"]}

Career summary:

{person.get("life_summary", "")}

Verified facts:

{json.dumps(person.get("notable_facts", []), ensure_ascii=False)}

Numerology values:

{json.dumps(numbers)}

The thread must have exactly five posts in this order.

POST 1 - BIRTHDAY WISH

Wish the person a happy birthday first.

Mention their name and profession.

Make it warm and personal, not generic.

POST 2 - MULANK

Explain their Mulank.

Include the compound and reduced number.

Give a short traditional numerology interpretation.

POST 3 - BHAGYANK

Explain their Bhagyank.

Include the compound and reduced number.

Give a short traditional numerology interpretation.

POST 4 - LIFE AND CAREER

Connect their documented life and career to the

numerological interpretation.

Use real achievements or career milestones.

Explain the connection thoughtfully.

Do not claim numerology caused their achievements.

POST 5 - PERSONAL YEAR

Explain their Personal Year for {FORECAST_YEAR}.

Include the compound and reduced number.

Give a short traditional interpretation.

WRITING STYLE:

Write like a person sharing an interesting observation,

not like an automated numerology report.

Keep the language simple and conversational.

Use natural sentence structures.

Avoid unnecessary introductions.

Avoid repeating the same phrases in every post.

Do not make every post sound like a definition.

Do not use headings such as "Mulank Analysis".

Do not use emojis, hashtags or decorative symbols.

Do not use marketing language.

Do not mention The Astro Bhaiya.

Do not call the person a celebrity.

Keep each post around 200 to 230 characters.

Never exceed 275 characters.

Numerology is a traditional interpretive system.

Do not present it as scientifically proven.

Return only JSON:

{{

  "posts": [

    "Birthday wish",

    "Mulank post",

    "Bhagyank post",

    "Life and career analysis",

    "Personal Year post"

  ]

}}

"""

    raw = ask_openai(prompt)

    data = extract_json(raw)

    posts = data.get("posts", [])

    if len(posts) != 5:

        raise ValueError(

            f"{person['name']}: expected exactly five posts."

        )

    posts = [clean_text(post) for post in posts]

    if any(len(post) > TARGET_POST_LENGTH for post in posts):

        posts = shorten_posts(

            posts,

            person["name"],

            numbers

        )

    if any(len(post) > MAX_POST_LENGTH for post in posts):

        posts = shorten_posts(

            posts,

            person["name"],

            numbers

        )

    for index, post in enumerate(posts, start=1):

        if not post:

            raise ValueError(

                f"{person['name']}: post {index} is empty."

            )

        if len(post) > MAX_POST_LENGTH:

            raise ValueError(

                f"{person['name']}: post {index} exceeds "

                f"{MAX_POST_LENGTH} characters."

            )

    return posts

# =========================================================

# SHORTEN LONG POSTS

# =========================================================

def shorten_posts(posts, name, numbers):

    prompt = f"""

Make these five X posts shorter and more natural.

Person: {name}

Do not change these numerology values:

{json.dumps(numbers)}

Posts:

{json.dumps(posts, ensure_ascii=False)}

Rules:

- Return exactly five posts.

- Keep the same order.

- Preserve all numbers exactly.

- Preserve the person's name.

- Do not add facts.

- Keep the career analysis meaningful.

- Use simple, natural language.

- No hashtags or emojis.

- Target 220 characters per post.

- Never exceed 275 characters.

Return JSON:

{{

  "posts": [

    "Post 1",

    "Post 2",

    "Post 3",

    "Post 4",

    "Post 5"

  ]

}}

"""

    raw = ask_openai(prompt)

    data = extract_json(raw)

    result = data.get("posts", [])

    if len(result) != 5:

        raise ValueError("Could not shorten the five posts.")

    return [clean_text(post) for post in result]

# =========================================================

# CREATE ALL THREADS

# =========================================================

def generate_threads(people):

    threads = []

    for person in people:

        dob = datetime.strptime(

            person["date_of_birth"],

            "%Y-%m-%d"

        ).date()

        numbers = calculate_numerology(

            dob.day,

            dob.month,

            dob.year

        )

        log(f"Writing posts for {person['name']}...")

        posts = create_posts(person, numbers)

        threads.append({

            "name": person["name"],

            "profession": person.get("profession", ""),

            "date_of_birth": person["date_of_birth"],

            "numerology": numbers,

            "posts": posts,

            "sources": person.get("sources", [])

        })

    return threads

# =========================================================

# BUFFER CONNECTION

# =========================================================

def buffer_request(query):

    if not BUFFER_TOKEN:

        raise RuntimeError(

            "BUFFER_X_ACCESS_TOKEN is missing."

        )

    response = requests.post(

        BUFFER_API_URL,

        headers={

            "Authorization": f"Bearer {BUFFER_TOKEN}",

            "Content-Type": "application/json"

        },

        json={"query": query},

        timeout=45

    )

    response.raise_for_status()

    result = response.json()

    if result.get("errors"):

        raise RuntimeError(

            json.dumps(result["errors"], ensure_ascii=False)

        )

    return result.get("data", {})

# =========================================================

# FIND THE X CHANNEL

# =========================================================

def get_buffer_channel():

    log("Finding your Buffer X channel...")

    query = """

    query {

      account {

        organizations {

          id

          name

        }

      }

    }

    """

    data = buffer_request(query)

    organizations = (

        data.get("account", {}).get("organizations", [])

    )

    if not organizations:

        raise RuntimeError("No Buffer organization found.")

    x_channels = []

    for organization in organizations:

        organization_id = json.dumps(organization["id"])

        channel_query = f"""

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

        channel_data = buffer_request(channel_query)

        for channel in channel_data.get("channels", []):

            service = str(

                channel.get("service", "")

            ).lower()

            if service in ("twitter", "x"):

                x_channels.append(channel)

    if not x_channels:

        raise RuntimeError("No X channel found in Buffer.")

    if len(x_channels) > 1:

        raise RuntimeError(

            "More than one X channel found. "

            "Please select the intended channel."

        )

    channel = x_channels[0]

    log(

        "Using channel: "

        + str(

            channel.get("displayName")

            or channel.get("name")

            or channel["id"]

        )

    )

    return channel["id"]

# =========================================================

# SEND ONE THREAD TO BUFFER

# =========================================================

def publish_thread(posts, channel_id):

    if len(posts) != 5:

        raise ValueError("A thread must contain five posts.")

    if any(len(post) > MAX_POST_LENGTH for post in posts):

        raise ValueError("A post exceeds the character limit.")

    first_post = json.dumps(

        posts[0],

        ensure_ascii=False

    )

    channel_value = json.dumps(channel_id)

    thread_items = ", ".join(

        "{ text: " + json.dumps(

            post,

            ensure_ascii=False

        ) + " }"

        for post in posts

    )

    mutation = f"""

    mutation {{

      createPost(input: {{

        text: {first_post}

        channelId: {channel_value}

        schedulingType: automatic

        mode: shareNow

        metadata: {{

          twitter: {{

            thread: [{thread_items}]

          }}

        }}

      }}) {{

        ... on PostActionSuccess {{

          post {{

            id

            text

            status

            dueAt

          }}

        }}

        ... on MutationError {{

          message

        }}

      }}

    }}

    """

    data = buffer_request(mutation)

    result = data.get("createPost", {})

    if result.get("message"):

        raise RuntimeError(result["message"])

    post = result.get("post")

    if not post:

        raise RuntimeError(

            "Buffer did not confirm the post creation: "

            + json.dumps(result)

        )

    return post

# =========================================================

# PREVIEW

# =========================================================

def show_preview(threads):

    print("\n")

    print("=" * 55)

    print("DAILY FAMOUS INDIAN NUMEROLOGY")

    print(TODAY_STR)

    print("=" * 55)

    for thread in threads:

        print("\n")

        print("-" * 55)

        print(thread["name"])

        print(thread["profession"])

        print("-" * 55)

        for index, post in enumerate(thread["posts"], start=1):

            print(f"\nPost {index}")

            print(post)

            print(f"{len(post)} characters")

    print("\n")

    print("People:", len(threads))

    print("Threads:", len(threads))

    print("Total posts:", len(threads) * 5)

# =========================================================

# MAIN

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

    if not args.force and history.get("status") in (

        "submitted_to_buffer",

        "publishing",

        "partial_failure"

    ):

        log(

            "Today's run has already been submitted or "

            "was interrupted."

        )

        log(

            "Check Buffer before using --force to avoid duplicates."

        )

        return

    # Find and verify today's birthdays.

    people = research_people()

    if not people:

        log("No verified birthdays found today.")

        save_history({

            "date": TODAY_STR,

            "status": "no_verified_birthdays",

            "people": [],

            "threads": []

        })

        return

    # Generate a separate five-post thread for each person.

    threads = generate_threads(people)

    if not threads:

        raise RuntimeError("No threads could be generated.")

    show_preview(threads)

    history = {

        "date": TODAY_STR,

        "status": "preview_generated",

        "people": [thread["name"] for thread in threads],

        "threads": threads,

        "published_threads": []

    }

    save_history(history)

    if args.preview:

        log("Preview completed. Nothing was sent to Buffer.")

        return

    # Connect to Buffer only when publishing.

    channel_id = get_buffer_channel()

    history["status"] = "publishing"

    history["buffer_channel_id"] = channel_id

    save_history(history)

    # Submit each person's thread separately.

    for index, thread in enumerate(threads, start=1):

        log(

            f"Submitting {index}/{len(threads)}: "

            f"{thread['name']}"

        )

        try:

            result = publish_thread(

                thread["posts"],

                channel_id

            )

            record = {

                "name": thread["name"],

                "buffer_post_id": result.get("id"),

                "buffer_status": result.get("status"),

                "due_at": result.get("dueAt"),

                "submission_status": "submitted"

            }

            history["published_threads"].append(record)

            save_history(history)

            log(

                f"Buffer accepted the thread for "

                f"{thread['name']}."

            )

            log(f"Buffer post ID: {result.get('id')}")

        except Exception as error:

            history["status"] = "partial_failure"

            history["error"] = str(error)

            save_history(history)

            log(

                f"Publishing stopped at {thread['name']}: {error}"

            )

            log(

                "Check Buffer before retrying. "

                "The previous submission may have reached Buffer."

            )

            raise

    history["status"] = "submitted_to_buffer"

    history["completed_at"] = datetime.now(TZ).isoformat()

    save_history(history)

    log("All individual threads have been submitted to Buffer.")

    log("Publishing was requested using Share Now.")

if __name__ == "__main__":

    main()