import os
import requests
from datetime import datetime
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]


client = OpenAI(api_key=OPENAI_API_KEY)

BUFFER_URL = "https://api.buffer.com"


# ============================================================
# GENERATE HOROSCOPE
# ============================================================

today = datetime.now().strftime("%d %B %Y")

prompt = f"""
You are the official horoscope writer for Mauksh.

Generate a daily Vedic astrology-inspired horoscope specifically for Threads.

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
- Do NOT use filler such as "stay positive", "good things are coming", "believe in yourself", or "avoid distractions".
- Give each zodiac sign a different situation, development, or theme.
- Naturally cover areas such as career, money, relationships, family, communication, travel, learning, decisions and opportunities.
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
# BUFFER GRAPHQL HELPER
# ============================================================

def buffer_request(query):
    response = requests.post(
        BUFFER_URL,
        headers={
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "query": query
        },
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
        "No Buffer organization found. "
        "Make sure your Buffer account and API key are correct."
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

channels_query = f"""
query {{
    channels(
        input: {{
            organizationId: "{organization_id}"
        }}
    ) {{
        id
        name
        displayName
        service
        descriptor
    }}
}}
"""

channels_data = buffer_request(channels_query)

channels = (
    channels_data
    .get("data", {})
    .get("channels", [])
)

threads_channels = [
    channel
    for channel in channels
    if str(channel.get("service", "")).lower() == "threads"
]

if not threads_channels:
    print("Connected Buffer channels:")

    for channel in channels:
        print(
            f"- {channel.get('service')}: "
            f"{channel.get('name') or channel.get('displayName')}"
        )

    raise RuntimeError(
        "No Threads channel was found in Buffer. "
        "Connect your Threads account to Buffer first."
    )

threads_channel = threads_channels[0]

channel_id = threads_channel["id"]

print(
    "Threads channel found:",
    threads_channel.get("name")
    or threads_channel.get("displayName")
    or threads_channels[0].get("descriptor")
)


# ============================================================
# CREATE BUFFER POST
# ============================================================

print("Sending horoscope to Buffer...")

# GraphQL strings need escaped quotes/backslashes.
safe_horoscope = (
    horoscope
    .replace("\\", "\\\\")
    .replace('"', '\\"')
    .replace("\r", "")
    .replace("\n", "\\n")
)

post_mutation = f"""
mutation {{
    createPost(
        input: {{
            text: "{safe_horoscope}"
            channelId: "{channel_id}"
            schedulingType: automatic
            mode: shareNow
        }}
    ) {{
        ... on PostActionSuccess {{
            post {{
                id
                text
                dueAt
                status
            }}
        }}

        ... on MutationError {{
            message
        }}
    }}
}}
"""

post_data = buffer_request(post_mutation)

create_post_result = (
    post_data
    .get("data", {})
    .get("createPost", {})
)

if "message" in create_post_result:
    raise RuntimeError(
        "Buffer could not create the post: "
        + str(create_post_result["message"])
    )

post = create_post_result.get("post")

if not post:
    raise RuntimeError(
        "Buffer did not return a created post."
        + str(create_post_result)
    )

print("========================================")
print("SUCCESS")
print("========================================")
print("Buffer Post ID:", post.get("id"))
print("Status:", post.get("status"))
print("Due At:", post.get("dueAt"))
print("The horoscope has been sent to Buffer.")
print("========================================")