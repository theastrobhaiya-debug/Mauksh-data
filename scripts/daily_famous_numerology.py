
import os
import sys
import json
import re
import logging
import argparse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# =========================================================
# CONFIGURATION
# =========================================================

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ).date()
FORECAST_YEAR = TODAY.year + 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-6-astra"

BUFFER_TOKEN = os.getenv("BUFFER_X_ACCESS_TOKEN")
BUFFER_X_CHANNEL_NAME = os.getenv(
    "BUFFER_X_CHANNEL_NAME", ""
).strip()

OPENAI_URL = "https://api.openai.com/v1/responses"
BUFFER_URL = "https://api.buffer.com"

MAX_PEOPLE = int(os.getenv("MAX_PEOPLE", "4"))
MAX_CHARS = 275
MAX_THREAD_POSTS = 20

TIMEOUT = 180

STATE_DIR = Path("data/famous_numerology")
STATE_FILE = STATE_DIR / f"{TODAY.isoformat()}.json"

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("mauksh-numerology")


# =========================================================
# ENVIRONMENT
# =========================================================

def require_environment(dry_run=False):

    missing = []

    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if not dry_run and not BUFFER_TOKEN:
        missing.append("BUFFER_X_ACCESS_TOKEN")

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# =========================================================
# STATE MANAGEMENT
# =========================================================

def load_state():

    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

    except (json.JSONDecodeError, OSError):
        log.warning("State file unreadable.")
        return {}


def save_state(record):

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    STATE_FILE.write_text(
        json.dumps(
            record,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def check_duplicate(force=False):

    state = load_state()

    if not state:
        return

    status = state.get("status")

    successful = {
        "submitted_to_buffer",
        "published",
        "sent",
        "scheduled"
    }

    if status in successful:

        log.info(
            "Today's thread already submitted. "
            "Skipping duplicate publication."
        )
        sys.exit(0)

    if status == "publishing":

        if not force:
            raise RuntimeError(
                "Previous publishing request may have reached "
                "Buffer. Check Buffer before retrying. "
                "Use --force only after verifying no thread exists."
            )

        log.warning(
            "Force enabled for an uncertain publishing attempt."
        )
        return

    log.info(
        "Previous status was '%s'. Retrying.",
        status or "unknown"
    )


# =========================================================
# NUMEROLOGY
# =========================================================

def digit_sum(number):

    return sum(int(x) for x in str(number))


def reduce_number(number, preserve_master=False):

    number = int(number)

    while number > 9:

        if preserve_master and number in (11, 22, 33):
            return number

        number = digit_sum(number)

    return number


def calculate_numbers(dob):

    day = dob.day
    month = dob.month
    year = dob.year

    mulank = reduce_number(day)

    full_dob = f"{day:02d}{month:02d}{year:04d}"

    bhagyank_compound = sum(
        int(x) for x in full_dob
    )

    bhagyank = reduce_number(
        bhagyank_compound,
        preserve_master=True
    )

    personal_year_compound = (
        digit_sum(day)
        + digit_sum(month)
        + digit_sum(FORECAST_YEAR)
    )

    personal_year = reduce_number(
        personal_year_compound
    )

    return {
        "mulank": mulank,
        "original_compound": day,
        "bhagyank": bhagyank,
        "bhagyank_compound": bhagyank_compound,
        "personal_year": personal_year,
        "personal_year_compound": personal_year_compound,
        "forecast_year": FORECAST_YEAR
    }


# =========================================================
# OPENAI HELPERS
# =========================================================

def extract_output_text(data):

    if data.get("output_text"):
        return data["output_text"].strip()

    chunks = []

    for item in data.get("output", []):

        for content in item.get("content", []):

            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))

    return "\n".join(chunks).strip()


def parse_json(text):

    text = text.strip()

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

        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])

        raise


def openai_request(prompt, use_search=False):

    payload = {
        "model": OPENAI_MODEL,
        "input": prompt
    }

    if use_search:

        payload["tools"] = [
            {
                "type": "web_search",
                "search_context_size": "high"
            }
        ]

    response = requests.post(
        OPENAI_URL,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=TIMEOUT
    )

    if not response.ok:

        raise RuntimeError(
            f"OpenAI HTTP {response.status_code}: "
            f"{response.text[:2000]}"
        )

    data = response.json()

    output = extract_output_text(data)

    if not output:
        raise RuntimeError("OpenAI returned empty output.")

    return parse_json(output)


# =========================================================
# RESEARCH BIRTHDAYS
# =========================================================

def research_birthdays():

    prompt = f"""
You are the research editor for Mauksh's daily
famous birthday numerology publication.

TODAY: {TODAY.isoformat()}
TIMEZONE: Asia/Kolkata

Find up to {MAX_PEOPLE} famous INDIAN personalities
whose Gregorian birthday is {TODAY.strftime("%d %B")}.

STRICT RULES:

1. Include only people alive today.
2. Verify exact Gregorian birth date.
3. Require at least TWO distinct reliable source URLs.
4. Prefer official biographies, reputable newspapers,
   sports organisations and institutional websites.
5. Never guess dates.
6. Never include deceased people.
7. No fictional personalities.
8. No invented career milestones.
9. Prioritise famous Indian sportspeople, actors,
   musicians and public figures.
10. Return fewer people if necessary.
11. Do not fill the list with obscure names.
12. Return an empty list if none can be verified.

Research:
- Full name
- Date of birth
- Profession
- Country
- Living status
- Career milestones
- Publicly documented turning points
- Reliable sources

Return ONLY valid JSON:

{{
  "date": "{TODAY.isoformat()}",
  "people": [
    {{
      "name": "Full name",
      "dob": "YYYY-MM-DD",
      "alive_verified": true,
      "dob_verified": true,
      "profession": "Profession",
      "country": "Country",
      "sources": [
        "https://source-one.example",
        "https://source-two.example"
      ],
      "documented_milestones": [
        "Verified milestone",
        "Verified turning point"
      ]
    }}
  ]
}}

Do not write social posts yet.
"""

    log.info("Researching birthdays for today.")

    return openai_request(
        prompt,
        use_search=True
    )


# =========================================================
# VALIDATE RESEARCH
# =========================================================

def validate_people(result):

    if result.get("date") != TODAY.isoformat():
        raise ValueError("Research date mismatch.")

    candidates = result.get("people", [])

    if not isinstance(candidates, list):
        raise ValueError("Invalid people list.")

    valid = []
    seen = set()

    for person in candidates:

        if not isinstance(person, dict):
            continue

        if person.get("alive_verified") is not True:
            continue

        if person.get("dob_verified") is not True:
            continue

        name = str(person.get("name", "")).strip()

        if not name or name.lower() in seen:
            continue

        try:

            dob = datetime.strptime(
                person["dob"], "%Y-%m-%d"
            ).date()

        except (KeyError, ValueError, TypeError):
            continue

        if (dob.day, dob.month) != (TODAY.day, TODAY.month):
            continue

        if dob >= TODAY:
            continue

        sources = person.get("sources", [])

        if not isinstance(sources, list):
            continue

        sources = list(dict.fromkeys(sources))

        if len(sources) < 2:
            continue

        if not all(
            isinstance(url, str)
            and url.startswith("https://")
            for url in sources
        ):
            continue

        milestones = person.get(
            "documented_milestones", []
        )

        if not isinstance(milestones, list) or not milestones:
            continue

        person["name"] = name
        person["dob"] = dob.isoformat()
        person["sources"] = sources
        person["calculated_numbers"] = calculate_numbers(dob)

        valid.append(person)
        seen.add(name.lower())

    return valid[:MAX_PEOPLE]


# =========================================================
# MAIN BIRTHDAY ROLL CALL
# =========================================================

def build_main_post(people):

    names = ", ".join(
        person["name"] for person in people
    )

    post = (
        f"Happy Birthday to {names}! "
        f"Today we explore the numerology behind "
        f"their life journeys, achievements and "
        f"upcoming personal years. 🧵"
    )

    if len(post) > MAX_CHARS:

        raise ValueError(
            "All birthday names cannot fit in one post. "
            "Reduce MAX_PEOPLE or use shorter verified names."
        )

    return post


# =========================================================
# GENERATE INDIVIDUAL POSTS
# =========================================================

def generate_individual_posts(people):

    research_data = []

    for person in people:

        research_data.append({
            "name": person["name"],
            "dob": person["dob"],
            "profession": person["profession"],
            "country": person["country"],
            "numbers": person["calculated_numbers"],
            "milestones": person["documented_milestones"],
            "sources": person["sources"]
        })

    prompt = f"""
You are Mauksh's numerology research writer.

Write EXACTLY THREE X posts per person.

DATE: {TODAY.isoformat()}
FORECAST YEAR: {FORECAST_YEAR}

VERIFIED DATA:
{json.dumps(research_data, ensure_ascii=False)}

Use supplied numerology values exactly.

POST 1: MULANK

Must begin:
Happy Birthday, [Full Name]!

Include:
- Mulank
- Original compound birth-day number
- Traditional symbolism
- Specific and thoughtful interpretation

POST 2: BHAGYANK

Include:
- Bhagyank
- Compound total
- Symbolic interpretation
- Connect with a documented career milestone.
- State clearly that numerology did not establish
  or cause the achievement.

POST 3: PERSONAL YEAR

Include:
- Personal Year for {FORECAST_YEAR}
- Compound calculation total
- Themes, possible opportunities and cautions.
- Relate carefully to public career stage.
- No guaranteed predictions.
- Brief disclaimer that numerology is interpretive.
- Include one supplied reliable source URL.

EDITORIAL RULES:

- Maximum {MAX_CHARS} characters per post.
- Natural analytical English.
- No hashtags.
- No marketing.
- No Astro Bhaiya branding.
- No exaggerated predictions.
- No invented milestones.
- No generic repetitive praise.
- Distinguish facts from interpretation.
- Exactly three posts per person.
- Do not omit anyone.

Return ONLY JSON:

{{
  "people": [
    {{
      "name": "Full name",
      "posts": [
        "Mulank analysis",
        "Bhagyank analysis",
        "Personal Year analysis with source URL"
      ]
    }}
  ]
}}
"""

    log.info("Generating numerology analyses.")

    return openai_request(
        prompt,
        use_search=False
    )


# =========================================================
# VALIDATE GENERATED POSTS
# =========================================================

def validate_posts(people, generated):

    generated_people = generated.get("people", [])

    if not isinstance(generated_people, list):
        raise ValueError("Invalid generated people.")

    generated_map = {}

    for person in generated_people:

        name = str(person.get("name", "")).strip().lower()

        if name in generated_map:
            raise ValueError("Duplicate generated personality.")

        generated_map[name] = person

    all_posts = []

    for person in people:

        name = person["name"]

        generated_person = generated_map.get(name.lower())

        if not generated_person:
            raise ValueError(f"Missing analysis for {name}.")

        posts = generated_person.get("posts")

        if not isinstance(posts, list) or len(posts) != 3:
            raise ValueError(
                f"{name} must have exactly three posts."
            )

        posts = [str(post).strip() for post in posts]

        if not posts[0].startswith(
            f"Happy Birthday, {name}!"
        ):
            raise ValueError(
                f"Incorrect birthday opening: {name}"
            )

        numbers = person["calculated_numbers"]

        required_values = [
            (numbers["mulank"], posts[0], "Mulank"),
            (numbers["original_compound"], posts[0], "Compound"),
            (numbers["bhagyank"], posts[1], "Bhagyank"),
            (numbers["bhagyank_compound"], posts[1], "Bhagyank total"),
            (numbers["personal_year"], posts[2], "Personal Year"),
            (FORECAST_YEAR, posts[2], "Forecast year")
        ]

        for value, post, label in required_values:

            if str(value) not in post:
                raise ValueError(
                    f"{label} missing for {name}."
                )

        for index, post in enumerate(posts, start=1):

            if not post or len(post) > MAX_CHARS:
                raise ValueError(
                    f"Post {index} exceeds character limit for {name}."
                )

        if not any(
            url in posts[2]
            for url in person["sources"]
        ):
            raise ValueError(
                f"Missing verified source URL for {name}."
            )

        person["posts"] = posts
        all_posts.extend(posts)

    return all_posts


# =========================================================
# BUFFER GRAPHQL
# =========================================================

def buffer_query(query, variables=None):

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
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if data.get("errors"):

        raise RuntimeError(
            "Buffer GraphQL error: "
            + json.dumps(data["errors"], ensure_ascii=False)
        )

    if "data" not in data:
        raise RuntimeError("Invalid Buffer response.")

    return data["data"]


# =========================================================
# FIND X CHANNEL AUTOMATICALLY
# =========================================================

def find_x_channel():

    log.info("Discovering Buffer organisations.")

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

    data = buffer_query(organization_query)

    organizations = (
        data.get("account", {}).get("organizations", [])
    )

    if not organizations:
        raise RuntimeError("No Buffer organisations found.")

    channel_query = """
    query GetChannels($organizationId: OrganizationId!) {
      channels(input: {
        organizationId: $organizationId
      }) {
        id
        name
        displayName
        service
        isDisconnected
      }
    }
    """

    channels_found = []

    for organization in organizations:

        result = buffer_query(
            channel_query,
            {"organizationId": organization["id"]}
        )

        for channel in result.get("channels", []):

            service = (
                channel.get("service") or ""
            ).lower()

            if service in ("twitter", "x") and not channel.get(
                "isDisconnected", False
            ):
                channels_found.append(channel)

    unique = {
        channel["id"]: channel
        for channel in channels_found
    }

    channels_found = list(unique.values())

    if not channels_found:
        raise RuntimeError("No connected X channel found.")

    if BUFFER_X_CHANNEL_NAME:

        matches = [
            channel for channel in channels_found
            if BUFFER_X_CHANNEL_NAME.lower()
            in (
                channel.get("name", "") + " " +
                (channel.get("displayName") or "")
            ).lower()
        ]

        if len(matches) != 1:
            raise RuntimeError(
                "Could not uniquely identify requested X channel."
            )

        selected = matches[0]

    elif len(channels_found) == 1:

        selected = channels_found[0]

    else:

        raise RuntimeError(
            "Multiple X accounts found. Set BUFFER_X_CHANNEL_NAME."
        )

    log.info(
        "Selected X channel: %s",
        selected.get("displayName") or selected.get("name")
    )

    return selected["id"]


# =========================================================
# PUBLISH THREAD
# =========================================================

def publish_thread(channel_id, posts):

    if not posts:
        raise ValueError("Empty thread.")

    if len(posts) > MAX_THREAD_POSTS:
        raise ValueError("Thread exceeds maximum size.")

    thread = [
        {"text": post}
        for post in posts
    ]

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
                    "thread": thread
                }
            }
        }
    }

    try:

        data = buffer_query(
            mutation,
            variables
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            "BUFFER_OUTCOME_UNKNOWN: The request may have "
            "reached Buffer. Verify Buffer before retrying."
        ) from exc

    result = data.get("createPost")

    if not result:
        raise RuntimeError(
            "BUFFER_OUTCOME_UNKNOWN: No createPost result. "
            "Verify Buffer before retrying."
        )

    if result.get("message"):
        raise RuntimeError(
            "Buffer rejected the thread: " + result["message"]
        )

    post = result.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            "BUFFER_OUTCOME_UNKNOWN: Buffer did not confirm "
            "the post ID. Verify Buffer before retrying."
        )

    return post


# =========================================================
# MAIN
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Override duplicate protection after manual verification."
    )

    args = parser.parse_args()

    require_environment(dry_run=args.dry_run)

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if not args.force:
        check_duplicate()

    # 1. Birthday research.
    research = research_birthdays()

    # 2. Validate candidates.
    people = validate_people(research)

    if not people:

        save_state({
            "date": TODAY.isoformat(),
            "status": "no_verified_people",
            "people": []
        })

        log.warning(
            "No sufficiently verified living birthday personalities."
        )

        return

    # 3. Main birthday roll call.
    main_post = build_main_post(people)

    # 4. Individual analysis.
    generated = generate_individual_posts(people)

    individual_posts = validate_posts(
        people,
        generated
    )

    # 5. One complete connected thread.
    all_posts = [main_post] + individual_posts

    if len(all_posts) > MAX_THREAD_POSTS:
        raise ValueError("Thread exceeds maximum configured size.")

    # 6. Display preview.
    print("\n" + "=" * 65)
    print("MAUKSH DAILY FAMOUS BIRTHDAYS & NUMEROLOGY")
    print(TODAY.isoformat())
    print("=" * 65)

    for index, post in enumerate(all_posts, start=1):

        print(f"\nPOST {index} | {len(post)} characters")
        print(post)
        print("-" * 65)

    print(f"\nPeople: {len(people)}")
    print(f"Total posts: {len(all_posts)}")

    if args.dry_run:

        log.info("Dry run completed. Nothing published.")
        return

    # 7. Discover channel.
    channel_id = find_x_channel()

    # 8. Persist publishing intent BEFORE calling Buffer.
    # If the workflow crashes during publishing, the next
    # run will stop for manual verification.

    save_state({
        "date": TODAY.isoformat(),
        "status": "publishing",
        "buffer_channel_id": channel_id,
        "people": people,
        "posts": all_posts,
        "started_at_ist": datetime.now(TZ).isoformat()
    })

    try:

        # 9. Publish immediately.
        published = publish_thread(
            channel_id,
            all_posts
        )

    except Exception as error:

        save_state({
            "date": TODAY.isoformat(),
            "status": "publishing",
            "buffer_channel_id": channel_id,
            "error": str(error),
            "people": people,
            "posts": all_posts,
            "needs_manual_verification": True,
            "updated_at_ist": datetime.now(TZ).isoformat()
        })

        raise

    # 10. Save successful submission.
    save_state({
        "date": TODAY.isoformat(),
        "forecast_year": FORECAST_YEAR,
        "status": "submitted_to_buffer",
        "buffer_channel_id": channel_id,
        "buffer_post_id": published["id"],
        "buffer_status": published.get("status"),
        "main_post": main_post,
        "people": people,
        "posts": all_posts,
        "published_at_ist": datetime.now(TZ).isoformat()
    })

    log.info("Thread submitted successfully.")
    log.info("Buffer post ID: %s", published["id"])


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        log.exception("Automation failed: %s", error)

        sys.exit(1)
