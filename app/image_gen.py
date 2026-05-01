"""Генерация интерьерных рендеров через OpenAI gpt-image-1."""

from __future__ import annotations

import asyncio
import base64
import io
import os
from pathlib import Path

from openai import AsyncOpenAI

from .style_presets import StylePreset

MODEL = "gpt-image-1"
SIZE = "1536x1024"
QUALITY = "high"

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
        "an isometric cutaway overview of the entire apartment, "
        "showing all rooms furnished, in the same orientation as the floor plan"
    ),
}


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _build_prompt(room_key: str, hint: str, preset: StylePreset) -> str:
    room_en = ROOM_PROMPTS_EN.get(room_key, "the room")
    return (
        f"Photorealistic interior render of {room_en}, faithful to the attached floor plan "
        f"(same proportions, window placement, and door positions). "
        f"Specific details from the plan: {hint or 'follow the floor plan precisely'}. "
        f"Style: {preset.prompt_fragment}. "
        f"Lighting: {preset.lighting}. "
        f"Mood: {preset.mood}. "
        f"Colour palette: {preset.palette}. "
        f"Camera: eye-level wide-angle 24mm, full-frame, sharp throughout. "
        f"Furnish the room appropriately for a high-end residential listing. "
        f"No text, no logos, no watermarks, no people."
    )


async def _render_one(
    floorplan_bytes: bytes,
    room_key: str,
    hint: str,
    preset: StylePreset,
    out_path: Path,
) -> Path:
    client = _client()
    prompt = _build_prompt(room_key, hint, preset)

    resp = await client.images.edit(
        model=MODEL,
        image=("floorplan.png", io.BytesIO(floorplan_bytes), "image/png"),
        prompt=prompt,
        size=SIZE,
        quality=QUALITY,
        n=1,
    )

    b64 = resp.data[0].b64_json
    out_path.write_bytes(base64.b64decode(b64))
    return out_path


async def render_rooms(
    floorplan_bytes: bytes,
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
        tasks.append(_render_one(floorplan_bytes, room, hint, preset, out_path))
    return await asyncio.gather(*tasks)


async def render_one_image(
    floorplan_bytes: bytes,
    room_key: str,
    hint: str,
    preset: StylePreset,
    out_path: Path,
) -> Path:
    """Перегенерация одной картинки (для regenerate-image эндпоинта)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return await _render_one(floorplan_bytes, room_key, hint, preset, out_path)
