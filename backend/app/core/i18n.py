"""Ngôn ngữ giao diện pipeline và nhãn bước xử lý."""

from .config import settings

STEP_LABELS_VI = {
    "vision_analysis": "Phân tích phong cách kiến trúc",
    "prompt_writing": "Viết prompt tối ưu",
    "image_generation": "Tạo ảnh kiến trúc",
    "video_generation": "Tạo video cinematic",
    "bgm_mux": "Ghép nhạc nền",
    "caption_writing": "Viết caption & hashtag",
}

STEP_LABELS_EN = {
    "vision_analysis": "Analyzing architectural style",
    "prompt_writing": "Writing optimized prompts",
    "image_generation": "Generating architecture images",
    "video_generation": "Creating cinematic video",
    "bgm_mux": "Adding background music",
    "caption_writing": "Writing captions & hashtags",
}


def is_vietnamese() -> bool:
    return (settings.CONTENT_LANGUAGE or "vi").lower().startswith("vi")


def step_labels() -> dict[str, str]:
    return STEP_LABELS_VI if is_vietnamese() else STEP_LABELS_EN
