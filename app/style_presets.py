"""Стилевые пресеты для генерации интерьерных рендеров."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StylePreset:
    id: str
    label: str
    description: str
    prompt_fragment: str
    lighting: str
    mood: str
    palette: str


PRESETS: dict[str, StylePreset] = {
    "cinematic_warm": StylePreset(
        id="cinematic_warm",
        label="Кинематографичный тёплый",
        description="Тёплый кинематографичный свет, плёночное зерно, глубокие тени",
        prompt_fragment=(
            "cinematic editorial interior photography, anamorphic 35mm film look, "
            "subtle film grain, rich warm tones, soft golden hour light spilling through windows, "
            "shallow depth of field, magazine-quality composition"
        ),
        lighting="warm golden hour sunlight streaming through large windows, soft shadows",
        mood="atmospheric, intimate, aspirational",
        palette="warm beige, terracotta, oak wood, brushed brass accents",
    ),
    "editorial_minimal": StylePreset(
        id="editorial_minimal",
        label="Журнальный минимализм",
        description="Свежий минимализм в духе AD / Elle Decor, естественный дневной свет",
        prompt_fragment=(
            "editorial interior photography in the style of Architectural Digest and Elle Decor, "
            "clean minimalist composition, generous negative space, premium materials, "
            "understated luxury, neutral tonal palette, sharp architectural lines"
        ),
        lighting="bright diffused daylight, soft natural shadows, no artificial light",
        mood="serene, refined, contemporary",
        palette="warm white, soft greige, pale oak, matte black accents",
    ),
    "luxury_dark": StylePreset(
        id="luxury_dark",
        label="Премиум тёмный",
        description="Тёмные тона, латунь, мрамор — премиум-сегмент",
        prompt_fragment=(
            "high-end luxury interior with dark dramatic palette, marble surfaces, "
            "brushed brass and bronze accents, velvet textures, statement lighting, "
            "moody chiaroscuro photography, five-star hotel suite aesthetic"
        ),
        lighting="dramatic warm pools of light from designer pendants, deep shadows",
        mood="opulent, sophisticated, exclusive",
        palette="charcoal, deep emerald, warm brass, veined marble, walnut",
    ),
    "scandi_light": StylePreset(
        id="scandi_light",
        label="Скандинавский светлый",
        description="Светлый дуб, лён, скандинавский нейтрал — уют и простор",
        prompt_fragment=(
            "Scandinavian interior design, white-oak floors, linen textiles, "
            "soft Nordic daylight, hygge atmosphere, restrained palette, "
            "natural materials, airy and uncluttered composition"
        ),
        lighting="cool soft Nordic daylight, very even and bright",
        mood="calm, airy, welcoming",
        palette="pure white, pale oak, soft grey, natural linen, muted sage",
    ),
    "coastal_sun": StylePreset(
        id="coastal_sun",
        label="Курортный солнечный",
        description="Курортная свежесть, белый-голубой, морской бриз — Сочи / Анапа / Крым",
        prompt_fragment=(
            "coastal resort interior with sun-drenched Mediterranean atmosphere, "
            "white walls, natural rattan and bleached oak, sheer linen curtains "
            "billowing in sea breeze, glimpse of turquoise sea through the window, "
            "vacation-home elegance"
        ),
        lighting="bright sun-bleached daylight with reflected blue light from the sea",
        mood="airy, fresh, vacation-mode",
        palette="crisp white, sky blue, sand, bleached wood, soft turquoise",
    ),
}


def get_preset(preset_id: str) -> StylePreset:
    if preset_id not in PRESETS:
        raise KeyError(f"Unknown style preset: {preset_id}")
    return PRESETS[preset_id]


def list_presets() -> list[dict]:
    return [
        {"id": p.id, "label": p.label, "description": p.description}
        for p in PRESETS.values()
    ]
