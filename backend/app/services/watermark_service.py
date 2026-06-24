"""
Watermark & Branding Service.
Adds company name + phone number overlay to generated images and videos.

Images  → Pillow (no extra deps, works offline, supports Unicode/Vietnamese)
Videos  → FFmpeg overlay with a pre-rendered PNG watermark (Unicode-safe)
"""

import os
import io
import requests
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .bgm_service import path_to_output_url


OUTPUT_ROOT = Path(__file__).parent.parent.parent / "output"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# Try Windows fonts → Linux fonts → Pillow default (in that order)
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _make_watermark_image(
    brand_name: str,
    brand_phone: str = "",
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    position: str = "bottom-right",
) -> Image.Image:
    """
    Render a transparent RGBA watermark image sized to match the video/image.
    Uses Pillow so Vietnamese text is always supported.
    """
    wm = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wm)

    # Font sizes scale with canvas height
    size_name = max(24, int(canvas_h * 0.022))
    size_phone = max(18, int(canvas_h * 0.016))
    font_name = _load_font(size_name)
    font_phone = _load_font(size_phone)

    lines = [(brand_name, font_name)]
    if brand_phone:
        lines.append((brand_phone, font_phone))

    # Measure all lines
    padding = max(10, int(canvas_h * 0.012))
    widths, heights = [], []
    for text, font in lines:
        bbox = draw.textbbox((0, 0), text, font=font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])

    box_w = max(widths) + padding * 4
    box_h = sum(heights) + padding * (len(lines) + 1)

    margin = max(20, int(canvas_w * 0.025))
    if "right" in position:
        box_x = canvas_w - box_w - margin
    else:
        box_x = margin
    if "bottom" in position:
        box_y = canvas_h - box_h - margin
    else:
        box_y = margin

    # Semi-transparent dark rounded box
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=10,
        fill=(0, 0, 0, 170),
    )

    # Text
    y = box_y + padding
    for text, font in lines:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = box_x + (box_w - tw) // 2
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 240))
        y += th + padding

    return wm


def add_image_watermark(
    image_source: str,
    brand_name: str,
    brand_phone: str = "",
    position: str = "bottom-right",
    output_path: Optional[str] = None,
) -> str:
    """
    Download (if URL) or open a local image, composite the watermark, save.

    Returns the local path to the watermarked image.
    """
    # Load image
    if image_source.startswith("http://") or image_source.startswith("https://"):
        resp = requests.get(image_source, timeout=30)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
    else:
        img = Image.open(image_source).convert("RGBA")

    w, h = img.size
    wm = _make_watermark_image(brand_name, brand_phone, w, h, position)
    result = Image.alpha_composite(img, wm).convert("RGB")

    if not output_path:
        stem = Path(image_source).stem if not image_source.startswith("http") else "image"
        output_path = str(OUTPUT_ROOT / f"{stem}_branded.jpg")

    result.save(output_path, "JPEG", quality=92)
    return output_path


def add_video_watermark(
    video_source: str,
    brand_name: str,
    brand_phone: str = "",
    position: str = "bottom-right",
    output_path: Optional[str] = None,
) -> str:
    """
    Download (if URL) or use a local video, overlay the watermark PNG via FFmpeg.

    Uses Pillow-rendered PNG as overlay → fully Unicode/Vietnamese safe.
    Returns the local path to the watermarked video.
    """
    # Download if URL
    if video_source.startswith("http://") or video_source.startswith("https://"):
        resp = requests.get(video_source, timeout=120, stream=True)
        resp.raise_for_status()
        tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        for chunk in resp.iter_content(chunk_size=8192):
            tmp_video.write(chunk)
        tmp_video.close()
        local_video = tmp_video.name
        _downloaded = True
    else:
        local_video = video_source
        _downloaded = False

    if not output_path:
        stem = Path(local_video).stem
        output_path = str(OUTPUT_ROOT / f"{stem}_branded.mp4")

    # Probe video dimensions
    try:
        import json as _json
        probe_result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", local_video],
            capture_output=True, text=True, timeout=15,
        )
        streams = _json.loads(probe_result.stdout).get("streams", [])
        vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
        vid_w = int(vstream.get("width", 1080))
        vid_h = int(vstream.get("height", 1920))
    except Exception:
        vid_w, vid_h = 1080, 1920

    # Render watermark PNG at video resolution
    wm_img = _make_watermark_image(brand_name, brand_phone, vid_w, vid_h, position)
    tmp_wm = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    wm_img.save(tmp_wm.name, "PNG")
    tmp_wm.close()

    # FFmpeg: overlay PNG watermark on video
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", local_video,
            "-i", tmp_wm.name,
            "-filter_complex", "overlay=0:0",
            "-c:v", "libx264",
            "-c:a", "copy",
            "-preset", "fast",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    finally:
        if os.path.exists(tmp_wm.name):
            os.unlink(tmp_wm.name)
        if _downloaded and os.path.exists(local_video):
            os.unlink(local_video)

    return output_path


def apply_branding_to_job(
    job_id: str,
    images: list[str],
    video_url: Optional[str],
    brand_name: str,
    brand_phone: str = "",
    position: str = "bottom-right",
) -> tuple[list[str], Optional[str]]:
    """
    Apply watermark to all images and video for a job.
    Skips gracefully if brand_name is empty.

    Returns (branded_images, branded_video_url).
    """
    if not brand_name:
        return images, video_url

    job_output_dir = OUTPUT_ROOT / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    # Watermark images
    branded_images = []
    for i, img_src in enumerate(images):
        try:
            out = str(job_output_dir / f"image_{i+1}_branded.jpg")
            branded = add_image_watermark(img_src, brand_name, brand_phone, position, out)
            branded_images.append(branded)
            print(f"  [Watermark] Image {i+1}/{len(images)} branded -> {branded}")
        except Exception as e:
            print(f"  [Watermark] Image {i+1} failed: {e} — using original")
            branded_images.append(img_src)

    # Watermark video
    branded_video = video_url
    if video_url:
        try:
            out = str(job_output_dir / "video_branded.mp4")
            branded_video = add_video_watermark(video_url, brand_name, brand_phone, position, out)
            branded_video = path_to_output_url(branded_video)
            print(f"  [Watermark] Video branded -> {branded_video}")
        except Exception as e:
            print(f"  [Watermark] Video failed: {e} — using original")

    return branded_images, branded_video
