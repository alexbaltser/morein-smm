# Морейн SMM

Веб-инструмент для подготовки постов в Telegram-канал агентства недвижимости Морейн.

**На вход:** тема поста + изображение планировки квартиры.
**На выход:** готовый текст поста (Claude Sonnet 4.6) + 1–4 фотореалистичных интерьерных рендера комнат, построенных по планировке (gpt-image-1, OpenAI Images Edit).

## Стек

- FastAPI + uvicorn
- Polza.ai (OpenAI-совместимый API) — единая точка для текста и картинок:
  - текст и vision-анализ планировки: `anthropic/claude-sonnet-4.6` через `chat/completions`
  - интерьерные рендеры: `google/gemini-3-pro-image-preview` через `images/generations`
- OpenAI SDK с `base_url=https://polza.ai/api/v1` (один SDK для обоих)
- Vanilla JS на фронте, без сборки

## Архитектура

```
app/
  main.py            # FastAPI: /api/generate, /api/styles, /api/jobs, /api/regenerate-*
  text_gen.py        # Claude — пост + анализ комнат + image_hints
  image_gen.py       # OpenAI gpt-image-1, параллельный рендер всех комнат
  style_presets.py   # 5 стилевых пресетов
  storage.py         # файловое хранилище jobs в data/jobs/<id>/
static/
  index.html, app.js, styles.css
data/jobs/<job_id>/
  job.json
  floorplan.png
  img_1_<room>.png ...
```

## Локальный запуск

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # вписать POLZA_API_KEY (pza_...)
uvicorn app.main:app --host 0.0.0.0 --port 8011 --env-file .env
```

UI: http://localhost:8011/

## Стилевые пресеты

| ID | Когда брать |
|---|---|
| `cinematic_warm` | универсальный, тёплый, эмоциональный |
| `editorial_minimal` | минимализм для широкой аудитории, AD/Elle Decor |
| `luxury_dark` | премиум-сегмент, дорогие ЖК |
| `scandi_light` | евро-форматы, семейные форматы |
| `coastal_sun` | курортный — Сочи, Анапа, Крым, Калининград |

Стили задаются в `app/style_presets.py`. После периода итераций — оставить 1–2 финальных.

## Деплой на 217.199.252.218

См. план: создать репо `alexbaltser/morein-smm`, на сервере:

```bash
mkdir /opt/morein-smm
git clone git@github.com:alexbaltser/morein-smm.git /opt/morein-smm
cd /opt/morein-smm
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
nano .env  # POLZA_API_KEY=pza_...
add-service morein-smm /opt/morein-smm "venv/bin/uvicorn app.main:app --host 0.0.0.0 --port \$PORT --env-file /opt/morein-smm/.env"
```

Nginx — добавить location `/smm/` с HTTP Basic Auth (`/etc/nginx/.htpasswd_morein`) и переадресацией на порт сервиса. Static-картинки отдавать через `alias` на `/opt/morein-smm/data/`.

## API

| Метод | Путь | Что |
|---|---|---|
| `GET` | `/health` | health-check |
| `GET` | `/api/styles` | список пресетов |
| `POST` | `/api/generate` | multipart: `topic`, `style`, `n_images`, `floorplan` → текст + картинки |
| `GET` | `/api/jobs/{id}` | вернуть сохранённый джоб |
| `POST` | `/api/regenerate-text/{id}` | новый вариант текста |
| `POST` | `/api/regenerate-image/{id}/{idx}` | перерендерить картинку (опц. `extra_prompt` form-field) |

## Стоимость генерации

Через Polza.ai в рублях. Точные тарифы — в `/api/v1/models`. Ориентир:
- Текст (claude-sonnet-4.6 с vision): ~5–10 ₽ за пост
- Картинка (gemini-3-pro-image-preview, 1536×1024): ~15–30 ₽ за штуку
- Один пост с 3 рендерами: ~50–100 ₽

## Заметки

- Polza отдаёт картинки асинхронно (с июля 2026): `images.generate` возвращает только `requestId`, готовый JPEG забирается поллингом `GET /images/{requestId}` до `status=COMPLETED` — реализовано в `image_gen._poll_result_url`. Параметр `size` агрегатор игнорирует, возвращает 1024×1024.
- Tone-of-voice и жёсткие правила (без «юридики», без латиницы кроме ROI/ADR, кварталы прописью) зашиты в системный промпт `text_gen.py`. При правке стиля — там же.
- Запрашиваемые ключи комнат и их русские названия — в `image_gen.ROOM_PROMPTS_*`.
- `data/` в `.gitignore` — не коммитим.
