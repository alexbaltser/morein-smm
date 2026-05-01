"""FastAPI приложение Морейн SMM."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import image_gen, storage, text_gen
from .style_presets import PRESETS, get_preset, list_presets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("morein-smm")

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

app = FastAPI(title="Морейн SMM")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/styles")
async def styles():
    return list_presets()


@app.post("/api/generate")
async def generate(
    topic: str = Form(...),
    style: str = Form(...),
    n_images: int = Form(3),
    floorplan: UploadFile = File(...),
):
    if style not in PRESETS:
        raise HTTPException(400, f"unknown style: {style}")
    if not 1 <= n_images <= 4:
        raise HTTPException(400, "n_images must be 1..4")

    floorplan_bytes = await floorplan.read()
    if len(floorplan_bytes) < 1000:
        raise HTTPException(400, "floorplan file too small")

    preset = get_preset(style)
    job_id = storage.new_job_id()
    suffix = Path(floorplan.filename or "floorplan.png").suffix.lower() or ".png"
    if suffix not in (".png", ".jpg", ".jpeg", ".webp"):
        suffix = ".png"
    storage.save_floorplan(job_id, floorplan_bytes, suffix=suffix)

    log.info("job %s start: topic=%r style=%s n=%d", job_id, topic[:80], style, n_images)

    try:
        text_result = await text_gen.generate_post_and_analyze(
            topic=topic,
            floorplan_bytes=floorplan_bytes,
            n_images=n_images,
            style_label=preset.label,
        )
    except Exception as e:
        log.exception("text gen failed for %s", job_id)
        raise HTTPException(500, f"text generation failed: {e}")

    rooms = text_result["rooms"]
    rooms_ru = text_result["rooms_ru"]
    hints = text_result["image_hints"]
    log.info("job %s rooms=%s", job_id, rooms)

    try:
        image_paths = await image_gen.render_rooms(
            floorplan_bytes=floorplan_bytes,
            rooms=rooms,
            hints=hints,
            preset=preset,
            job_dir=storage.job_dir(job_id),
        )
    except Exception as e:
        log.exception("image gen failed for %s", job_id)
        raise HTTPException(500, f"image generation failed: {e}")

    images_meta = []
    for path, room, room_ru, hint in zip(image_paths, rooms, rooms_ru, hints):
        images_meta.append({
            "url": f"/data/jobs/{job_id}/{path.name}",
            "room": room,
            "room_ru": room_ru,
            "hint": hint,
        })

    payload = {
        "job_id": job_id,
        "topic": topic,
        "style": style,
        "post_text": text_result["post_text"],
        "images": images_meta,
    }
    storage.save_job(job_id, payload)
    log.info("job %s done", job_id)
    return payload


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    try:
        return storage.load_job(job_id)
    except FileNotFoundError:
        raise HTTPException(404, "job not found")


@app.post("/api/regenerate-text/{job_id}")
async def regenerate_text(job_id: str):
    try:
        job = storage.load_job(job_id)
    except FileNotFoundError:
        raise HTTPException(404, "job not found")
    rooms_ru = [img["room_ru"] for img in job["images"]]
    new_text = await text_gen.regenerate_text_only(job["topic"], rooms_ru)
    job["post_text"] = new_text
    storage.save_job(job_id, job)
    return {"post_text": new_text}


@app.post("/api/regenerate-image/{job_id}/{idx}")
async def regenerate_image(
    job_id: str,
    idx: int,
    extra_prompt: str = Form(""),
):
    try:
        job = storage.load_job(job_id)
    except FileNotFoundError:
        raise HTTPException(404, "job not found")
    if not 0 <= idx < len(job["images"]):
        raise HTTPException(400, "image index out of range")

    floorplan_bytes = storage.load_floorplan(job_id)
    preset = get_preset(job["style"])
    img = job["images"][idx]
    hint = img["hint"]
    if extra_prompt.strip():
        hint = (hint + ". " + extra_prompt.strip()).strip(". ")

    out_path = storage.job_dir(job_id) / Path(img["url"]).name
    await image_gen.render_one_image(
        floorplan_bytes=floorplan_bytes,
        room_key=img["room"],
        hint=hint,
        preset=preset,
        out_path=out_path,
    )
    img["hint"] = hint
    img["url"] = img["url"] + f"?v={out_path.stat().st_mtime_ns}"
    storage.save_job(job_id, job)
    return {"image": img}


# --- статика ---
app.mount(
    "/data",
    StaticFiles(directory=storage.DATA_ROOT, check_dir=False),
    name="data",
)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
