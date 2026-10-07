import os
import time
import json
import requests
import textwrap

from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# CONFIG
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

TODAY = datetime.now(IST)
DATE_TEXT = TODAY.strftime("%d %B %Y")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

BUFFER_ACCESS_TOKEN = os.environ["BUFFER_ACCESS_TOKEN"]
BUFFER_X_ACCESS_TOKEN = os.environ["BUFFER_X_ACCESS_TOKEN"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]

PICRD_UPLOAD_URL = "https://picrd.com/api/upload"
BUFFER_URL = "https://api.buffer.com"

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# MULANK BIRTH DATE MAPPING
# ============================================================

MULANKS = {
    1: "1, 10, 19, 28",
    2: "2, 11, 20, 29",
    3: "3, 12, 21, 30",
    4: "4, 13, 22, 31",
    5: "5, 14, 23",
    6: "6, 15, 24",
    7: "7, 16, 25",
    8: "8, 17, 26",
    9: "9, 18, 27",
}


# ============================================================
# NUMBER REDUCTION
# ============================================================

def reduce_to_single_digit(number):
    while number > 9:
        number = sum(int(digit) for digit in str(number))

    return number


def get_daily_number():

    total = (
        TODAY.day
        + TODAY.month
        + TODAY.year
    )

    return reduce_to_single_digit(total)


DAILY_NUMBER = get_daily_number()


# ============================================================
# GENERATE MULANK HOROSCOPES
# ============================================================

def generate_mulank_horoscopes():

    prompt = f"""
You are writing Mauksh Daily Numerology for {DATE_TEXT}.

Generate exactly 9 daily numerology predictions.

Today's numerology energy number is {DAILY_NUMBER}.

The Mulank birth date groups are:

Mulank 1: born on 1, 10, 19, 28
Mulank 2: born on 2, 11, 20, 29
Mulank 3: born on 3, 12, 21, 30
Mulank 4: born on 4, 13, 22, 31
Mulank 5: born on 5, 14, 23
Mulank 6: born on 6, 15, 24
Mulank 7: born on 7, 16, 25
Mulank 8: born on 8, 17, 26
Mulank 9: born on 9, 18, 27

CONTENT RULES:

Write one prediction for each Mulank from 1 to 9.

Each prediction must be between 18 and 24 words.

Write natural, human sounding English.

The tone should feel like an experienced numerologist giving practical daily guidance.

Focus on the overall energy of the day.

Predictions may cover work, money, relationships, communication, decisions, confidence, productivity or emotional balance.

Make every Mulank prediction meaningfully different.

Do not mention planets.

Do not mention astrology.

Do not make guaranteed predictions.

Do not use fear based language.

Do not use emojis.

Do not use hashtags.

Do not use Markdown.

Do not use bullet points.

Do not use hyphens.

Do not use em dashes.

Do not use en dashes.

Do not use dash based formatting.

Avoid generic AI sounding phrases.

Keep the language simple and natural.

Return valid JSON only.

Use exactly this structure:

{{
    "1": "prediction",
    "2": "prediction",
    "3": "prediction",
    "4": "prediction",
    "5": "prediction",
    "6": "prediction",
    "7": "prediction",
    "8": "prediction",
    "9": "prediction"
}}
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    raw = response.output_text.strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "")
        raw = raw.replace("```", "")
        raw = raw.strip()

    data = json.loads(raw)

    results = []

    for mulank in range(1, 10):

        prediction = str(
            data[str(mulank)]
        ).strip()

        # Remove AI style dash characters
        prediction = prediction.replace("—", "")
        prediction = prediction.replace("–", "")
        prediction = prediction.replace(" - ", " ")

        results.append({
            "mulank": mulank,
            "birth_dates": MULANKS[mulank],
            "text": prediction
        })

    return results


# ============================================================
# SOCIAL MEDIA POST FORMAT
# ============================================================

def format_mulank_post(item):

    return (
        f"Mulank {item['mulank']}\n\n"
        f"Born on {item['birth_dates']}\n\n"
        f"{item['text']}"
    )


# ============================================================
# TITLE FORMAT
# ============================================================

def format_title():

    return (
        "MAUKSH DAILY NUMEROLOGY\n\n"
        f"{DATE_TEXT}"
    )


# ============================================================
# FONT LOADER
# ============================================================

def load_font(size, bold=False):

    if bold:

        possible_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        ]

    else:

        possible_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
        ]

    for path in possible_fonts:

        if os.path.exists(path):

            return ImageFont.truetype(
                path,
                size
            )

    return ImageFont.load_default()


# ============================================================
# CREATE GOLDEN POSTER
# ============================================================

def create_poster(horoscopes):

    WIDTH = 1080
    HEIGHT = 1350

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (250, 194, 55)
    )

    draw = ImageDraw.Draw(img)

    title_font = load_font(
        48,
        bold=True
    )

    date_font = load_font(
        30
    )

    number_font = load_font(
        32,
        bold=True
    )

    body_font = load_font(
        24
    )

    small_font = load_font(
        22
    )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    title = "MAUKSH DAILY NUMEROLOGY"

    bbox = draw.textbbox(
        (0, 0),
        title,
        font=title_font
    )

    title_width = bbox[2] - bbox[0]

    draw.text(
        (
            (WIDTH - title_width) / 2,
            35
        ),
        title,
        fill=(55, 35, 10),
        font=title_font
    )

    date_y = 100

    bbox = draw.textbbox(
        (0, 0),
        DATE_TEXT,
        font=date_font
    )

    date_width = bbox[2] - bbox[0]

    draw.text(
        (
            (WIDTH - date_width) / 2,
            date_y
        ),
        DATE_TEXT,
        fill=(75, 50, 15),
        font=date_font
    )

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

    card_x = 45
    card_width = WIDTH - 90

    card_height = 120
    gap = 10

    start_y = 155

    for index, item in enumerate(horoscopes):

        y = start_y + index * (
            card_height + gap
        )

        # Card background
        draw.rounded_rectangle(
            (
                card_x,
                y,
                card_x + card_width,
                y + card_height
            ),
            radius=20,
            fill=(255, 248, 225)
        )

        # ----------------------------------------------------
        # MULANK
        # ----------------------------------------------------

        number_text = (
            f"Mulank {item['mulank']}"
        )

        draw.text(
            (
                70,
                y + 12
            ),
            number_text,
            fill=(70, 45, 10),
            font=number_font
        )

        # ----------------------------------------------------
        # BIRTH DATES
        # ----------------------------------------------------

        birth_text = (
            f"Born on {item['birth_dates']}"
        )

        draw.text(
            (
                70,
                y + 55
            ),
            birth_text,
            fill=(100, 75, 30),
            font=small_font
        )

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        prediction = item["text"]

        wrapped = textwrap.wrap(
            prediction,
            width=48
        )

        prediction_x = 420
        prediction_y = y + 18

        for line in wrapped[:3]:

            draw.text(
                (
                    prediction_x,
                    prediction_y
                ),
                line,
                fill=(55, 45, 25),
                font=body_font
            )

            prediction_y += 29

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    output_file = (
        "mulank_daily_horoscope.png"
    )

    img.save(
        output_file,
        quality=95
    )

    return output_file


# ============================================================
# UPLOAD IMAGE TO PICRD
# ============================================================

def upload_image_to_picrd(image_path):

    with open(
        image_path,
        "rb"
    ) as image_file:

        response = requests.post(
            PICRD_UPLOAD_URL,
            files={
                "file": image_file
            },
            timeout=60
        )

    response.raise_for_status()

    data = response.json()

    image_url = (
        data.get("url")
        or data.get("image_url")
        or data.get("link")
    )

    if not image_url:

        raise RuntimeError(
            "Picrd did not return an image URL: "
            + json.dumps(data)
        )

    return image_url


# ============================================================
# BUFFER REQUEST
# ============================================================

def buffer_request(
    token,
    query,
    variables=None
):

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": query
    }

    if variables is not None:

        payload["variables"] = variables

    response = requests.post(
        BUFFER_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:

        raise RuntimeError(
            "Buffer API error:\n"
            + json.dumps(
                data["errors"],
                indent=2
            )
        )

    return data


# ============================================================
# GET BUFFER CHANNELS
# ============================================================

def get_channels(token):

    query = """
    query {
        account {
            organizations {
                id
                channels {
                    id
                    name
                    service
                }
            }
        }
    }
    """

    return buffer_request(
        token,
        query
    )


# ============================================================
# FIND BUFFER CHANNEL
# ============================================================

def find_channel(
    token,
    service
):

    data = get_channels(
        token
    )

    organizations = (
        data["data"]["account"]["organizations"]
    )

    for organization in organizations:

        for channel in organization["channels"]:

            if (
                channel["service"].lower()
                == service.lower()
            ):

                return channel["id"]

    raise RuntimeError(
        f"No Buffer channel found for {service}"
    )


# ============================================================
# INSTAGRAM
# ============================================================

def create_instagram_post(
    image_url,
    caption
):

    channel_id = find_channel(
        BUFFER_ACCESS_TOKEN,
        "instagram"
    )

    mutation = """
    mutation CreateInstagramPost(
        $input: CreatePostInput!
    ) {
        createPost(input: $input) {

            ... on PostActionSuccess {
                post {
                    id
                    status
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
            ]
        }
    }

    data = buffer_request(
        BUFFER_ACCESS_TOKEN,
        mutation,
        variables
    )

    print(
        "\nInstagram response:"
    )

    print(
        json.dumps(
            data,
            indent=2
        )
    )

    return data


# ============================================================
# X THREAD
# ============================================================

def create_x_thread(
    horoscopes
):

    channel_id = find_channel(
        BUFFER_X_ACCESS_TOKEN,
        "twitter"
    )

    thread_items = []

    for item in horoscopes:

        thread_items.append({
            "text": format_mulank_post(item)
        })

    first_text = thread_items[0]["text"]

    mutation = """
    mutation CreateXThread(
        $input: CreatePostInput!
    ) {
        createPost(input: $input) {

            ... on PostActionSuccess {
                post {
                    id
                    status
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

            "text": first_text,

            "channelId": channel_id,

            "schedulingType": "automatic",

            "mode": "shareNow",

            "metadata": {

                "twitter": {

                    "thread": thread_items

                }

            }

        }
    }

    data = buffer_request(
        BUFFER_X_ACCESS_TOKEN,
        mutation,
        variables
    )

    print(
        "\nX thread response:"
    )

    print(
        json.dumps(
            data,
            indent=2
        )
    )

    return data


# ============================================================
# THREADS THREAD
# ============================================================

def create_threads_thread(
    horoscopes
):

    channel_id = find_channel(
        BUFFER_API_KEY,
        "threads"
    )

    thread_items = []

    for item in horoscopes:

        thread_items.append({
            "text": format_mulank_post(item)
        })

    first_text = thread_items[0]["text"]

    mutation = """
    mutation CreateThreadsThread(
        $input: CreatePostInput!
    ) {
        createPost(input: $input) {

            ... on PostActionSuccess {
                post {
                    id
                    status
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

            "text": first_text,

            "channelId": channel_id,

            "schedulingType": "automatic",

            "mode": "shareNow",

            "metadata": {

                "threads": {

                    "thread": thread_items

                }

            }

        }
    }

    data = buffer_request(
        BUFFER_API_KEY,
        mutation,
        variables
    )

    print(
        "\nThreads response:"
    )

    print(
        json.dumps(
            data,
            indent=2
        )
    )

    return data


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 60
    )

    print(
        "MAUKSH DAILY NUMEROLOGY"
    )

    print(
        DATE_TEXT
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    print(
        "\nGenerating Mulank predictions..."
    )

    horoscopes = (
        generate_mulank_horoscopes()
    )

    for item in horoscopes:

        print(
            f"Mulank {item['mulank']}"
        )

        print(
            f"Born on {item['birth_dates']}"
        )

        print(
            item["text"]
        )

        print()

    # --------------------------------------------------------
    # POSTER
    # --------------------------------------------------------

    print(
        "Creating poster..."
    )

    image_path = create_poster(
        horoscopes
    )

    print(
        f"Poster created: {image_path}"
    )

    # --------------------------------------------------------
    # PICRD
    # --------------------------------------------------------

    print(
        "Uploading poster..."
    )

    image_url = upload_image_to_picrd(
        image_path
    )

    print(
        f"Image URL: {image_url}"
    )

    # --------------------------------------------------------
    # INSTAGRAM
    # --------------------------------------------------------

    print(
        "\nPublishing Instagram..."
    )

    instagram_caption = (
        "Mauksh Daily Numerology\n\n"
        f"{DATE_TEXT}\n\n"
        "Check your Mulank and see what today's "
        "energy brings.\n\n"
        "Spirituality is Personal."
    )

    create_instagram_post(
        image_url,
        instagram_caption
    )

    time.sleep(5)

    # --------------------------------------------------------
    # X
    # --------------------------------------------------------

    print(
        "\nPublishing X thread..."
    )

    create_x_thread(
        horoscopes
    )

    time.sleep(5)

    # --------------------------------------------------------
    # THREADS
    # --------------------------------------------------------

    print(
        "\nPublishing Threads thread..."
    )

    create_threads_thread(
        horoscopes
    )

    # --------------------------------------------------------
    # DONE
    # --------------------------------------------------------

    print(
        "\n"
        + "=" * 60
    )

    print(
        "ALL POSTS SENT"
    )

    print(
        "=" * 60
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
