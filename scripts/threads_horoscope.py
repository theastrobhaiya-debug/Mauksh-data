import os
from datetime import datetime
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

today = datetime.now().strftime("%d %B %Y")

prompt = f"""
You are the official horoscope writer for Mauksh.

Generate a daily Vedic astrology-inspired horoscope specifically for Threads.

Date: {today}

FORMAT:

Mauksh Daily Horoscope
{today}

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

WRITING RULES:

- Keep each zodiac sign to 1–2 short sentences.
- Make predictions meaningful and specific.
- Do NOT write generic motivational advice.
- Do NOT use filler such as "stay positive", "good things are coming", "believe in yourself", or "avoid distractions".
- Give each zodiac sign a different situation, development, or theme.
- Naturally cover areas such as career, money, relationships, family, communication, travel, learning, decisions and opportunities.
- Make the predictions feel like an actual horoscope, not life advice.
- Keep the language natural and human.
- Avoid repeating the same sentence structure for every sign.
- Do not mention planetary calculations or explain the astrology.
- Do not add hashtags.
- Do not add an introduction or conclusion.
- Do not use bullet points.
- Do not change the title.
- Return ONLY the finished Threads post.
"""

response = client.responses.create(
    model="gpt-5.6",
    input=prompt
)

print(response.output_text)