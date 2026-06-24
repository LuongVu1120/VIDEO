# Thư viện nhạc nền (BGM)

Pipeline tự ghép nhạc vào video sau khi fal/Kling tạo xong (cần **FFmpeg**).

## Cấu trúc thư mục

Đặt file **royalty-free** (mp3, wav, m4a…) vào thư mục theo mood:

```
bgm/
  peaceful/     ← calm, serene
  luxurious/    ← premium, elegant
  dramatic/     ← epic, cinematic
  cozy/         ← warm, homely
  futuristic/   ← modern, tech
  serene/       ← minimal, zen
```

Hệ thống chọn **file đầu tiên** trong thư mục khớp `mood` của job (từ phân tích kiến trúc).

## Nếu chưa có file nhạc

Lần chạy đầu có thể tạo `peaceful/_fallback_ambient.mp3` (tiếng ồn rất nhẹ) để demo.  
Để có nhạc thật: tải nhạc miễn phí bản quyền (Uppbeat, Pixabay Music, YouTube Audio Library…) và copy vào các thư mục trên.

## Cấu hình `.env`

```env
VIDEO_ADD_BGM=true
BGM_VOLUME=0.22
# BGM_LIBRARY_DIR=D:/Music/arch-bgm
```

Tắt nhạc nền: `VIDEO_ADD_BGM=false`
