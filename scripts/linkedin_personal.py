import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

import requests
from openai import OpenAI


# ============================================================
# CONFIG
# ============================================================

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
LINKEDIN_ACCESS_TOKEN = os.environ["LINKEDIN_ACCESS_TOKEN"]
LINKEDIN_PERSON_ID = os.environ["LINKEDIN_PERSON_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)

ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = ROOT / "data" / "linkedin_personal_history.json"

HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# CONTENT ROTATION
# ============================================================

CONTENT_TYPES = {
    0: "Motivation + real-life story",
    1: "Failure, setback + lesson",
    2: "Business/life observation",
    3: "Real-life story + mindset lesson",
    4: "Founder/entrepreneur lesson",
    5: "Human behavior, success or relationships",
    6: "Sunday reflection + lesson for the coming week",
}


# ============================================================
# HISTORY
# ============================================================

def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history):
    # Keep the history manageable
    history = history[-100:]

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


history = load_history()


# ============================================================
# DATE
# ============================================================

now = datetime.now()
today = now.strftime("%d %B %Y")
weekday = now.weekday()

content_type = CONTENT_TYPES[weekday]


# ============================================================
# PREVIOUS TOPICS
# ============================================================

previous_topics = [
    item.get("topic", "")
    for item in history
    if item.get("topic")
]

previous_topics_text = "\n".join(
    f"- {topic}" for topic in previous_topics[-40:]
)

if not previous_topics_text:
    previous_topics_text = "No previous topics."


# ============================================================
# STORY SOURCE RULE
# ============================================================

story_rules = """
Use a documented real-life story involving a person,
company, event, historical moment or business situation.

Good examples include:

- entrepreneurs
- founders
- athletes
- creators
- scientists
- investors
- business leaders
- artists
- historical figures
- companies that faced difficult situations
- people who failed before succeeding

Do NOT invent a person, event, quote or achievement.

Do NOT present an invented story as a true story.

Do NOT fabricate direct quotations.

If using a famous story, use only widely established facts.
"""


# ============================================================
# GENERATION PROMPT
# ============================================================

prompt = f"""
You are writing a LinkedIn post for a personal founder/entrepreneur
account.

Date:
{today}

Today's content category:
{content_type}

The account owner wants to build a personal brand around:

- ambition
- business
- entrepreneurship
- failure
- persistence
- decision making
- human behavior
- personal growth
- lessons from real life

The post must feel like a thoughtful human wrote it.

It must NOT sound like an AI motivational post.

{story_rules}

PREVIOUS TOPICS USED:
{previous_topics_text}

IMPORTANT:
Choose a completely different story, lesson and angle from the
previous topics.

Do not recycle famous stories unnecessarily.

Do not repeat the same lesson such as:
"never give up",
"believe in yourself",
"hard work pays off",
"failure is success",
or "keep going".

The insight should come from the actual story.

STYLE:

- Strong opening hook.
- Short paragraphs.
- Natural LinkedIn formatting.
- Conversational but intelligent.
- Personal and reflective.
- No corporate jargon.
- No exaggerated motivational language.
- No fake statistics.
- No fake quotes.
- No clickbait.
- No "Here are 5 lessons..." unless genuinely appropriate.
- Do not sound like a motivational speaker.
- Do not mention that you are AI.
- Do not mention this prompt.
- Do not mention automation.
- Do not mention astrology.
- Do not mention Mauksh unless naturally relevant.
- Avoid emojis unless genuinely useful.
- Maximum approximately 1,300 characters.
- End with a memorable insight or question.
- Add 3–5 relevant LinkedIn hashtags.

IMPORTANT:
The post should make someone stop scrolling because the STORY
is interesting, not because the post is artificially motivational.

Return ONLY the finished LinkedIn post.
"""


# ============================================================
# GENERATE
# ============================================================

print("Generating personal LinkedIn post...")

response = client.responses.create(
    model="gpt-5.6",
    input=prompt
)

post_text = response.output_text.strip()

print("\n------------------------------------------")
print(post_text)
print("------------------------------------------\n")


# ============================================================
# DUPLICATE PROTECTION
# ============================================================

post_hash = hashlib.sha256(
    post_text.lower().encode("utf-8")
).hexdigest()

existing_hashes = {
    item.get("hash")
    for item in history
}

if post_hash in existing_hashes:
    raise RuntimeError(
        "Duplicate post detected. Refusing to publish."
    )


# ============================================================
# LINKEDIN PERSON URN
# ============================================================

person_urn = f"urn:li:person:{LINKEDIN_PERSON_ID}"


# ============================================================
# LINKEDIN API
# ============================================================

url = "https://api.linkedin.com/rest/posts"

headers = {
    "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
    "X-Restli-Protocol-Version": "2.0.0",
    "Linkedin-Version": "202608",
    "Content-Type": "application/json",
}


payload = {
    "author": person_urn,
    "commentary": post_text,
    "visibility": "PUBLIC",
    "distribution": {
        "feedDistribution": "MAIN_FEED",
        "targetEntities": [],
        "thirdPartyDistributionChannels": [],
    },
    "lifecycleState": "PUBLISHED",
    "isReshareDisabledByAuthor": False,
}


print("Publishing to personal LinkedIn account...")


result = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=30,
)


# ============================================================
# ERROR
# ============================================================

if result.status_code not in (200, 201):

    print("\n==========================================")
    print("LINKEDIN API ERROR")
    print("==========================================")
    print("Status:", result.status_code)
    print("Response:", result.text)

    raise RuntimeError(
        f"LinkedIn posting failed: HTTP "
        f"{result.status_code}"
    )


# ============================================================
# SUCCESS
# ============================================================

post_id = result.headers.get("x-restli-id")

history.append(
    {
        "date": today,
        "content_type": content_type,
        "topic": post_text[:180],
        "hash": post_hash,
        "linkedin_post_id": post_id,
    }
)

save_history(history)

print("\n==========================================")
print("SUCCESS")
print("==========================================")
print("Personal LinkedIn post published.")
print("Content type:", content_type)

if post_id:
    print("Post ID:", post_id)

print()