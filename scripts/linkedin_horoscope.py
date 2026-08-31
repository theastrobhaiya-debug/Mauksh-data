import os
import requests
from datetime import datetime
from openai import OpenAI


# ============================================================
# MAUKSH DAILY CAREER HOROSCOPE — LINKEDIN
# ============================================================

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
LINKEDIN_ACCESS_TOKEN = os.environ["LINKEDIN_ACCESS_TOKEN"]
LINKEDIN_ORGANIZATION_ID = os.environ["LINKEDIN_ORGANIZATION_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)


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
# LINKEDIN ORGANIZATION
# ============================================================

organization_urn = (
    f"urn:li:organization:{LINKEDIN_ORGANIZATION_ID}"
)

print("LinkedIn Organization:")
print(organization_urn)


# ============================================================
# LINKEDIN POSTS API
# ============================================================

url = "https://api.linkedin.com/rest/posts"

headers = {
    "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
    "X-Restli-Protocol-Version": "2.0.0",
    "Linkedin-Version": "202608",
    "Content-Type": "application/json"
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


print("Publishing to Mauksh LinkedIn Page...")


result = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=30
)


# ============================================================
# ERROR HANDLING
# ============================================================

if result.status_code not in (200, 201):

    print()
    print("==========================================")
    print("LINKEDIN API ERROR")
    print("==========================================")
    print("Status Code:", result.status_code)
    print("Response:", result.text)
    print()

    raise RuntimeError(
        f"LinkedIn posting failed with HTTP "
        f"{result.status_code}"
    )


# ============================================================
# SUCCESS
# ============================================================

print()
print("==========================================")
print("SUCCESS")
print("==========================================")
print("Mauksh Daily Career Horoscope was posted")
print("successfully to LinkedIn.")
print()

post_id = result.headers.get("x-restli-id")

if post_id:
    print("LinkedIn Post ID:", post_id)

print()
print(post_text)
