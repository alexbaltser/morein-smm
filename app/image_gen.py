"""Генерация интерьерных рендеров через Polza.ai (OpenAI-compatible images endpoint).

Стратегия v1: используем `images.generate` с Gemini 3 Pro Image. Детали планировки
(площадь, окна, форма комнаты, евро/изолированная) уже извлечены текстовой моделью
на предыдущем шаге и приходят в `hint`. Это даёт верный по духу рендер без зависимости
от поддержки image-to-image edit-эндпойнтов на стороне агрегатора.
"""

from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path

from openai import AsyncOpenAI

from .style_presets import StylePreset

POLZA_BASE_URL = "https://polza.ai/api/v1"
MODEL = "google/gemini-3-pro-image-preview"
SIZE = "1536x1024"

ROOM_PROMPTS_RU = {
    "living_room": "просторной гостиной",
    "bedroom": "спальни",
    "kitchen": "кухни",
    "kitchen_living": "кухни-гостиной (евро-формат)",
    "bathroom": "ванной комнаты",
    "hallway": "прихожей",
    "balcony": "балкона",
    "terrace": "террасы с видом",
    "kids_room": "детской комнаты",
    "office": "кабинета",
    "dining_room": "обеденной зоны",
    "master_bedroom": "мастер-спальни с собственной ванной",
    "full_apartment_overview": "общего вида квартиры (открытое пространство)",
}

ROOM_PROMPTS_EN = {
    "living_room": "the living room",
    "bedroom": "the bedroom",
    "kitchen": "the kitchen",
    "kitchen_living": "the open-plan kitchen-living room (Euro layout)",
    "bathroom": "the bathroom",
    "hallway": "the entrance hallway",
    "balcony": "the balcony with a view",
    "terrace": "the terrace with a view",
    "kids_room": "the kids' room",
    "office": "the home office",
    "dining_room": "the dining area",
    "master_bedroom": "the master bedroom with ensuite",
    "full_apartment_overview": (
        "an isometric cutaway overview of an entire apartment, "
        "showing all rooms furnished, top-down 3/4 angle"
    ),
}


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["POLZA_API_KEY"],
        base_url=POLZA_BASE_URL,
    )


def _build_prompt(room_key: str, hint: str, preset: StylePreset) -> str:
    room_en = ROOM_PROMPTS_EN.get(room_key, "the room")
    return (
        f"Photorealistic interior render of {room_en}. "
        f"Architectural details from the apartment floor plan: {hint or 'follow standard residential proportions'}. "
        f"Style: {preset.prompt_fragment}. "
        f"Lighting: {preset.lighting}. "
        f"Mood: {preset.mood}. "
        f"Colour palette: {preset.palette}. "
        f"Camera: eye-level wide-angle 24mm, full-frame, sharp throughout. "
        f"Furnish the room appropriately for a high-end residential listing in a Russian coastal resort city. "
        f"No text, no logos, no watermarks, no people, no signage in any language."
    )


async def _render_one(
    room_key: str,
    hint: str,
    preset: StylePreset,
    out_path: Path,
) -> Path:
    client = _client()
    prompt = _build_prompt(room_key, hint, preset)

    resp = await client.images.generate(
        model=MODEL,
        prompt=prompt,
        size=SIZE,
        n=1,
    )

    item = resp.data[0]
    if getattr(item, "b64_json", None):
        out_path.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        # Fallback: скачать по URL
        import httpx
        async with httpx.AsyncClient(timeout=60) as http:
            r = await http.get(item.url)
            r.raise_for_status()
            out_path.write_bytes(r.content)
    else:
        raise RuntimeError(f"image response had neither b64_json nor url: {item}")

    return out_path


async def render_rooms(
    floorplan_bytes: bytes,  # сохраняем сигнатуру для совместимости с main.py
    rooms: list[str],
    hints: list[str],
    preset: StylePreset,
    job_dir: Path,
) -> list[Path]:
    """Параллельно рендерит все запрошенные комнаты, возвращает список путей к PNG."""
    job_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for idx, (room, hint) in enumerate(zip(rooms, hints), start=1):
        out_path = job_dir / f"img_{idx}_{room}.png"
        tasks.append(_render_one(room, hint, preset, out_path))
    return await asyncio.gather(*tasks)


async def render_one_image(
    floorplan_bytes: bytes,
    room_key: str,
    hint: str,
    preset: StylePreset,
    out_path: Path,
) -> Path:
    """Перегенерация одной картинки."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return await _render_one(room_key, hint, preset, out_path)
