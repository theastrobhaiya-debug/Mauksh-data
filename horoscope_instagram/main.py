
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
# English | Golden theme | 12 signs | Instagram
# Temporary image hosting: Picrd
# Publishing: Buffer API, shareNow
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
        (
            "/usr/share/fonts/truetype/dejavu/"
            + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
        ),
        (
            "/usr/share/fonts/truetype/liberation2/"
            + (
                "LiberationSans-Bold.ttf"
                if bold
                else "LiberationSans-Regular.ttf"
            )
        ),
    ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ==================================================
# GENERATE HOROSCOPES WITH OPENAI
# ==================================================

def generate_horoscopes():
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = f"""
Create daily horoscopes in English for {TODAY.strftime('%d %B %Y')}.

Brand: Mauksh.
Tone: practical, warm, clear, grounded and encouraging.
Write 18 to 24 words for each sign.
Give every sign distinct daily guidance.
Avoid fear, guaranteed predictions and claims of certainty.
Do not invent or claim specific planetary transits.
No Hindi, Hinglish, emojis, hashtags or markdown.

Return only valid JSON:
{{
  "horoscopes": [
    {{"sign": "ARIES", "text": "Daily guidance here"}}
  ]
}}

Return exactly these 12 signs in this order:
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
        raise ValueError("OpenAI did not return exactly 12 horoscopes.")

    for i, item in enumerate(horoscopes):
        expected_sign = SIGNS[i][0]
        actual_sign = str(item.get("sign", "")).upper()
        horoscope_text = str(item.get("text", "")).strip()

        if actual_sign != expected_sign:
            raise ValueError(
                f"Expected {expected_sign}, received {actual_sign}."
            )

        if not horoscope_text:
            raise ValueError(f"Missing horoscope for {expected_sign}.")

    print("Generated and validated all 12 horoscopes.")
    return horoscopes


# ==================================================
# CREATE THE GOLDEN MAUKSH POSTER
# ==================================================

def create_poster(horoscopes):
    image = Image.new("RGB", (WIDTH, HEIGHT), GOLD)
    draw = ImageDraw.Draw(image)

    # Simple golden background accents
    draw.arc(
        (-180, -180, 250, 250),
        0, 270,
        fill=(232, 168, 30),
        width=5,
    )
    draw.arc(
        (850, 1130, 1260, 1540),
        180, 360,
        fill=(232, 168, 30),
        width=5,
    )

    # Brand
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

    # Requested title and date
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

    # 3 columns x 4 rows
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
        "ASTROLOGY  |  SELF GROWTH  |  A BETTER YOU",
        font=get_font(14, True),
        fill=DARK,
        anchor="mt",
    )

    image.save(OUTPUT_PATH, "JPEG", quality=94, optimize=True)
    print(f"Poster created: {OUTPUT_PATH}")
    return OUTPUT_PATH


# ==================================================
# UPLOAD TO PICRD TEMPORARY PUBLIC HOSTING
# ==================================================

def upload_to_picrd(image_path):
    with open(image_path, "rb") as image_file:
        response = requests.post(
            "https://picrd.com/api/upload",
            files={
                "file": (
                    "mauksh_daily_horoscope.jpg",
                    image_file,
                    "image/jpeg",
                )
            },
            data={"visibility": "unlisted"},
            timeout=60,
        )

    response.raise_for_status()
    result = response.json()

    image_url = result.get("image_url")
    delete_url = result.get("delete_url")

    if not image_url or not delete_url:
        raise RuntimeError(
            "Image host did not return image_url and delete_url: "
            + json.dumps(result)
        )

    # Verify the image is publicly reachable before using it.
    check = requests.get(
        image_url,
        stream=True,
        timeout=30,
    )
    check.raise_for_status()
    check.close()

    print("Poster uploaded to temporary image hosting.")
    return image_url, delete_url


# ==================================================
# BUFFER GRAPHQL REQUEST HELPER
# ==================================================

def buffer_graphql(query, variables=None):
    response = requests.post(
        "https://api.buffer.com",
        headers={
            "Authorization": (
                "Bearer " + os.environ["BUFFER_ACCESS_TOKEN"]
            ),
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
            "Buffer GraphQL error: "
            + json.dumps(result["errors"])
        )

    return result.get("data", {})


# ==================================================
# CREATE AN IMMEDIATE BUFFER POST
# ==================================================

def publish_to_buffer(image_url):
    channel_id = os.environ["BUFFER_INSTAGRAM_CHANNEL_ID"]

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
            sentAt
            shareMode
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
        raise RuntimeError(
            "Buffer rejected the post: " + str(result["message"])
        )

    post = result.get("post")
    if not post or not post.get("id"):
        raise RuntimeError(
            "Buffer did not return a post ID: " + json.dumps(data)
        )

    print(
        "Buffer accepted post:",
        post["id"],
        "| initial status:",
        post.get("status"),
    )

    return post


# ==================================================
# WAIT FOR BUFFER TO CONFIRM PUBLICATION
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
        data = buffer_graphql(
            query,
            {"id": post_id},
        )

        post = data.get("post")

        if not post:
            print("Could not read post status; will keep waiting.")
        else:
            status = str(post.get("status", "")).lower()
            print("Current Buffer post status:", status)

            if status == "sent" or post.get("sentAt"):
                print("Buffer confirms the post was published.")
                return True

            if status == "error":
                print(
                    "Buffer reports a publishing error. "
                    "The hosted image will not be deleted."
                )
                return False

        time.sleep(20)

    print(
        "Publication was not confirmed before timeout. "
        "The hosted image will be retained."
    )
    return False


# ==================================================
# DELETE TEMPORARY IMAGE AFTER CONFIRMED PUBLISHING
# ==================================================

def delete_hosted_image(delete_url):
    # Picrd documents this as a secret, single-use deletion URL.
    # Never print or expose it in logs.
    response = requests.get(
        delete_url,
        timeout=30,
    )
    response.raise_for_status()

    print("Temporary hosted image deletion requested.")


# ==================================================
# MAIN
# ==================================================

def main():
    print(
        "Starting Mauksh Daily Horoscope for "
        + TODAY.strftime("%d %B %Y")
    )

    horoscopes = generate_horoscopes()
    image_path = create_poster(horoscopes)

    preview_only = (
        os.getenv("PREVIEW_ONLY", "false").lower() == "true"
    )

    if preview_only:
        print("PREVIEW_ONLY is enabled. No Instagram post will be created.")
        return

    image_url, delete_url = upload_to_picrd(image_path)

    # If Buffer submission fails, retain the hosted image for debugging
    # and to avoid losing a media URL while investigating the failure.
    post = publish_to_buffer(image_url)

    published = wait_until_published(post["id"])

    if published:
        try:
            delete_hosted_image(delete_url)
        except Exception as exc:
            # Publishing has succeeded; deletion failure is non-fatal.
            print(
                "Post published, but temporary image cleanup failed:",
                type(exc).__name__,
            )
    else:
        print(
            "Image was intentionally retained because publication "
            "was not confirmed."
        )

    print("Workflow finished.")


if __name__ == "__main__":
    main()

