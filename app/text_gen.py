"""Генерация текста поста и анализ планировки через Claude Sonnet 4.6."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from anthropic import AsyncAnthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """Ты — SMM-копирайтер агентства недвижимости Морейн. Морейн помогает клиентам выбирать и покупать курортную недвижимость в России (Сочи, Анапа, Крым, Алтай, Калининград, Горы).

Тон голоса:
- Уверенный экспертный, без воды и без штампов вроде «жилой комплекс мечты»
- Конкретные факты и цифры важнее эмоций. Если фактов нет — не выдумывай
- Без канцелярита и продающего давления. Не пиши «успей», «горячее предложение», «не упусти»
- Без обращений «друзья», «дорогие подписчики». Сразу к делу
- Эмодзи — максимум 1–2 на пост, в начале строк-буллетов или в конце абзаца. Не злоупотребляй

Жёсткие правила:
- НЕ использовать слово «юридика» — заменять на «правовой вопрос», «правовая сторона»
- НЕ использовать английские слова латиницей в тексте поста. Писать по-русски: «верхний ценовой сегмент» вместо premium, «пентхаус» вместо penthouse, «семейный» вместо family. Исключения: ROI, ADR, RevPAR, IRR
- Кварталы писать словами: «1 квартал», «2 квартал» — НЕ Q1/Q2
- Ничего не выдумывать про конкретные ЖК, цены, доходность, если это не дано в теме поста

Структура поста для Telegram-канала Морейн:
- Хук в первой строке (1 короткое предложение, цепляющее внимание)
- Пустая строка
- 1–2 абзаца ключевой мысли (что за объект / преимущество / идея)
- 2–3 буллета с конкретикой по планировке или объекту (использовать •)
- Финальная строка-CTA: ссылка на morein.pro или приглашение в личку
- Длина 600–900 знаков

Формат вывода — ТОЛЬКО JSON без markdown-обёртки:
{
  "post_text": "готовый текст поста",
  "rooms": ["living_room", "bedroom", "kitchen"],
  "rooms_ru": ["гостиная", "спальня", "кухня"],
  "image_hints": ["конкретные детали для рендера комнаты 1", "...для комнаты 2", "..."]
}

Поле `rooms` — английские ключи комнат, которые ты определил по планировке (для промпта генератора картинок). Доступные ключи: living_room, bedroom, kitchen, kitchen_living, bathroom, hallway, balcony, terrace, kids_room, office, dining_room, master_bedroom, full_apartment_overview.
Поле `image_hints` — массив строк той же длины, что rooms. В каждой строке — конкретные архитектурные детали из планировки (площадь комнаты, наличие окон/балкона, форма комнаты), чтобы рендер был верен планировке.
Количество комнат в rooms должно совпадать с запрошенным n_images."""


def _client() -> AsyncAnthropic:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    return AsyncAnthropic(api_key=api_key)


def _image_to_base64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def _detect_media_type(image_bytes: bytes) -> str:
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


async def generate_post_and_analyze(
    topic: str,
    floorplan_bytes: bytes,
    n_images: int,
    style_label: str,
) -> dict[str, Any]:
    """Возвращает {post_text, rooms, rooms_ru, image_hints}."""
    user_text = f"""Тема поста: {topic}

Стиль рендеров: {style_label}

К посту прикладывается планировка квартиры (см. изображение). Проанализируй планировку:
- какие комнаты на ней изображены, их площади и расположение
- что в ней сильного с точки зрения покупателя (евро-формат, мастер-спальня, окна на две стороны, балкон с видом, и т.д.)

Затем напиши пост по правилам выше и подбери {n_images} комнат(ы) для рендеров — самые продающие в этой планировке.

Верни СТРОГО JSON, без markdown-обёртки."""

    media_type = _detect_media_type(floorplan_bytes)
    image_b64 = _image_to_base64(floorplan_bytes)

    client = _client()
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    )

    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json\n"):
            raw = raw[5:]
    parsed = json.loads(raw)

    rooms = parsed.get("rooms") or []
    rooms_ru = parsed.get("rooms_ru") or rooms
    hints = parsed.get("image_hints") or [""] * len(rooms)
    if len(hints) < len(rooms):
        hints = hints + [""] * (len(rooms) - len(hints))

    return {
        "post_text": parsed["post_text"].strip(),
        "rooms": rooms[:n_images],
        "rooms_ru": rooms_ru[:n_images],
        "image_hints": hints[:n_images],
    }


async def regenerate_text_only(topic: str, prior_rooms_ru: list[str]) -> str:
    """Перегенерация только текста без новой обработки планировки."""
    client = _client()
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Тема: {topic}\n"
                            f"В планировке выделены комнаты: {', '.join(prior_rooms_ru)}\n\n"
                            "Напиши новый вариант поста по правилам. "
                            'Верни JSON: {"post_text": "..."}'
                        ),
                    }
                ],
            }
        ],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json\n"):
            raw = raw[5:]
    return json.loads(raw)["post_text"].strip()
