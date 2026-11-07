
import os
import re
import json
import argparse
import requests

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI


# SETTINGS

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

client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=240.0,
    max_retries=2
)


# BASIC FUNCTIONS

def log(message):
    print(
        f"[{datetime.now(TZ).strftime('%H:%M:%S')}] {message}",
        flush=True
    )


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

    if not text:
        raise ValueError("OpenAI returned an empty response.")

    # Remove Markdown fences
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"\s*```$", "", text)

    # First try direct JSON parsing
    try:
        result = json.loads(text)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    # Search for a valid JSON object inside surrounding text
    decoder = json.JSONDecoder()

    for index, character in enumerate(text):

        if character != "{":
            continue

        try:
            result, end = decoder.raw_decode(text[index:])

            if isinstance(result, dict):
                return result

        except json.JSONDecodeError:
            continue

    log("JSON parsing failed. Original response follows:")
    log(text[:12000])

    raise ValueError("OpenAI did not return valid JSON.")


# NUMEROLOGY

def digit_sum(number):
    return sum(int(x) for x in str(number))


def reduce_number(number):
    while number > 9:
        number = digit_sum(number)

    return number


def calculate_numerology(day, month, year):

    mulank_compound = day
    mulank_reduced = reduce_number(day)

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


# OPENAI

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

    log(
        "Waiting for OpenAI. "
        + (
            "Live birthday research is running..."
            if use_web_search
            else "Generating content..."
        )
    )

    response = client.responses.create(**params)

    log("OpenAI response received.")

    return response.output_text


# JSON RECOVERY FOR RESEARCH

def normalize_research_json(raw):

    log("Converting birthday research into structured JSON...")

    prompt = """
Convert the following birthday research into valid JSON.

Return exactly this structure:

{
  "people": [
    {
      "name": "Full name",
      "date_of_birth": "YYYY-MM-DD",
      "profession": "Profession",
      "verified_alive": true,
      "life_summary": "Factual career summary",
      "notable_facts": [
        "Verified achievement"
      ],
      "sources": [
        {
          "title": "Source title",
          "url": "https://example.com",
          "supports": "What it verifies"
        }
      ]
    }
  ]
}

STRICT RULES:

1. Use only information in the research provided.
2. Never invent names, dates, achievements or URLs.
3. Keep only Indian personalities.
4. Keep only people explicitly identified as living.
5. Preserve source URLs exactly.
6. Do not manufacture a second source.
7. If information is insufficient, exclude that person.
8. If no person qualifies, return an empty people array.
9. Return JSON only.

Research to convert:
""" + json.dumps(raw[:30000], ensure_ascii=False)

    result = ask_openai(prompt)

    data = extract_json(result)

    if not isinstance(data.get("people"), list):
        raise ValueError(
            "Normalized research does not contain a people array."
        )

    log("Research successfully converted into JSON.")

    return data


# BIRTHDAY RESEARCH

def research_people():

    prompt = f"""
Today's date in India is {TODAY_STR}.

Find famous Indian personalities whose birthday is today.

Include people from sports, business, cinema,
literature, science, public life and arts.

STRICT RULES:

1. Include only Indian personalities.
2. Include only people currently alive.
3. Their day and month of birth must match today.
4. Verify their birth date using at least two
   independent reliable sources.
5. Verify their current living status.
6. Prefer official websites, established newspapers,
   institutions and reputable biographies.
7. Do not rely only on Wikipedia.
8. Never invent dates or achievements.
9. Do not include uncertain birthdays.
10. Prioritise people with documented careers.

Return JSON in this format:

{{
  "people": [
    {{
      "name": "Full name",
      "date_of_birth": "YYYY-MM-DD",
      "profession": "Profession",
      "verified_alive": true,
      "life_summary": "Factual career summary",
      "notable_facts": [
        "Verified achievement",
        "Another verified achievement"
      ],
      "sources": [
        {{
          "title": "Source title",
          "url": "https://example.com",
          "supports": "What it verifies"
        }},
        {{
          "title": "Second source",
          "url": "https://example.com",
          "supports": "What it verifies"
        }}
      ]
    }}
  ]
}}

Return an empty people array if nobody can be verified.
Do not guess.
"""

    log("Starting birthday research...")

    raw = ask_openai(prompt, use_web_search=True)

    # First attempt: parse the research response directly.
    try:

        data = extract_json(raw)

    except ValueError:

        # Second attempt: convert research into JSON.
        log("Direct JSON extraction failed. Starting recovery.")

        data = normalize_research_json(raw)

    people = data.get("people", [])

    if not isinstance(people, list):
        raise ValueError("Invalid people data returned by OpenAI.")

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

            if person.get("verified_alive") is not True:
                continue

            sources = person.get("sources", [])

            valid_sources = [
                source for source in sources
                if isinstance(source, dict)
                and str(source.get("url", "")).startswith("https://")
                and source.get("title")
                and source.get("supports")
            ]

            # Require two distinct source URLs.
            unique_urls = {
                source["url"]
                for source in valid_sources
            }

            if len(unique_urls) < 2:
                continue

            name = clean_text(person.get("name"))

            if not name or name.lower() in seen:
                continue

            seen.add(name.lower())

            person["name"] = name
            person["date_of_birth"] = dob.isoformat()
            person["sources"] = valid_sources

            verified.append(person)

        except (ValueError, TypeError, KeyError):
            continue

    log(
        f"Birthday research completed. "
        f"Found {len(verified)} people."
    )

    return verified


# SHORTEN POSTS

def shorten_posts(posts, name, numbers):

    prompt = f"""
Rewrite these five posts to make them shorter and natural.

Person: {name}

Exact numerology values:
{json.dumps(numbers)}

Existing posts:
{json.dumps(posts, ensure_ascii=False)}

Rules:
- Return exactly five posts.
- Keep the same order.
- Preserve all numerology values.
- Preserve the person's name.
- Do not add facts.
- Keep the career analysis meaningful.
- No hashtags or emojis.
- Aim for 220 characters per post.
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
    result = extract_json(raw).get("posts", [])

    if len(result) != 5:
        raise ValueError("Could not shorten the five posts.")

    return [clean_text(post) for post in result]


# WRITE FIVE POSTS FOR EACH PERSON

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

Numerology:
{json.dumps(numbers)}

Create exactly five posts in this order.

POST 1: BIRTHDAY WISH

Wish the person a happy birthday first.
Mention their name and profession.
Make it warm and personal.

POST 2: MULANK

Explain their Mulank.
Include the compound and reduced number.
Give a short traditional interpretation.

POST 3: BHAGYANK

Explain their Bhagyank.
Include the compound and reduced number.
Give a short traditional interpretation.

POST 4: LIFE AND CAREER

Connect their documented life and career
to the numerological interpretation.

Use real achievements and milestones.
Explain the connection thoughtfully.
Do not claim numerology caused their success.

POST 5: PERSONAL YEAR

Explain their Personal Year for {FORECAST_YEAR}.
Include the compound and reduced number.
Give a short traditional interpretation.

WRITING STYLE:

Write like a person sharing an interesting observation.

Use simple, conversational English.
Keep sentences short.
Avoid unnecessary introductions.
Avoid repeating the same phrases.
Do not make every post sound like a definition.
Do not use headings inside the posts.
No emojis, hashtags or decorative symbols.
No marketing language.
Do not mention The Astro Bhaiya.
Do not call the person a celebrity.

Aim for 200 to 230 characters per post.
Never exceed 275 characters.

Numerology is a traditional interpretive system,
not a scientifically proven explanation of success.

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

    log(f"Generating five posts for {person['name']}...")

    raw = ask_openai(prompt)
    posts = extract_json(raw).get("posts", [])

    if len(posts) != 5:
        raise ValueError(
            f"{person['name']}: expected exactly five posts."
        )

    posts = [clean_text(post) for post in posts]

    if any(len(post) > TARGET_POST_LENGTH for post in posts):
        log(f"Shortening posts for {person['name']}...")

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
                f"{person['name']}: post {index} has "
                f"{len(post)} characters."
            )

    return posts


# GENERATE THREADS

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


# BUFFER REQUEST

def buffer_request(query, label="Buffer request"):

    if not BUFFER_TOKEN:
        raise RuntimeError("BUFFER_X_ACCESS_TOKEN is missing.")

    log(f"{label}: sending request...")

    response = requests.post(
        BUFFER_API_URL,
        headers={
            "Authorization": f"Bearer {BUFFER_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"query": query},
        timeout=(15, 30)
    )

    log(f"{label}: HTTP {response.status_code}")

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(
            f"{label}: Buffer returned invalid JSON."
        )

    if result.get("errors"):
        raise RuntimeError(
            f"{label}: "
            + json.dumps(result["errors"], ensure_ascii=False)
        )

    return result.get("data", {})


# FIND BUFFER X CHANNEL

def get_buffer_channel():

    log("Connecting to Buffer account...")

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

    data = buffer_request(
        account_query,
        "Loading Buffer organizations"
    )

    organizations = (
        data.get("account", {}).get("organizations", [])
    )

    if not organizations:
        raise RuntimeError(
            "Buffer returned no organizations. "
            "Check your access token and account permissions."
        )

    log(f"Found {len(organizations)} Buffer organization(s).")

    x_channels = []

    for organization in organizations:

        organization_name = organization.get("name", "Unknown")

        log(f"Checking organization: {organization_name}")

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

        channel_data = buffer_request(
            channels_query,
            f"Loading channels for {organization_name}"
        )

        channels = channel_data.get("channels", [])

        log(f"Found {len(channels)} channel(s) in this organization.")

        for channel in channels:

            service = str(
                channel.get("service", "")
            ).lower()

            if service in ("twitter", "x"):
                x_channels.append(channel)

    if not x_channels:
        raise RuntimeError(
            "No X/Twitter channel was returned by Buffer. "
            "Check that your X account is connected to the "
            "same Buffer organization as your access token."
        )

    if len(x_channels) > 1:
        names = [
            channel.get("displayName")
            or channel.get("name")
            or channel["id"]
            for channel in x_channels
        ]

        raise RuntimeError(
            "Multiple X channels found: "
            + ", ".join(names)
            + ". A channel ID must be selected."
        )

    channel = x_channels[0]

    log(
        "X channel found: "
        + str(
            channel.get("displayName")
            or channel.get("name")
            or channel["id"]
        )
    )

    if channel.get("isQueuePaused"):
        log("Warning: Buffer reports that the channel queue is paused.")

    return channel["id"]


# PUBLISH ONE PERSON'S THREAD

def publish_thread(posts, channel_id):

    if len(posts) != 5:
        raise ValueError("A thread must contain exactly five posts.")

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

    data = buffer_request(
        mutation,
        "Submitting thread to Buffer"
    )

    result = data.get("createPost", {})

    if result.get("message"):
        raise RuntimeError(result["message"])

    post = result.get("post")

    if not post:
        raise RuntimeError(
            "Buffer did not return a created post: "
            + json.dumps(result, ensure_ascii=False)
        )

    return post


# PREVIEW

def show_preview(threads):

    print("\n")
    print("=" * 50)
    print("DAILY FAMOUS INDIAN NUMEROLOGY")
    print(TODAY_STR)
    print("=" * 50)

    for thread in threads:

        print("\n")
        print("-" * 50)
        print(thread["name"])
        print(thread["profession"])
        print("-" * 50)

        for index, post in enumerate(thread["posts"], start=1):

            print(f"\nPost {index}")
            print(post)
            print(f"{len(post)} characters")

    print("\n")
    print("People:", len(threads))
    print("Separate threads:", len(threads))
    print("Total posts:", len(threads) * 5)


# MAIN

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    history = load_history()

    if not args.force and history.get("status") in (
        "submitted_to_buffer",
        "publishing",
        "partial_failure"
    ):
        log("Today's run was already submitted or interrupted.")
        log("Check Buffer before using --force.")
        return

    log(f"Starting daily numerology for {TODAY_STR}.")

    people = research_people()

    if not people:

        log("No verified living Indian birthday personalities found.")

        save_history({
            "date": TODAY_STR,
            "status": "no_verified_birthdays",
            "people": [],
            "threads": []
        })

        return

    threads = generate_threads(people)

    if not threads:
        raise RuntimeError("No valid threads were generated.")

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

    channel_id = get_buffer_channel()

    history["status"] = "publishing"
    history["buffer_channel_id"] = channel_id
    save_history(history)

    for index, thread in enumerate(threads, start=1):

        name = thread["name"]

        log(f"Submitting thread {index}/{len(threads)}: {name}")

        try:

            result = publish_thread(
                thread["posts"],
                channel_id
            )

            record = {
                "name": name,
                "buffer_post_id": result.get("id"),
                "buffer_status": result.get("status"),
                "due_at": result.get("dueAt"),
                "submission_status": "submitted"
            }

            history["published_threads"].append(record)
            save_history(history)

            log(f"Buffer accepted the thread for {name}.")
            log(f"Buffer post ID: {result.get('id')}")

        except Exception as error:

            history["status"] = "partial_failure"
            history["error"] = str(error)
            save_history(history)

            log(f"Publishing stopped: {error}")
            log("Check Buffer before attempting another run.")

            raise

    history["status"] = "submitted_to_buffer"
    history["completed_at"] = datetime.now(TZ).isoformat()

    save_history(history)

    log("All threads have been submitted to Buffer.")
    log("Share Now was requested for each thread.")


if __name__ == "__main__":
    main()
