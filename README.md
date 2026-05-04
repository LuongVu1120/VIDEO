# 🏛️ AI Automated Architecture Video Generator

> Upload ảnh kiến trúc → AI phân tích phong cách → Tự động tạo ảnh & video → Auto đăng lên mạng xã hội

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

---

## 📋 Mục lục

- [Tổng quan](#-tổng-quan)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Pipeline AI](#-pipeline-ai--deepseek-v4-thay-thế)
- [Tech Stack](#-tech-stack)
- [Cài đặt & Chạy](#-cài-đặt--chạy)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Biến môi trường](#-biến-môi-trường)
- [API Reference](#-api-reference)
- [Luồng Automation (n8n)](#-luồng-automation-n8n)
- [Chi phí ước tính](#-chi-phí-ước-tính)
- [Lộ trình phát triển](#-lộ-trình-phát-triển)
- [Đóng góp](#-đóng-góp)

---

## 🌐 Tổng quan

Hệ thống tự động hoá toàn bộ quy trình tạo nội dung kiến trúc:

1. Người dùng upload **1 ảnh kiến trúc** làm tham chiếu
2. AI phân tích phong cách, vật liệu, ánh sáng, tâm trạng
3. AI tự động viết prompt tối ưu cho image gen và video gen
4. Hệ thống tạo **4–6 ảnh** chất lượng cao cùng phong cách
5. Hệ thống render **video cinematic** 15–30 giây
6. AI viết caption, tiêu đề, hashtag
7. (Tuỳ chọn) Tự động lên lịch và đăng lên Instagram, TikTok, YouTube Shorts

### Tại sao DeepSeek V4 thay thế được?

DeepSeek V4 (còn gọi là DeepSeek-R2 / DeepSeek-V3 successor) là mô hình ngôn ngữ mạnh, **chi phí thấp hơn GPT-4 tới 90%**, phù hợp thay thế ở các bước **text-only** trong pipeline:

| Bước | Mô hình gốc | Thay bằng DeepSeek V4 | Tiết kiệm |
|------|-------------|----------------------|-----------|
| Phân tích style (text output) | GPT-4o | ✅ DeepSeek V4 | ~85% |
| Viết prompt image/video | Claude 3.5 Sonnet | ✅ DeepSeek V4 | ~80% |
| Viết caption & hashtag | GPT-4 mini | ✅ DeepSeek V4 | ~70% |
| Phân tích ảnh (vision) | Claude Vision / GPT-4o Vision | ⚠️ Hạn chế* | — |
| Sinh ảnh | DALL-E / Midjourney | ❌ Không thay thế | — |
| Sinh video | Runway / Pika | ❌ Không thay thế | — |

> \* DeepSeek V4 có hỗ trợ vision nhưng hiệu suất nhận diện phong cách kiến trúc chưa bằng GPT-4o Vision hoặc Claude 3.5 Sonnet. Nên kết hợp: dùng Claude/GPT-4o cho bước phân tích ảnh, DeepSeek V4 cho các bước viết text.

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│              Next.js 14 + TailwindCSS + Shadcn               │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API / WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                      BACKEND API                             │
│                FastAPI (Python 3.11+)                        │
│          Auth · Job Manager · Storage Handler                │
└──────┬───────────────────┬──────────────────────────────────┘
       │                   │
       ▼                   ▼
┌──────────────┐   ┌───────────────────┐
│  PostgreSQL  │   │   Redis + Celery   │
│  (metadata)  │   │   (task queue)     │
└──────────────┘   └────────┬──────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    n8n Orchestrator                          │
│              (Workflow Automation Engine)                    │
└───┬───────────────┬────────────────┬────────────┬──────────┘
    │               │                │            │
    ▼               ▼                ▼            ▼
┌───────┐    ┌──────────┐    ┌──────────┐  ┌──────────┐
│Vision │    │ Prompt   │    │ Image    │  │ Video    │
│  AI   │    │ Writer   │    │   Gen    │  │   Gen    │
│       │    │   AI     │    │   API    │  │   API    │
└───────┘    └──────────┘    └──────────┘  └──────────┘
    │               │                │            │
    └───────────────┴────────────────┴────────────┘
                            │
                ┌───────────▼───────────┐
                │      Caption AI        │
                │  (DeepSeek V4 / GPT)  │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │     Output Storage     │
                │   AWS S3 / Cloudinary  │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │  Social Media Poster   │
                │  Buffer / Later API    │
                └───────────────────────┘
```

---

## 🤖 Pipeline AI & DeepSeek V4 Thay Thế

### Bước 1 — Phân tích phong cách (Vision Analysis)

**Mô hình chính:** Claude 3.5 Sonnet Vision hoặc GPT-4o Vision
**Thay thế bằng DeepSeek V4:** ⚠️ Có thể (hạn chế)

```python
# services/vision_analyzer.py

import anthropic
import openai
from openai import OpenAI

class StyleAnalyzer:
    def __init__(self, provider="claude"):
        self.provider = provider

    def analyze(self, image_base64: str) -> dict:
        prompt = """
        Analyze this architecture image and extract:
        - style: (Modern Minimalist / Contemporary / Industrial / etc.)
        - materials: list of visible materials
        - colors: primary color palette
        - lighting: lighting conditions
        - mood: emotional tone
        - architecture_type: (house / commercial / interior / etc.)
        - environment: surrounding context

        Respond in JSON format only.
        """

        if self.provider == "claude":
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            return response.content[0].text

        elif self.provider == "gpt4o":
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            return response.choices[0].message.content

        # DeepSeek V4 (vision mode - thử nghiệm)
        elif self.provider == "deepseek":
            client = OpenAI(
                api_key="YOUR_DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com"
            )
            response = client.chat.completions.create(
                model="deepseek-chat",  # hoặc deepseek-reasoner
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            return response.choices[0].message.content
```

---

### Bước 2 — Viết Prompt (✅ DeepSeek V4 thay thế hoàn toàn)

**Đây là bước tiết kiệm chi phí nhất khi dùng DeepSeek V4**

```python
# services/prompt_writer.py

from openai import OpenAI

class PromptWriter:
    def __init__(self, use_deepseek=True):
        if use_deepseek:
            self.client = OpenAI(
                api_key="YOUR_DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com"
            )
            self.model = "deepseek-chat"
        else:
            self.client = OpenAI()
            self.model = "gpt-4o"

    def generate_prompts(self, style_analysis: dict) -> dict:
        system_prompt = """
        You are an expert architectural photography and AI art director.
        Generate precise, detailed prompts for AI image and video generation
        based on architectural style analysis. Always output valid JSON.
        """

        user_prompt = f"""
        Based on this architectural style analysis:
        {style_analysis}

        Generate:
        1. image_prompt: A detailed prompt for Midjourney/DALL-E (max 200 words)
           - Include: style, materials, lighting, camera angle, mood
           - End with: ultra realistic, architectural photography, 8k, award winning

        2. video_prompt: A cinematic video prompt for Runway/Pika (max 100 words)
           - Include: camera movement (slow push-in / orbit / dolly)
           - Include: time of day, atmosphere

        3. negative_prompt: Things to avoid in generation

        4. style_tags: 5-8 relevant hashtags for social media

        Return as JSON: {{image_prompt, video_prompt, negative_prompt, style_tags}}
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        return response.choices[0].message.content
```

---

### Bước 3 — Sinh ảnh

**Không thể thay thế bằng DeepSeek** — cần model chuyên biệt cho image generation.

```python
# services/image_generator.py

import openai
import replicate

class ImageGenerator:
    def generate_dalle(self, prompt: str, n: int = 4) -> list[str]:
        """DALL-E 3 — dễ tích hợp, chất lượng tốt"""
        client = openai.OpenAI()
        images = []
        for _ in range(n):
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1792x1024",
                quality="hd",
                n=1
            )
            images.append(response.data[0].url)
        return images

    def generate_sdxl(self, prompt: str, negative: str, n: int = 4) -> list[str]:
        """Stable Diffusion XL qua Replicate — rẻ hơn DALL-E"""
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
            }
        )
        return list(output)

    def generate_midjourney(self, prompt: str) -> list[str]:
        """Midjourney qua UseAPI.net hoặc Piapi.ai (unofficial)"""
        import requests
        response = requests.post(
            "https://api.useapi.net/v2/jobs/imagine",
            headers={"Authorization": f"Bearer YOUR_USEAPI_KEY"},
            json={
                "prompt": f"{prompt} --ar 16:9 --v 6.1 --q 2",
                "discord": "YOUR_DISCORD_TOKEN",
                "server": "YOUR_SERVER_ID",
                "channel": "YOUR_CHANNEL_ID"
            }
        )
        return response.json()
```

---

### Bước 4 — Sinh Video

```python
# services/video_generator.py

import requests
import time

class VideoGenerator:
    def generate_runway(self, image_url: str, prompt: str) -> str:
        """Runway Gen-3 Alpha — chất lượng cao nhất"""
        headers = {
            "Authorization": f"Bearer YOUR_RUNWAY_API_KEY",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06"
        }

        # Tạo task
        response = requests.post(
            "https://api.dev.runwayml.com/v1/image_to_video",
            headers=headers,
            json={
                "model": "gen3a_turbo",
                "promptImage": image_url,
                "promptText": prompt,
                "duration": 10,
                "ratio": "1280:768",
                "watermark": False
            }
        )
        task_id = response.json()["id"]

        # Poll kết quả (video gen mất 2–5 phút)
        while True:
            status = requests.get(
                f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                headers=headers
            ).json()

            if status["status"] == "SUCCEEDED":
                return status["output"][0]
            elif status["status"] == "FAILED":
                raise Exception(f"Video generation failed: {status}")

            time.sleep(10)

    def generate_pika(self, image_url: str, prompt: str) -> str:
        """Pika Labs — lựa chọn rẻ hơn"""
        # Tương tự Runway nhưng qua Pika API
        pass
```

---

### Bước 5 — Viết Caption (✅ DeepSeek V4 thay thế hoàn toàn)

```python
# services/caption_writer.py

from openai import OpenAI

class CaptionWriter:
    def __init__(self, use_deepseek=True):
        if use_deepseek:
            self.client = OpenAI(
                api_key="YOUR_DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com"
            )
            self.model = "deepseek-chat"
        else:
            self.client = OpenAI()
            self.model = "gpt-4o-mini"

    def write_caption(self, style_analysis: dict, platform: str = "instagram") -> dict:
        platform_configs = {
            "instagram": "engaging, aesthetic, 150-200 words, 20-25 hashtags",
            "tiktok": "trendy, hook in first line, 80-100 words, 5-10 hashtags",
            "youtube": "descriptive, SEO-friendly title + description, 3-5 hashtags"
        }

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": f"""
                Write a {platform} caption for architectural content with this style:
                {style_analysis}

                Requirements: {platform_configs[platform]}

                Return JSON: {{title, caption, hashtags, call_to_action}}
                """
            }],
            response_format={"type": "json_object"}
        )

        return response.choices[0].message.content
```

---

## 🛠️ Tech Stack

### Frontend
| Công nghệ | Mục đích |
|-----------|----------|
| Next.js 14 (App Router) | Framework chính |
| TailwindCSS | Styling |
| Shadcn/UI | Component library |
| React Query | Data fetching & caching |
| Zustand | State management |
| Uploadthing | File upload |

### Backend
| Công nghệ | Mục đích |
|-----------|----------|
| FastAPI | REST API server |
| PostgreSQL | Lưu user, jobs, outputs |
| Redis | Task queue, caching |
| Celery | Background job processor |
| SQLAlchemy | ORM |
| Alembic | Database migrations |
| JWT | Authentication |

### Infrastructure
| Công nghệ | Mục đích |
|-----------|----------|
| AWS S3 / Cloudinary | Lưu ảnh & video |
| Docker + Docker Compose | Containerization |
| n8n (self-hosted) | Workflow orchestration |
| Nginx | Reverse proxy |
| GitHub Actions | CI/CD |

### AI Models
| Bước | Mô hình chính | DeepSeek V4 |
|------|--------------|-------------|
| Vision Analysis | Claude 3.5 Sonnet | ⚠️ Thử nghiệm |
| Prompt Writing | Claude / GPT-4o | ✅ Thay được |
| Image Generation | DALL-E 3 / SDXL | ❌ |
| Video Generation | Runway Gen-3 | ❌ |
| Caption Writing | GPT-4o-mini | ✅ Thay được |

---

## 🚀 Cài đặt & Chạy

### Yêu cầu hệ thống
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- Git

### 1. Clone repo

```bash
git clone https://github.com/your-org/ai-arch-video-generator.git
cd ai-arch-video-generator
```

### 2. Cấu hình biến môi trường

```bash
cp .env.example .env
# Chỉnh sửa .env với API keys của bạn
```

### 3. Khởi động với Docker Compose

```bash
docker-compose up -d
```

### 4. Chạy database migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 5. Truy cập ứng dụng

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| n8n Dashboard | http://localhost:5678 |
| Redis UI | http://localhost:8081 |

---

## 📁 Cấu trúc thư mục

```
ai-arch-video-generator/
├── frontend/                    # Next.js app
│   ├── app/
│   │   ├── (auth)/
│   │   ├── dashboard/
│   │   │   ├── upload/          # Trang upload ảnh
│   │   │   ├── jobs/            # Danh sách jobs
│   │   │   └── outputs/         # Kết quả đã tạo
│   │   └── api/
│   ├── components/
│   │   ├── upload/
│   │   ├── job-status/
│   │   └── output-gallery/
│   └── lib/
│
├── backend/                     # FastAPI app
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── upload.py
│   │   │   │   ├── jobs.py
│   │   │   │   └── outputs.py
│   │   ├── services/
│   │   │   ├── vision_analyzer.py    # Bước 1
│   │   │   ├── prompt_writer.py      # Bước 2 (DeepSeek OK)
│   │   │   ├── image_generator.py    # Bước 3
│   │   │   ├── video_generator.py    # Bước 4
│   │   │   └── caption_writer.py     # Bước 5 (DeepSeek OK)
│   │   ├── models/
│   │   ├── workers/                  # Celery tasks
│   │   └── core/
│   │       ├── config.py
│   │       └── database.py
│   ├── alembic/
│   └── requirements.txt
│
├── n8n-workflows/               # n8n workflow JSON exports
│   ├── main-pipeline.json
│   └── social-posting.json
│
├── docker-compose.yml
├── docker-compose.prod.yml
└── .env.example
```

---

## 🔑 Biến môi trường

```env
# ===================== DATABASE =====================
DATABASE_URL=postgresql://user:password@localhost:5432/archvideo
REDIS_URL=redis://localhost:6379

# ===================== STORAGE =====================
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_S3_BUCKET=arch-video-outputs
AWS_REGION=ap-southeast-1

# ===================== AI - VISION & TEXT =====================
ANTHROPIC_API_KEY=sk-ant-...           # Claude Vision + Prompt
OPENAI_API_KEY=sk-...                   # GPT-4o Vision (backup)

# ===================== AI - DEEPSEEK V4 =====================
# Dùng thay thế cho Prompt Writing & Caption (tiết kiệm 80% chi phí)
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat            # hoặc deepseek-reasoner

# ===================== AI - IMAGE GENERATION =====================
REPLICATE_API_TOKEN=r8_...              # Stable Diffusion XL
USEAPI_KEY=...                          # Midjourney unofficial

# ===================== AI - VIDEO GENERATION =====================
RUNWAY_API_KEY=...                      # Runway Gen-3
PIKA_API_KEY=...                        # Pika Labs (backup)

# ===================== SOCIAL MEDIA =====================
BUFFER_ACCESS_TOKEN=...
INSTAGRAM_ACCESS_TOKEN=...
TIKTOK_ACCESS_TOKEN=...

# ===================== APP =====================
SECRET_KEY=your-secret-key-here
AI_PROVIDER=deepseek                    # claude | openai | deepseek
USE_DEEPSEEK_FOR_PROMPTS=true
USE_DEEPSEEK_FOR_CAPTIONS=true
```

---

## 📡 API Reference

### Upload & Tạo Job

```http
POST /api/v1/jobs
Content-Type: multipart/form-data

{
  "image": <file>,
  "options": {
    "num_images": 4,
    "generate_video": true,
    "video_duration": 10,
    "platforms": ["instagram", "tiktok"],
    "auto_post": false,
    "ai_provider": "deepseek"    // claude | openai | deepseek
  }
}
```

**Response:**
```json
{
  "job_id": "job_abc123",
  "status": "queued",
  "estimated_time_seconds": 180,
  "webhook_url": "/api/v1/jobs/job_abc123/status"
}
```

---

### Lấy trạng thái Job

```http
GET /api/v1/jobs/{job_id}
```

**Response:**
```json
{
  "job_id": "job_abc123",
  "status": "processing",        // queued | processing | completed | failed
  "progress": 60,
  "current_step": "generating_images",
  "steps_completed": ["vision_analysis", "prompt_writing"],
  "estimated_remaining_seconds": 72
}
```

---

### Lấy kết quả

```http
GET /api/v1/outputs/{job_id}
```

**Response:**
```json
{
  "job_id": "job_abc123",
  "style_analysis": { "style": "Modern Minimalist", "..." : "..." },
  "prompts": {
    "image_prompt": "Modern minimalist house...",
    "video_prompt": "Cinematic slow push-in..."
  },
  "images": ["https://cdn.../img1.jpg", "..."],
  "video_url": "https://cdn.../video.mp4",
  "captions": {
    "instagram": { "title": "...", "caption": "...", "hashtags": [...] },
    "tiktok": { "..." : "..." }
  },
  "cost_usd": 0.87,
  "created_at": "2025-05-02T10:30:00Z"
}
```

---

## ⚙️ Luồng Automation (n8n)

Import file `n8n-workflows/main-pipeline.json` vào n8n dashboard.

**Các node trong workflow:**

```
[Webhook Trigger]
       ↓
[Download Image from S3]
       ↓
[HTTP Request → Vision API]     ← Claude / GPT-4o / DeepSeek
       ↓
[Parse JSON → Style Data]
       ↓
[HTTP Request → Prompt Writer]  ← DeepSeek V4 (tiết kiệm)
       ↓
[Split → Parallel Processing]
   ↙         ↘
[Image API]  [Video API]
[DALL-E/SDXL] [Runway Gen-3]
   ↘         ↙
[Wait → Merge Results]
       ↓
[HTTP Request → Caption Writer] ← DeepSeek V4 (tiết kiệm)
       ↓
[Upload to S3]
       ↓
[Update DB → Mark Completed]
       ↓
[Notify Frontend via WebSocket]
       ↓
[If auto_post = true]
       ↓
[Buffer API → Schedule Posts]
```

---

## 💰 Chi phí ước tính

### Mỗi lần xử lý (1 ảnh đầu vào → 4 ảnh + 1 video)

| Bước | Provider | Chi phí | Với DeepSeek |
|------|----------|---------|--------------|
| Vision Analysis | Claude 3.5 Sonnet | $0.012 | $0.012 (giữ nguyên) |
| Prompt Writing | GPT-4o → **DeepSeek V4** | $0.030 → **$0.002** | **$0.002** |
| Image Generation (4x) | DALL-E 3 HD | $0.160 | $0.160 (không đổi) |
| Video Generation (10s) | Runway Gen-3 Turbo | $0.500 | $0.500 (không đổi) |
| Caption Writing | GPT-4o-mini → **DeepSeek V4** | $0.004 → **$0.001** | **$0.001** |
| **Tổng** | | **~$0.706** | **~$0.675** |

### Chi phí hạ tầng hàng tháng

| Service | Chi phí |
|---------|---------|
| VPS (4 CPU, 8GB RAM) | $40–60/tháng |
| PostgreSQL (managed) | $15–25/tháng |
| Redis (managed) | $10–15/tháng |
| CDN + S3 Storage | $5–20/tháng |
| **Tổng infrastructure** | **~$70–120/tháng** |

> **Gợi ý pricing cho SaaS:** Gói Basic $29/tháng (30 lần tạo), Gói Pro $79/tháng (150 lần), Gói Agency $199/tháng (500 lần + multi-user).

---

## 🗓️ Lộ trình phát triển

### Phase 1 — MVP (Tuần 1–6)
- [ ] Setup Next.js frontend + upload UI
- [ ] Setup FastAPI backend + PostgreSQL
- [ ] Tích hợp Claude Vision (Bước 1)
- [ ] Tích hợp DeepSeek V4 cho prompt writing (Bước 2)
- [ ] Tích hợp DALL-E 3 image generation (Bước 3)
- [ ] Job status tracking + WebSocket notifications
- [ ] Deploy lên VPS với Docker

### Phase 2 — Video Generation (Tuần 7–10)
- [ ] Tích hợp Runway Gen-3 (Bước 4)
- [ ] Tích hợp DeepSeek V4 cho caption writing (Bước 5)
- [ ] Thêm Pika Labs làm backup video provider
- [ ] Output gallery với download

### Phase 3 — Auto Posting (Tuần 11–13)
- [ ] Tích hợp Buffer API
- [ ] Instagram Graph API
- [ ] TikTok Content Posting API
- [ ] YouTube Data API (Shorts)
- [ ] Scheduling UI

### Phase 4 — Scale & SaaS (Tuần 14+)
- [ ] Multi-user với billing (Stripe)
- [ ] Usage dashboard & analytics
- [ ] Team/Agency workspace
- [ ] Bulk processing (nhiều ảnh cùng lúc)
- [ ] Custom brand voice cho caption
- [ ] A/B test prompts

---

## 🤝 Đóng góp

1. Fork repo
2. Tạo branch: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m 'feat: thêm tính năng X'`
4. Push: `git push origin feature/ten-tinh-nang`
5. Mở Pull Request

---

## 📄 License

MIT License — xem file [LICENSE](LICENSE) để biết thêm.

---

*Built with ❤️ — Powered by Claude Vision, DeepSeek V4, Runway Gen-3*
