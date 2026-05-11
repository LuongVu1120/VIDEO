import asyncio
import sys
import os

# Add PATH for ffmpeg
os.environ["PATH"] += os.pathsep + r"C:\Users\vudai\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"

sys.path.insert(0, "backend")

from app.services.tts_service import TTSService
from app.services.video_composer import VideoComposer


async def create_video_and_thumbnail():
    print("=" * 60)
    print("🎬 TẠO VIDEO VÀ XUẤT ẢNH THUMBNAIL")
    print("=" * 60)

    # === BƯỚC 1: TẠO SCRIPT NARRATION ===
    print("\n[1/5] Tạo narration script...")
    script = """Welcome to Azure Heights, a stunning contemporary villa nestled in the hills of Santorini. 
    Every curve tells a story of elegance, every window frames a masterpiece of nature.
    This architectural wonder combines minimalist design with sustainable innovation.
    Floor-to-ceiling glass walls invite natural light to dance across marble floors.
    A infinity pool seems to merge with the Aegean Sea on the horizon."""
    
    word_count = len(script.split())
    print(f"  Script: {word_count} words")

    # === BƯỚC 2: TẠO AUDIO NARRATION (TTS - FREE) ===
    print("\n[2/5] Tạo narration audio (Edge TTS - FREE)...")
    tts = TTSService()
    
    os.makedirs("test_demo/audio", exist_ok=True)
    os.makedirs("test_demo/video", exist_ok=True)
    os.makedirs("test_demo/images", exist_ok=True)

    narration = await tts.synthesize_with_duration(
        text=script,
        voice="en-US-JennyNeural",
        speed=1.0,
        output_dir="test_demo/audio",
    )
    
    audio_path = narration["path"]
    audio_duration = narration["duration"]
    print(f"  Audio: {audio_path}")
    print(f"  Duration: {audio_duration:.2f}s")

    # === BƯỚC 3: TẠO ẢNH NỀN TỪ CODE (KHÔNG CẦN API KEY) ===
    print("\n[3/5] Tạo ảnh nền kiến trúc...")
    
    # Tạo ảnh PNG từ code (Pillow)
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    
    def create_arch_image(filename, width=1920, height=1080, color_scheme="modern"):
        img = Image.new("RGB", (width, height), (10, 15, 30))
        draw = ImageDraw.Draw(img)
        
        # Sky gradient
        for y in range(height):
            r = int(10 + (y / height) * 40)
            g = int(15 + (y / height) * 30)
            b = int(50 + (y / height) * 20)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Modern building shape
        # Main structure
        building_w = 600
        building_h = 500
        bx = (width - building_w) // 2
        by = height - building_h - 100
        
        # Draw building
        draw.rectangle([bx, by, bx + building_w, by + building_h], fill=(30, 45, 70), outline=(80, 120, 180), width=3)
        
        # Windows
        window_size = 40
        gap = 60
        for row in range(6):
            for col in range(7):
                wx = bx + 50 + col * (window_size + gap)
                wy = by + 50 + row * (window_size + gap)
                # Window glow
                glow = (255, 200, 100) if (row + col) % 2 == 0 else (100, 180, 255)
                draw.rectangle([wx, wy, wx + window_size, wy + window_size], fill=glow)
                # Window frame
                draw.rectangle([wx, wy, wx + window_size, wy + window_size], outline=(60, 80, 120), width=2)
        
        # Ground
        draw.rectangle([0, height - 100, width, height], fill=(20, 40, 20))
        
        # Pool
        pool_y = height - 130
        draw.ellipse([bx - 50, pool_y - 60, bx + building_w + 50, pool_y + 40], fill=(30, 100, 150), outline=(100, 200, 255), width=2)
        
        # Sun/Moon
        draw.ellipse([width - 200, 80, width - 100, 180], fill=(255, 200, 50))
        
        img.save(filename, "PNG")
        return filename

    # Tạo 3 ảnh cho slideshow
    images = []
    for i, scheme in enumerate(["modern", "sunset", "night"]):
        img_path = f"test_demo/images/scene_{i+1}.png"
        create_arch_image(img_path, color_scheme=scheme)
        images.append(img_path)
        print(f"  Ảnh {i+1}: {img_path}")

    # === BƯỚC 4: TẠO VIDEO TỪ ẢNH + AUDIO ===
    print("\n[4/5] Tạo video từ ảnh + narration...")
    composer = VideoComposer()
    
    # Tính thời gian cho mỗi scene
    scene_duration = audio_duration / len(images)
    
    video_segments = []
    for i, img in enumerate(images):
        seg_path = f"test_demo/video/segment_{i+1}.mp4"
        print(f"  Segment {i+1}: {img} -> {seg_path}")
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", img,
            "-c:v", "libx264",
            "-t", str(scene_duration),
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-b:v", "2M",
            "-r", "30",
            seg_path
        ]
        import subprocess
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        video_segments.append(seg_path)
    
    # Ghép các segment
    concat_path = "test_demo/video/concatenated.mp4"
    if len(video_segments) > 1:
        with open("test_demo/video/filelist.txt", "w") as f:
            for seg in video_segments:
                f.write(f"file '{os.path.abspath(seg)}'\n")
        
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", "test_demo/video/filelist.txt",
            "-c", "copy",
            concat_path
        ], check=True, capture_output=True, timeout=120)
    else:
        import shutil
        shutil.copy(video_segments[0], concat_path)
    
    # Thêm audio vào video
    final_video = "test_demo/video/Azure_Heights_Final.mp4"
    print(f"\n  Thêm narration vào video...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", concat_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        final_video
    ], check=True, capture_output=True, timeout=120)
    
    print(f"  ✅ Video hoàn chỉnh: {final_video}")

    # === BƯỚC 5: XUẤT ẢNH THUMBNAIL TỪ VIDEO ===
    print("\n[5/5] Xuất ảnh thumbnail từ video...")
    
    thumbnails = [
        ("test_demo/images/thumbnail_1.jpg", "00:00:01"),
        ("test_demo/images/thumbnail_2.jpg", f"00:00:{int(scene_duration):02d}"),
        ("test_demo/images/thumbnail_3.jpg", f"00:00:{int(scene_duration*2):02d}"),
    ]
    
    for thumb_path, time in thumbnails:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", final_video,
            "-ss", time,
            "-vframes", "1",
            "-q:v", "2",
            thumb_path
        ], check=True, capture_output=True, timeout=30)
        size_kb = os.path.getsize(thumb_path) / 1024
        print(f"  Thumbnail: {thumb_path} ({size_kb:.0f} KB @ {time})")
    
    # === TỔNG KẾT ===
    print("\n" + "=" * 60)
    print("🎉 HOÀN THÀNH!")
    print("=" * 60)
    print(f"\n📹 Video: {final_video}")
    print(f"   Size: {os.path.getsize(final_video) / 1024 / 1024:.1f} MB")
    print(f"   Duration: {audio_duration:.1f}s")
    print(f"\n🖼️  Thumbnails:")
    for t, _ in thumbnails:
        print(f"   - {t}")
    print(f"\n📁 Tất cả output trong thư mục: test_demo/")
    print("\nĐể xem video, mở file:")
    print(f"   {os.path.abspath(final_video)}")


if __name__ == "__main__":
    asyncio.run(create_video_and_thumbnail())
