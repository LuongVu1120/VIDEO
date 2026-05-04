"""Step 3: Image Generation - Generate architecture images using DALL-E 3 and SDXL.

DALL-E 3 duoc cau hinh voi aspect ratio 16:9 (1792x1024) de phu hop voi video.
Su dung quality="hd" cho architecture photography (yeu cau chi tiet cao).
"""

import base64
import json
import requests
from io import BytesIO
from PIL import Image
import openai
import replicate
from ..core.config import settings


class ImageGenerator:
    def generate_images(self, prompt: str, negative: str = "", n: int = 4) -> list:
        """Generate images using DALL-E 3 (primary) or SDXL (fallback)."""
        images = self._generate_dalle(prompt, n)
        if images:
            return images
        # Fallback to SDXL
        return self._generate_sdxl(prompt, negative, n)

    def _generate_dalle(self, prompt: str, n: int = 4) -> list:
        """DALL-E 3 generation with architecture-optimized settings."""
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            images = []

            # Generate in batches (DALL-E 3 max 1 per call)
            for i in range(n):
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1792x1024",  # 16:9 aspect ratio - perfect for video
                    quality="hd",       # HD for architectural detail
                    style="natural",    # natural > vivid for realistic architecture
                    n=1
                )

                # Get the image URL
                image_url = response.data[0].url

                # Optionally download and convert to local file
                # for more reliable storage
                try:
                    img_response = requests.get(image_url, timeout=30)
                    if img_response.status_code == 200:
                        # Save reference
                        images.append(image_url)

                        # We keep the URL for immediate use, but also
                        # could save locally for fallback
                        print(f"  DALL-E {i+1}/{n}: generated ({len(img_response.content)} bytes)")
                except Exception as e:
                    print(f"  DALL-E download warning: {e}")
                    images.append(image_url)

            return images

        except Exception as e:
            print(f"DALL-E generation failed: {e}")
            return []

    def _generate_sdxl(self, prompt: str, negative: str, n: int = 4) -> list:
        """Stable Diffusion XL via Replicate - fallback."""
        try:
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2319f9baefea59bff2d1b4d2f",
                input={
                    "prompt": prompt,
                    "negative_prompt": negative,
                    "num_outputs": n,
                    "width": 1344,
                    "height": 768,
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
