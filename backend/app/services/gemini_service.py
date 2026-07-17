"""
Gemini API service for 4-panel comic story generation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

from app.config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel(settings.gemini_model)


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
        "color_tone": "warm golden tones, bright soft colors",
        "atmosphere": "joyful, uplifting, heartwarming",
    },
    "sad": {
        "thai": "เศร้า อ่อนโยน คิดถึง",
        "color_tone": "cool blue tones, soft desaturated colors",
        "atmosphere": "melancholic, bittersweet, reflective",
    },
    "stressed": {
        "thai": "เครียด กดดัน วิตกกังวล",
        "color_tone": "dark muted tones, high contrast shadows",
        "atmosphere": "tense, pressured, anxious",
    },
    "excited": {
        "thai": "ตื่นเต้น กระฉับกระเฉง มีพลัง",
        "color_tone": "vibrant saturated colors, dynamic bright tones",
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
- คำอธิบายฉากต้องเป็นภาษาอังกฤษ (ใช้ส่งให้ image model)

ตอบกลับเป็น JSON เท่านั้น ในรูปแบบ:
{{
  "panels": [
    {{
      "panel": 1,
      "scene_description": "English scene description for image AI, include art style: {art_style_desc}, {emotion_info['color_tone']}, {emotion_info['atmosphere']}",
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

    response = await _model.generate_content_async(prompt)
    raw = response.text.strip()

    # Extract JSON from response
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        raise ValueError(f"Gemini did not return valid JSON: {raw[:200]}")

    data = json.loads(json_match.group())
    panels_raw = data.get("panels", [])

    panels = [
        PanelContent(
            panel_number=p.get("panel", i + 1),
            scene_description=p.get("scene_description", ""),
            dialogue=p.get("dialogue", ""),
        )
        for i, p in enumerate(panels_raw[:4])
    ]

    full_prompt = f"Emotion: {emotion} | Art: {art_style} | Story: {input_story}"

    return ComicStory(
        panels=panels,
        full_prompt=full_prompt,
        emotion_used=emotion,
        art_style_used=art_style,
    )
