import os
import requests
from datetime import datetime
from openai import OpenAI


# ============================================================
# MAUKSH DAILY CAREER HOROSCOPE — BUFFER
# ============================================================

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
MAUKSH_CAREER_BUFFER_TOKEN = os.environ["MAUKSH_CAREER_BUFFER_TOKEN"]

client = OpenAI(api_key=OPENAI_API_KEY)

BUFFER_URL = "https://api.buffer.com"


# ============================================================
# DATE
# ============================================================

today = datetime.now().strftime("%d %B %Y")


# ============================================================
# GENERATE CAREER HOROSCOPE
# ============================================================

prompt = f"""
You are the official astrology content writer for Mauksh.

Create today's Daily Career Horoscope specifically for
Mauksh's LinkedIn Page.

Date: {today}

Write career-focused Vedic astrology predictions for all
12 zodiac signs.

FORMAT EXACTLY:

Mauksh Daily Career Horoscope
{today}

♈ Aries: prediction

♉ Taurus: prediction

♊ Gemini: prediction

♋ Cancer: prediction

♌ Leo: prediction

♍ Virgo: prediction

♎ Libra: prediction

♏ Scorpio: prediction

♐ Sagittarius: prediction

♑ Capricorn: prediction

♒ Aquarius: prediction

♓ Pisces: prediction


WRITING RULES:

- Write ONLY about career and professional life.
- Write entirely in English.
- Make every zodiac prediction genuinely different.
- Each prediction should be 1–2 concise sentences.
- Base the predictions on Vedic astrology themes.
- Make the predictions specific and meaningful.
- Make them feel like actual horoscope predictions,
  not generic career advice.
- Naturally vary professional themes between signs.

Possible themes include:

promotions,
leadership,
job opportunities,
interviews,
workplace politics,
recognition,
new responsibilities,
career changes,
business decisions,
networking,
communication with seniors,
colleagues,
clients,
projects,
professional reputation,
skill development,
workplace decisions,
career timing,
professional visibility,
competition,
authority,
and long-term career direction.

IMPORTANT:

- Do NOT make every sign about promotion.
- Do NOT make every sign about changing jobs.
- Do NOT make every sign about success.
- Do NOT make every sign about opportunities.
- Do NOT repeat the same theme across multiple signs.
- Do NOT use the same sentence structure for every sign.
- Do NOT use generic motivational language.
- Do NOT say "stay positive".
- Do NOT say "believe in yourself".
- Do NOT say "good things are coming".
- Do NOT use filler.
- Do NOT give general life advice.
- Do NOT discuss love or relationships.
- Do NOT discuss health.
- Do NOT discuss family.
- Do NOT discuss general lifestyle.
- Do NOT mention planetary calculations.
- Do NOT explain the astrology.
- Do NOT add hashtags.
- Do NOT add a conclusion.
- Do NOT add an introduction.
- Do NOT use bullet points.
- Do NOT add emojis other than the zodiac symbols already
  shown in the required format.
- Keep the exact title and date format.
- Keep the post concise enough for LinkedIn.
- Make the writing natural, human and professional.
- Make today's predictions substantially different from
  previous days rather than recycling the same wording.

Return ONLY the finished LinkedIn post.
"""


# ============================================================
# GENERATE
# ============================================================

print("Generating Mauksh Daily Career Horoscope...")

response = client.responses.create(
    model="gpt-5.6",
    input=prompt
)

post_text = response.output_text.strip()


print()
print("HOROSCOPE GENERATED")
print("------------------------------------------")
print(post_text)
print("------------------------------------------")
print()


# ============================================================
# BUFFER HEADERS
# ============================================================

headers = {
    "Authorization": f"Bearer {MAUKSH_CAREER_BUFFER_TOKEN}",
    "Content-Type": "application/json"
}


# ============================================================
# STEP 1 — GET BUFFER ORGANIZATION
# ============================================================

print("Getting Buffer organization...")

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

organization_result = requests.post(
    BUFFER_URL,
    headers=headers,
    json={
        "query": organization_query
    },
    timeout=30
)


if organization_result.status_code != 200:

    print()
    print("==========================================")
    print("BUFFER ORGANIZATION ERROR")
    print("==========================================")
    print("Status Code:", organization_result.status_code)
    print("Response:", organization_result.text)
    print("==========================================")

    raise RuntimeError(
        "Could not retrieve Buffer organization."
    )


organization_data = organization_result.json()


if "errors" in organization_data:

    print()
    print("==========================================")
    print("BUFFER ORGANIZATION GRAPHQL ERROR")
    print("==========================================")
    print(organization_data)
    print("==========================================")

    raise RuntimeError(
        "Buffer organization lookup failed."
    )


organizations = (
    organization_data
    .get("data", {})
    .get("account", {})
    .get("organizations", [])
)


if not organizations:

    raise RuntimeError(
        "No Buffer organization found for this API token."
    )


# Use the first organization
organization_id = organizations[0]["id"]

print("Buffer Organization:")
print(organizations[0].get("name"))
print("Organization ID:", organization_id)


# ============================================================
# STEP 2 — GET CONNECTED CHANNELS
# ============================================================

print()
print("Getting Buffer channels...")


channels_query = f"""
query GetChannels {{
    channels(
        input: {{
            organizationId: "{organization_id}"
        }}
    ) {{
        id
        name
        displayName
        service
    }}
}}
"""


channels_result = requests.post(
    BUFFER_URL,
    headers=headers,
    json={
        "query": channels_query
    },
    timeout=30
)


if channels_result.status_code != 200:

    print()
    print("==========================================")
    print("BUFFER CHANNEL ERROR")
    print("==========================================")
    print("Status Code:", channels_result.status_code)
    print("Response:", channels_result.text)
    print("==========================================")

    raise RuntimeError(
        "Could not retrieve Buffer channels."
    )


channels_data = channels_result.json()


if "errors" in channels_data:

    print()
    print("==========================================")
    print("BUFFER CHANNEL GRAPHQL ERROR")
    print("==========================================")
    print(channels_data)
    print("==========================================")

    raise RuntimeError(
        "Buffer channel lookup failed."
    )


channels = (
    channels_data
    .get("data", {})
    .get("channels", [])
)


if not channels:

    raise RuntimeError(
        "No Buffer channels found."
    )


# ============================================================
# ONE CHANNEL
# ============================================================

if len(channels) > 1:

    print()
    print("WARNING:")
    print(
        f"Buffer returned {len(channels)} channels."
    )
    print("Using the first channel.")


channel = channels[0]

channel_id = channel["id"]

print()
print("Buffer Channel:")
print("Name:", channel.get("name"))
print("Display Name:", channel.get("displayName"))
print("Service:", channel.get("service"))
print("Channel ID:", channel_id)


# ============================================================
# STEP 3 — CREATE BUFFER POST
# ============================================================

print()
print("Publishing to Buffer...")


create_post_query = """
mutation CreatePost($input: CreatePostInput!) {

    createPost(input: $input) {

        ... on PostActionSuccess {
            post {
                id
                text
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
        "text": post_text,
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "addToQueue"
    }
}


create_post_result = requests.post(
    BUFFER_URL,
    headers=headers,
    json={
        "query": create_post_query,
        "variables": variables
    },
    timeout=30
)


# ============================================================
# HTTP ERROR
# ============================================================

if create_post_result.status_code != 200:

    print()
    print("==========================================")
    print("BUFFER POST HTTP ERROR")
    print("==========================================")
    print("Status Code:", create_post_result.status_code)
    print("Response:", create_post_result.text)
    print("==========================================")

    raise RuntimeError(
        f"Buffer posting failed with HTTP "
        f"{create_post_result.status_code}"
    )


buffer_data = create_post_result.json()


# ============================================================
# GRAPHQL ERROR
# ============================================================

if "errors" in buffer_data:

    print()
    print("==========================================")
    print("BUFFER GRAPHQL ERROR")
    print("==========================================")
    print(buffer_data)
    print("==========================================")

    raise RuntimeError(
        "Buffer posting failed."
    )


# ============================================================
# RESPONSE
# ============================================================

create_post_data = (
    buffer_data
    .get("data", {})
    .get("createPost")
)


if not create_post_data:

    raise RuntimeError(
        f"Unexpected Buffer response: {buffer_data}"
    )


# ============================================================
# BUFFER MUTATION ERROR
# ============================================================

if "message" in create_post_data:

    print()
    print("==========================================")
    print("BUFFER POST ERROR")
    print("==========================================")
    print(create_post_data["message"])
    print("==========================================")

    raise RuntimeError(
        create_post_data["message"]
    )


# ============================================================
# SUCCESS
# ============================================================

post = create_post_data.get("post")


if not post:

    raise RuntimeError(
        f"Buffer did not return a post: {buffer_data}"
    )


print()
print("==========================================")
print("SUCCESS")
print("==========================================")
print("Mauksh Daily Career Horoscope was")
print("successfully added to Buffer.")
print()

print("Buffer Post ID:", post.get("id"))
print("Buffer Due At:", post.get("dueAt"))

print()
print("POST:")
print("------------------------------------------")
print(post_text)
print("------------------------------------------")
