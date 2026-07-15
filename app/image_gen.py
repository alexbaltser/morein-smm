"""Генерация интерьерных рендеров через Polza.ai (OpenAI-compatible images endpoint).

Стратегия v1: используем `images.generate` с Gemini 3 Pro Image. Детали планировки
(площадь, окна, форма комнаты, евро/изолированная) уже извлечены текстовой моделью
на предыдущем шаге и приходят в `hint`. Это даёт верный по духу рендер без зависимости
от поддержки image-to-image edit-эндпойнтов на стороне агрегатора.

Polza отдаёт генерацию асинхронно: `images.generate` возвращает только `requestId`
(`resp.data` = None), результат забираем поллингом `GET /images/{requestId}` до
`status=COMPLETED` — там ссылка на готовый JPEG. Параметр `size` агрегатор сейчас
игнорирует и возвращает 1024×1024.
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from .style_presets import StylePreset

POLZA_BASE_URL = "https://polza.ai/api/v1"
MODEL = "google/gemini-3-pro-image-preview"
SIZE = "1536x1024"
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 300

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


async def _poll_result_url(request_id: str) -> str:
    """Поллит GET /images/{requestId}, пока Polza не отдаст ссылку на готовую картинку."""
    headers = {"Authorization": f"Bearer {os.environ['POLZA_API_KEY']}"}
    deadline = time.monotonic() + POLL_TIMEOUT_S
    async with httpx.AsyncClient(timeout=60, headers=headers) as http:
        while time.monotonic() < deadline:
            await asyncio.sleep(POLL_INTERVAL_S)
            r = await http.get(f"{POLZA_BASE_URL}/images/{request_id}")
            r.raise_for_status()
            data = r.json()
            status = (data.get("status") or "").upper()
            if status == "COMPLETED":
                url = data.get("url") or (data.get("images") or [None])[0]
                if not url:
                    raise RuntimeError(f"generation {request_id} completed without url: {data}")
                return url
            if status in ("FAILED", "ERROR", "CANCELLED"):
                raise RuntimeError(f"generation {request_id} ended with {status}: {data}")
    raise TimeoutError(f"generation {request_id} not completed in {POLL_TIMEOUT_S}s")


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

    url: str | None = None
    if resp.data:
        # Синхронный ответ (старый формат) — вдруг Polza вернёт его снова
        item = resp.data[0]
        if getattr(item, "b64_json", None):
            out_path.write_bytes(base64.b64decode(item.b64_json))
            return out_path
        url = getattr(item, "url", None)

    if not url:
        request_id = getattr(resp, "requestId", None) or (resp.model_extra or {}).get("requestId")
        if not request_id:
            raise RuntimeError(f"image response had neither data nor requestId: {resp}")
        url = await _poll_result_url(request_id)

    async with httpx.AsyncClient(timeout=120) as http:
        r = await http.get(url)
        r.raise_for_status()
        out_path.write_bytes(r.content)

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
