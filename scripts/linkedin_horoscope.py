import os
import requests
from datetime import datetime
from openai import OpenAI

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
LINKEDIN_ACCESS_TOKEN = os.environ["LINKEDIN_ACCESS_TOKEN"]

client = OpenAI(api_key=OPENAI_API_KEY)

today = datetime.now().strftime("%d %B %Y")

prompt = f"""
You are the official horoscope writer for Mauksh.

Write today's Daily Vedic Astrology Horoscope for LinkedIn.

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

- Give every zodiac sign a genuinely different prediction.
- Each prediction should be 1–2 concise sentences.
- Base the writing on Vedic astrology themes.
- Make predictions specific and meaningful.
- Naturally cover career, money, relationships, family,
  communication, travel, learning, decisions and opportunities.
- Do not make every sign about the same theme.
- Do not repeat yesterday's style or wording.
- Write naturally and humanly.
- This is a horoscope, not motivational advice.
- Do not use generic filler.
- Do not say "stay positive", "believe in yourself",
  "good things are coming", etc.
- Do not mention planetary calculations.
- Do not add hashtags.
- Do not add an introduction or conclusion.
- Do not use bullet points.
- Keep the exact title and date format.
- Return ONLY the finished LinkedIn post.
"""

response = client.responses.create(
    model="gpt-5.6",
    input=prompt
)

post_text = response.output_text.strip()

# Find Mauksh LinkedIn organization
lookup_url = "https://api.linkedin.com/rest/organizations"

headers = {
    "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
    "X-Restli-Protocol-Version": "2.0.0",
    "Linkedin-Version": "202608",
}

params = {
    "q": "vanityName",
    "vanityName": "mauksh",
}

lookup = requests.get(
    lookup_url,
    headers=headers,
    params=params,
    timeout=30
)

lookup.raise_for_status()

data = lookup.json()

elements = data.get("elements", [])

if not elements:
    raise RuntimeError("Mauksh LinkedIn organization was not found.")

organization_id = elements[0]["id"]

organization_urn = f"urn:li:organization:{organization_id}"

# Create LinkedIn post
post_url = "https://api.linkedin.com/rest/posts"

post_headers = {
    "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
    "X-Restli-Protocol-Version": "2.0.0",
    "Linkedin-Version": "202608",
    "Content-Type": "application/json",
}

payload = {
    "author": organization_urn,
    "commentary": post_text,
    "visibility": "PUBLIC",
    "distribution": {
        "feedDistribution": "MAIN_FEED",
        "targetEntities": [],
        "thirdPartyDistributionChannels": []
    },
    "lifecycleState": "PUBLISHED",
    "isReshareDisabledByAuthor": False
}

post = requests.post(
    post_url,
    headers=post_headers,
    json=payload,
    timeout=30
)

if not post.ok:
    print("LinkedIn response:")
    print(post.text)

post.raise_for_status()

print("Successfully posted Daily Horoscope to Mauksh LinkedIn Page.")
print(post_text)