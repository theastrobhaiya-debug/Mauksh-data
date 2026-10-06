
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
        + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/liberation2/"
        + (
            "LiberationSans-Bold.ttf"
            if bold
            else "LiberationSans-Regular.ttf"
        ),
    ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ==================================================
# OPENAI: GENERATE 12 HOROSCOPES
# ==================================================

def generate_horoscopes():
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = f"""
Write daily horoscopes in English for
{TODAY.strftime('%d %B %Y')}.

Brand: Mauksh.
Tone: practical, warm, grounded, encouraging.
Write 18-24 words for each zodiac sign.
Give each sign distinct daily guidance.
Avoid fear, guaranteed outcomes, and invented planetary transits.
No Hindi, Hinglish, emojis, hashtags, or markdown.

Return only valid JSON in this format:
{{
  "horoscopes": [
    {{"sign": "ARIES", "text": "Daily guidance"}}
  ]
}}

Return exactly these signs in this order:
ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO,
LIBRA, SCORPIO, SAGITTARIUS, CAPRICORN,
AQUARIUS, PISCES.
"""

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        input=prompt,
    )

    raw = response.output_text.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    horoscopes = data.get("horoscopes", [])

    if len(horoscopes) != 12:
        raise ValueError("Expected exactly 12 horoscopes.")

    for i, item in enumerate(horoscopes):
        if str(item.get("sign", "")).upper() != SIGNS[i][0]:
            raise ValueError(f"Incorrect zodiac sign at position {i + 1}.")

        if not str(item.get("text", "")).strip():
            raise ValueError(f"Missing horoscope for {SIGNS[i][0]}.")

    print("All 12 horoscopes generated.")
    return horoscopes


# ==================================================
# CREATE GOLDEN MAUKSH IMAGE
# ==================================================

def create_poster(horoscopes):
    image = Image.new("RGB", (WIDTH, HEIGHT), GOLD)
    draw = ImageDraw.Draw(image)

    draw.arc(
        (-180, -180, 250, 250),
        0, 270, fill=(232, 168, 30), width=5
    )
    draw.arc(
        (850, 1130, 1260, 1540),
        180, 360, fill=(232, 168, 30), width=5
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
    card_w = (WIDTH - 2 * margin_x - 2 * gap_x) // 3
    top = 270
    gap_y = 12
    card_h = 226

    for index, item in enumerate(horoscopes):
        col = index % 3
        row = index // 3
        x = margin_x + col * (card_w + gap_x)
        y = top + row * (card_h + gap_y)

        draw.rounded_rectangle(
            (x, y, x + card_w, y + card_h),
            radius=18,
            fill=CARD,
            outline=(255, 255, 255),
            width=2,
        )

        sign, date_range = SIGNS[index]

        draw.text(
            (x + card_w // 2, y + 12),
            sign,
            font=get_font(22, True),
            fill=DARK,
            anchor="mt",
        )
        draw.text(
            (x + card_w // 2, y + 45),
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
            str(item["text"]).strip(),
            width=26,
            break_long_words=True,
        )

        if len(lines) > 6:
            lines = lines[:6]
            lines[-1] = lines[-1].rstrip(" .,;:") + "..."

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

    image.save(OUTPUT_PATH, "JPEG", quality=94, optimize=True)
    print("Poster created.")
    return OUTPUT_PATH


# ==================================================
# BUFFER GRAPHQL HELPER
# ==================================================

def buffer_graphql(query, variables=None):
    response = requests.post(
        "https://api.buffer.com",
        headers={
            "Authorization": "Bearer " + os.environ["BUFFER_ACCESS_TOKEN"],
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "variables": variables or {},
        },
        timeout=60,
    )

    response.raise_for_status()
    result = response.json()

    if result.get("errors"):
        raise RuntimeError(
            "Buffer API error: " + json.dumps(result["errors"])
        )

    return result.get("data", {})


# ==================================================
# FIND THE ONLY INSTAGRAM CHANNEL AUTOMATICALLY
# ==================================================

def get_instagram_channel_id():
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

    data = buffer_graphql(organizations_query)
    organizations = data.get("account", {}).get("organizations", [])

    instagram_channels = []

    for organization in organizations:
        organization_id = organization["id"]

        channels_query = """
        query GetChannels($organizationId: String!) {
          channels(input: { organizationId: $organizationId }) {
            id
            name
            service
          }
        }
        """

        channel_data = buffer_graphql(
            channels_query,
            {"organizationId": organization_id},
        )

        for channel in channel_data.get("channels", []):
            service = str(channel.get("service", "")).lower()

            if service == "instagram":
                instagram_channels.append(channel)

    if len(instagram_channels) != 1:
        raise RuntimeError(
            "Expected exactly one Instagram channel across your "
            f"Buffer organizations; found {len(instagram_channels)}. "
            "No post was created."
        )

    channel = instagram_channels[0]

    print(
        "Selected Instagram channel:",
        channel.get("name", "Instagram"),
    )

    return channel["id"]


# ==================================================
# UPLOAD IMAGE TO PICRD
# ==================================================

def upload_to_picrd(image_path):
    with open(image_path, "rb") as file:
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
                "visibility": "unlisted",
                "ttl_seconds": "86400",
            },
            timeout=60,
        )

    response.raise_for_status()
    result = response.json()

    image_url = result.get("image_url")
    delete_url = result.get("delete_url")

    if not image_url:
        raise RuntimeError(
            "Image host did not return image_url: " + json.dumps(result)
        )

    print("Image uploaded to temporary hosting.")
    return image_url, delete_url


# ==================================================
# CREATE BUFFER POST
# ==================================================

def publish_to_buffer(image_url):
    channel_id = get_instagram_channel_id()

    caption = (
        f"Mauksh Daily Horoscope for {TODAY.strftime('%d %B %Y')}\n\n"
        "Read your sign and take what feels useful. "
        "Save this post for your day.\n\n"
        "#Mauksh #DailyHoroscope #ZodiacSigns #SelfGrowth"
    )

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
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
            "text": caption,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "shareNow",
            "assets": [
                {
                    "image": {
                        "url": image_url
                    }
                }
            ],
            "metadata": {
                "instagram": {
                    "type": "post"
                }
            },
        }
    }

    data = buffer_graphql(mutation, variables)
    result = data.get("createPost", {})

    if result.get("message"):
        raise RuntimeError("Buffer rejected post: " + result["message"])

    post = result.get("post")

    if not post or not post.get("id"):
        raise RuntimeError(
            "Buffer did not return a post ID: " + json.dumps(data)
        )

    print("Buffer accepted post ID:", post["id"])
    print("Initial status:", post.get("status"))

    return post


# ==================================================
# WAIT FOR PUBLICATION CONFIRMATION
# ==================================================

def wait_until_published(post_id, timeout_seconds=900):
    query = """
    query GetPost($id: PostId!) {
      post(input: { id: $id }) {
        id
        status
        sentAt
      }
    }
    """

    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        data = buffer_graphql(query, {"id": post_id})
        post = data.get("post")

        if post:
            status = str(post.get("status", "")).lower()
            print("Buffer post status:", status)

            if status == "sent" or post.get("sentAt"):
                return True

            if status in ("error", "failed"):
                return False

        time.sleep(20)

    return False


# ==================================================
# CLEANUP
# ==================================================

def delete_temporary_image(delete_url):
    if not delete_url:
        print("No deletion URL returned; image host TTL will handle expiry.")
        return

    # Keep this URL private: it is a secret deletion link.
    # Picrd may present a confirmation page instead of deleting directly.
    # The host's documented TTL is the fallback if manual confirmation is needed.
    response = requests.get(
        delete_url,
        timeout=30,
        allow_redirects=True,
    )
    response.raise_for_status()

    print("Temporary image cleanup request completed.")


# ==================================================
# MAIN
# ==================================================

def main():
    print(
        "Starting Mauksh Daily Horoscope:",
        TODAY.strftime("%d %B %Y"),
    )

    horoscopes = generate_horoscopes()
    image_path = create_poster(horoscopes)

    if os.getenv("PREVIEW_ONLY", "false").lower() == "true":
        print("Preview mode: no image upload or post created.")
        return

    image_url, delete_url = upload_to_picrd(image_path)

    # Do not delete the public image unless publication is confirmed.
    post = publish_to_buffer(image_url)
    published = wait_until_published(post["id"])

    if published:
        print("Buffer confirms publication.")
        try:
            delete_temporary_image(delete_url)
        except Exception as exc:
            print(
                "Image cleanup needs attention:",
                type(exc).__name__,
            )
    else:
        print(
            "Publication was not confirmed. "
            "The image has been retained until its host TTL expires."
        )

    print("Mauksh horoscope workflow finished.")


if __name__ == "__main__":
    main()
