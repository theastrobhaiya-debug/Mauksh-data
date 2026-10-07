import json
import os
import time
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
# ==================================================
# MAUKSH DAILY HOROSCOPE
# ==================================================
TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ)
WIDTH, HEIGHT = 1080, 1350
GOLD = (255, 210, 70)
DARK = (45, 29, 8)
CARD = (255, 246, 215)
ACCENT = (218, 157, 22)
OUTPUT_PATH = "/tmp/mauksh_daily_horoscope.jpg"
SIGNS = [
    ("ARIES", "21 MAR – 19 APR"),
    ("TAURUS", "20 APR – 20 MAY"),
    ("GEMINI", "21 MAY – 20 JUN"),
    ("CANCER", "21 JUN – 22 JUL"),
    ("LEO", "23 JUL – 22 AUG"),
    ("VIRGO", "23 AUG – 22 SEP"),
    ("LIBRA", "23 SEP – 22 OCT"),
    ("SCORPIO", "23 OCT – 21 NOV"),
    ("SAGITTARIUS", "22 NOV – 21 DEC"),
    ("CAPRICORN", "22 DEC – 19 JAN"),
    ("AQUARIUS", "20 JAN – 18 FEB"),
    ("PISCES", "19 FEB – 20 MAR"),
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
# OPENAI
# GENERATE 12 ORIGINAL VEDIC HOROSCOPES
# ==================================================
def generate_horoscopes():
    client = OpenAI(
        api_key=os.environ[
            "OPENAI_API_KEY"
        ]
    )
    date_text = TODAY.strftime(
        "%d %B %Y"
    )
    sign_names = [
        sign
        for sign, _ in SIGNS
    ]
    prompt = f"""
You are an experienced Vedic astrology writer creating daily
horoscopes for the Mauksh brand.
DATE: {date_text}
ASTROLOGY SYSTEM:
Vedic astrology using the sidereal zodiac.
TASK:
Generate one daily horoscope for each of the 12 zodiac signs,
interpreting relevant Vedic planetary transit themes for this date.
VEDIC TRANSIT GUIDELINES:
1. Use Vedic astrological principles to interpret relevant
   planetary transit themes for each zodiac sign.
2. Consider the Sun, Moon, Mars, Mercury, Jupiter, Venus,
   Saturn, Rahu and Ketu where relevant.
3. Do not invent planetary positions, sign changes,
   conjunctions, aspects, nakshatras or transit events.
4. Do not claim to have verified live transits or calculated
   an accurate chart if that information is unavailable.
5. If exact transit information is unavailable, do not pretend
   that specific planetary positions have been verified.
6. Present astrology as interpretive guidance,
   not guaranteed fact.
STRICT NON-REPETITION CHECK:
Before returning your final answer, review all 12 horoscopes together.
- Do not copy or paraphrase one sign's prediction for another.
- Give every sign a distinct central theme and practical advice.
- Avoid repeated openings.
- Avoid repeated sentence structures.
- Avoid repeated metaphors.
- Avoid generic recycled horoscope clichés.
- Do not merely replace a few words to disguise repetition.
- If two predictions feel similar, rewrite them.
STYLE:
- English only.
- Each horoscope must contain 18–24 words.
- Warm, practical, grounded, encouraging and thoughtful.
- Focus on work, money, relationships, communication,
  decisions or personal growth.
- Do not mention planet names in the published horoscope text.
- Avoid fear, alarming predictions and guaranteed outcomes.
- No Hindi.
- No Hinglish.
- No emojis.
- No hashtags.
- No Markdown inside horoscope text.
Return exactly 12 entries in this order:
{json.dumps(sign_names)}
Return ONLY valid JSON:
{{
  "horoscopes": [
    {{"sign": "ARIES", "text": "Daily guidance."}},
    {{"sign": "TAURUS", "text": "Daily guidance."}}
  ]
}}
Include all 12 signs.
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
        not isinstance(
            horoscopes,
            list
        )
        or len(horoscopes) != 12
    ):
        raise ValueError(
            "Expected exactly 12 horoscopes."
        )
    for index, item in enumerate(
        horoscopes
    ):
        expected_sign = SIGNS[index][0]
        if not isinstance(
            item,
            dict
        ):
            raise ValueError(
                "Invalid horoscope entry."
            )
        if (
            str(
                item.get(
                    "sign",
                    ""
                )
            ).upper()
            != expected_sign
        ):
            raise ValueError(
                f"Expected {expected_sign} "
                f"at position {index + 1}."
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
                f"{expected_sign} horoscope "
                f"has {word_count} words; "
                "expected 18–24."
            )
        item["sign"] = expected_sign
        item["text"] = text
    print(
        f"Generated and validated 12 "
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
        "MAUKSH DAILY HOROSCOPE",
        font=get_font(42, True),
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
        "12 ZODIAC SIGNS  |  DAILY GUIDANCE",
        font=get_font(17, True),
        fill=DARK,
        anchor="mt",
    )
    margin_x = 55
    gap_x = 14
    card_w = (
        WIDTH
        - 2 * margin_x
        - 2 * gap_x
    ) // 3
    top = 270
    gap_y = 12
    card_h = 226
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
        sign, date_range = SIGNS[index]
        draw.text(
            (
                x + card_w // 2,
                y + 12
            ),
            sign,
            font=get_font(22, True),
            fill=DARK,
            anchor="mt",
        )
        draw.text(
            (
                x + card_w // 2,
                y + 45
            ),
            date_range,
            font=get_font(12, True),
            fill=DARK,
            anchor="mt",
        )
        draw.line(
            (
                x + card_w // 2 - 24,
                y + 68,
                x + card_w // 2 + 24,
                y + 68,
            ),
            fill=ACCENT,
            width=3,
        )
        lines = textwrap.wrap(
            str(
                item["text"]
            ).strip(),
            width=26,
            break_long_words=True,
        )
        if len(lines) > 6:
            lines = lines[:6]
            lines[-1] = (
                lines[-1]
                .rstrip(" .,;:")
                + "..."
            )
        yy = y + 82
        for line in lines:
            draw.text(
                (x + 17, yy),
                line,
                font=get_font(17),
                fill=DARK,
            )
            yy += 24
    draw.text(
        (WIDTH // 2, 1239),
        "mauksh.com",
        font=get_font(31, True),
        fill=DARK,
        anchor="mt",
    )
    draw.text(
        (WIDTH // 2, 1283),
        "ASTROLOGY  |  SELF GROWTH  |  A BETTER YOU",
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
# FIND INSTAGRAM CHANNEL
# ==================================================
def get_instagram_channel_id():
    access_token = os.environ[
        "BUFFER_ACCESS_TOKEN"
    ]
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
    instagram_channels = []
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
            if (
                str(
                    channel.get(
                        "service",
                        ""
                    )
                ).lower()
                == "instagram"
            ):
                instagram_channels.append(
                    channel
                )
    if len(
        instagram_channels
    ) != 1:
        raise RuntimeError(
            "Expected exactly one Instagram "
            "channel across Buffer organizations; "
            f"found {len(instagram_channels)}."
        )
    channel = instagram_channels[0]
    print(
        "Selected Instagram channel:",
        channel.get(
            "name",
            "Instagram"
        )
    )
    return channel["id"]
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
                    "mauksh_daily_horoscope.jpg",
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
        "Image uploaded to "
        "temporary hosting."
    )
    return image_url, delete_url
# ==================================================
# PUBLISH INSTAGRAM
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
        f"Mauksh Daily Horoscope "
        f"for {TODAY.strftime('%d %B %Y')}\n\n"
        "Read your sign and take what feels useful. "
        "Save this post for your day.\n\n"
        "#Mauksh #DailyHoroscope "
        "#ZodiacSigns #SelfGrowth"
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
    if (
        not post
        or not post.get("id")
    ):
        raise RuntimeError(
            "Buffer did not return "
            "Instagram post ID: "
            + json.dumps(data)
        )
    print(
        "Instagram Buffer post ID:",
        post["id"]
    )
    print(
        "Instagram initial status:",
        post.get("status")
    )
    return post
# ==================================================
# FIND X CHANNEL
# ==================================================
def get_x_channel_id():
    access_token = os.environ[
        "BUFFER_X_ACCESS_TOKEN"
    ]
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
    x_channels = []
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
            service = str(
                channel.get(
                    "service",
                    ""
                )
            ).lower()
            if service in (
                "twitter",
                "x"
            ):
                x_channels.append(
                    channel
                )
    if len(x_channels) != 1:
        raise RuntimeError(
            "Expected exactly one X/Twitter "
            "channel in the X Buffer account; "
            f"found {len(x_channels)}. "
            "No X post was created."
        )
    channel = x_channels[0]
    print(
        "Selected X channel:",
        channel.get(
            "name",
            "X"
        )
    )
    return channel["id"]
# ==================================================
# ZODIAC SYMBOLS
# ==================================================
ZODIAC_SYMBOLS = {
    "ARIES": "♈",
    "TAURUS": "♉",
    "GEMINI": "♊",
    "CANCER": "♋",
    "LEO": "♌",
    "VIRGO": "♍",
    "LIBRA": "♎",
    "SCORPIO": "♏",
    "SAGITTARIUS": "♐",
    "CAPRICORN": "♑",
    "AQUARIUS": "♒",
    "PISCES": "♓",
}
# ==================================================
# CREATE 12 X THREAD POSTS
# ==================================================
def create_x_thread(
    horoscopes
):
    thread_posts = []
    # ------------------------------------------------
    # ROOT POST
    # ------------------------------------------------
    root_text = (
        f"Mauksh Daily Horoscope — "
        f"{TODAY.strftime('%d %B %Y')}\n\n"
        "Read your sign below. "
        "Take what feels useful."
    )
    if len(root_text) > 280:
        raise ValueError(
            "X root post exceeds 280 characters."
        )
    thread_posts.append(
        {
            "text": root_text
        }
    )
    # ------------------------------------------------
    # 12 ZODIAC POSTS
    # ------------------------------------------------
    for item in horoscopes:
        sign = item[
            "sign"
        ]
        text = item[
            "text"
        ].strip()
        symbol = ZODIAC_SYMBOLS.get(
            sign,
            ""
        )
        post_text = (
            f"{symbol} {sign.title()}\n\n"
            f"{text}"
        )
        # X character safety check
        if len(post_text) > 280:
            raise ValueError(
                f"{sign} X thread post is "
                f"{len(post_text)} characters. "
                "Maximum allowed is 280."
            )
        thread_posts.append(
            {
                "text": post_text
            }
        )
    # ------------------------------------------------
    # FINAL POST
    # ------------------------------------------------
    final_text = (
        "Astrology is guidance, "
        "not certainty.\n\n"
        "#Mauksh #DailyHoroscope"
    )
    if len(final_text) > 280:
        raise ValueError(
            "X final post exceeds 280 characters."
        )
    thread_posts.append(
        {
            "text": final_text
        }
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
    thread_posts = (
        create_x_thread(
            horoscopes
        )
    )
    print(
        "\n=============================="
    )
    print(
        "X THREAD"
    )
    print(
        "=============================="
    )
    for index, item in enumerate(
        thread_posts
    ):
        print(
            f"\n[{index + 1}/"
            f"{len(thread_posts)}]"
        )
        print(
            item["text"]
        )
        print(
            f"Characters: "
            f"{len(item['text'])}"
        )
    print(
        "\n==============================\n"
    )
    # ------------------------------------------------
    # IMPORTANT:
    # Buffer requires:
    #
    # top-level text = first thread item
    #
    # metadata.twitter.thread =
    # ALL thread items
    # ------------------------------------------------
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
            # MUST MATCH FIRST THREAD ITEM
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
    if (
        not post
        or not post.get("id")
    ):
        raise RuntimeError(
            "Buffer did not return "
            "X thread post ID: "
            + json.dumps(data)
        )
    print(
        "X Buffer thread ID:",
        post["id"]
    )
    print(
        "X initial status:",
        post.get("status")
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
    while (
        time.time()
        < deadline
    ):
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
                f"Buffer post status:",
                status
            )
            if (
                status == "sent"
                or post.get(
                    "sentAt"
                )
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
# CLEANUP TEMPORARY IMAGE
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
        "Temporary image cleanup "
        "request completed."
    )
# ==================================================
# MAIN
# ==================================================
def main():
    print(
        "=================================="
    )
    print(
        "Starting Mauksh Daily Horoscope"
    )
    print(
        TODAY.strftime(
            "%d %B %Y"
        )
    )
    print(
        "=================================="
    )
    # ------------------------------------------------
    # 1. GENERATE HOROSCOPES ONCE
    # ------------------------------------------------
    horoscopes = (
        generate_horoscopes()
    )
    # ------------------------------------------------
    # 2. CREATE INSTAGRAM POSTER
    # ------------------------------------------------
    image_path = (
        create_poster(
            horoscopes
        )
    )
    # ------------------------------------------------
    # 3. PREVIEW MODE
    # ------------------------------------------------
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
            "No Instagram or X "
            "posts will be created."
        )
        return
    # ------------------------------------------------
    # 4. INSTAGRAM
    # ------------------------------------------------
    print(
        "\n========== INSTAGRAM ==========\n"
    )
    image_url, delete_url = (
        upload_to_picrd(
            image_path
        )
    )
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
    else:
        print(
            "Instagram publication was "
            "not confirmed."
        )
    # ------------------------------------------------
    # 5. X THREAD
    # ------------------------------------------------
    print(
        "\n============== X ==============\n"
    )
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
    else:
        print(
            "X thread publication was "
            "not confirmed."
        )
    # ------------------------------------------------
    # 6. CLEANUP INSTAGRAM IMAGE
    # ------------------------------------------------
    try:
        delete_temporary_image(
            delete_url
        )
    except Exception as exc:
        print(
            "Image cleanup needs attention:",
            type(exc).__name__
        )
    # ------------------------------------------------
    # FINISHED
    # ------------------------------------------------
    print(
        "\n=================================="
    )
    print(
        "Mauksh horoscope workflow finished."
    )
    print(
        "Instagram: 1 post"
    )
    print(
        "X: 1 thread"
    )
    print(
        "=================================="
    )
# ==================================================
# RUN
# ==================================================
if __name__ == "__main__":
    main()
