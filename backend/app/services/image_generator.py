"""Step 3: Image Generation - Generate architecture images using DALL-E 3 and SDXL.

DALL-E 3 configured with 9:16 portrait (1024x1792) for mobile phone display.
SDXL fallback uses 768x1344 (9:16).
"""

import base64
import json
import requests
from io import BytesIO
from PIL import Image
import openai
import replicate
from ..core.config import settings


# === MOBILE-FIRST CONFIG ===
MOBILE_PORTRAIT_SIZE = "1024x1792"   # DALL-E 3: 9:16 portrait
SDXL_PORTRAIT_WIDTH = 768             # SDXL: 9:16 portrait
SDXL_PORTRAIT_HEIGHT = 1344


class ImageGenerator:
    def generate_images(self, prompt: str, negative: str = "", n: int = 4) -> list:
        """Generate images using DALL-E 3 (primary) or SDXL (fallback)."""
        images = self._generate_dalle(prompt, n)
        if images:
            return images
        # Fallback to SDXL
        return self._generate_sdxl(prompt, negative, n)

    def _generate_dalle(self, prompt: str, n: int = 4) -> list:
        """DALL-E 3 generation with 9:16 portrait for mobile."""
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            images = []

            for i in range(n):
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size=MOBILE_PORTRAIT_SIZE,  # 9:16 portrait for mobile
                    quality="hd",
                    style="natural",
                    n=1
                )

                image_url = response.data[0].url

                try:
                    img_response = requests.get(image_url, timeout=30)
                    if img_response.status_code == 200:
                        images.append(image_url)
                        print(f"  DALL-E {i+1}/{n}: generated 9:16 portrait ({len(img_response.content)} bytes)")
                except Exception as e:
                    print(f"  DALL-E download warning: {e}")
                    images.append(image_url)

            return images

        except Exception as e:
            print(f"DALL-E generation failed: {e}")
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
