# Thư viện nhạc nền (BGM)

Pipeline **tự chọn nhạc theo phong cách mỗi video** sau khi fal/Kling tạo xong (cần **FFmpeg**).

## Cách chọn nhạc

Hệ thống phân tích `style`, `mood`, `lighting`, `environment` của từng variation và chọn mood BGM:

| Mood folder | Phù hợp với |
|-------------|-------------|
| `peaceful/` | Tropical, coastal, organic, calm |
| `luxurious/` | Neoclassical, elegant, luxury |
| `dramatic/` | Industrial, brutalist, cinematic |
| `cozy/` | Mediterranean, rustic, warm |
| `futuristic/` | Modern, contemporary, urban tech |
| `serene/` | Minimalist, Scandinavian, zen |

Mỗi video variation nhận **track khác** (xoay vòng trong thư mục mood, không trùng trong cùng job).

## Cấu trúc thư mục

Đặt file **royalty-free** (mp3, wav, m4a…) vào thư mục theo mood:

```
bgm/
  peaceful/
  luxurious/
  dramatic/
  cozy/
  futuristic/
  serene/
```

Nên có **ít nhất 2 file** mỗi mood để các variation không dùng cùng một track.

## Thiết lập thư viện demo (dev)

```bash
brew install ffmpeg   # macOS
cd backend
.venv/bin/python scripts/setup_bgm_library.py
```

Script tạo ambient demo royalty-free cho mỗi mood nếu thư mục trống.

Để có nhạc thật: tải từ Uppbeat, Pixabay Music, YouTube Audio Library… và copy vào các thư mục trên.

## Cấu hình `.env`

```env
VIDEO_ADD_BGM=true
BGM_VOLUME=0.22
# BGM_LIBRARY_DIR=/path/to/custom/bgm
```

Tắt nhạc nền: `VIDEO_ADD_BGM=false`
