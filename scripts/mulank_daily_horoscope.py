import json
import os
import time
from datetime import datetime
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
        + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/liberation2/"
        + ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"),
    ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ==================================================
# MULANK CALCULATION
# ==================================================

def reduce_to_single_digit(number):
    while number > 9:
        number = sum(int(digit) for digit in str(number))
    return number


def calculate_daily_number(date):
    total = date.day + date.month + date.year
    return reduce_to_single_digit(total)


# ==================================================
# OPENAI: GENERATE 9 ORIGINAL MULANK HOROSCOPES
# ==================================================

def generate_horoscopes():
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    date_text = TODAY.strftime("%d %B %Y")
    daily_number = calculate_daily_number(TODAY)
    mulank_names = [str(number) for number, _ in MULANKS]

    prompt = f"""
You are an experienced Vedic numerology writer creating daily guidance for the Mauksh brand.

DATE: {date_text}
DAILY NUMEROLOGY NUMBER: {daily_number}
SYSTEM: Vedic / Indian numerology.

Generate one original daily horoscope for each Mulank from 1 to 9.

MULANK MEANING:
1 = born on 1, 10, 19, 28
2 = born on 2, 11, 20, 29
3 = born on 3, 12, 21, 30
4 = born on 4, 13, 22, 31
5 = born on 5, 14, 23
6 = born on 6, 15, 24
7 = born on 7, 16, 25
8 = born on 8, 17, 26
9 = born on 9, 18, 27

GUIDELINES:
- Interpret the day's numerological influence through each Mulank.
- Consider traditional Vedic numerology characteristics.
- Do not invent planetary positions, transits, conjunctions, nakshatras or astronomical events.
- Do not claim guaranteed outcomes.
- Keep guidance practical and useful.
- Make every prediction distinctly different.

NON-REPETITION:
Review all 9 predictions together. Do not copy or paraphrase one Mulank prediction for another.
Give every Mulank a distinct central theme. Avoid repeated openings, sentence structures and clichés.
Do not merely replace a few words between predictions.

STYLE:
- English only.
- Exactly 18–20 words per horoscope.
- Warm, practical, grounded, encouraging and thoughtful.
- Focus on career, money, relationships, communication, decisions or personal growth.
- Do not mention planet names or numerological calculations inside the prediction.
- No fear, guaranteed predictions, Hindi, Hinglish, emojis, hashtags or Markdown.
- Write complete, grammatically finished sentences.
- Never end a prediction with an unfinished phrase.

Return exactly these Mulanks in this order: {json.dumps(mulank_names)}

Return ONLY valid JSON:
{{
  "horoscopes": [
    {{"mulank": 1, "text": "Complete daily guidance."}},
    {{"mulank": 2, "text": "Complete daily guidance."}}
  ]
}}
Include all 9 Mulanks.
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

    if not isinstance(horoscopes, list) or len(horoscopes) != 9:
        raise ValueError("Expected exactly 9 Mulank horoscopes.")

    for index, item in enumerate(horoscopes):
        expected_mulank = MULANKS[index][0]

        if not isinstance(item, dict):
            raise ValueError("Invalid horoscope entry.")

        actual_mulank = int(item.get("mulank", 0))
        if actual_mulank != expected_mulank:
            raise ValueError(
                f"Expected Mulank {expected_mulank} at position {index + 1}."
            )

        text = str(item.get("text", "")).strip()
        word_count = len(text.split())

        if not 18 <= word_count <= 20:
            raise ValueError(
                f"Mulank {expected_mulank} has {word_count} words; "
                "expected 18–20. Rerun the workflow."
            )

        if not text.endswith((".", "!", "?")):
            raise ValueError(
                f"Mulank {expected_mulank} does not end with a complete sentence."
            )

        item["mulank"] = expected_mulank
        item["text"] = text

    print(f"Generated and validated 9 Mulank horoscopes for {date_text}.")
    return horoscopes


# ==================================================
# FIT COMPLETE TEXT INSIDE A CARD
# ==================================================

def fit_horoscope_text(draw, text, max_width, max_height):
    """Reduce font size until the entire prediction fits; never truncate it."""
    for font_size in (16, 15, 14, 13, 12):
        font = get_font(font_size)
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            candidate = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font)

            if bbox[2] - bbox[0] <= max_width:
                current_line = candidate
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

                bbox = draw.textbbox((0, 0), word, font=font)
                if bbox[2] - bbox[0] > max_width:
                    raise ValueError(f"Word cannot fit inside card: {word}")

        if current_line:
            lines.append(current_line)

        line_height = font_size + 6
        total_height = len(lines) * line_height

        if total_height <= max_height:
            return font, lines, line_height

    raise ValueError(
        "Complete Mulank prediction cannot fit inside its card. "
        "Shorten the generated text or enlarge the card."
    )


# ==================================================
# CREATE GOLDEN MAUKSH IMAGE
# ==================================================

def create_poster(horoscopes):
    image = Image.new("RGB", (WIDTH, HEIGHT), GOLD)
    draw = ImageDraw.Draw(image)

    draw.arc(
        (-180, -180, 250, 250), 0, 270,
        fill=(232, 168, 30), width=5
    )
    draw.arc(
        (850, 1130, 1260, 1540), 180, 360,
        fill=(232, 168, 30), width=5
    )

    draw.text(
        (WIDTH // 2, 22), "mauksh.com",
        font=get_font(43, True), fill=DARK, anchor="mt"
    )
    draw.text(
        (WIDTH // 2, 73), "SPIRITUALITY IS PERSONAL",
        font=get_font(17, True), fill=DARK, anchor="mt"
    )
    draw.text(
        (WIDTH // 2, 116), "MAUKSH DAILY NUMEROLOGY",
        font=get_font(40, True), fill=DARK, anchor="mt"
    )
    draw.text(
        (WIDTH // 2, 176),
        f"FOR {TODAY.strftime('%d %B %Y').upper()}",
        font=get_font(27, True), fill=DARK, anchor="mt"
    )
    draw.text(
        (WIDTH // 2, 221), "MULANK 1 – 9  |  DAILY GUIDANCE",
        font=get_font(17, True), fill=DARK, anchor="mt"
    )

    margin_x = 55
    gap_x = 14
    card_w = (WIDTH - 2 * margin_x - 2 * gap_x) // 3
    top = 270
    gap_y = 12
    card_h = 290

    for index, item in enumerate(horoscopes):
        col = index % 3
        row = index // 3
        x = margin_x + col * (card_w + gap_x)
        y = top + row * (card_h + gap_y)

        draw.rounded_rectangle(
            (x, y, x + card_w, y + card_h),
            radius=18, fill=CARD, outline=(255, 255, 255), width=2
        )

        mulank = item["mulank"]
        birth_dates = dict(MULANKS)[mulank]

        draw.text(
            (x + card_w // 2, y + 12),
            f"MULANK {mulank}",
            font=get_font(23, True), fill=DARK, anchor="mt"
        )
        draw.text(
            (x + card_w // 2, y + 47),
            f"Born on {birth_dates}",
            font=get_font(12, True), fill=DARK, anchor="mt"
        )
        draw.line(
            (x + card_w // 2 - 24, y + 70,
             x + card_w // 2 + 24, y + 70),
            fill=ACCENT, width=3
        )

        font, lines, line_height = fit_horoscope_text(
            draw,
            str(item["text"]).strip(),
            max_width=card_w - 34,
            max_height=card_h - 88,
        )

        yy = y + 88
        for line in lines:
            draw.text((x + 17, yy), line, font=font, fill=DARK)
            yy += line_height

    draw.text(
        (WIDTH // 2, 1239), "mauksh.com",
        font=get_font(31, True), fill=DARK, anchor="mt"
    )
    draw.text(
        (WIDTH // 2, 1283),
        "NUMEROLOGY  |  SELF GROWTH  |  A BETTER YOU",
        font=get_font(14, True), fill=DARK, anchor="mt"
    )

    image.save(OUTPUT_PATH, "JPEG", quality=94, optimize=True)
    print("Poster created:", OUTPUT_PATH)
    return OUTPUT_PATH


# ==================================================
# BUFFER GRAPHQL HELPER
# ==================================================

def buffer_graphql(access_token, query, variables=None):
    response = requests.post(
        "https://api.buffer.com",
        headers={
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()

    if result.get("errors"):
        raise RuntimeError("Buffer API error: " + json.dumps(result["errors"]))

    return result.get("data", {})


# ==================================================
# FIND CHANNEL
# ==================================================

def get_channel_id(access_token, service, platform_name):
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
    data = buffer_graphql(access_token, organizations_query)
    organizations = data.get("account", {}).get("organizations", [])
    matching_channels = []

    for organization in organizations:
        channels_query = """
        query GetChannels($organizationId: OrganizationId!) {
          channels(input: { organizationId: $organizationId }) {
            id
            name
            service
          }
        }
        """
        channel_data = buffer_graphql(
            access_token,
            channels_query,
            {"organizationId": organization["id"]},
        )

        for channel in channel_data.get("channels", []):
            if str(channel.get("service", "")).lower() == service.lower():
                matching_channels.append(channel)

    if len(matching_channels) != 1:
        raise RuntimeError(
            f"Expected exactly one {platform_name} channel; "
            f"found {len(matching_channels)}. No post was created."
        )

    channel = matching_channels[0]
    print(f"Selected {platform_name} channel:", channel.get("name", platform_name))
    return channel["id"]


def get_instagram_channel_id():
    return get_channel_id(
        os.environ["BUFFER_ACCESS_TOKEN"], "instagram", "Instagram"
    )


def get_facebook_channel_id():
    return get_channel_id(
        os.environ["BUFFER_FACEBOOK_ACCESS_TOKEN"], "facebook", "Facebook"
    )


def get_x_channel_id():
    return get_channel_id(
        os.environ["BUFFER_X_ACCESS_TOKEN"], "twitter", "X"
    )


def get_threads_channel_id():
    return get_channel_id(
        os.environ["BUFFER_API_KEY"], "threads", "Threads"
    )


# ==================================================
# UPLOAD IMAGE TO FREEIMAGE.HOST
# ==================================================

def upload_to_freeimage_host(image_path):
    api_key = os.environ.get("FREEIMAGE_HOST_API_KEY")

    if not api_key:
        raise RuntimeError(
            "FREEIMAGE_HOST_API_KEY environment variable is missing."
        )

    with open(image_path, "rb") as file:
        response = requests.post(
            "https://freeimage.host/api/1/upload",
            params={"key": api_key, "format": "json"},
            files={
                "source": (
                    "mauksh_daily_mulank.jpg",
                    file,
                    "image/jpeg",
                )
            },
            timeout=120,
        )

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Freeimage.host returned non-JSON data: "
            + response.text[:500]
        ) from exc

    image_data = result.get("image") or {}
    image_url = image_data.get("url")

    if not image_url:
        raise RuntimeError(
            "Freeimage.host did not return an image URL: "
            + json.dumps(result)
        )

    print("Image uploaded successfully to Freeimage.host.")
    print("Direct image URL:", image_url)

    # Freeimage.host's response is not Picrd's response;
    # no Picrd delete_url or expiry fields are assumed.
    return image_url, None


# ==================================================
# CREATE BUFFER POST
# ==================================================

def create_buffer_post(access_token, channel_id, text, metadata, assets=None):
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

    post_input = {
        "text": text,
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "shareNow",
        "metadata": metadata,
    }
    if assets is not None:
        post_input["assets"] = assets

    data = buffer_graphql(
        access_token, mutation, {"input": post_input}
    )
    result = data.get("createPost", {})

    if result.get("message"):
        raise RuntimeError(result["message"])

    post = result.get("post")
    if not post or not post.get("id"):
        raise RuntimeError("Buffer did not return a post ID: " + json.dumps(data))

    print("Buffer post ID:", post["id"])
    print("Initial status:", post.get("status"))
    return post


# ==================================================
# INSTAGRAM POST
# ==================================================

def publish_to_instagram(image_url):
    token = os.environ["BUFFER_ACCESS_TOKEN"]
    channel_id = get_instagram_channel_id()

    caption = (
        f"Mauksh Daily Numerology for {TODAY.strftime('%d %B %Y')}\n\n"
        "Find your Mulank from your birth date and read today's guidance.\n\n"
        "Save this post for later.\n\n"
        "#Mauksh #Mulank #Numerology #DailyNumerology"
    )

    return create_buffer_post(
        token,
        channel_id,
        caption,
        {"instagram": {"type": "post", "shouldShareToFeed": True}},
        [{"image": {"url": image_url}}],
    )


# ==================================================
# FACEBOOK POST
# ==================================================

def publish_to_facebook(image_url):
    token = os.environ["BUFFER_FACEBOOK_ACCESS_TOKEN"]
    channel_id = get_facebook_channel_id()

    caption = (
        f"Mauksh Daily Numerology for {TODAY.strftime('%d %B %Y')}\n\n"
        "Find your Mulank from your birth date and read today's guidance.\n\n"
        "Save this post for later.\n\n"
        "#Mauksh #Mulank #Numerology #DailyNumerology"
    )

    return create_buffer_post(
        token,
        channel_id,
        caption,
        {"facebook": {"type": "post"}},
        [{"image": {"url": image_url}}],
    )


# ==================================================
# CREATE THREAD ITEMS
# ==================================================

def create_thread_items(horoscopes, platform):
    thread_posts = []

    for index, item in enumerate(horoscopes):
        mulank = item["mulank"]
        birth_dates = dict(MULANKS)[mulank]

        if index == 0:
            post_text = (
                f"Mauksh Daily Numerology\n\n"
                f"{TODAY.strftime('%d %B %Y')}\n\n"
                f"Mulank {mulank}\n\n"
                f"Born on {birth_dates}\n\n"
                f"{item['text']}"
            )
        else:
            post_text = (
                f"Mulank {mulank}\n\n"
                f"Born on {birth_dates}\n\n"
                f"{item['text']}"
            )

        thread_posts.append({"text": post_text})

    thread_posts[-1]["text"] += (
        "\n\nTake what feels useful. Numerology is guidance, not certainty.\n\n"
        "#Mauksh #Mulank"
    )

    if platform == "x":
        for index, item in enumerate(thread_posts):
            if len(item["text"]) > 280:
                if index == 8:
                    item["text"] = (
                        f"Mulank 9\n\n"
                        f"Born on {dict(MULANKS)[9]}\n\n"
                        f"{horoscopes[-1]['text']}\n\n"
                        "#Mauksh #Mulank"
                    )
                if len(item["text"]) > 280:
                    raise ValueError(
                        f"X post {index + 1} exceeds 280 characters."
                    )

    return thread_posts


# ==================================================
# PUBLISH X THREAD
# ==================================================

def publish_to_x(horoscopes):
    token = os.environ["BUFFER_X_ACCESS_TOKEN"]
    channel_id = get_x_channel_id()
    thread_posts = create_thread_items(horoscopes, "x")

    print("\n========== X THREAD ==========\n")
    for index, item in enumerate(thread_posts):
        print(
            f"X [{index + 1}/{len(thread_posts)}] "
            f"{len(item['text'])} characters"
        )

    return create_buffer_post(
        token,
        channel_id,
        thread_posts[0]["text"],
        {"twitter": {"thread": thread_posts}},
    )


# ==================================================
# PUBLISH THREADS THREAD
# ==================================================

def publish_to_threads(horoscopes):
    token = os.environ["BUFFER_API_KEY"]
    channel_id = get_threads_channel_id()
    thread_posts = create_thread_items(horoscopes, "threads")

    print("\n======= THREADS THREAD =======\n")
    for index, item in enumerate(thread_posts):
        print(
            f"Threads [{index + 1}/{len(thread_posts)}] "
            f"{len(item['text'])} characters"
        )

    return create_buffer_post(
        token,
        channel_id,
        thread_posts[0]["text"],
        {"threads": {"thread": thread_posts}},
    )


# ==================================================
# WAIT FOR PUBLICATION
# ==================================================

def wait_until_published(
    post_id, access_token, platform_name, timeout_seconds=900
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

    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        data = buffer_graphql(
            access_token, query, {"id": post_id}
        )
        post = data.get("post")

        if post:
            status = str(post.get("status", "")).lower()
            print(f"{platform_name} status: {status}")

            if status == "sent" or post.get("sentAt"):
                return True
            if status in ("error", "failed"):
                return False

        time.sleep(20)

    return False


# ==================================================
# MAIN
# ==================================================

def main():
    print("==================================")
    print("Starting Mauksh Daily Mulank Horoscope")
    print(TODAY.strftime("%d %B %Y"))
    print("==================================")

    horoscopes = generate_horoscopes()
    image_path = create_poster(horoscopes)

    if os.getenv("PREVIEW_ONLY", "false").lower() == "true":
        print("Preview mode enabled.")
        print("No Instagram, Facebook, X or Threads posts will be created.")
        return

    print("\n======= IMAGE UPLOAD ========\n")
    image_url, _delete_url = upload_to_freeimage_host(image_path)

    print("\n========== INSTAGRAM ==========\n")
    try:
        post = publish_to_instagram(image_url)
        published = wait_until_published(
            post["id"], os.environ["BUFFER_ACCESS_TOKEN"], "Instagram"
        )
        print("Instagram publication confirmed." if published
              else "Instagram publication not confirmed.")
    except Exception as exc:
        print("Instagram failed:", type(exc).__name__, str(exc))

    print("\n========== FACEBOOK ============\n")
    try:
        post = publish_to_facebook(image_url)
        published = wait_until_published(
            post["id"], os.environ["BUFFER_FACEBOOK_ACCESS_TOKEN"], "Facebook"
        )
        print("Facebook publication confirmed." if published
              else "Facebook publication not confirmed.")
    except Exception as exc:
        print("Facebook failed:", type(exc).__name__, str(exc))

    print("\n============== X ==============\n")
    try:
        post = publish_to_x(horoscopes)
        published = wait_until_published(
            post["id"], os.environ["BUFFER_X_ACCESS_TOKEN"], "X"
        )
        print("X thread publication confirmed." if published
              else "X thread publication not confirmed.")
    except Exception as exc:
        print("X failed:", type(exc).__name__, str(exc))

    print("\n========== THREADS ============\n")
    try:
        post = publish_to_threads(horoscopes)
        published = wait_until_published(
            post["id"], os.environ["BUFFER_API_KEY"], "Threads"
        )
        print("Threads publication confirmed." if published
              else "Threads publication not confirmed.")
    except Exception as exc:
        print("Threads failed:", type(exc).__name__, str(exc))

    print("\n==================================")
    print("Mauksh Mulank horoscope workflow finished.")
    print("Instagram: 1 image post")
    print("Facebook: 1 image post")
    print("X: 9-post thread")
    print("Threads: 9-post thread")
    print("==================================")


if __name__ == "__main__":
    main()