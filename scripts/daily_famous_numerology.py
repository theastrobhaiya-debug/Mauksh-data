import os
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# ---------------- CONFIG ----------------

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ).date()
FORECAST_YEAR = TODAY.year + 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-6-astra"

BUFFER_TOKEN = os.getenv("BUFFER_X_ACCESS_TOKEN")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_X_CHANNEL_ID")

STATE_DIR = Path("data/famous_numerology")
STATE_FILE = STATE_DIR / f"{TODAY.isoformat()}.json"

MAX_PEOPLE = 4
MAX_CHARS = 275
TIMEOUT = 180

# ---------------- VALIDATION ----------------

def require_environment():
    missing = []

    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if not BUFFER_TOKEN:
        missing.append("BUFFER_X_ACCESS_TOKEN")

    if not BUFFER_CHANNEL_ID:
        missing.append("BUFFER_X_CHANNEL_ID")

    if missing:
        raise RuntimeError(
            "Missing GitHub secrets: " + ", ".join(missing)
        )


def digit_sum(number):
    return sum(int(digit) for digit in str(number))


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

    mulank = reduce_number(day)

    bhagyank_total = digit_sum(
        int(f"{day:02d}{month:02d}{year:04d}")
    )
    bhagyank = reduce_number(
        bhagyank_total,
        preserve_master=True
    )

    personal_year_total = (
        digit_sum(day)
        + digit_sum(month)
        + digit_sum(FORECAST_YEAR)
    )
    personal_year = reduce_number(personal_year_total)

    return {
        "mulank": mulank,
        "mulank_compound": day,
        "bhagyank": bhagyank,
        "bhagyank_compound": bhagyank_total,
        "personal_year": personal_year,
        "forecast_year": FORECAST_YEAR,
    }


# ---------------- OPENAI RESEARCH ----------------

def ask_openai():
    prompt = f"""
Today's date in India is {TODAY.isoformat()}.

Research famous Indian people whose Gregorian date of birth
(day and month) is {TODAY.day} {TODAY.strftime("%B")}.

STRICT RESEARCH RULES:

1. Include only famous Indian people who are alive today.
2. Verify each person's exact full date of birth.
3. Verify that each person is currently alive.
4. Require at least TWO distinct, reliable source URLs per person.
5. Prefer official biographies, institutional profiles,
   sports organisations, reputable newspapers and interviews.
6. Exclude anyone whose date of birth or living status is uncertain.
7. Do not guess or infer birth dates.
8. Maximum {MAX_PEOPLE} people.
9. If no person meets the verification standard, return an empty list.
10. Do not include deceased people.

NUMEROLOGY METHOD:

Mulank:
- Reduce the birth day to one digit from 1 to 9.
- Preserve the original day as its compound number.

Bhagyank:
- Add every digit of the full Gregorian date of birth.
- Reduce to one digit, preserving 11, 22 and 33 if reached.

Personal Year:
- Add birth day + birth month + digit sum of {FORECAST_YEAR}.
- Reduce to one digit from 1 to 9.
- Do not preserve master numbers for Personal Year.

CONTENT REQUIREMENTS:

Create exactly THREE X posts per person.

POST 1:
- Begin exactly: Happy Birthday, [Full Name]!
- Include Mulank and original compound birth-day number.
- Give a thoughtful, detailed numerological interpretation.
- Avoid generic personality descriptions.

POST 2:
- Include Bhagyank and its compound total.
- Connect its numerological symbolism thoughtfully with
  documented milestones in the person's life or career.
- Clearly state that this is a numerological interpretation,
  not evidence that numerology caused those achievements.
- Do not invent milestones.

POST 3:
- Include the Personal Year number for {FORECAST_YEAR}.
- Explain possible themes, opportunities and cautions.
- Do not present predictions as guaranteed events.
- Include a short disclaimer that numerology is interpretive.
- Include one reliable source URL.

WRITING RULES:

- Each post must be at most {MAX_CHARS} characters.
- No hashtags.
- No emojis.
- No Astro Bhaiya branding or promotional signature.
- No marketing language.
- Use clear, natural English.
- Make the analysis substantive and specific.
- Separate documented facts from numerological interpretation.
- Do not claim numerology scientifically predicts outcomes.
- Do not repeat the same generic interpretation for every person.
- No more than {MAX_PEOPLE} people.

Return ONLY valid JSON in this exact structure:

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
        "A verifiable milestone"
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
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "tools": [
                {
                    "type": "web_search",
                    "search_context_size": "high"
                }
            ],
            "tool_choice": "required",
            "input": prompt,
        },
        timeout=TIMEOUT,
    )

    if not response.ok:
        raise RuntimeError(
            f"OpenAI API error {response.status_code}: "
            f"{response.text[:2000]}"
        )

    data = response.json()

    output_text = data.get("output_text", "").strip()

    if not output_text:
        raise RuntimeError("OpenAI returned no output_text.")

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
            f"OpenAI did not return valid JSON: {output_text[:1500]}"
        ) from exc


# ---------------- CONTENT VALIDATION ----------------

def validate_people(result):
    if result.get("date") != TODAY.isoformat():
        raise ValueError("Research date does not match today's date.")

    people = result.get("people")

    if not isinstance(people, list):
        raise ValueError("The people field must be a list.")

    if len(people) > MAX_PEOPLE:
        raise ValueError("Too many people returned.")

    valid_people = []

    for person in people:
        if person.get("alive_verified") is not True:
            continue

        if person.get("dob_verified") is not True:
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
        if not isinstance(sources, list) or len(set(sources)) < 2:
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
            f"Happy Birthday, {person.get('name', '')}!"
        ):
            continue

        if not all(
            isinstance(post, str)
            and post.strip()
            and len(post) <= MAX_CHARS
            for post in posts
        ):
            continue

        if not any(
            url in posts[2] for url in sources
        ):
            continue

        numbers = calculate_numbers(dob)

        person["calculated_numbers"] = numbers
        valid_people.append(person)

    return valid_people


# ---------------- BUFFER API ----------------

def buffer_query(query):
    response = requests.post(
        "https://api.buffer.com",
        headers={
            "Authorization": f"Bearer {BUFFER_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=60,
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

    return data.get("data", {})


def publish_thread(posts):
    if not posts:
        raise ValueError("Cannot publish an empty thread.")

    thread_items = []

    for post in posts:
        escaped = json.dumps(post, ensure_ascii=False)
        thread_items.append(f"{{ text: {escaped} }}")

    thread_string = "\n".join(thread_items)

    first_post = json.dumps(posts[0], ensure_ascii=False)
    channel_id = json.dumps(BUFFER_CHANNEL_ID)

    mutation = f"""
    mutation CreateBirthdayNumerologyThread {{
      createPost(
        input: {{
          text: {first_post}
          channelId: {channel_id}
          schedulingType: automatic
          mode: shareNow
          metadata: {{
            twitter: {{
              thread: [
                {thread_string}
              ]
            }}
          }}
        }}
      ) {{
        ... on PostActionSuccess {{
          post {{
            id
            status
            text
          }}
        }}
        ... on MutationError {{
          message
        }}
      }}
    }}
    """

    result = buffer_query(mutation)
    action = result.get("createPost")

    if not action:
        raise RuntimeError(
            "Buffer returned no createPost result: "
            + json.dumps(result)
        )

    if action.get("message"):
        raise RuntimeError(
            "Buffer rejected the post: " + action["message"]
        )

    post = action.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            "Buffer did not confirm post creation: "
            + json.dumps(action)
        )

    return post


# ---------------- MAIN ----------------

def main():
    require_environment()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if STATE_FILE.exists():
        print(f"Already processed {TODAY}. Skipping duplicate run.")
        return

    print(f"Researching famous Indian birthdays for {TODAY}...")

    result = ask_openai()
    people = validate_people(result)

    if not people:
        print("No sufficiently verified living people found. Nothing posted.")

        STATE_FILE.write_text(
            json.dumps({
                "date": TODAY.isoformat(),
                "status": "no_verified_people",
                "people": []
            }, indent=2),
            encoding="utf-8"
        )
        return

    # One combined thread: three posts per person.
    all_posts = []

    for person in people:
        print(
            f"Verified candidate: {person['name']} "
            f"({person['dob']})"
        )
        all_posts.extend(person["posts"])

    if len(all_posts) > 20:
        raise ValueError("Thread exceeds the configured 20-post limit.")

    if not all(
        len(post) <= MAX_CHARS for post in all_posts
    ):
        raise ValueError("A post exceeds the character limit.")

    print(f"Publishing one thread containing {len(all_posts)} posts...")

    published = publish_thread(all_posts)

    record = {
        "date": TODAY.isoformat(),
        "forecast_year": FORECAST_YEAR,
        "status": "submitted_to_buffer",
        "buffer_post_id": published["id"],
        "buffer_status": published.get("status"),
        "people": people,
        "posts": all_posts,
        "created_at_ist": datetime.now(TZ).isoformat(),
    }

    STATE_FILE.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Buffer accepted the thread.")
    print(f"Buffer post ID: {published['id']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        raise