import json
import os
import time
import textwrap
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont


# ==================================================
# MAUKSH DAILY MULANK HOROSCOPE
# ==================================================

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ)

WIDTH, HEIGHT = 1080, 1350

GOLD = (255, 210, 70)
DARK = (45, 29, 8)
CARD = (255, 246, 215)
ACCENT = (218, 157, 22)

OUTPUT_PATH = "/tmp/mauksh_daily_mulank.jpg"


MULANKS = [
    (1, "1, 10, 19, 28"),
    (2, "2, 11, 20, 29"),
    (3, "3, 12, 21, 30"),
    (4, "4, 13, 22, 31"),
    (5, "5, 14, 23"),
    (6, "6, 15, 24"),
    (7, "7, 16, 25"),
    (8, "8, 17, 26"),
    (9, "9, 18, 27"),
]


# ==================================================
# FONTS
# ==================================================

def get_font(size, bold=False):

    candidates = [
        "/usr/share/fonts/truetype/dejavu/"
        + (
            "DejaVuSans-Bold.ttf"
            if bold
            else "DejaVuSans.ttf"
        ),

        "/usr/share/fonts/truetype/liberation2/"
        + (
            "LiberationSans-Bold.ttf"
            if bold
            else "LiberationSans-Regular.ttf"
        ),
    ]

    for path in candidates:

        if os.path.exists(path):

            return ImageFont.truetype(
                path,
                size
            )

    return ImageFont.load_default()


# ==================================================
# MULANK CALCULATION
# ==================================================

def reduce_to_single_digit(number):

    while number > 9:

        number = sum(
            int(digit)
            for digit in str(number)
        )

    return number


def calculate_daily_number(date):

    total = (
        date.day
        + date.month
        + date.year
    )

    return reduce_to_single_digit(total)


# ==================================================
# OPENAI
# GENERATE 9 ORIGINAL MULANK HOROSCOPES
# ==================================================

def generate_horoscopes():

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"]
    )

    date_text = TODAY.strftime(
        "%d %B %Y"
    )

    daily_number = calculate_daily_number(
        TODAY
    )

    mulank_names = [
        str(number)
        for number, _ in MULANKS
    ]

    prompt = f"""
You are an experienced Vedic numerology writer
creating daily numerology guidance for the Mauksh brand.

DATE:
{date_text}

DAILY NUMEROLOGY NUMBER:
{daily_number}

SYSTEM:
Use Vedic / Indian numerology principles.

TASK:
Generate one original daily horoscope for each
Mulank from 1 to 9.

MULANK MEANING:
Mulank is calculated from the day of birth only.

1 = born on 1, 10, 19, 28
2 = born on 2, 11, 20, 29
3 = born on 3, 12, 21, 30
4 = born on 4, 13, 22, 31
5 = born on 5, 14, 23
6 = born on 6, 15, 24
7 = born on 7, 16, 25
8 = born on 8, 17, 26
9 = born on 9, 18, 27

NUMEROLOGY GUIDELINES:

1. Interpret the day's numerological influence
   through each Mulank.

2. Consider traditional Vedic numerology
   characteristics of each Mulank.

3. Do not invent specific planetary positions,
   transits, conjunctions, nakshatras or
   astronomical events.

4. Do not claim guaranteed outcomes.

5. Keep the guidance practical and useful.

6. The prediction should feel specifically
   different for each Mulank.

STRICT NON-REPETITION:

Review all 9 predictions together.

Do not copy or paraphrase one Mulank prediction
for another.

Every Mulank must have a distinct central theme.

Avoid repeated openings.

Avoid repeated sentence structures.

Avoid generic recycled horoscope clichés.

Do not simply replace a few words between predictions.

If two predictions feel similar, rewrite them.

STYLE:

English only.

Each horoscope must contain 18–24 words.

Warm.

Practical.

Grounded.

Encouraging.

Thoughtful.

Focus on:

career
money
relationships
communication
decisions
personal growth

Do not mention planet names.

Do not mention numerological calculations
inside the prediction.

Do not use fear.

Do not make guaranteed predictions.

No Hindi.

No Hinglish.

No emojis.

No hashtags.

No Markdown.

Return exactly 9 entries in this order:

{json.dumps(mulank_names)}

Return ONLY valid JSON.

Format:

{{
  "horoscopes": [
    {{
      "mulank": 1,
      "text": "Daily guidance."
    }},
    {{
      "mulank": 2,
      "text": "Daily guidance."
    }}
  ]
}}

Include all 9 Mulanks.
"""

    response = client.responses.create(
        model=os.getenv(
            "OPENAI_MODEL",
            "gpt-5-mini"
        ),
        input=prompt,
    )

    raw = response.output_text.strip()

    if raw.startswith("```"):

        raw = (
            raw
            .split("\n", 1)[1]
            .rsplit("```", 1)[0]
            .strip()
        )

    data = json.loads(raw)

    horoscopes = data.get(
        "horoscopes",
        []
    )

    if (
        not isinstance(horoscopes, list)
        or len(horoscopes) != 9
    ):

        raise ValueError(
            "Expected exactly 9 Mulank horoscopes."
        )

    for index, item in enumerate(
        horoscopes
    ):

        expected_mulank = MULANKS[index][0]

        if not isinstance(item, dict):

            raise ValueError(
                "Invalid horoscope entry."
            )

        actual_mulank = int(
            item.get(
                "mulank",
                0
            )
        )

        if actual_mulank != expected_mulank:

            raise ValueError(
                f"Expected Mulank "
                f"{expected_mulank} "
                f"at position "
                f"{index + 1}."
            )

        text = str(
            item.get(
                "text",
                ""
            )
        ).strip()

        word_count = len(
            text.split()
        )

        if not 18 <= word_count <= 24:

            raise ValueError(
                f"Mulank {expected_mulank} "
                f"has {word_count} words; "
                "expected 18–24."
            )

        item["mulank"] = expected_mulank
        item["text"] = text

    print(
        f"Generated and validated 9 Mulank "
        f"horoscopes for {date_text}."
    )

    return horoscopes


# ==================================================
# CREATE GOLDEN MAUKSH IMAGE
# ==================================================

def create_poster(horoscopes):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        GOLD
    )

    draw = ImageDraw.Draw(image)

    # Decorative arcs
    draw.arc(
        (-180, -180, 250, 250),
        0,
        270,
        fill=(232, 168, 30),
        width=5
    )

    draw.arc(
        (850, 1130, 1260, 1540),
        180,
        360,
        fill=(232, 168, 30),
        width=5
    )

    # Header
    draw.text(
        (WIDTH // 2, 22),
        "mauksh.com",
        font=get_font(43, True),
        fill=DARK,
        anchor="mt",
    )

    draw.text(
        (WIDTH // 2, 73),
        "SPIRITUALITY IS PERSONAL",
        font=get_font(17, True),
        fill=DARK,
        anchor="mt",
    )

    draw.text(
        (WIDTH // 2, 116),
        "MAUKSH DAILY NUMEROLOGY",
        font=get_font(40, True),
        fill=DARK,
        anchor="mt",
    )

    draw.text(
        (WIDTH // 2, 176),
        f"FOR {TODAY.strftime('%d %B %Y').upper()}",
        font=get_font(27, True),
        fill=DARK,
        anchor="mt",
    )

    draw.text(
        (WIDTH // 2, 221),
        "MULANK 1 – 9  |  DAILY GUIDANCE",
        font=get_font(17, True),
        fill=DARK,
        anchor="mt",
    )

    # Cards
    margin_x = 55
    gap_x = 14

    card_w = (
        WIDTH
        - 2 * margin_x
        - 2 * gap_x
    ) // 3

    top = 270
    gap_y = 12
    card_h = 290

    for index, item in enumerate(
        horoscopes
    ):

        col = index % 3
        row = index // 3

        x = (
            margin_x
            + col * (
                card_w + gap_x
            )
        )

        y = (
            top
            + row * (
                card_h + gap_y
            )
        )

        draw.rounded_rectangle(
            (
                x,
                y,
                x + card_w,
                y + card_h
            ),
            radius=18,
            fill=CARD,
            outline=(255, 255, 255),
            width=2,
        )

        mulank = item["mulank"]

        birth_dates = dict(
            MULANKS
        )[mulank]

        draw.text(
            (
                x + card_w // 2,
                y + 12
            ),
            f"MULANK {mulank}",
            font=get_font(23, True),
            fill=DARK,
            anchor="mt",
        )

        draw.text(
            (
                x + card_w // 2,
                y + 47
            ),
            f"Born on {birth_dates}",
            font=get_font(12, True),
            fill=DARK,
            anchor="mt",
        )

        draw.line(
            (
                x + card_w // 2 - 24,
                y + 70,
                x + card_w // 2 + 24,
                y + 70,
            ),
            fill=ACCENT,
            width=3,
        )

        lines = textwrap.wrap(
            str(item["text"]).strip(),
            width=26,
            break_long_words=True,
        )

        if len(lines) > 8:

            lines = lines[:8]

            lines[-1] = (
                lines[-1]
                .rstrip(" .,;:")
                + "..."
            )

        yy = y + 88

        for line in lines:

            draw.text(
                (x + 17, yy),
                line,
                font=get_font(16),
                fill=DARK,
            )

            yy += 25

    # Footer
    draw.text(
        (WIDTH // 2, 1239),
        "mauksh.com",
        font=get_font(31, True),
        fill=DARK,
        anchor="mt",
    )

    draw.text(
        (WIDTH // 2, 1283),
        "NUMEROLOGY  |  SELF GROWTH  |  A BETTER YOU",
        font=get_font(14, True),
        fill=DARK,
        anchor="mt",
    )

    image.save(
        OUTPUT_PATH,
        "JPEG",
        quality=94,
        optimize=True
    )

    print(
        "Poster created:",
        OUTPUT_PATH
    )

    return OUTPUT_PATH


# ==================================================
# BUFFER GRAPHQL HELPER
# ==================================================

def buffer_graphql(
    access_token,
    query,
    variables=None
):

    response = requests.post(
        "https://api.buffer.com",
        headers={
            "Authorization":
                "Bearer " + access_token,

            "Content-Type":
                "application/json",
        },

        json={
            "query": query,
            "variables":
                variables or {},
        },

        timeout=60,
    )

    response.raise_for_status()

    result = response.json()

    if result.get("errors"):

        raise RuntimeError(
            "Buffer API error: "
            + json.dumps(
                result["errors"]
            )
        )

    return result.get(
        "data",
        {}
    )


# ==================================================
# FIND CHANNEL
# ==================================================

def get_channel_id(
    access_token,
    service,
    platform_name
):

    organizations_query = """
    query GetOrganizations {
      account {
        organizations {
          id
          name
        }
      }
    }
    """

    data = buffer_graphql(
        access_token,
        organizations_query
    )

    organizations = (
        data
        .get("account", {})
        .get(
            "organizations",
            []
        )
    )

    matching_channels = []

    for organization in organizations:

        organization_id = (
            organization["id"]
        )

        channels_query = """
        query GetChannels(
          $organizationId: OrganizationId!
        ) {
          channels(
            input: {
              organizationId: $organizationId
            }
          ) {
            id
            name
            service
          }
        }
        """

        channel_data = buffer_graphql(
            access_token,
            channels_query,
            {
                "organizationId":
                    organization_id
            },
        )

        for channel in channel_data.get(
            "channels",
            []
        ):

            channel_service = str(
                channel.get(
                    "service",
                    ""
                )
            ).lower()

            if (
                channel_service
                == service.lower()
            ):

                matching_channels.append(
                    channel
                )

    if len(matching_channels) != 1:

        raise RuntimeError(
            f"Expected exactly one "
            f"{platform_name} channel; "
            f"found "
            f"{len(matching_channels)}."
        )

    channel = matching_channels[0]

    print(
        f"Selected {platform_name} channel:",
        channel.get(
            "name",
            platform_name
        )
    )

    return channel["id"]


# ==================================================
# CHANNELS
# ==================================================

def get_instagram_channel_id():

    return get_channel_id(
        os.environ[
            "BUFFER_ACCESS_TOKEN"
        ],
        "instagram",
        "Instagram"
    )


def get_x_channel_id():

    return get_channel_id(
        os.environ[
            "BUFFER_X_ACCESS_TOKEN"
        ],
        "twitter",
        "X"
    )


def get_threads_channel_id():

    return get_channel_id(
        os.environ[
            "BUFFER_API_KEY"
        ],
        "threads",
        "Threads"
    )


# ==================================================
# UPLOAD IMAGE TO PICRD
# ==================================================

def upload_to_picrd(
    image_path
):

    with open(
        image_path,
        "rb"
    ) as file:

        response = requests.post(
            "https://picrd.com/api/upload",

            files={
                "file": (
                    "mauksh_daily_mulank.jpg",
                    file,
                    "image/jpeg",
                )
            },

            data={
                "visibility":
                    "unlisted",

                "ttl_seconds":
                    "86400",
            },

            timeout=60,
        )

    response.raise_for_status()

    result = response.json()

    image_url = result.get(
        "image_url"
    )

    delete_url = result.get(
        "delete_url"
    )

    if not image_url:

        raise RuntimeError(
            "Image host did not return "
            "image_url: "
            + json.dumps(result)
        )

    print(
        "Image uploaded to temporary hosting."
    )

    return image_url, delete_url


# ==================================================
# INSTAGRAM
# ==================================================

def publish_to_instagram(
    image_url
):

    access_token = os.environ[
        "BUFFER_ACCESS_TOKEN"
    ]

    channel_id = (
        get_instagram_channel_id()
    )

    caption = (
        f"Mauksh Daily Numerology "
        f"for {TODAY.strftime('%d %B %Y')}\n\n"

        "Find your Mulank from your birth date "
        "and read today's guidance.\n\n"

        "Save this post for later.\n\n"

        "#Mauksh #Mulank "
        "#Numerology #DailyNumerology"
    )

    mutation = """
    mutation CreatePost(
      $input: CreatePostInput!
    ) {
      createPost(input: $input) {

        ... on PostActionSuccess {
          post {
            id
            text
            status
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

            "text":
                caption,

            "channelId":
                channel_id,

            "schedulingType":
                "automatic",

            "mode":
                "shareNow",

            "assets": [

                {
                    "image": {
                        "url":
                            image_url
                    }
                }

            ],

            "metadata": {

                "instagram": {

                    "type":
                        "post",

                    "shouldShareToFeed":
                        True,
                }
            },
        }
    }

    data = buffer_graphql(
        access_token,
        mutation,
        variables
    )

    result = data.get(
        "createPost",
        {}
    )

    if result.get("message"):

        raise RuntimeError(
            "Buffer rejected Instagram post: "
            + result["message"]
        )

    post = result.get(
        "post"
    )

    if not post or not post.get("id"):

        raise RuntimeError(
            "Buffer did not return Instagram "
            "post ID: "
            + json.dumps(data)
        )

    print(
        "Instagram Buffer post ID:",
        post["id"]
    )

    return post


# ==================================================
# MULANK SYMBOLS
# ==================================================

MULANK_SYMBOLS = {
    1: "1",
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
}


# ==================================================
# CREATE THREAD ITEMS
# ==================================================

def create_thread_items(
    horoscopes,
    platform
):

    thread_posts = []

    # Root
    first = horoscopes[0]

    first_text = (
        f"Mauksh Daily Numerology — "
        f"{TODAY.strftime('%d %B %Y')}\n\n"

        f"Mulank {first['mulank']}\n\n"

        f"{first['text']}"
    )

    thread_posts.append(
        {
            "text":
                first_text
        }
    )

    # Remaining
    for item in horoscopes[1:]:

        mulank = item["mulank"]

        post_text = (
            f"Mulank {mulank}\n\n"
            f"{item['text']}"
        )

        thread_posts.append(
            {
                "text":
                    post_text
            }
        )

    # Final post
    thread_posts[-1]["text"] += (

        "\n\n"
        "Take what feels useful. "
        "Numerology is guidance, not certainty.\n\n"
        "#Mauksh #Mulank"
    )

    # X validation
    if platform == "x":

        for item in thread_posts:

            if len(
                item["text"]
            ) > 280:

                raise ValueError(
                    "X post exceeds 280 characters: "
                    + item["text"]
                )

    return thread_posts


# ==================================================
# PUBLISH X THREAD
# ==================================================

def publish_to_x(
    horoscopes
):

    access_token = os.environ[
        "BUFFER_X_ACCESS_TOKEN"
    ]

    channel_id = (
        get_x_channel_id()
    )

    thread_posts = create_thread_items(
        horoscopes,
        "x"
    )

    print(
        "\n========== X THREAD ==========\n"
    )

    for index, item in enumerate(
        thread_posts
    ):

        print(
            f"X [{index + 1}/"
            f"{len(thread_posts)}] "
            f"{len(item['text'])} characters"
        )

    mutation = """
    mutation CreateThread(
      $input: CreatePostInput!
    ) {
      createPost(input: $input) {

        ... on PostActionSuccess {
          post {
            id
            text
            status
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

            "text":
                thread_posts[0]["text"],

            "channelId":
                channel_id,

            "schedulingType":
                "automatic",

            "mode":
                "shareNow",

            "metadata": {

                "twitter": {

                    "thread":
                        thread_posts
                }
            }
        }
    }

    data = buffer_graphql(
        access_token,
        mutation,
        variables
    )

    result = data.get(
        "createPost",
        {}
    )

    if result.get("message"):

        raise RuntimeError(
            "Buffer rejected X thread: "
            + result["message"]
        )

    post = result.get(
        "post"
    )

    if not post or not post.get("id"):

        raise RuntimeError(
            "Buffer did not return X thread ID: "
            + json.dumps(data)
        )

    print(
        "X Buffer thread ID:",
        post["id"]
    )

    return post


# ==================================================
# PUBLISH THREADS THREAD
# ==================================================

def publish_to_threads(
    horoscopes
):

    access_token = os.environ[
        "BUFFER_API_KEY"
    ]

    channel_id = (
        get_threads_channel_id()
    )

    thread_posts = create_thread_items(
        horoscopes,
        "threads"
    )

    print(
        "\n======= THREADS THREAD =======\n"
    )

    for index, item in enumerate(
        thread_posts
    ):

        print(
            f"Threads [{index + 1}/"
            f"{len(thread_posts)}] "
            f"{len(item['text'])} characters"
        )

    mutation = """
    mutation CreateThreadsThread(
      $input: CreatePostInput!
    ) {
      createPost(input: $input) {

        ... on PostActionSuccess {
          post {
            id
            text
            status
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

            "text":
                thread_posts[0]["text"],

            "channelId":
                channel_id,

            "schedulingType":
                "automatic",

            "mode":
                "shareNow",

            "metadata": {

                "threads": {

                    "thread":
                        thread_posts
                }
            }
        }
    }

    data = buffer_graphql(
        access_token,
        mutation,
        variables
    )

    result = data.get(
        "createPost",
        {}
    )

    if result.get("message"):

        raise RuntimeError(
            "Buffer rejected Threads thread: "
            + result["message"]
        )

    post = result.get(
        "post"
    )

    if not post or not post.get("id"):

        raise RuntimeError(
            "Buffer did not return Threads "
            "thread ID: "
            + json.dumps(data)
        )

    print(
        "Threads Buffer thread ID:",
        post["id"]
    )

    return post


# ==================================================
# WAIT FOR PUBLICATION
# ==================================================

def wait_until_published(
    post_id,
    access_token,
    platform_name,
    timeout_seconds=900
):

    query = """
    query GetPost($id: PostId!) {

      post(input: { id: $id }) {

        id
        status
        sentAt

      }
    }
    """

    deadline = (
        time.time()
        + timeout_seconds
    )

    while time.time() < deadline:

        data = buffer_graphql(
            access_token,
            query,
            {
                "id":
                    post_id
            }
        )

        post = data.get(
            "post"
        )

        if post:

            status = str(
                post.get(
                    "status",
                    ""
                )
            ).lower()

            print(
                f"{platform_name} "
                f"status: {status}"
            )

            if (
                status == "sent"
                or post.get("sentAt")
            ):

                return True

            if status in (
                "error",
                "failed"
            ):

                return False

        time.sleep(20)

    return False


# ==================================================
# CLEANUP
# ==================================================

def delete_temporary_image(
    delete_url
):

    if not delete_url:

        print(
            "No deletion URL returned; "
            "relying on host expiry."
        )

        return

    response = requests.get(
        delete_url,
        timeout=30,
        allow_redirects=True,
    )

    response.raise_for_status()

    print(
        "Temporary image cleanup completed."
    )


# ==================================================
# MAIN
# ==================================================

def main():

    print(
        "=================================="
    )

    print(
        "Starting Mauksh Daily Mulank Horoscope"
    )

    print(
        TODAY.strftime(
            "%d %B %Y"
        )
    )

    print(
        "=================================="
    )

    # Generate once
    horoscopes = (
        generate_horoscopes()
    )

    # Create poster
    image_path = (
        create_poster(
            horoscopes
        )
    )

    # Preview
    if (
        os.getenv(
            "PREVIEW_ONLY",
            "false"
        ).lower()
        == "true"
    ):

        print(
            "Preview mode enabled."
        )

        print(
            "No Instagram, X or Threads "
            "posts will be created."
        )

        return

    # Upload image once
    image_url, delete_url = (
        upload_to_picrd(
            image_path
        )
    )

    # ==========================================
    # INSTAGRAM
    # ==========================================

    print(
        "\n========== INSTAGRAM ==========\n"
    )

    try:

        instagram_post = (
            publish_to_instagram(
                image_url
            )
        )

        instagram_published = (
            wait_until_published(
                instagram_post["id"],

                os.environ[
                    "BUFFER_ACCESS_TOKEN"
                ],

                "Instagram"
            )
        )

        if instagram_published:

            print(
                "Instagram publication confirmed."
            )

    except Exception as exc:

        print(
            "Instagram failed:",
            type(exc).__name__,
            str(exc)
        )

    # ==========================================
    # X
    # ==========================================

    print(
        "\n============== X ==============\n"
    )

    try:

        x_post = publish_to_x(
            horoscopes
        )

        x_published = (
            wait_until_published(
                x_post["id"],

                os.environ[
                    "BUFFER_X_ACCESS_TOKEN"
                ],

                "X"
            )
        )

        if x_published:

            print(
                "X thread publication confirmed."
            )

    except Exception as exc:

        print(
            "X failed:",
            type(exc).__name__,
            str(exc)
        )

    # ==========================================
    # THREADS
    # ==========================================

    print(
        "\n========== THREADS ============\n"
    )

    try:

        threads_post = (
            publish_to_threads(
                horoscopes
            )
        )

        threads_published = (
            wait_until_published(
                threads_post["id"],

                os.environ[
                    "BUFFER_API_KEY"
                ],

                "Threads"
            )
        )

        if threads_published:

            print(
                "Threads publication confirmed."
            )

    except Exception as exc:

        print(
            "Threads failed:",
            type(exc).__name__,
            str(exc)
        )

    # ==========================================
    # CLEANUP
    # ==========================================

    try:

        delete_temporary_image(
            delete_url
        )

    except Exception as exc:

        print(
            "Image cleanup needs attention:",
            type(exc).__name__
        )

    # ==========================================
    # FINISHED
    # ==========================================

    print(
        "\n=================================="
    )

    print(
        "Mauksh Mulank horoscope workflow finished."
    )

    print(
        "Instagram: 1 post"
    )

    print(
        "X: 9-post thread"
    )

    print(
        "Threads: 9-post thread"
    )

    print(
        "=================================="
    )


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":
    main()
