
import json
import os
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo

import cloudinary
import cloudinary.uploader
import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------
# MAUKSH DAILY HOROSCOPE SETTINGS
# --------------------------------------------------

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ)

WIDTH = 1080
HEIGHT = 1350

GOLD = (255, 210, 70)
DARK = (45, 29, 8)
CARD = (255, 246, 215)
ACCENT = (218, 157, 22)

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


# --------------------------------------------------
# FONTS
# --------------------------------------------------

def get_font(size, bold=False):
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans-Bold.ttf"
            if bold else
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans.ttf"
        ),
        (
            "/usr/share/fonts/truetype/liberation2/"
            "LiberationSans-Bold.ttf"
            if bold else
            "/usr/share/fonts/truetype/liberation2/"
            "LiberationSans-Regular.ttf"
        ),
    ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# --------------------------------------------------
# GENERATE 12 ENGLISH HOROSCOPES
# --------------------------------------------------

def generate_horoscopes():
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"]
    )

    prompt = f"""
Create 12 original daily horoscopes in English
for {TODAY.strftime('%d %B %Y')}.

Brand: Mauksh.
Tone: practical, warm, positive, grounded and honest.
Use clear, simple English.
Each horoscope should contain 18 to 24 words.
Give every zodiac sign distinct, useful daily guidance.
Avoid fear-based predictions and guaranteed outcomes.
Do not invent planetary transit calculations.
No Hindi, Hinglish, emojis, hashtags or markdown.

Return ONLY valid JSON in this format:
{{
  "horoscopes": [
    {{"sign": "ARIES", "text": "Your horoscope here"}}
  ]
}}

Return exactly 12 signs in this exact order:
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
        raw = raw.split("\n", 1)[1].rsplit(
            "```", 1
        )[0].strip()

    data = json.loads(raw)
    horoscopes = data["horoscopes"]

    if len(horoscopes) != 12:
        raise ValueError(
            "Expected exactly 12 horoscopes."
        )

    # Validate sign order and required text.
    for index, item in enumerate(horoscopes):
        if item.get("sign", "").upper() != SIGNS[index][0]:
            raise ValueError(
                f"Unexpected sign at position {index + 1}."
            )

        if not str(item.get("text", "")).strip():
            raise ValueError(
                f"Missing horoscope for {SIGNS[index][0]}."
            )

    return horoscopes


# --------------------------------------------------
# CREATE MAUKSH GOLDEN POSTER
# --------------------------------------------------

def create_poster(horoscopes):
    image = Image.new(
        "RGB", (WIDTH, HEIGHT), GOLD
    )
    draw = ImageDraw.Draw(image)

    # Simple decorative accents
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

    # Brand name
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

    # Main title
    draw.text(
        (WIDTH // 2, 116),
        "MAUKSH DAILY HOROSCOPE",
        font=get_font(42, True),
        fill=DARK,
        anchor="mt",
    )

    # Date
    date_text = (
        f"FOR {TODAY.strftime('%d %B %Y').upper()}"
    )

    draw.text(
        (WIDTH // 2, 176),
        date_text,
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

    # Grid dimensions: 3 columns x 4 rows
    margin_x = 55
    gap_x = 14
    card_w = (
        WIDTH - 2 * margin_x - 2 * gap_x
    ) // 3

    top = 270
    gap_y = 12
    card_h = 226

    for index, item in enumerate(horoscopes):
        col = index % 3
        row = index // 3

        x = margin_x + col * (card_w + gap_x)
        y = top + row * (card_h + gap_y)

        # Rounded cream card
        draw.rounded_rectangle(
            (
                x,
                y,
                x + card_w,
                y + card_h,
            ),
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

        # Small divider
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

        horoscope = str(
            item.get("text", "")
        ).strip()

        # Wrap horoscope to fit each card.
        lines = textwrap.wrap(
            horoscope,
            width=26,
            break_long_words=True,
        )

        # Limit line count to keep text inside the card.
        if len(lines) > 6:
            lines = lines[:6]
            lines[-1] = lines[-1].rstrip(
                " .,;:"
            ) + "..."

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

    output_path = (
        "/tmp/mauksh_daily_horoscope.jpg"
    )

    image.save(
        output_path,
        "JPEG",
        quality=94,
        optimize=True,
    )

    print(f"Poster created: {output_path}")

    return output_path


# --------------------------------------------------
# UPLOAD IMAGE TO CLOUDINARY
# --------------------------------------------------

def upload_image(image_path):
    cloudinary.config(
        cloud_name=os.environ[
            "CLOUDINARY_CLOUD_NAME"
        ],
        api_key=os.environ[
            "CLOUDINARY_API_KEY"
        ],
        api_secret=os.environ[
            "CLOUDINARY_API_SECRET"
        ],
        secure=True,
    )

    result = cloudinary.uploader.upload(
        image_path,
        folder="mauksh/daily-horoscope",
        public_id=(
            f"horoscope-{TODAY.strftime('%Y-%m-%d')}"
        ),
        overwrite=True,
        resource_type="image",
    )

    image_url = result["secure_url"]

    print(f"Uploaded poster: {image_url}")

    return image_url


# --------------------------------------------------
# SEND POST TO BUFFER QUEUE
# --------------------------------------------------

def send_to_buffer(image_url):
    token = os.environ["BUFFER_ACCESS_TOKEN"]

    channel_id = os.environ[
        "BUFFER_INSTAGRAM_CHANNEL_ID"
    ]

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            text
            status
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    caption = (
        f"Mauksh Daily Horoscope for "
        f"{TODAY.strftime('%d %B %Y')}\n\n"
        "Read your sign and take what feels useful. "
        "Save this post for your day.\n\n"
        "#Mauksh #DailyHoroscope "
        "#ZodiacSigns #SelfGrowth"
    )

    variables = {
        "input": {
            "text": caption,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [
                {
                    "image": {
                        "url": image_url
                    }
                }
            ],
            "metadata": {
                "instagram": {
                    "type": "post",
                    "shouldShareToFeed": True
                }
            },
        }
    }

    response = requests.post(
        "https://api.buffer.com",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "variables": variables,
        },
        timeout=60,
    )

    response.raise_for_status()
    result = response.json()

    if result.get("errors"):
        raise RuntimeError(
            "Buffer API error: "
            + json.dumps(result["errors"])
        )

    data = result.get("data", {}).get(
        "createPost", {}
    )

    if data.get("message"):
        raise RuntimeError(
            "Buffer rejected the post: "
            + str(data["message"])
        )

    print(
        "Buffer response:",
        json.dumps(data, indent=2),
    )

    return data


# --------------------------------------------------
# MAIN WORKFLOW
# --------------------------------------------------

def main():
    print(
        "Mauksh Daily Horoscope for "
        + TODAY.strftime("%d %B %Y")
    )

    horoscopes = generate_horoscopes()

    image_path = create_poster(horoscopes)

    image_url = upload_image(image_path)

    # Preview mode creates the poster but does not
    # submit anything to Buffer.
    preview_only = (
        os.getenv("PREVIEW_ONLY", "false").lower()
        == "true"
    )

    if preview_only:
        print("Preview mode enabled.")
        print("Image URL:", image_url)
        print("No post was sent to Buffer.")
        return

    send_to_buffer(image_url)

    print("Horoscope submitted to Buffer queue.")


if __name__ == "__main__":
    main()
