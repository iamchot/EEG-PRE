"""
ComfyUI service for Stable Diffusion image generation.
Sends workflow payloads to local ComfyUI REST API.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

settings = get_settings()


# ─── Default ComfyUI workflow template ────────────────────────────────────────
# Simplified txt2img workflow. Adjust node IDs to match your actual ComfyUI setup.
_BASE_WORKFLOW: dict = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,
            "steps": 20,
            "cfg": 7.5,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"},
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1},
    },
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "ugly, blurry, low quality, deformed, text, watermark",
            "clip": ["4", 1],
        },
    },
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "dreamcomic", "images": ["8", 0]},
    },
}

ART_STYLE_SUFFIX = {
    "Webtoon": ", webtoon style, clean lines, Korean manhwa, digital art",
    "Manga": ", manga style, black and white, screen tones, Japanese comic",
    "American Comic": ", American comic book style, bold outlines, vivid colors, superhero comic",
    "Comic": ", classic comic strip, simple expressive characters, cartoon",
}


async def generate_panel_image(
    scene_description: str,
    art_style: str,
    panel_number: int,
    output_dir: str = settings.comfyui_output_dir,
) -> Optional[str]:
    """
    Submit a generation job to ComfyUI and poll for the output image.
    Returns the relative URL path to the saved image, or None on failure.
    """
    os.makedirs(output_dir, exist_ok=True)

    prompt_text = scene_description + ART_STYLE_SUFFIX.get(art_style, "")
    workflow = json.loads(json.dumps(_BASE_WORKFLOW))  # deep copy
    workflow["6"]["inputs"]["text"] = prompt_text
    workflow["3"]["inputs"]["seed"] = uuid.uuid4().int % (2**32)

    payload = {"prompt": workflow, "client_id": str(uuid.uuid4())}

    async with httpx.AsyncClient(timeout=180.0) as client:
        # Submit prompt
        resp = await client.post(f"{settings.comfyui_url}/prompt", json=payload)
        resp.raise_for_status()
        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            return None

        # Poll for completion
        for _ in range(120):  # up to 120s
            await asyncio.sleep(1.0)
            hist_resp = await client.get(f"{settings.comfyui_url}/history/{prompt_id}")
            if hist_resp.status_code != 200:
                continue
            hist = hist_resp.json()
            if prompt_id not in hist:
                continue
            outputs = hist[prompt_id].get("outputs", {})
            for node_output in outputs.values():
                images = node_output.get("images", [])
                if images:
                    img_info = images[0]
                    img_filename = img_info.get("filename", "")
                    img_subfolder = img_info.get("subfolder", "")
                    # Download the image
                    view_resp = await client.get(
                        f"{settings.comfyui_url}/view",
                        params={"filename": img_filename, "subfolder": img_subfolder},
                    )
                    if view_resp.status_code == 200:
                        out_filename = f"panel_{panel_number}_{uuid.uuid4().hex[:8]}.png"
                        out_path = Path(output_dir) / out_filename
                        out_path.write_bytes(view_resp.content)
                        # Return URL path for serving via /static/
                        return f"/static/panels/{out_filename}"
        return None


async def generate_all_panels(
    panel_descriptions: list[str],
    art_style: str,
    output_dir: str = settings.comfyui_output_dir,
) -> list[Optional[str]]:
    """Generate all 4 panels concurrently."""
    tasks = [
        generate_panel_image(desc, art_style, i + 1, output_dir)
        for i, desc in enumerate(panel_descriptions)
    ]
    return list(await asyncio.gather(*tasks, return_exceptions=False))
