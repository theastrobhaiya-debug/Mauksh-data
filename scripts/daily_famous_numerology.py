
import os
import sys
import json
import re
import argparse
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# =========================================================
# MAUKSH DAILY FAMOUS BIRTHDAYS & NUMEROLOGY
# =========================================================

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ).date()
FORECAST_YEAR = TODAY.year + 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-6-astra"

BUFFER_TOKEN = os.getenv("BUFFER_X_ACCESS_TOKEN")
BUFFER_X_CHANNEL_NAME = os.getenv("BUFFER_X_CHANNEL_NAME", "").strip()

OPENAI_URL = "https://api.openai.com/v1/responses"
BUFFER_URL = "https://api.buffer.com"

MAX_PEOPLE = int(os.getenv("MAX_PEOPLE", "4"))
MAX_CHARS = 275
MAX_THREAD_POSTS = 20
TIMEOUT = 180

STATE_DIR = Path("data/famous_numerology")
STATE_FILE = STATE_DIR / f"{TODAY.isoformat()}.json"

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
# NUMEROLOGY CALCULATIONS
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

    # MULANK
    # Original birth day retained separately.
    mulank = reduce_number(day)

    # BHAGYANK
    # Sum every digit of the full Gregorian DOB.
    full_dob = f"{day:02d}{month:02d}{year:04d}"

    bhagyank_compound = sum(
        int(x) for x in full_dob
    )

    bhagyank = reduce_number(
        bhagyank_compound,
        preserve_master=True
    )

    # PERSONAL YEAR
    # Day digits + month digits + forecast year's digits.
    personal_year_compound = (
        digit_sum(day)
        + digit_sum(month)
        + digit_sum(FORECAST_YEAR)
    )

    personal_year = reduce_number(
        personal_year_compound,
        preserve_master=False
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
# OPENAI RESPONSE HELPERS
# =========================================================

def extract_output_text(data):

    if data.get("output_text"):
        return data["output_text"].strip()

    chunks = []

    for item in data.get("output", []):

        if item.get("type") != "message":
            continue

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

        # Recover a JSON object if surrounding text exists.
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
            f"{response.text[:2500]}"
        )

    data = response.json()

    text = extract_output_text(data)

    if not text:
        raise RuntimeError(
            "OpenAI returned no readable output."
        )

    return parse_json(text)


# =========================================================
# STEP 1: RESEARCH BIRTHDAY PERSONALITIES
# =========================================================

def research_birthdays():

    prompt = f"""
You are the research editor for Mauksh's daily
famous birthday numerology publication.

TODAY: {TODAY.isoformat()}
INDIAN TIMEZONE: Asia/Kolkata

Find up to {MAX_PEOPLE} famous INDIAN personalities
whose Gregorian date of birth is:

{TODAY.strftime("%d %B")}.

STRICT REQUIREMENTS:

1. Include only people who are alive today.
2. Verify exact day, month and year of birth.
3. Require TWO distinct reliable source URLs.
4. Prefer official biographies, reputable newspapers,
   sports organisations and institutional websites.
5. Never guess a birthday.
6. Never include deceased personalities.
7. Do not include fictional characters.
8. Do not invent career milestones.
9. Include people who are genuinely well-known.
10. Prioritise sports, cinema, music and public life.
11. Include a mix of Indian and internationally
    recognised Indian personalities where appropriate.
12. Do not fill the list with obscure names.
13. Return fewer people if fewer meet the standards.
14. Return an empty list if no one can be verified.

For each person research:

- Full name.
- Exact date of birth.
- Profession.
- Country.
- Evidence of living status.
- Important career achievements.
- Documented career turning points.
- Major publicly documented life events.
- Two or more distinct credible sources.

Return only valid JSON:

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
        "Verified career milestone",
        "Verified life event"
      ]
    }}
  ]
}}

Do not generate numerology posts in this step.
"""

    log.info(
        "Researching living famous personalities born on %s",
        TODAY.strftime("%d %B")
    )

    return openai_request(
        prompt,
        use_search=True
    )


# =========================================================
# STEP 2: VALIDATE RESEARCH
# =========================================================

def validate_people(result):

    if result.get("date") != TODAY.isoformat():
        raise ValueError("Research date does not match today.")

    people = result.get("people", [])

    if not isinstance(people, list):
        raise ValueError("Invalid people list.")

    valid = []
    seen = set()

    for person in people:

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

        # Birthday must match today's Indian calendar date.
        if (dob.day, dob.month) != (TODAY.day, TODAY.month):
            continue

        # Exclude impossible/future birth dates.
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

        milestones = person.get("documented_milestones", [])

        if not isinstance(milestones, list) or not milestones:
            continue

        person["name"] = name
        person["sources"] = sources
        person["dob"] = dob.isoformat()
        person["calculated_numbers"] = calculate_numbers(dob)

        valid.append(person)
        seen.add(name.lower())

    return valid[:MAX_PEOPLE]


# =========================================================
# STEP 3: BUILD MAIN BIRTHDAY ROLL CALL
# =========================================================

def build_main_post(people):

    names = [person["name"] for person in people]

    names_text = ", ".join(names)

    post = (
        f"Happy Birthday to {names_text}! "
        f"Today we explore the numerology behind "
        f"their life journeys, achievements and "
        f"upcoming personal years. 🧵"
    )

    if len(post) <= MAX_CHARS:
        return post, people

    # All names must fit in the main post.
    # Reduce the candidate count rather than omit names.
    while len(people) > 1:

        people = people[:-1]
        names_text = ", ".join(
            person["name"] for person in people
        )

        post = (
            f"Happy Birthday to {names_text}! "
            f"Explore the numbers behind their "
            f"life journeys and achievements. 🧵"
        )

        if len(post) <= MAX_CHARS:
            return post, people

    raise ValueError(
        "Birthday names cannot fit in one X post."
    )


# =========================================================
# STEP 4: GENERATE INDIVIDUAL ANALYSIS
# =========================================================

def generate_individual_posts(people):

    research_data = []

    for person in people:

        research_data.append({
            "name": person["name"],
            "dob": person["dob"],
            "profession": person["profession"],
            "country": person["country"],
            "mulank": person["calculated_numbers"]["mulank"],
            "original_compound": person["calculated_numbers"]["original_compound"],
            "bhagyank": person["calculated_numbers"]["bhagyank"],
            "bhagyank_compound": person["calculated_numbers"]["bhagyank_compound"],
            "personal_year": person["calculated_numbers"]["personal_year"],
            "personal_year_compound": person["calculated_numbers"]["personal_year_compound"],
            "forecast_year": FORECAST_YEAR,
            "documented_milestones": person["documented_milestones"],
            "sources": person["sources"]
        })

    prompt = f"""
You are Mauksh's numerology research writer.

Write exactly THREE analytical X posts for EVERY
person in the research data.

TODAY: {TODAY.isoformat()}

FORECAST YEAR: {FORECAST_YEAR}

VERIFIED DATA:
{json.dumps(research_data, ensure_ascii=False)}

All numerology calculations are already completed.
Use the supplied values exactly. Do not recalculate them.

====================================================
POST 1: MULANK AND ORIGINAL COMPOUND
====================================================

Must begin exactly:

Happy Birthday, [Full Name]!

Include:
- Mulank.
- Original compound birth-day number.
- Traditional meaning of the number.
- A thoughtful interpretation of the tension,
  strength or challenge represented by the number.

Make the analysis individual and meaningful.
Avoid generic personality descriptions.

====================================================
POST 2: BHAGYANK AND LIFE JOURNEY
====================================================

Include:
- Bhagyank.
- Original Bhagyank compound total.
- Traditional numerological symbolism.
- Connect the symbolism with at least one
  documented career milestone or life event.
- Explain the parallel critically.

Clearly state:
"This is a numerological interpretation, not
evidence that numerology caused the achievement."

Never invent a milestone.

====================================================
POST 3: PERSONAL YEAR
====================================================

Include:
- Personal Year for {FORECAST_YEAR}.
- Its compound calculation total.
- Symbolic themes.
- Possible opportunities.
- Possible cautions.
- Relate themes cautiously to the documented
  public career stage.

No guaranteed predictions.
End with a brief disclaimer that numerology
is interpretive.

Include ONE relevant verified source URL from
the supplied source list.

====================================================
EDITORIAL RULES
====================================================

- Every post maximum {MAX_CHARS} characters.
- Exactly three posts per person.
- No hashtags.
- No promotional signature.
- No Astro Bhaiya branding.
- No exaggerated claims.
- No fake quotes.
- No invented facts.
- No scientific claims for numerology.
- Natural, analytical English.
- Vary the writing between personalities.
- Avoid repetitive generic praise.
- Keep facts and interpretations distinct.
- Do not omit any person.
- Do not change supplied numerical values.

Return ONLY valid JSON:

{{
  "people": [
    {{
      "name": "Full name",
      "posts": [
        "Mulank analysis",
        "Bhagyank and life journey analysis",
        "Personal Year analysis with source URL"
      ]
    }}
  ]
}}
"""

    log.info("Generating individual numerology analysis.")

    return openai_request(
        prompt,
        use_search=False
    )


# =========================================================
# STEP 5: VALIDATE POSTS
# =========================================================

def validate_posts(people, generated):

    generated_people = generated.get("people", [])

    if not isinstance(generated_people, list):
        raise ValueError("Invalid generated people list.")

    generated_map = {}

    for person in generated_people:

        name = str(person.get("name", "")).strip().lower()

        if name in generated_map:
            raise ValueError(
                f"Duplicate generated person: {name}"
            )

        generated_map[name] = person

    all_posts = []

    for person in people:

        name = person["name"]
        generated_person = generated_map.get(name.lower())

        if not generated_person:
            raise ValueError(
                f"Missing analysis for {name}"
            )

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
                f"Incorrect birthday opening for {name}"
            )

        numbers = person["calculated_numbers"]

        # Verify the generated content includes the
        # numerological values supplied by our code.
        if str(numbers["mulank"]) not in posts[0]:
            raise ValueError(f"Mulank missing for {name}")

        if str(numbers["original_compound"]) not in posts[0]:
            raise ValueError(
                f"Original compound missing for {name}"
            )

        if str(numbers["bhagyank"]) not in posts[1]:
            raise ValueError(f"Bhagyank missing for {name}")

        if str(numbers["bhagyank_compound"]) not in posts[1]:
            raise ValueError(
                f"Bhagyank total missing for {name}"
            )

        if str(numbers["personal_year"]) not in posts[2]:
            raise ValueError(
                f"Personal Year missing for {name}"
            )

        if str(FORECAST_YEAR) not in posts[2]:
            raise ValueError(
                f"Forecast year missing for {name}"
            )

        if not all(
            post and len(post) <= MAX_CHARS
            for post in posts
        ):
            raise ValueError(
                f"Post length exceeds {MAX_CHARS} for {name}"
            )

        sources = person["sources"]

        if not any(
            url in posts[2] for url in sources
        ):
            raise ValueError(
                f"Personal Year post needs a verified URL: {name}"
            )

        person["posts"] = posts
        all_posts.extend(posts)

    return all_posts


# =========================================================
# STEP 6: BUFFER GRAPHQL REQUEST
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

    if not response.ok:
        raise RuntimeError(
            f"Buffer HTTP {response.status_code}: "
            f"{response.text[:2000]}"
        )

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            "Buffer GraphQL error: "
            + json.dumps(data["errors"], ensure_ascii=False)
        )

    if "data" not in data:
        raise RuntimeError(
            "Unexpected Buffer response: "
            + json.dumps(data, ensure_ascii=False)
        )

    return data["data"]


# =========================================================
# STEP 7: AUTOMATIC X CHANNEL DISCOVERY
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

    x_channels = []

    for organization in organizations:

        org_id = organization["id"]

        channel_data = buffer_query(
            channel_query,
            {"organizationId": org_id}
        )

        for channel in channel_data.get("channels", []):

            service = (
                channel.get("service") or ""
            ).lower()

            if service == "twitter" and not channel.get("isDisconnected"):
                x_channels.append(channel)

    # Deduplicate.
    x_channels = list({
        channel["id"]: channel
        for channel in x_channels
    }.values())

    if not x_channels:
        raise RuntimeError(
            "No connected X/Twitter channel found."
        )

    if BUFFER_X_CHANNEL_NAME:

        matches = [
            channel for channel in x_channels
            if BUFFER_X_CHANNEL_NAME.lower()
            in (
                channel.get("name", "") + " " +
                (channel.get("displayName") or "")
            ).lower()
        ]

        if len(matches) != 1:
            raise RuntimeError(
                "BUFFER_X_CHANNEL_NAME did not match "
                "exactly one channel."
            )

        selected = matches[0]

    elif len(x_channels) == 1:

        selected = x_channels[0]

    else:

        available = [
            channel.get("name", channel["id"])
            for channel in x_channels
        ]

        raise RuntimeError(
            "Multiple X accounts found. Set "
            "BUFFER_X_CHANNEL_NAME. Available: "
            + ", ".join(available)
        )

    log.info(
        "Selected X channel: %s",
        selected.get("displayName") or selected.get("name")
    )

    return selected["id"]


# =========================================================
# STEP 8: PUBLISH ONE CONNECTED X THREAD
# =========================================================

def publish_thread(channel_id, posts):

    if not posts:
        raise ValueError("Empty thread.")

    if len(posts) > MAX_THREAD_POSTS:
        raise ValueError(
            f"Thread contains {len(posts)} posts. "
            f"Maximum configured: {MAX_THREAD_POSTS}."
        )

    for index, post in enumerate(posts, start=1):

        if len(post) > MAX_CHARS:
            raise ValueError(
                f"Post {index} exceeds {MAX_CHARS} characters."
            )

    # IMPORTANT:
    # Include the main birthday roll-call post as
    # the FIRST item in the thread array.
    #
    # Then include all three posts for each person.

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

    data = buffer_query(
        mutation,
        variables
    )

    result = data.get("createPost")

    if not result:
        raise RuntimeError(
            "Buffer returned no createPost result."
        )

    if result.get("message"):
        raise RuntimeError(
            "Buffer publishing failed: "
            + result["message"]
        )

    published = result.get("post")

    if not published or not published.get("id"):
        raise RuntimeError(
            "Buffer did not confirm thread creation: "
            + json.dumps(result, ensure_ascii=False)
        )

    return published


# =========================================================
# STEP 9: MAIN
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and validate without publishing."
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if today's state file exists."
    )

    args = parser.parse_args()

    require_environment(dry_run=args.dry_run)

    STATE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if STATE_FILE.exists() and not args.force:

        log.info(
            "Today's date already processed. "
            "Skipping duplicate execution."
        )
        return

    # 1. Research.
    research = research_birthdays()

    # 2. Validate living people and birthdays.
    people = validate_people(research)

    if not people:

        log.warning("No verified living personalities found.")

        if not args.dry_run:
            STATE_FILE.write_text(
                json.dumps({
                    "date": TODAY.isoformat(),
                    "status": "no_verified_people",
                    "people": []
                }, indent=2),
                encoding="utf-8"
            )

        return

    # 3. Build the main birthday post.
    main_post, people = build_main_post(people)

    # 4. Generate three posts for every person.
    generated = generate_individual_posts(people)

    individual_posts = validate_posts(
        people,
        generated
    )

    # 5. Combine everything into one connected thread.
    all_posts = [main_post] + individual_posts

    if len(all_posts) > MAX_THREAD_POSTS:
        raise ValueError("Thread exceeds configured post limit.")

    # 6. Display preview.
    print("\n" + "=" * 65)
    print("MAUKSH DAILY FAMOUS BIRTHDAYS & NUMEROLOGY")
    print(TODAY.isoformat())
    print("=" * 65)

    for index, post in enumerate(all_posts, start=1):

        print(
            f"\nPOST {index} | {len(post)} characters"
        )

        print(post)
        print("-" * 65)

    print(
        f"\nPeople: {len(people)}"
        f"\nTotal posts: {len(all_posts)}"
    )

    if args.dry_run:

        log.info("Dry run successful. Nothing published.")
        return

    # 7. Discover X channel.
    channel_id = find_x_channel()

    # 8. Publish.
    published = publish_thread(
        channel_id,
        all_posts
    )

    # 9. Save history only after Buffer confirms creation.
    record = {
        "date": TODAY.isoformat(),
        "forecast_year": FORECAST_YEAR,
        "status": "submitted_to_buffer",
        "buffer_channel_id": channel_id,
        "buffer_post_id": published["id"],
        "buffer_status": published.get("status"),
        "main_post": main_post,
        "people": people,
        "posts": all_posts,
        "created_at_ist": datetime.now(TZ).isoformat()
    }

    STATE_FILE.write_text(
        json.dumps(
            record,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    log.info("Successfully submitted the thread to Buffer.")
    log.info("Buffer post ID: %s", published["id"])


if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        log.exception("Mauksh automation failed: %s", error)

        sys.exit(1)
