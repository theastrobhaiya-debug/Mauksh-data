import os
import re
import json
import requests

from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI


# ============================================================
# API KEYS
# ============================================================

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

BUFFER_URL = "https://api.buffer.com"


# ============================================================
# DATE — ALWAYS IST
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

now_ist = datetime.now(IST)

today = now_ist.strftime("%d %B %Y")


# ============================================================
# HISTORY FILE
# ============================================================

HISTORY_FILE = "horoscope_history.json"

MAX_HISTORY = 14


# ============================================================
# LOAD HOROSCOPE HISTORY
# ============================================================

def load_history():

    if not os.path.exists(HISTORY_FILE):
        return []

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, list):
            return []

        return data[-MAX_HISTORY:]

    except Exception as e:

        print(
            "Could not read horoscope history:",
            e
        )

        return []


horoscope_history = load_history()


print("")
print("Previous horoscopes loaded:", len(horoscope_history))


# ============================================================
# PREPARE HISTORY FOR GPT
# ============================================================

def format_history_for_prompt(history):

    if not history:
        return "No previous horoscope history is available."

    formatted = []

    for item in history:

        date = item.get("date", "Unknown date")
        text = item.get("text", "")

        formatted.append(
            f"\n--- HOROSCOPE: {date} ---\n{text}"
        )

    return "\n".join(formatted)


recent_history = format_history_for_prompt(
    horoscope_history
)


# ============================================================
# HOROSCOPE PROMPT
# ============================================================

prompt = f"""
You are the official daily horoscope writer for Mauksh.

Generate today's Vedic astrology-inspired horoscope specifically
for Threads.

Today's date:
{today}


============================================================
RECENT MAUKSH HOROSCOPES
============================================================

The following are recently published Mauksh horoscopes.

They are provided specifically so you can AVOID repeating them.

{recent_history}


============================================================
CORE REQUIREMENT
============================================================

Today's horoscope must feel like a completely new edition.

Do NOT rewrite, paraphrase, recycle or slightly modify predictions
from the previous horoscopes.

If a recent horoscope said that someone may receive a career
opportunity, today's horoscope should NOT simply turn that into
"professional progress" or "a new work opportunity."

It must use a genuinely different situation.

Think in terms of:

NEW EVENT
+
NEW CIRCUMSTANCE
+
NEW CONSEQUENCE


============================================================
FORMAT
============================================================

Daily Horoscope for {today}

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


============================================================
PREDICTION STYLE
============================================================

Write about what could actually happen during the day.

The predictions should feel like observations about likely
developments, situations and events — NOT motivational advice.

GOOD:

"A delayed payment may finally move after an approval or
confirmation arrives."

GOOD:

"Someone who has been quiet about an old disagreement may
bring the subject up again, but this time with a practical
solution."

GOOD:

"A change in someone's schedule could unexpectedly put you
in charge of a task that was not originally yours."

GOOD:

"A purchase you were ready to make may be reconsidered after
you discover a better option or a hidden cost."

BAD:

"Stay positive and trust yourself."

BAD:

"Your career looks promising today."

BAD:

"Good things are coming your way."

BAD:

"You may experience growth and success."

BAD:

"Communication will be important."

The prediction should describe a recognizable situation.


============================================================
EACH SIGN MUST BE DIFFERENT
============================================================

All 12 zodiac signs must have substantially different
primary situations.

Do NOT use the same theme for several signs.

For example, this is NOT acceptable:

Aries — career opportunity
Taurus — career growth
Gemini — work opportunity
Cancer — professional success

Instead, distribute different situations across the signs.

Possible situations include:

- a delayed payment finally moving
- a conversation with a senior person
- an unexpected message
- a family discussion
- a change in travel plans
- a purchase decision
- paperwork being completed
- a meeting changing direction
- reconnecting with someone
- an old issue returning
- an invitation
- a responsibility being handed over
- a disagreement becoming clearer
- a new contact becoming useful
- a household decision
- a learning opportunity
- an examination or application matter
- an administrative issue
- a negotiation
- a refund or reimbursement
- a change in schedule
- a plan being postponed
- information arriving unexpectedly
- someone asking for help
- a decision between two options
- a forgotten task resurfacing
- a social interaction changing your plans


============================================================
DO NOT FORCE THEMES
============================================================

Do not try to mention career, money, love and family in every sign.

Each sign should have its own storyline.

Some signs can be heavily career-focused.

Another can focus on family.

Another can involve money.

Another can involve travel.

Another can involve communication.

Another can involve a decision.

Natural variation is more important than covering every category.


============================================================
MAKE PREDICTIONS CONCRETE
============================================================

Avoid vague statements.

Instead of:

"You may have financial improvement."

Use:

"A pending refund, reimbursement or payment could finally
show movement today."

Instead of:

"You may face a relationship issue."

Use:

"Someone close to you may question a decision you recently
made, leading to a conversation you had been postponing."

Instead of:

"You may have travel changes."

Use:

"A change in timing or transportation could force you to
rearrange part of today's plan."

Instead of:

"You may get an opportunity."

Use:

"Someone may ask you to take responsibility for a task that
was originally assigned to somebody else."


============================================================
EVENT + CONSEQUENCE
============================================================

Whenever possible, each prediction should contain:

1. A concrete event or situation.
2. What that situation could lead to.

Example:

"A delayed payment may finally move after an approval arrives,
allowing you to settle an expense you had been postponing."

Example:

"An unexpected message from someone you have not spoken to
recently may reopen a conversation you thought was finished."


============================================================
VARY SENTENCE STRUCTURE
============================================================

Do NOT start every sign with:

"You may..."

Avoid repetitive structures.

Naturally vary openings such as:

"An unexpected..."
"Someone close to you..."
"A pending..."
"Today's conversation..."
"Later in the day..."
"A decision around..."
"An old..."
"Work may..."
"One practical matter..."
"A message..."
"Something you postponed..."
"A change in..."
"Before the day ends..."


============================================================
AVOID THESE CLICHÉS
============================================================

Do not repeatedly use:

"stay positive"
"stay focused"
"trust yourself"
"be patient"
"avoid distractions"
"keep an open mind"
"good things are coming"
"positive energy"
"new opportunities"
"career growth"
"financial stability"
"emotional clarity"
"believe in yourself"
"you are on the right path"


============================================================
REPETITION RULE
============================================================

Before producing the final answer, internally compare every sign
against the recent horoscopes.

If a prediction is substantially similar to a recent prediction,
replace it.

Do not simply change the wording.

Change the actual situation.


============================================================
ASTROLOGICAL FEEL
============================================================

The horoscope should feel Vedic astrology-inspired.

Do not mention:

- planetary calculations
- degrees
- houses
- nakshatras
- transits
- planetary positions
- astrological reasoning

The reader should simply experience it as a horoscope.


============================================================
LENGTH
============================================================

Each zodiac sign:

- 1–2 short sentences
- specific
- natural
- readable on Threads

Do not make the predictions unnecessarily long.


============================================================
FINAL OUTPUT RULES
============================================================

Do not add hashtags.

Do not add an introduction.

Do not add a conclusion.

Do not add bullet points.

Do not explain your reasoning.

Do not mention these instructions.

Do not mention previous horoscopes.

Do not mention repetition checking.

Return ONLY the finished Threads post.
"""


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# WORD SIMILARITY
# ============================================================

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "your",
    "you",
    "may",
    "could",
    "will",
    "today",
    "this",
    "that",
    "is",
    "be",
    "as",
    "from"
}


def meaningful_words(text):

    normalized = normalize_text(text)

    words = normalized.split()

    return {
        word
        for word in words
        if len(word) >= 4
        and word not in STOPWORDS
    }


def similarity_score(text_a, text_b):

    words_a = meaningful_words(text_a)
    words_b = meaningful_words(text_b)

    if not words_a or not words_b:
        return 0

    intersection = words_a.intersection(words_b)
    union = words_a.union(words_b)

    return len(intersection) / len(union)


# ============================================================
# CHECK AGAINST PREVIOUS HOROSCOPES
# ============================================================

def find_high_similarity(text, history):

    matches = []

    for item in history:

        old_text = item.get("text", "")

        if not old_text:
            continue

        score = similarity_score(
            text,
            old_text
        )

        if score >= 0.38:

            matches.append({
                "date": item.get("date"),
                "score": round(score, 3)
            })

    matches.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return matches


# ============================================================
# CHECK ZODIAC PREDICTION REPETITION
# ============================================================

ZODIAC_SYMBOLS = [
    "♈",
    "♉",
    "♊",
    "♋",
    "♌",
    "♍",
    "♎",
    "♏",
    "♐",
    "♑",
    "♒",
    "♓"
]


def extract_zodiac_lines(text):

    result = {}

    for line in text.splitlines():

        line = line.strip()

        for symbol in ZODIAC_SYMBOLS:

            if line.startswith(symbol):

                result[symbol] = line
                break

    return result


def check_internal_repetition(text):

    predictions = extract_zodiac_lines(text)

    symbols = list(predictions.keys())

    repeated_pairs = []

    for i in range(len(symbols)):

        for j in range(i + 1, len(symbols)):

            first = predictions[symbols[i]]
            second = predictions[symbols[j]]

            score = similarity_score(
                first,
                second
            )

            if score >= 0.45:

                repeated_pairs.append({
                    "first": symbols[i],
                    "second": symbols[j],
                    "score": round(score, 3)
                })

    return repeated_pairs


# ============================================================
# GENERATE HOROSCOPE
# ============================================================

print("")
print("Generating horoscope...")


MAX_GENERATION_ATTEMPTS = 3

horoscope = None


for attempt in range(
    1,
    MAX_GENERATION_ATTEMPTS + 1
):

    print(
        f"Generation attempt {attempt}/{MAX_GENERATION_ATTEMPTS}"
    )

    response = client.responses.create(
        model="gpt-5.6",
        input=prompt
    )

    candidate = response.output_text.strip()

    if not candidate:

        print(
            "OpenAI returned empty output."
        )

        continue


    # --------------------------------------------------------
    # CHECK PREVIOUS HOROSCOPE SIMILARITY
    # --------------------------------------------------------

    similar_matches = find_high_similarity(
        candidate,
        horoscope_history
    )


    # --------------------------------------------------------
    # CHECK SAME-DAY REPETITION
    # --------------------------------------------------------

    internal_repetition = check_internal_repetition(
        candidate
    )


    print(
        "Previous-horoscope similarity matches:",
        len(similar_matches)
    )

    print(
        "Internal repeated-sign pairs:",
        len(internal_repetition)
    )


    # --------------------------------------------------------
    # ACCEPT IF CLEAN
    # --------------------------------------------------------

    if (
        len(similar_matches) == 0
        and len(internal_repetition) <= 1
    ):

        horoscope = candidate

        print(
            "Horoscope passed repetition checks."
        )

        break


    # --------------------------------------------------------
    # REGENERATE WITH STRONGER WARNING
    # --------------------------------------------------------

    print(
        "Horoscope was too repetitive. Regenerating..."
    )

    prompt += f"""

IMPORTANT — REGENERATION REQUIRED

The previous generated version was rejected because it was
too similar to existing Mauksh content.

Do NOT repeat those storylines.

Generate substantially different situations.

Do not merely replace words with synonyms.

Change the actual events, circumstances and consequences.

Previous similarity matches detected:
{similar_matches}

Internal repeated-sign pairs detected:
{internal_repetition}

Generate a completely fresh version.
"""


# ============================================================
# FINAL VALIDATION
# ============================================================

if not horoscope:

    raise RuntimeError(
        "Could not generate a sufficiently original horoscope."
    )


# ============================================================
# BASIC FORMAT CHECK
# ============================================================

missing_signs = []

for symbol in ZODIAC_SYMBOLS:

    if symbol not in horoscope:

        missing_signs.append(symbol)


if missing_signs:

    raise RuntimeError(
        "Horoscope is missing zodiac signs: "
        + ", ".join(missing_signs)
    )


print("")
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


thread_posts = split_into_thread(
    horoscope
)


print("")
print(
    "Thread posts created:",
    len(thread_posts)
)


for i, post in enumerate(
    thread_posts,
    1
):

    print("")
    print(
        f"--- THREAD POST {i} "
        f"({len(post)} chars) ---"
    )

    print(post)


# ============================================================
# BUFFER REQUEST HELPER
# ============================================================

def buffer_request(
    query,
    variables=None
):

    payload = {
        "query": query
    }

    if variables is not None:

        payload["variables"] = variables


    response = requests.post(
        BUFFER_URL,
        headers={
            "Authorization":
                f"Bearer {BUFFER_API_KEY}",
            "Content-Type":
                "application/json",
        },
        json=payload,
        timeout=30,
    )


    response.raise_for_status()


    data = response.json()


    if "errors" in data:

        raise RuntimeError(
            "Buffer API error: "
            + str(data["errors"])
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


organization_data = buffer_request(
    organization_query
)


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
    organizations[0].get(
        "name",
        organization_id
    )
)


# ============================================================
# FIND THREADS CHANNEL
# ============================================================

print(
    "Finding connected Threads channel..."
)


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
        "organizationId":
            organization_id
    }
)


channels = (
    channels_data
    .get("data", {})
    .get("channels", [])
)


threads_channel = None


for channel in channels:

    if (
        str(
            channel.get("service", "")
        ).lower()
        == "threads"
    ):

        threads_channel = channel

        break


if threads_channel is None:

    print(
        "Available Buffer channels:"
    )

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
    or threads_channel.get(
        "displayName"
    )
)


# ============================================================
# CREATE THREAD
# ============================================================

print("")
print(
    "Sending horoscope thread to Buffer..."
)


# ============================================================
# GRAPHQL ESCAPE
# ============================================================

def graphql_escape(value):

    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "\\n")
    )


# ============================================================
# BUILD THREAD ITEMS
# ============================================================

thread_items = []


for post in thread_posts:

    escaped = graphql_escape(post)

    thread_items.append(
        f'{{ text: "{escaped}" }}'
    )


thread_array = "\n".join(
    thread_items
)


first_post = graphql_escape(
    thread_posts[0]
)


# ============================================================
# BUFFER MUTATION
# ============================================================

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


result = buffer_request(
    mutation
)


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
        + str(
            create_result["message"]
        )
    )


post = create_result.get("post")


if not post:

    raise RuntimeError(
        "Buffer did not return a created "
        "thread."
        + str(create_result)
    )


# ============================================================
# SAVE TO HISTORY
# ONLY AFTER BUFFER SUCCESS
# ============================================================

horoscope_history.append({

    "date": today,

    "generated_at": now_ist.isoformat(),

    "text": horoscope,

    "buffer_post_id": post.get("id")

})


horoscope_history = (
    horoscope_history[-MAX_HISTORY:]
)


with open(
    HISTORY_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        horoscope_history,
        file,
        ensure_ascii=False,
        indent=2
    )


print("")
print(
    "Horoscope history updated."
)


# ============================================================
# SUCCESS
# ============================================================

print("")
print("========================================")
print("SUCCESS")
print("========================================")
print(
    "Date:",
    today
)
print(
    "Buffer Post ID:",
    post.get("id")
)
print(
    "Status:",
    post.get("status")
)
print(
    "Thread posts:",
    len(thread_posts)
)
print(
    "History entries:",
    len(horoscope_history)
)
print(
    "Mauksh horoscope sent to Buffer."
)
print("========================================")