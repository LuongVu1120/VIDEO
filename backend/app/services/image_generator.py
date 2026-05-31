"""Step 3: Image Generation - Generate architecture images using gpt-image-1 and SDXL.

gpt-image-1 configured with 2:3 portrait (1024x1536) for mobile phone display.
SDXL fallback uses 768x1344 (9:16).
"""

import base64
import json
import requests
from io import BytesIO
from pathlib import Path
from PIL import Image
import openai
import replicate
from ..core.config import settings


# === MOBILE-FIRST CONFIG ===
# gpt-image-1 supports: 1024x1024, 1024x1536 (portrait), 1536x1024 (landscape), auto
PORTRAIT_SIZE = "1024x1536"           # 2:3 portrait — closest to 9:16 supported by gpt-image-1
SDXL_PORTRAIT_WIDTH = 768
SDXL_PORTRAIT_HEIGHT = 1344

# Absolute output directory under backend/output/images/
_BACKEND_DIR = Path(__file__).parent.parent.parent  # VIDEO/backend/
OUTPUT_DIR = _BACKEND_DIR / "output" / "images"


class ImageGenerator:
    def generate_images(self, prompt: str, negative: str = "", n: int = 4) -> list:
        """Generate images using gpt-image-1 (primary) or SDXL (fallback)."""
        images = self._generate_gpt_image(prompt, n)
        if images:
            return images
        return self._generate_sdxl(prompt, negative, n)

    def _generate_gpt_image(self, prompt: str, n: int = 4) -> list:
        """gpt-image-1 generation — saves to backend/output/images/, returns URL paths."""
        import time, uuid
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            images = []
            batch_id = uuid.uuid4().hex[:8]

            for i in range(n):
                for attempt in range(3):
                    try:
                        response = client.images.generate(
                            model="gpt-image-1",
                            prompt=prompt,
                            size=PORTRAIT_SIZE,
                            quality="medium",
                            n=1
                        )
                        break
                    except openai.RateLimitError:
                        if attempt < 2:
                            print(f"  gpt-image-1 rate limit, retrying in 10s...")
                            time.sleep(10)
                            continue
                        raise

                item = response.data[0]
                # gpt-image-1 always returns b64_json
                if hasattr(item, "b64_json") and item.b64_json:
                    img_bytes = base64.b64decode(item.b64_json)
                    fname = OUTPUT_DIR / f"gen_{batch_id}_{i}.png"
                    fname.write_bytes(img_bytes)
                    url_path = f"/output/images/gen_{batch_id}_{i}.png"
                    images.append(url_path)
                    print(f"  gpt-image-1 {i+1}/{n}: saved {fname} ({len(img_bytes)} bytes)")
                elif hasattr(item, "url") and item.url:
                    images.append(item.url)
                    print(f"  gpt-image-1 {i+1}/{n}: url {item.url[:60]}")
                else:
                    print(f"  gpt-image-1 {i+1}/{n}: no b64_json or url in response")

            return images

        except Exception as e:
            print(f"[ImageGenerator] gpt-image-1 failed (prompt len={len(prompt)}): {type(e).__name__}: {e}")
            return []

    def _generate_sdxl(self, prompt: str, negative: str, n: int = 4) -> list:
        """Stable Diffusion XL via Replicate - 9:16 portrait fallback."""
        try:
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2319f9baefea59bff2d1b4d2f",
                input={
                    "prompt": prompt,
                    "negative_prompt": negative,
                    "num_outputs": n,
                    "width": SDXL_PORTRAIT_WIDTH,    # 768px
                    "height": SDXL_PORTRAIT_HEIGHT,  # 1344px = 9:16
                    "scheduler": "DPMSolverMultistep",
                    "num_inference_steps": 35,
                    "guidance_scale": 7.5,
                    "refine": "expert_ensemble_refiner",
                    "high_noise_frac": 0.8,
                }
            )
            return list(output)
        except Exception as e:
            print(f"SDXL generation failed: {e}")
            return []

    def _generate_flux(self, prompt: str, n: int = 4) -> list:
        """Flux Pro via Replicate - best quality for architecture."""
        try:
            output = replicate.run(
                "black-forest-labs/flux-dev",
                input={
                    "prompt": prompt,
                    "num_outputs": n,
                    "aspect_ratio": "16:9",
                    "output_format": "png",
                    "guidance_scale": 3.0,
                    "num_inference_steps": 25,
                }
            )
            return list(output)
        except Exception as e:
            print(f"FLUX generation failed: {e}")
            return []
