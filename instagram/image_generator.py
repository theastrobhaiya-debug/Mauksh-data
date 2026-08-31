import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

DATA_FILE = OUTPUT_DIR / "daily_horoscope.json"

WIDTH = 1080
HEIGHT = 1350

BACKGROUND = "#F8F3EA"
TEXT = "#1F1A17"
ACCENT = "#8B5E34"


SIGNS = [
    ("aries", "♈", "Aries"),
    ("taurus", "♉", "Taurus"),
    ("gemini", "♊", "Gemini"),
    ("cancer", "♋", "Cancer"),
    ("leo", "♌", "Leo"),
    ("virgo", "♍", "Virgo"),
    ("libra", "♎", "Libra"),
    ("scorpio", "♏", "Scorpio"),
    ("sagittarius", "♐", "Sagittarius"),
    ("capricorn", "♑", "Capricorn"),
    ("aquarius", "♒", "Aquarius"),
    ("pisces", "♓", "Pisces"),
]


def load_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    path = candidates[1] if size > 30 else candidates[0]

    return ImageFont.truetype(path, size)


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()

        bbox = draw.textbbox(
            (0, 0),
            test,
            font=font
        )

        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


def draw_wrapped(
    draw,
    text,
    x,
    y,
    font,
    max_width,
    line_spacing=8,
):
    lines = wrap_text(
        draw,
        text,
        font,
        max_width
    )

    line_height = font.size + line_spacing

    for line in lines:
        draw.text(
            (x, y),
            line,
            font=font,
            fill=TEXT
        )

        y += line_height

    return y


with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)


def create_slide(sign_group, slide_number):
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BACKGROUND
    )

    draw = ImageDraw.Draw(image)

    title_font = load_font(54)
    sign_font = load_font(34)
    body_font = load_font(24)
    small_font = load_font(20)

    y = 60

    draw.text(
        (60, y),
        "MAUKSH",
        font=title_font,
        fill=ACCENT
    )

    y += 70

    draw.text(
        (60, y),
        f"DAILY HOROSCOPE · {data['date']}",
        font=small_font,
        fill=TEXT
    )

    y += 65

    for slug, emoji, name in sign_group:

        draw.text(
            (60, y),
            f"{emoji} {name}",
            font=sign_font,
            fill=ACCENT
        )

        y += 48

        sections = [
            ("Overall", data[slug]["overall"]),
            ("Career", data[slug]["career"]),
            ("Love", data[slug]["love"]),
            ("Money", data[slug]["money"]),
            ("Advice", data[slug]["advice"]),
            ("Mauksh Truth", data[slug]["mauksh_truth"]),
        ]

        for label, value in sections:

            text = f"{label}: {value}"

            y = draw_wrapped(
                draw,
                text,
                60,
                y,
                body_font,
                WIDTH - 120,
                5,
            )

            y += 7

        y += 20

        # Safety check to prevent overflow
        if y > HEIGHT - 70:
            raise ValueError(
                f"Slide {slide_number} text overflowed. "
                "Reduce horoscope length."
            )

    draw.text(
        (60, HEIGHT - 45),
        f"MAUKSH · {slide_number}/2",
        font=small_font,
        fill=ACCENT
    )

    filename = OUTPUT_DIR / f"instagram_{slide_number}.jpg"

    image.save(
        filename,
        "JPEG",
        quality=95,
        optimize=True
    )

    print(f"Created {filename}")


create_slide(SIGNS[:6], 1)
create_slide(SIGNS[6:], 2)
