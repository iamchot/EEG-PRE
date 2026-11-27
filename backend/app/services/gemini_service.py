"""
Gemini API service for 4-panel comic story generation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PanelContent:
    panel_number: int
    scene_description: str   # Scene description for image generation
    dialogue: str             # Character dialogue / caption


@dataclass
class ComicStory:
    panels: list[PanelContent]
    full_prompt: str
    emotion_used: str
    art_style_used: str


EMOTION_TONE_MAP = {
    "happy": {
        "thai": "มีความสุข ร่าเริง อบอุ่น",
        "color_tone": "warm golden ambient lighting, bright cheerful atmosphere",
        "atmosphere": "joyful, uplifting, heartwarming",
    },
    "sad": {
        "thai": "เศร้า อ่อนโยน คิดถึง",
        "color_tone": "cool blue ambient lighting, soft rain or twilight mood",
        "atmosphere": "melancholic, bittersweet, reflective",
    },
    "stressed": {
        "thai": "เครียด กดดัน วิตกกังวล",
        "color_tone": "dramatic high-contrast shadows, moody tense lighting",
        "atmosphere": "tense, pressured, anxious",
    },
    "excited": {
        "thai": "ตื่นเต้น กระฉับกระเฉง มีพลัง",
        "color_tone": "vibrant dynamic lighting, energetic bright atmosphere",
        "atmosphere": "energetic, thrilling, dynamic",
    },
}

ART_STYLE_PROMPT_MAP = {
    "Webtoon": "vertical webtoon style, clean lines, Korean manhwa aesthetic",
    "Manga": "manga style, black and white with screen tones, Japanese comic aesthetic",
    "American Comic": "American comic book style, bold outlines, dynamic composition",
    "Comic": "classic comic strip style, simple expressive characters",
}


async def generate_comic_story(
    input_story: str,
    emotion: str,
    art_style: str,
    persona_name: Optional[str] = None,
    persona_appearance: Optional[str] = None,
) -> ComicStory:
    """
    Call Gemini to generate 4-panel comic story with dialogues.
    Returns structured panel content for image generation.
    """
    emotion_info = EMOTION_TONE_MAP.get(emotion, EMOTION_TONE_MAP["happy"])
    art_style_desc = ART_STYLE_PROMPT_MAP.get(art_style, art_style)

    persona_desc = ""
    if persona_name:
        persona_desc = f"\nตัวละครหลัก: {persona_name}"
        if persona_appearance:
            persona_desc += f"\nลักษณะ: {persona_appearance}"

    prompt = f"""คุณเป็นนักเขียนการ์ตูนมืออาชีพ สร้างเรื่องราวการ์ตูน 4 ช่องจบในภาษาไทย

โครงเรื่อง: {input_story}{persona_desc}
อารมณ์หลัก: {emotion_info['thai']} ({emotion})
สไตล์ภาพ: {art_style} — {art_style_desc}

กฎสำคัญ:
- ช่องที่ 1-3: ดำเนินเรื่อง
- ช่องที่ 4: จบแบบ punch line หรือ twist ที่สอดคล้องกับอารมณ์ "{emotion}"
- บทพูดสั้น กระชับ ไม่เกิน 2 ประโยค/ช่อง
- คำอธิบายฉาก (scene_description) ต้องเป็นภาษาอังกฤษแบบคีย์เวิร์ดสั้นกระชับ 25-40 คำ (เพื่อให้ Stable Diffusion 1.5 อ่านเข้าใจแม่นยำ) โดยเรียงลำดับ: [ตัวละครหลัก + character_tags] -> [การกระทำ สัตว์เลี้ยง/คู่หู และวัตถุสำคัญของฉากนั้นๆ] -> [ฉากหลังและแสง]
- ใส่คำว่า "solo" เฉพาะฉากที่มีตัวละครคนเดียว (ห้ามใส่ "solo" ในฉากที่มีสัตว์ เช่น แมว/หมา หรือตัวละครอื่นอยู่ด้วย ให้ระบุชัด เช่น "1boy holding a small black cat" เพื่อไม่ให้ภาพกลืนกัน)
- คุมโทนสีและบรรยากาศให้ต่อเนื่องกันทั้ง 4 ช่อง ไม่เปลี่ยนโทนสีกระโดดไปมา
- หากมีข้อมูลตัวละคร ให้สรุป character_tags เป็นภาษาอังกฤษสั้นๆ (เช่น 1boy, short black hair, brown eyes, red hoodie) โดยรักษาสีผม ทรงผม และชุดให้ตรงกันทุกช่อง

ตอบกลับเป็น JSON เท่านั้น ในรูปแบบ:
{{
  "character_tags": "English visual tags for the main character (e.g. 1boy, short black hair, brown eyes, school uniform) or empty string if none",
  "panels": [
    {{
      "panel": 1,
      "scene_description": "character_tags, key action and companion/object in English, consistent background, {art_style_desc}, {emotion_info['color_tone']}, {emotion_info['atmosphere']}",
      "dialogue": "Thai dialogue or caption"
    }},
    {{
      "panel": 2,
      "scene_description": "...",
      "dialogue": "..."
    }},
    {{
      "panel": 3,
      "scene_description": "...",
      "dialogue": "..."
    }},
    {{
      "panel": 4,
      "scene_description": "...",
      "dialogue": "..."
    }}
  ]
}}"""

    primary_model = settings.gemini_model.strip().removeprefix("models/")
    models_to_try = list(dict.fromkeys([primary_model, "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]))

    payload = None
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=25.0) as client:
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            logger.info("Calling Gemini REST API model=%s emotion=%s art_style=%s", model, emotion, art_style)
            try:
                resp = await client.post(
                    url,
                    params={"key": settings.gemini_api_key},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                )
                if resp.status_code in (404, 429, 500, 502, 503, 504):
                    logger.warning("Gemini model=%s returned HTTP %s: %s", model, resp.status_code, resp.text[:200])
                    last_error = ValueError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                    continue
                if resp.status_code >= 400:
                    raise ValueError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                payload = resp.json()
                break
            except httpx.TimeoutException as exc:
                logger.warning("Gemini model=%s timed out (%s)", model, type(exc).__name__)
                last_error = exc
                continue

    if payload is None:
        if last_error is not None:
            raise last_error
        raise ValueError("All Gemini models failed without response")

    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError(f"Gemini returned no candidates: {str(payload)[:300]}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    raw = "".join(part.get("text", "") for part in parts).strip()
    if not raw:
        raise ValueError(f"Gemini returned empty text: {str(payload)[:300]}")

    # Extract JSON from response
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        raise ValueError(f"Gemini did not return valid JSON: {raw[:200]}")

    data = json.loads(json_match.group())
    character_tags = str(data.get("character_tags") or "").strip()
    panels_raw = data.get("panels", [])

    def _with_character(desc: str) -> str:
        clean = desc.strip()
        if character_tags and character_tags.lower() not in clean.lower():
            return f"{character_tags}, {clean}" if clean else character_tags
        return clean

    panels = [
        PanelContent(
            panel_number=p.get("panel", i + 1),
            scene_description=_with_character(p.get("scene_description", "")),
            dialogue=p.get("dialogue", ""),
        )
        for i, p in enumerate(panels_raw[:4])
    ]
    for p in panels:
        logger.info("Gemini panel %d prompt: %s", p.panel_number, p.scene_description)

    full_prompt = f"Emotion: {emotion} | Art: {art_style} | Story: {input_story}"

    return ComicStory(
        panels=panels,
        full_prompt=full_prompt,
        emotion_used=emotion,
        art_style_used=art_style,
    )
