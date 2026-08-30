import os
import re
import requests
from datetime import datetime
from openai import OpenAI


# ============================================================
# API KEYS
# ============================================================

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

BUFFER_URL = "https://api.buffer.com"


# ============================================================
# DATE
# ============================================================

today = datetime.now().strftime("%d %B %Y")


# ============================================================
# HOROSCOPE PROMPT
# ============================================================

prompt = f"""
You are the official horoscope writer for Mauksh.

Generate a daily Vedic astrology-inspired horoscope specifically
for Threads.

Date: {today}

FORMAT:

Mauksh Daily Horoscope
{today}

♈ Aries: [prediction]

♉ Taurus: [prediction]

♊ Gemini: [prediction]

♋ Cancer: [prediction]

♌ Leo: [prediction]

♍ Virgo: [prediction]

♎ Libra: [prediction]

♏ Scorpio: [prediction]

♐ Sagittarius: [prediction]

♑ Capricorn: [prediction]

♒ Aquarius: [prediction]

♓ Pisces: [prediction]

WRITING RULES:

- Keep each zodiac sign to 1–2 short sentences.
- Make predictions meaningful and specific.
- Do NOT write generic motivational advice.
- Do NOT use filler such as "stay positive", "good things are coming",
  "believe in yourself", or "avoid distractions".
- Give each zodiac sign a different situation, development, or theme.
- Naturally cover areas such as career, money, relationships, family,
  communication, travel, learning, decisions and opportunities.
- Make the predictions feel like an actual horoscope, not life advice.
- Keep the language natural and human.
- Avoid repeating the same sentence structure for every sign.
- Do not mention planetary calculations or explain the astrology.
- Do not add hashtags.
- Do not add an introduction or conclusion.
- Do not use bullet points.
- Do not change the title.
- Return ONLY the finished Threads post.
"""


# ============================================================
# GENERATE HOROSCOPE
# ============================================================

print("Generating horoscope...")

response = client.responses.create(
    model="gpt-5.6",
    input=prompt
)

horoscope = response.output_text.strip()

if not horoscope:
    raise RuntimeError("OpenAI returned an empty horoscope.")

print("Horoscope generated successfully.")


# ============================================================
# SPLIT HOROSCOPE INTO THREAD POSTS
# ============================================================

def split_into_thread(text, max_chars=480):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    posts = []
    current = ""

    for line in lines:

        # A zodiac line should ideally stay together.
        candidate = (
            line
            if not current
            else current + "\n\n" + line
        )

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            posts.append(current)

        # If a single line itself is too long,
        # split it safely by words.
        if len(line) > max_chars:

            words = line.split()
            chunk = ""

            for word in words:

                candidate_word = (
                    word
                    if not chunk
                    else chunk + " " + word
                )

                if len(candidate_word) <= max_chars:
                    chunk = candidate_word
                else:
                    if chunk:
                        posts.append(chunk)

                    chunk = word

            current = chunk

        else:
            current = line

    if current:
        posts.append(current)

    return posts


thread_posts = split_into_thread(horoscope)

print("")
print("Thread posts created:", len(thread_posts))

for i, post in enumerate(thread_posts, 1):
    print("")
    print(f"--- THREAD POST {i} ({len(post)} chars) ---")
    print(post)


# ============================================================
# BUFFER REQUEST HELPER
# ============================================================

def buffer_request(query, variables=None):

    payload = {
        "query": query
    }

    if variables is not None:
        payload["variables"] = variables

    response = requests.post(
        BUFFER_URL,
        headers={
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise RuntimeError(
            "Buffer API error: " + str(data["errors"])
        )

    return data


# ============================================================
# FIND BUFFER ORGANIZATION
# ============================================================

print("")
print("Finding Buffer organization...")

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

organization_data = buffer_request(organization_query)

organizations = (
    organization_data
    .get("data", {})
    .get("account", {})
    .get("organizations", [])
)

if not organizations:
    raise RuntimeError(
        "No Buffer organization found."
    )

organization_id = organizations[0]["id"]

print(
    "Using Buffer organization:",
    organizations[0].get("name", organization_id)
)


# ============================================================
# FIND THREADS CHANNEL
# ============================================================

print("Finding connected Threads channel...")

channels_query = """
query GetChannels($organizationId: OrganizationId!) {
    channels(
        input: {
            organizationId: $organizationId
        }
    ) {
        id
        name
        displayName
        service
    }
}
"""

channels_data = buffer_request(
    channels_query,
    {
        "organizationId": organization_id
    }
)

channels = (
    channels_data
    .get("data", {})
    .get("channels", [])
)

threads_channel = None

for channel in channels:

    if str(channel.get("service", "")).lower() == "threads":
        threads_channel = channel
        break


if threads_channel is None:

    print("Available Buffer channels:")

    for channel in channels:
        print(
            "-",
            channel.get("service"),
            "|",
            channel.get("name")
            or channel.get("displayName")
        )

    raise RuntimeError(
        "No Threads channel found."
    )


channel_id = threads_channel["id"]

print(
    "Threads channel found:",
    threads_channel.get("name")
    or threads_channel.get("displayName")
)


# ============================================================
# CREATE THREAD
# ============================================================

print("")
print("Sending horoscope thread to Buffer...")


# Escape values for GraphQL.
def graphql_escape(value):
    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "\\n")
    )


thread_items = []

for post in thread_posts:

    escaped = graphql_escape(post)

    thread_items.append(
        f'{{ text: "{escaped}" }}'
    )


thread_array = "\n".join(thread_items)

first_post = graphql_escape(thread_posts[0])


mutation = f"""
mutation CreateThread {{
    createPost(
        input: {{
            text: "{first_post}"
            channelId: "{channel_id}"
            schedulingType: automatic
            mode: shareNow
            metadata: {{
                threads: {{
                    thread: [
                        {thread_array}
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


result = buffer_request(mutation)


# ============================================================
# CHECK RESULT
# ============================================================

create_result = (
    result
    .get("data", {})
    .get("createPost", {})
)

if "message" in create_result:

    raise RuntimeError(
        "Buffer could not create thread: "
        + str(create_result["message"])
    )


post = create_result.get("post")

if not post:

    raise RuntimeError(
        "Buffer did not return a created thread."
        + str(create_result)
    )


# ============================================================
# SUCCESS
# ============================================================

print("")
print("========================================")
print("SUCCESS")
print("========================================")
print("Buffer Post ID:", post.get("id"))
print("Status:", post.get("status"))
print("Thread posts:", len(thread_posts))
print("Mauksh horoscope sent to Buffer.")
print("========================================")