import os
import json
import re
import sys
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

# Optional: if multiple X accounts are connected to Buffer,
# set this variable to the exact channel name to select.
BUFFER_X_CHANNEL_NAME = os.getenv("BUFFER_X_CHANNEL_NAME")

STATE_DIR = Path("data/famous_numerology")
STATE_FILE = STATE_DIR / f"{TODAY.isoformat()}.json"

MAX_PEOPLE = 4
MAX_CHARS = 275
TIMEOUT = 180


# =========================================================
# ENVIRONMENT
# =========================================================

def require_environment():
    missing = []

    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if not BUFFER_TOKEN:
        missing.append("BUFFER_X_ACCESS_TOKEN")

    if missing:
        raise RuntimeError(
            "Missing GitHub secrets: " + ", ".join(missing)
        )


# =========================================================
# NUMEROLOGY CALCULATIONS
# =========================================================

def digit_sum(number):
    return sum(int(x) for x in str(number))


def reduce_number(number, preserve_master=False):
    while number > 9:
        if preserve_master and number in (11, 22, 33):
            return number
        number = digit_sum(number)

    return number


def calculate_numbers(dob):
    day = dob.day
    month = dob.month
    year = dob.year

    # Mulank
    mulank = reduce_number(day)

    # Bhagyank: sum every digit of full DOB
    full_dob = f"{day:02d}{month:02d}{year:04d}"
    bhagyank_compound = digit_sum(int(full_dob))

    bhagyank = reduce_number(
        bhagyank_compound,
        preserve_master=True
    )

    # Personal Year for next calendar year
    personal_year_compound = (
        digit_sum(day)
        + digit_sum(month)
        + digit_sum(FORECAST_YEAR)
    )

    personal_year = reduce_number(personal_year_compound)

    return {
        "mulank": mulank,
        "mulank_compound": day,
        "bhagyank": bhagyank,
        "bhagyank_compound": bhagyank_compound,
        "personal_year": personal_year,
        "personal_year_compound": personal_year_compound,
        "forecast_year": FORECAST_YEAR
    }


# =========================================================
# OPENAI RESEARCH
# =========================================================

def ask_openai():

    prompt = f"""
Today's date in India is {TODAY.isoformat()}.

Find famous Indian people born on {TODAY.day}
{TODAY.strftime("%B")}.

The publication is for today's date, not historical birthdays
of people who are no longer alive.

STRICT RESEARCH RULES:

1. Include only famous Indian people alive today.
2. Verify their exact Gregorian date of birth.
3. Verify their current living status.
4. Require at least TWO distinct reliable source URLs.
5. Prefer official biographies, institutional websites,
   reputable newspapers, sports organisations and interviews.
6. Exclude people whose date of birth or living status is uncertain.
7. Do not guess dates.
8. Maximum {MAX_PEOPLE} people.
9. If nobody meets the verification standard, return an empty list.
10. Do not include deceased people.

NUMEROLOGY METHOD:

MULANK:
Reduce the birth day to a number from 1 to 9.
Preserve the original birth day as its compound number.

BHAGYANK:
Add every digit of the full Gregorian date of birth.
Reduce to one digit, preserving 11, 22 and 33 if reached.

PERSONAL YEAR:
Add birth day + birth month + digit sum of {FORECAST_YEAR}.
Reduce to a single digit from 1 to 9.
Do not preserve master numbers for Personal Year.

Create exactly THREE posts per person.

POST 1:
- Must begin exactly:
  Happy Birthday, [Full Name]!
- Include Mulank and original compound birth-day number.
- Explain the numerological symbolism in depth.
- Avoid generic personality descriptions.

POST 2:
- Include Bhagyank and its compound total.
- Connect its symbolism with documented career or life milestones.
- Explicitly state that this is a numerological interpretation,
  not evidence that numerology caused the achievements.
- Never invent biographical milestones.

POST 3:
- Include Personal Year for {FORECAST_YEAR}.
- Discuss possible themes, opportunities and cautions.
- Do not present predictions as guaranteed events.
- Include a short disclaimer that numerology is interpretive.
- Include at least one reliable source URL.

WRITING RULES:

- Each post must be at most {MAX_CHARS} characters.
- No hashtags.
- No emojis.
- No Astro Bhaiya branding or promotional signature.
- No marketing language.
- Use natural, thoughtful English.
- Avoid repetitive generic interpretations.
- Clearly distinguish documented facts from numerological interpretation.
- Never claim numerology scientifically predicts outcomes.
- No more than {MAX_PEOPLE} people.

Return ONLY valid JSON in this structure:

{{
  "date": "{TODAY.isoformat()}",
  "people": [
    {{
      "name": "Full name",
      "dob": "YYYY-MM-DD",
      "alive_verified": true,
      "dob_verified": true,
      "sources": [
        "https://source-one.example",
        "https://source-two.example"
      ],
      "documented_milestones": [
        "Verifiable milestone"
      ],
      "posts": [
        "First post",
        "Second post",
        "Third post"
      ]
    }}
  ]
}}
"""

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENAI_MODEL,
            "tools": [
                {
                    "type": "web_search",
                    "search_context_size": "high"
                }
            ],
            "input": prompt
        },
        timeout=TIMEOUT
    )

    if not response.ok:
        raise RuntimeError(
            f"OpenAI error {response.status_code}: "
            f"{response.text[:2000]}"
        )

    data = response.json()
    output_text = data.get("output_text", "").strip()

    if not output_text:
        # Fallback: collect text blocks from output items.
        chunks = []

        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))

        output_text = "\n".join(chunks).strip()

    if not output_text:
        raise RuntimeError("OpenAI returned no readable text.")

    output_text = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        output_text,
        flags=re.IGNORECASE
    ).strip()

    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "OpenAI returned invalid JSON:\n"
            + output_text[:2000]
        ) from exc


# =========================================================
# VALIDATE RESEARCH
# =========================================================

def validate_people(result):

    if result.get("date") != TODAY.isoformat():
        raise ValueError("Research date does not match today.")

    people = result.get("people")

    if not isinstance(people, list):
        raise ValueError("Invalid people list.")

    if len(people) > MAX_PEOPLE:
        raise ValueError("Too many candidates returned.")

    valid_people = []
    seen_names = set()

    for person in people:

        if person.get("alive_verified") is not True:
            continue

        if person.get("dob_verified") is not True:
            continue

        name = person.get("name", "").strip()

        if not name or name.lower() in seen_names:
            continue

        try:
            dob = datetime.strptime(
                person["dob"], "%Y-%m-%d"
            ).date()
        except (KeyError, ValueError):
            continue

        if (dob.day, dob.month) != (TODAY.day, TODAY.month):
            continue

        sources = person.get("sources", [])

        if not isinstance(sources, list):
            continue

        sources = list(dict.fromkeys(sources))

        if len(sources) < 2:
            continue

        if not all(
            isinstance(url, str)
            and url.startswith(("https://", "http://"))
            for url in sources
        ):
            continue

        posts = person.get("posts", [])

        if not isinstance(posts, list) or len(posts) != 3:
            continue

        if not posts[0].startswith(
            f"Happy Birthday, {name}!"
        ):
            continue

        if not all(
            isinstance(post, str)
            and post.strip()
            and len(post) <= MAX_CHARS
            for post in posts
        ):
            continue

        if not any(url in posts[2] for url in sources):
            continue

        person["sources"] = sources
        person["calculated_numbers"] = calculate_numbers(dob)

        seen_names.add(name.lower())
        valid_people.append(person)

    return valid_people


# =========================================================
# BUFFER GRAPHQL
# =========================================================

def buffer_query(query, variables=None):

    response = requests.post(
        "https://api.buffer.com",
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
            f"Buffer HTTP error {response.status_code}: "
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
# AUTOMATIC X CHANNEL DISCOVERY
# =========================================================

def find_x_channel():

    print("Finding Buffer organisations...")

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
        raise RuntimeError(
            "No Buffer organisations found for this account."
        )

    x_channels = []

    channel_query = """
    query GetChannels($organizationId: OrganizationId!) {
      channels(input: { organizationId: $organizationId }) {
        id
        name
        service
      }
    }
    """

    for organization in organizations:

        org_id = organization["id"]

        print(
            "Checking organisation:",
            organization.get("name", org_id)
        )

        channel_data = buffer_query(
            channel_query,
            {"organizationId": org_id}
        )

        channels = channel_data.get("channels", [])

        for channel in channels:

            service = (
                channel.get("service") or ""
            ).lower()

            if service in ("twitter", "x"):
                x_channels.append(channel)

    # Remove duplicate channel IDs.
    unique_channels = {
        channel["id"]: channel
        for channel in x_channels
    }

    x_channels = list(unique_channels.values())

    if not x_channels:
        raise RuntimeError(
            "No X/Twitter channel found. "
            "Check that your X account is connected to Buffer."
        )

    if BUFFER_X_CHANNEL_NAME:
        matches = [
            channel for channel in x_channels
            if channel.get("name", "").lower()
            == BUFFER_X_CHANNEL_NAME.lower()
        ]

        if len(matches) != 1:
            raise RuntimeError(
                "BUFFER_X_CHANNEL_NAME did not identify "
                "exactly one X channel."
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
            "Multiple X channels found. Set the optional "
            "BUFFER_X_CHANNEL_NAME variable to select one. "
            "Available channels: " + ", ".join(available)
        )

    print(
        "Selected X channel:",
        selected.get("name", selected["id"])
    )

    return selected["id"]


# =========================================================
# PUBLISH ONE X THREAD
# =========================================================

def publish_thread(channel_id, posts):

    if not posts:
        raise ValueError("Cannot publish an empty thread.")

    if len(posts) > 20:
        raise ValueError("Thread exceeds 20 posts.")

    if any(len(post) > MAX_CHARS for post in posts):
        raise ValueError("A post exceeds the character limit.")

    # Every item, including the first, belongs in the thread array.
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

    data = buffer_query(mutation, variables)
    result = data.get("createPost")

    if not result:
        raise RuntimeError(
            "Buffer returned no createPost result."
        )

    if result.get("message"):
        raise RuntimeError(
            "Buffer rejected the thread: "
            + result["message"]
        )

    post = result.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            "Buffer did not confirm successful creation: "
            + json.dumps(result)
        )

    return post


# =========================================================
# MAIN
# =========================================================

def main():

    require_environment()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Prevent a second workflow run posting the same date.
    if STATE_FILE.exists():
        print(
            f"{TODAY} has already been processed. "
            "Skipping duplicate run."
        )
        return

    # Discover the X channel automatically.
    channel_id = find_x_channel()

    # Research birthday candidates.
    print(
        f"Researching famous Indian people born on "
        f"{TODAY.day} {TODAY.strftime('%B')}..."
    )

    research = ask_openai()
    people = validate_people(research)

    if not people:

        print(
            "No sufficiently verified living people found. "
            "No X post will be published."
        )

        STATE_FILE.write_text(
            json.dumps(
                {
                    "date": TODAY.isoformat(),
                    "status": "no_verified_people",
                    "people": []
                },
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return

    # Create one combined thread:
    # Person 1: 3 posts
    # Person 2: 3 posts
    # Person 3: 3 posts
    # Person 4: 3 posts

    all_posts = []

    for person in people:

        print(
            "Verified candidate:",
            person["name"],
            person["dob"]
        )

        all_posts.extend(person["posts"])

    if len(all_posts) > 20:
        raise ValueError("Maximum thread size exceeded.")

    print(
        f"Publishing {len(all_posts)} posts "
        f"for {len(people)} people..."
    )

    published = publish_thread(channel_id, all_posts)

    record = {
        "date": TODAY.isoformat(),
        "forecast_year": FORECAST_YEAR,
        "status": "submitted_to_buffer",
        "buffer_channel_id": channel_id,
        "buffer_post_id": published["id"],
        "buffer_status": published.get("status"),
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

    print("Buffer accepted the thread.")
    print("Buffer post ID:", published["id"])


if __name__ == "__main__":

    try:
        main()

    except Exception as error:
        print(
            f"FAILED: {error}",
            file=sys.stderr
        )
        raise