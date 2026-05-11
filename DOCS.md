# Hướng Dẫn Sử Dụng — AI Architecture Video Generator

> Nền tảng tự động tạo nội dung kiến trúc và đăng lên mạng xã hội bằng AI.

---

## Mục lục

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Yêu cầu hệ thống](#2-yêu-cầu-hệ-thống)
3. [Cài đặt nhanh](#3-cài-đặt-nhanh)
4. [Cấu hình biến môi trường](#4-cấu-hình-biến-môi-trường)
5. [Pipeline AI 5 bước](#5-pipeline-ai-5-bước)
6. [Sử dụng giao diện web (Frontend)](#6-sử-dụng-giao-diện-web-frontend)
7. [API Reference — tất cả endpoints](#7-api-reference)
8. [Tính năng nâng cao](#8-tính-năng-nâng-cao)
9. [Train CLIP (Semantic AI)](#9-train-clip-semantic-ai)
10. [Chi phí ước tính](#10-chi-phí-ước-tính)
11. [Xử lý lỗi thường gặp](#11-xử-lý-lỗi-thường-gặp)

---

## 1. Tổng quan dự án

Dự án này là một hệ thống AI hoàn chỉnh giúp các công ty kiến trúc / nội thất tự động hóa việc tạo và đăng nội dung lên mạng xã hội:

```
Ảnh kiến trúc (upload)  +  Mô tả yêu cầu sáng tạo (tuỳ chọn)
        │                              │
        └──────────────┬───────────────┘
                       ▼
┌───────────────────────────────────────────────────────┐
│  PIPELINE AI (5 bước tự động)                         │
│                                                       │
│  1. Phân tích phong cách kiến trúc  (GPT-4o Vision)   │
│     └─ Điều chỉnh theo mô tả người dùng              │
│  2. Viết prompt AI                  (DeepSeek V4)     │
│     └─ Ưu tiên mô tả người dùng khi tạo prompt       │
│  3. Tạo ảnh render                  (DALL-E 3)        │
│  4. Tạo video cinematic             (Google Veo 3.1)  │
│  5. Viết caption song ngữ           (DeepSeek V4)     │
└───────────────────────────────────────────────────────┘
        │
        ▼
  Ảnh + Video + Caption (EN/VI)
        │
        ├─── Watermark thương hiệu
        ├─── Export 9:16 / 1:1 / 16:9
        ├─── Before/After comparison video
        ├─── Lên lịch đăng bài
        └─── Đăng tự động: Instagram · Facebook · TikTok · YouTube
```

**Stack công nghệ:**

| Tầng | Công nghệ |
|------|-----------|
| Frontend | Next.js 16, React 19, TailwindCSS 4, Shadcn/UI |
| Backend | FastAPI, Python 3.11+, SQLAlchemy 2.0 |
| Database | PostgreSQL (chính) / SQLite (fallback) |
| Task Queue | Celery + Redis |
| AI Models | GPT-4o, DALL-E 3, DeepSeek V4, Google Veo 3.1, Runway |
| ML | CLIP embeddings + ChromaDB |
| Scheduling | APScheduler |

---

## 2. Yêu cầu hệ thống

### Bắt buộc

| Phần mềm | Phiên bản | Mục đích |
|----------|-----------|---------|
| Python | 3.11+ | Backend |
| Node.js | 18+ | Frontend |
| FFmpeg | 6.0+ | Xử lý video/ảnh |
| Git | bất kỳ | Clone repo |

### Khuyến nghị thêm (để chạy đầy đủ)

| Phần mềm | Mục đích |
|----------|---------|
| Docker Desktop | Chạy PostgreSQL + Redis dễ dàng |
| PostgreSQL 15+ | Database chính (có thể dùng SQLite để test) |
| Redis 7+ | Task queue |

### Cài FFmpeg trên Windows

```powershell
# Cách 1: Dùng winget
winget install Gyan.FFmpeg

# Cách 2: Tải từ https://ffmpeg.org/download.html
# Giải nén → thêm đường dẫn bin/ vào PATH

# Kiểm tra
ffmpeg -version
```

---

## 3. Cài đặt nhanh

### Bước 1 — Clone và cấu hình

```powershell
cd d:\TU_DONG_DANG_VIDEO

# Tạo file .env từ template
copy .env.example .env

# Mở .env và điền API keys (xem mục 4)
notepad .env
```

### Bước 2 — Khởi động Backend

```powershell
cd backend

# Tạo virtual environment
python -m venv .venv
.venv\Scripts\activate

# Cài dependencies (lần đầu ~5 phút)
pip install -r requirements.txt

# Khởi động API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server chạy tại: http://localhost:8000
Swagger UI (API docs): http://localhost:8000/docs

### Bước 3 — Khởi động Frontend

Mở terminal mới:

```powershell
cd d:\TU_DONG_DANG_VIDEO\frontend

npm install
npm run dev
```

Giao diện web tại: http://localhost:3000

### Bước 4 — Khởi động Database (nếu dùng PostgreSQL)

```powershell
# Dùng Docker (dễ nhất)
docker run -d --name archvideo-db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=archvideo \
  -p 5432:5432 \
  postgres:15

# Nếu không có Docker → backend tự dùng SQLite (file local)
# Chỉnh .env: bỏ qua DATABASE_URL, backend tự fallback
```

### Kiểm tra hệ thống hoạt động

```powershell
# Ping API
curl http://localhost:8000/health
# Expected: {"status":"ok","app":"AI Architecture Video Generator"}

# Mở Swagger UI để test từng endpoint
start http://localhost:8000/docs
```

---

## 4. Cấu hình biến môi trường

File `.env` nằm tại thư mục gốc dự án. Dưới đây là giải thích từng nhóm:

### Nhóm bắt buộc (phải có để chạy pipeline)

```env
# --- AI Vision (phân tích ảnh kiến trúc) ---
OPENAI_API_KEY=sk-...          # Dùng GPT-4o Vision để phân tích ảnh
# HOẶC
ANTHROPIC_API_KEY=sk-ant-...   # Dùng Claude 3.5 Sonnet

# Chọn provider: claude | openai | deepseek
AI_PROVIDER=openai

# --- AI Text (viết prompt & caption — rẻ hơn nhiều) ---
DEEPSEEK_API_KEY=sk-...        # Tại: platform.deepseek.com
USE_DEEPSEEK_FOR_PROMPTS=true
USE_DEEPSEEK_FOR_CAPTIONS=true

# --- Bảo mật ---
# Tạo key ngẫu nhiên:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-random-secret-here
```

### Nhóm tùy chọn (mở rộng tính năng)

```env
# --- Tạo ảnh (nếu muốn dùng DALL-E 3) ---
OPENAI_API_KEY=sk-...           # Dùng chung với Vision ở trên

# --- Tạo video ---
GOOGLE_API_KEY=AIza...          # Google Veo 3.1 qua Gemini API
RUNWAY_API_KEY=...              # Runway Gen-3 (fallback)

# --- Stable Diffusion (fallback tạo ảnh) ---
REPLICATE_API_TOKEN=r8_...      # Tại: replicate.com

# --- Database (bỏ trống → dùng SQLite local) ---
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/archvideo
DATABASE_URL_SYNC=postgresql+psycopg2://user:password@localhost:5432/archvideo

# --- Watermark thương hiệu ---
BRAND_NAME=Công Ty Kiến Trúc ABC
BRAND_PHONE=0901 234 567
BRAND_WATERMARK_POSITION=bottom-right   # bottom-right | bottom-left | top-right | top-left
```

### Nhóm mạng xã hội (cần để đăng bài tự động)

```env
# Instagram (dùng Facebook Graph API v21)
INSTAGRAM_ACCESS_TOKEN=EAAxxxxx...    # Long-lived User Access Token
INSTAGRAM_USER_ID=17841401234567890   # Lấy từ: graph.facebook.com/me?fields=id

# Facebook Page
FACEBOOK_PAGE_ID=123456789012345
FACEBOOK_PAGE_ACCESS_TOKEN=EAAxxxxx...  # Page Access Token (khác User token)

# TikTok
TIKTOK_ACCESS_TOKEN=...

# CORS (thêm domain frontend nếu deploy)
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### Hướng dẫn lấy Instagram/Facebook tokens

1. Truy cập [developers.facebook.com](https://developers.facebook.com)
2. Tạo App → chọn **Business** type
3. Thêm sản phẩm **Instagram Basic Display** + **Instagram Graph API**
4. Tạo **System User** → Generate token với quyền: `instagram_content_publish`, `pages_manage_posts`, `pages_read_engagement`
5. Convert sang **Long-Lived Token** (60 ngày hoặc vĩnh cửu với System User)

---

## 5. Pipeline AI 5 bước

Khi upload ảnh, hệ thống tự động chạy 5 bước:

### Bước 1 — Phân tích phong cách kiến trúc

**Model:** GPT-4o Vision (hoặc Claude 3.5 Sonnet)

Phân tích ảnh và trả về:
- `style` — phong cách: minimalist, modern, tropical, industrial...
- `materials` — vật liệu: concrete, wood, glass...
- `lighting` — ánh sáng: natural daylight, golden hour...
- `mood` — cảm xúc: serene, bold, luxury...
- `architecture_type` — loại công trình: villa, apartment, office...
- `color_palette` — bảng màu chủ đạo
- `key_features` — điểm đặc trưng

**Mô tả sáng tạo (`user_description`):** Nếu người dùng nhập mô tả, nó được inject vào prompt phân tích dưới section `USER DIRECTION`. AI sẽ điều chỉnh kết quả để bám sát ý định, ví dụ ưu tiên phong cách Japandi thay vì tự suy luận từ ảnh. Output bổ sung thêm `user_direction_applied: true` và `direction_notes`.

**Có CLIP training:** Kết quả được enrich thêm bằng semantic similarity (độ chính xác cao hơn ~30%).

### Bước 2 — Viết Prompt AI

**Model:** DeepSeek V4 (hoặc GPT-4o)

Dựa trên phân tích, tạo ra:
- `image_prompt` — prompt tối ưu cho DALL-E 3
- `video_prompt` — prompt cho Google Veo / Runway
- `negative_prompt` — loại bỏ chất lượng kém
- `style_tags` — hashtag phong cách

**Mô tả sáng tạo:** Nếu `user_description` được truyền vào, nó xuất hiện dưới section `USER CREATIVE DIRECTION` trong prompt và được đánh dấu *takes priority over default style assumptions* — đảm bảo ảnh/video tạo ra phản ánh đúng yêu cầu.

Kết quả stream realtime qua WebSocket.

### Bước 3 — Tạo ảnh render

**Model:** DALL-E 3 (1024×1792 = 9:16) → fallback: SDXL via Replicate

Tạo 4-6 ảnh render kiến trúc chất lượng cao, tỉ lệ 9:16 (tối ưu cho mobile/TikTok/Instagram Reels).

### Bước 4 — Tạo video cinematic

**Model:** Google Veo 3.1 → fallback: Runway Gen-3

Video 10-30 giây, cinematic camera movement, từ ảnh render đầu tiên.

### Bước 5 — Viết caption song ngữ

**Model:** DeepSeek V4 (hoặc GPT-4o-mini)

Tạo caption theo từng platform:

| Platform | Caption EN (đăng thật) | Caption VI (dịch tham khảo) |
|----------|------------------------|----------------------------|
| Instagram | Hashtags, CTA, 2200 ký tự max | Bản dịch để chủ nhân hiểu |
| TikTok | Hook mạnh, trending hashtags | Bản dịch tiếng Việt |
| YouTube | SEO-optimized title + description | Bản dịch tiếng Việt |
| Facebook | Storytelling format | Bản dịch tiếng Việt |

> **Lưu ý quan trọng:** Caption tiếng Anh (`en`) là caption thật được đăng lên mạng xã hội. Caption tiếng Việt (`vi`) chỉ để bạn đọc hiểu nội dung, không được đăng.

---

## 6. Sử dụng giao diện web (Frontend)

Mở http://localhost:3000

### Tạo job mới

1. **Dashboard** → nhấn **New Job**
2. Upload ảnh kiến trúc (JPG, PNG, WEBP)
3. **(Tùy chọn — khuyến nghị)** Nhập **Mô tả yêu cầu sáng tạo**: phong cách, vật liệu, ánh sáng, đối tượng khách hàng. Tối đa 300 ký tự. Có 4 chip gợi ý sẵn để click nhanh. Hệ thống hiển thị cảnh báo nếu mô tả không liên quan đến kiến trúc.
4. Chọn platform mục tiêu: Instagram / TikTok / Facebook / YouTube
5. Nhấn **Generate** → pipeline bắt đầu

Theo dõi tiến độ realtime qua thanh progress (WebSocket).

### Xem kết quả

Sau ~2-5 phút (tùy tốc độ API), vào tab **Outputs**:
- Ảnh render (4-6 ảnh, tỉ lệ 9:16)
- Video cinematic
- Caption EN + VI
- Nút: Copy Caption / Download / Schedule / Export

### Lên lịch đăng bài

Từ màn hình Outputs:
1. Nhấn **Schedule Post**
2. Chọn platform, ngày giờ đăng
3. Xem **gợi ý giờ tốt nhất** → nhấn **Use This Time**
4. Nhấn **Confirm** → bài sẽ tự đăng đúng giờ

### Xem lịch đăng

Menu **Schedule** → xem tất cả bài đã lên lịch, trạng thái (pending / posted / failed).

### Xem analytics

Menu **Analytics** → xem:
- Tổng bài đã đăng / thất bại / chờ đăng
- Tỉ lệ thành công theo platform
- Likes, comments, reach từng bài (kéo từ Instagram/Facebook API)

---

## 7. API Reference

Base URL: `http://localhost:8000/api/v1`

> Xem Swagger UI đầy đủ tại: http://localhost:8000/docs

### Jobs — Tạo và theo dõi pipeline

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/jobs/upload` | Upload ảnh, tạo job mới, chạy pipeline |
| `GET` | `/jobs/{job_id}` | Lấy trạng thái job |
| `GET` | `/outputs/{job_id}` | Lấy kết quả (ảnh, video, caption) |
| `PATCH` | `/outputs/{job_id}/captions` | Lưu caption đã chỉnh sửa thủ công |
| `POST` | `/outputs/{job_id}/regenerate-image` | Tái tạo 1 ảnh với prompt mới |
| `POST` | `/outputs/{job_id}/trim-video` | Cắt video theo khoảng thời gian (FFmpeg) |
| `POST` | `/outputs/{job_id}/regenerate-caption` | Tái tạo caption AI với hướng dẫn thêm |
| `WS` | `/ws/jobs/{job_id}` | Kết nối WebSocket nhận tiến độ realtime |

**Upload ảnh và chạy pipeline:**
```bash
curl -X POST http://localhost:8000/api/v1/jobs/upload \
  -F "image=@/path/to/photo.jpg" \
  -F "platforms=instagram,tiktok,facebook,youtube" \
  -F "num_images=4" \
  -F "generate_video=true" \
  -F "user_description=Phong cách Japandi hiện đại, vật liệu gỗ tự nhiên và bê tông thô"
```

**Tham số `user_description`:**

| Tham số | Kiểu | Mặc định | Mô tả |
|---------|------|---------|-------|
| `user_description` | `string` | `""` | Mô tả yêu cầu sáng tạo. Tối đa 300 ký tự. Nên liên quan đến: phong cách kiến trúc, vật liệu, ánh sáng, đối tượng khách hàng. |

**Response:**
```json
{
  "job_id": "abc-123",
  "status": "queued",
  "websocket_url": "/api/v1/ws/jobs/abc-123"
}
```

**Kết nối WebSocket (JavaScript):**
```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/ws/jobs/abc-123");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: "started" | "progress" | "stream_chunk" | "completed" | "error"
  // data.step: "vision" | "prompts" | "images" | "video" | "captions"
  // data.progress: 0.0 → 1.0
  // data.chunk: text chunk khi streaming caption/prompt
  console.log(data);
};
```

**Chỉnh sửa caption thủ công:**
```bash
curl -X PATCH http://localhost:8000/api/v1/outputs/abc-123/captions \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "instagram",
    "title": "Không gian sống tối giản",
    "caption": "Where simplicity meets elegance...",
    "hashtags": ["#MinimalistDesign", "#JapandiStyle"],
    "call_to_action": "Follow us for more inspiration"
  }'
```

**Tái tạo caption AI với hướng dẫn:**
```bash
curl -X POST http://localhost:8000/api/v1/outputs/abc-123/regenerate-caption \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "tiktok",
    "extra_instruction": "More casual tone, start with a trending hook, under 80 words"
  }'
```

**Tái tạo ảnh với prompt mới:**
```bash
curl -X POST http://localhost:8000/api/v1/outputs/abc-123/regenerate-image \
  -H "Content-Type: application/json" \
  -d '{
    "image_index": 2,
    "image_prompt": "Minimalist living room, warm natural light, oak wood floors, floor-to-ceiling windows, 8K, photorealistic",
    "negative_prompt": "cartoon, blur, overexposed"
  }'
```

**Cắt video (chỉ hỗ trợ video lưu cục bộ trong `/output/`):**
```bash
curl -X POST http://localhost:8000/api/v1/outputs/abc-123/trim-video \
  -H "Content-Type: application/json" \
  -d '{
    "start_sec": 2.5,
    "end_sec": 12.0
  }'
```

---

### Auth — Đăng nhập / Đăng ký

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/auth/register` | Đăng ký tài khoản |
| `POST` | `/auth/login` | Đăng nhập, nhận JWT token |

---

### Schedule — Lên lịch đăng bài

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/schedule` | Tạo lịch đăng mới |
| `POST` | `/schedule/from-job` | Lên lịch từ job đã hoàn thành |
| `GET` | `/schedule` | Danh sách tất cả lịch đăng |
| `GET` | `/schedule/{id}` | Chi tiết 1 lịch đăng |
| `PATCH` | `/schedule/{id}` | Đổi giờ đăng |
| `DELETE` | `/schedule/{id}` | Huỷ lịch đăng |

**Tạo lịch đăng từ job:**
```bash
curl -X POST http://localhost:8000/api/v1/schedule/from-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "abc-123",
    "platform": "instagram",
    "scheduled_at": "2026-05-15T19:00:00+07:00"
  }'
```

**Dùng giờ gợi ý từ best-times API:**
```bash
# 1. Lấy gợi ý giờ tốt nhất cho Instagram
curl http://localhost:8000/api/v1/analytics/best-times/instagram

# Response trả về trường "iso_for_schedule" — dùng trực tiếp cho scheduled_at
```

---

### Analytics — Phân tích hiệu suất

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/analytics/summary` | Tổng kết tất cả bài đăng |
| `GET` | `/analytics/post/{post_id}` | Metrics bài đã đăng (likes, reach, impressions) |
| `GET` | `/analytics/instagram/{media_id}` | Kéo metrics trực tiếp từ Instagram |
| `GET` | `/analytics/facebook/{post_id}` | Kéo metrics trực tiếp từ Facebook |
| `GET` | `/analytics/best-times` | Gợi ý giờ đăng tốt nhất tất cả platform |
| `GET` | `/analytics/best-times/{platform}` | Gợi ý giờ đăng tốt nhất cho 1 platform |

**Lấy gợi ý giờ tốt nhất (3 slot):**
```bash
curl "http://localhost:8000/api/v1/analytics/best-times/instagram?n=3"
```

**Response:**
```json
{
  "platform": "instagram",
  "best_times": [
    {
      "datetime_vn": "2026-05-13T19:00:00+07:00",
      "day_label": "Thứ Ba",
      "time_label": "19:00",
      "score": "⭐⭐⭐",
      "iso_for_schedule": "2026-05-13T19:00:00+07:00"
    }
  ],
  "note": "Engagement cao nhất vào giờ nghỉ trưa và tối."
}
```

---

### Before/After — Video so sánh

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/before-after` | Tạo video so sánh trước/sau |

**Tạo video Before/After:**
```bash
curl -X POST http://localhost:8000/api/v1/before-after \
  -F "before=@hien_trang.jpg" \
  -F "after=@render.jpg" \
  -F "effect=reveal" \
  -F "add_labels=true" \
  -F "gen_caption=true" \
  -F "platform=instagram" \
  -F "duration=8"
```

**Các effect có sẵn:**

| Effect | Mô tả |
|--------|-------|
| `reveal` | Wipe từ trái → phải, reveal ảnh "sau" (mặc định) |
| `split` | Màn hình chia đôi song song |
| `slideshow` | Fade chuyển cảnh giữa 2 ảnh |

**Response:**
```json
{
  "success": true,
  "job_id": "xyz-456",
  "effect": "reveal",
  "video_url": "/output/before_after/xyz-456_reveal.mp4",
  "caption": {
    "en": { "title": "...", "body": "...", "hashtags": [...] },
    "vi": { "title": "...", "body": "..." }
  }
}
```

---

### Export — Xuất đa định dạng

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/export` | Upload file → xuất các format khác |
| `POST` | `/export/from-output` | Xuất từ URL job đã có |

**Upload và xuất đa format:**
```bash
curl -X POST http://localhost:8000/api/v1/export \
  -F "file=@video_916.mp4" \
  -F "formats=9:16,1:1,16:9" \
  -F "apply_watermark=true"
```

**Các format:**

| Format | Kích thước | Dùng cho |
|--------|-----------|---------|
| `9:16` | Gốc | TikTok, Instagram Reels, YouTube Shorts |
| `1:1` | 1080×1080 | Instagram Feed, Facebook post |
| `16:9` | 1920×1080 | YouTube, Facebook video cover |

**Response:**
```json
{
  "success": true,
  "formats_created": ["9:16", "1:1", "16:9"],
  "files": {
    "9:16": "/output/exports/abc/9_16.mp4",
    "1:1":  "/output/exports/abc/1_1.mp4",
    "16:9": "/output/exports/abc/16_9.mp4"
  }
}
```

---

### Pipeline Video (TTS + Compose)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/video/enhance/tts` | Tạo audio narration từ text |
| `GET` | `/api/video/enhance/voices` | Danh sách giọng đọc có sẵn |
| `POST` | `/api/video/enhance/compose` | Ghép video + narration + nhạc nền |
| `POST` | `/api/video/enhance/image-to-video` | Tạo video từ ảnh + audio |
| `POST` | `/api/v1/pipeline/narration` | Tạo narration với tiến độ WebSocket |
| `POST` | `/api/v1/pipeline/compose` | Compose video với tiến độ WebSocket |

**Tạo narration:**
```bash
curl -X POST http://localhost:8000/api/video/enhance/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Welcome to this stunning minimalist villa...",
    "voice": "en-US-JennyNeural",
    "speed": 1.0
  }'
```

**Danh sách giọng phổ biến:**

| Voice ID | Giọng |
|----------|-------|
| `en-US-JennyNeural` | Nữ Mỹ (mặc định) |
| `en-US-GuyNeural` | Nam Mỹ |
| `en-GB-SoniaNeural` | Nữ Anh |
| `vi-VN-HoaiMyNeural` | Nữ Việt Nam |
| `vi-VN-NamMinhNeural` | Nam Việt Nam |

---

## 8. Tính năng nâng cao

### Watermark thương hiệu

Cấu hình trong `.env`:
```env
BRAND_NAME=Công Ty Kiến Trúc ABC
BRAND_PHONE=0901 234 567
BRAND_WATERMARK_POSITION=bottom-right
```

Watermark tự động được áp dụng:
- Sau khi pipeline hoàn thành (tất cả ảnh + video)
- Khi export đa định dạng (`apply_watermark=true`)
- Khi tạo Before/After video

Thiết kế watermark: nền tối trong suốt, tên + số điện thoại, font tự động (Arial trên Windows, DejaVu trên Linux).

---

### Content Calendar (Lên lịch đăng)

Hệ thống kiểm tra mỗi 60 giây và tự đăng bài đúng giờ.

**Workflow đơn giản:**
```
1. Chạy pipeline → có ảnh + video + caption
2. POST /schedule/from-job → chọn platform + giờ đăng
3. Hệ thống tự đăng đúng giờ
4. GET /schedule → kiểm tra trạng thái "posted"
5. GET /analytics/post/{id} → xem likes, reach
```

**Trạng thái bài đăng:**

| Trạng thái | Ý nghĩa |
|-----------|---------|
| `pending` | Chờ đến giờ đăng |
| `posted` | Đã đăng thành công |
| `failed` | Lỗi khi đăng (xem `error_message`) |
| `cancelled` | Đã huỷ |

---

### Gợi ý giờ đăng tốt nhất

API này dựa trên dữ liệu engagement research theo múi giờ Việt Nam (UTC+7):

| Platform | Giờ tốt nhất | Ngày tốt nhất |
|----------|-------------|---------------|
| Instagram | 11h, 14h, 17h, 20h | Thứ Ba, Tư, Sáu |
| TikTok | 7h, 12h, 17h, 21h | Thứ Ba, Năm, Sáu |
| Facebook | 9h, 13h, 16h | Thứ Tư, Năm, Sáu |
| YouTube | 14h, 17h, 20h | Thứ Sáu–Chủ Nhật, Thứ Hai |

```bash
# Gợi ý 3 slot tốt nhất cho tất cả platform
curl http://localhost:8000/api/v1/analytics/best-times?n=3
```

---

### Mô tả yêu cầu sáng tạo (`user_description`)

Field tuỳ chọn nhưng quan trọng — giúp AI bám sát ý định của bạn thay vì tự suy luận hoàn toàn từ ảnh.

**Nên mô tả gì:**

| Chủ đề | Ví dụ tốt | Ví dụ không liên quan |
|--------|-----------|----------------------|
| Phong cách | "Japandi tối giản, đường nét sạch" | "Tôi thích màu xanh biển" (mơ hồ) |
| Vật liệu | "Gỗ tự nhiên, bê tông thô, kính low-e" | "Nhà đẹp" (không cụ thể) |
| Ánh sáng | "Ánh sáng tự nhiên ban ngày, không dùng tone vàng ấm" | — |
| Khách hàng | "Hướng đến gia đình trẻ 30–40 tuổi, quan tâm bền vững" | — |
| Mục tiêu | "Video TikTok nhấn mạnh sự yên tĩnh, thư giãn" | — |

**Cảnh báo off-topic:** Frontend hiển thị cảnh báo vàng nếu mô tả dài hơn 20 ký tự nhưng không chứa từ khoá kiến trúc (phong cách, vật liệu, ánh sáng, thiết kế, platform...).

**Giới hạn:** 300 ký tự. Backend tự cắt nếu vượt.

---

### Streaming realtime (WebSocket)

Mỗi bước pipeline stream tiến độ qua WebSocket. Các loại message:

```javascript
// Bước bắt đầu
{ "type": "started", "job_id": "...", "step": "vision" }

// Tiến độ
{ "type": "progress", "step": "images", "progress": 0.6, "message": "Generating image 3/5..." }

// Streaming text (prompt / caption)
{ "type": "stream_chunk", "step": "captions", "chunk": "Welcome to" }

// Hoàn thành
{ "type": "completed", "job_id": "...", "result": { ... } }

// Lỗi
{ "type": "error", "error": "API rate limit exceeded" }
```

---

## 9. Train CLIP (Semantic AI)

CLIP giúp hệ thống nhận diện phong cách kiến trúc chính xác hơn, không phụ thuộc hoàn toàn vào GPT-4o.

### Bước 1 — Chuẩn bị ảnh training

```
backend/scripts/training_data/
├── minimalist/       ← Ảnh phong cách tối giản
│   ├── img001.jpg
│   ├── img002.jpg
│   └── ...
├── tropical/         ← Phong cách nhiệt đới
├── industrial/       ← Phong cách công nghiệp
├── modern/           ← Phong cách hiện đại
└── luxury/           ← Phong cách sang trọng
```

Mỗi folder = 1 phong cách. Tên folder = tên style. Tối thiểu 10-20 ảnh/folder.

### Bước 2 — Cài dependencies ML

```powershell
cd backend
.venv\Scripts\activate
pip install torch torchvision transformers chromadb
```

### Bước 3 — Chạy training

```powershell
python scripts/train_clip.py
```

Training sẽ:
1. Load model CLIP `openai/clip-vit-base-patch32`
2. Tạo 512-dim embedding cho từng ảnh
3. Lưu vào ChromaDB tại `scripts/training_output/chroma_db/`
4. Tạo report `clip_style_profile.json`

Thời gian: ~5-15 phút tùy số lượng ảnh (CPU).

### Bước 4 — Kiểm tra

```bash
curl http://localhost:8000/api/v1/jobs/clip-status
# Nếu trả về "clip_ready: true" → CLIP đang hoạt động
```

Sau khi train, bước 1 của pipeline sẽ tự động dùng CLIP để enrich kết quả phân tích (nếu confidence ≥ 55%).

---

## 10. Chi phí ước tính

### Chi phí mỗi lần chạy pipeline (1 ảnh → 4 ảnh render + 1 video)

| Bước | Model | Chi phí | Ghi chú |
|------|-------|---------|---------|
| Vision Analysis | GPT-4o Vision | ~$0.012 | ~$0.005 nếu dùng Claude Haiku |
| Prompt Writing | DeepSeek V4 | ~$0.002 | ~$0.030 nếu dùng GPT-4o |
| Image Generation (4 ảnh HD) | DALL-E 3 HD 1024×1792 | ~$0.48 | $0.12/ảnh × 4 |
| Image Generation (4 ảnh) | SDXL via Replicate (fallback) | ~$0.04 | $0.010/ảnh × 4 |
| Video Generation (10s) | Google Veo 3.1 | ~$0.50–1.00 | Giá ước tính, xem Google AI pricing |
| Video Generation (10s) | Runway Gen-3 Turbo (fallback) | ~$0.50 | $0.05/giây |
| Caption Writing | DeepSeek V4 × 4 platform | ~$0.004 | ~$0.016 nếu dùng GPT-4o-mini |
| **Tổng (DALL-E + Veo)** | | **~$1.00–1.50** | Cấu hình mặc định |
| **Tổng (DALL-E + Runway)** | | **~$1.00** | Veo không có key → fallback |
| **Tổng (SDXL + Runway)** | | **~$0.56** | Chi phí thấp nhất |

### Tính năng không tốn API cost

| Tính năng | Xử lý tại |
|-----------|---------|
| Watermark thương hiệu | Local (Pillow) |
| Export 9:16 / 1:1 / 16:9 | Local (FFmpeg) |
| Before/After comparison video | Local (FFmpeg) |
| Lên lịch đăng bài | Local (APScheduler) |
| CLIP style matching | Local (PyTorch) |
| Analytics kéo từ Instagram/Facebook | Miễn phí (Graph API) |

### Chi phí hạ tầng hàng tháng

| Dịch vụ | Chi phí |
|---------|---------|
| VPS (4 CPU, 8 GB RAM) | $40–60/tháng |
| PostgreSQL managed (nếu cần) | $15–25/tháng |
| Redis managed (nếu cần) | $10–15/tháng |
| Storage (output files) | $5–15/tháng |
| **Tổng** | **~$70–115/tháng** |

> **Mẹo tiết kiệm:** Dùng DeepSeek V4 cho tất cả bước text (`USE_DEEPSEEK_FOR_PROMPTS=true`, `USE_DEEPSEEK_FOR_CAPTIONS=true`). Dùng SDXL via Replicate thay DALL-E 3 nếu volume cao. Không cần S3 — output phục vụ qua `/output` static files trực tiếp.

---

## 11. Xử lý lỗi thường gặp

### Backend không khởi động

```
Error: No module named 'app'
```
**Giải pháp:** Chạy uvicorn từ đúng thư mục:
```powershell
cd backend
uvicorn app.main:app --reload
```

---

```
SECURITY WARNING: SECRET_KEY is still the default value!
```
**Giải pháp:** Tạo secret key và thêm vào `.env`:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
# Copy kết quả → SECRET_KEY=... trong .env
```

---

### Pipeline thất bại

```
{"type": "error", "error": "API rate limit exceeded"}
```
**Giải pháp:** Đợi vài phút và thử lại, hoặc kiểm tra quota API key.

---

```
{"type": "error", "error": "OPENAI_API_KEY not configured"}
```
**Giải pháp:** Kiểm tra file `.env` có `OPENAI_API_KEY=sk-...` chưa. Restart backend sau khi sửa `.env`.

---

### FFmpeg không tìm thấy

```
RuntimeError: FFmpeg not found
```
**Giải pháp Windows:**
```powershell
winget install Gyan.FFmpeg
# Restart terminal sau khi cài
ffmpeg -version  # Kiểm tra
```

---

### Watermark không hiện

**Nguyên nhân:** `BRAND_NAME` trống trong `.env`.
**Giải pháp:** Thêm vào `.env`:
```env
BRAND_NAME=Tên Công Ty Của Bạn
```

---

### Bài đăng không được đăng tự động

**Kiểm tra:**
1. Token Instagram/Facebook có hết hạn chưa? → Tạo lại Long-Lived Token
2. `FACEBOOK_PAGE_ACCESS_TOKEN` phải là **Page token**, không phải User token
3. Tài khoản Instagram phải là **Business** hoặc **Creator** (không phải Personal)
4. Xem `error_message` trong response `GET /schedule/{id}`

---

### Database lỗi

```
sqlalchemy.exc.OperationalError: could not connect to server
```
**Giải pháp:** Nếu không cần PostgreSQL, để trống `DATABASE_URL` trong `.env` → hệ thống tự dùng SQLite:
```env
# Xoá hoặc comment dòng DATABASE_URL
# DATABASE_URL=...
```

---

## Cấu trúc thư mục quan trọng

```
TU_DONG_DANG_VIDEO/
├── .env                          ← Cấu hình (TẠO TỪ .env.example)
├── .env.example                  ← Template biến môi trường
├── output/                       ← Ảnh/video được tạo ra (served tại /output)
│   ├── {job_id}/                 ← Kết quả từng job
│   ├── before_after/             ← Video before/after
│   └── exports/                  ← File export đa định dạng
├── uploads/                      ← File upload tạm thời
├── frontend/                     ← Next.js app (port 3000)
└── backend/
    ├── app/
    │   ├── main.py               ← FastAPI entry point
    │   ├── core/config.py        ← Đọc .env
    │   ├── api/routes/           ← Tất cả API endpoints
    │   └── services/             ← Logic AI + xử lý
    ├── scripts/
    │   ├── train_clip.py         ← Train CLIP embeddings
    │   └── training_data/        ← Ảnh training (tạo thủ công)
    └── requirements.txt
```

---

## Tóm tắt các URL quan trọng

| URL | Mục đích |
|-----|---------|
| http://localhost:3000 | Giao diện web chính |
| http://localhost:8000/docs | Swagger API documentation |
| http://localhost:8000/health | Kiểm tra backend hoạt động |
| http://localhost:8000/output/{path} | Truy cập file output (ảnh, video) |

---

*Tài liệu này được tạo tự động cho dự án TU_DONG_DANG_VIDEO. Cập nhật lần cuối: 2026-05-11.*

---

## Changelog

| Ngày | Thay đổi |
|------|---------|
| 2026-05-11 | Thêm tính năng Mô tả yêu cầu sáng tạo (`user_description`) |
| 2026-05-11 | Thêm mục Chi phí ước tính (mục 10) |
| 2026-05-11 | Sửa bug: `import os` trong video_enhance.py, `TTSService` import trong pipeline_routes.py |
| 2026-05-11 | Sửa relative paths trong before_after.py, export.py, format_exporter.py |
| 2026-05-11 | Tạo tài liệu DOCS.md, USER_GUIDE.md |
| 2026-05-11 | Thêm: Before/After video, Export đa định dạng, Analytics, Scheduling, Watermark, Best Times |
