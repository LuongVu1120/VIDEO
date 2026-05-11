# Hướng Dẫn Sử Dụng Dành Cho Người Dùng

**AI Architecture Video Generator** — Công cụ tạo nội dung kiến trúc tự động bằng AI

---

## Nó làm được gì?

Bạn chỉ cần **upload 1 ảnh kiến trúc** — phòng khách, mặt tiền, nội thất, bản vẽ render — hệ thống sẽ tự động:

- Phân tích phong cách thiết kế
- Tạo ra 4–6 ảnh render chất lượng cao cùng phong cách
- Tạo video cinematic 10–30 giây
- Viết caption tiếng Anh sẵn sàng đăng (kèm bản dịch tiếng Việt để bạn đọc hiểu)
- Đóng watermark tên công ty / số điện thoại
- Lên lịch và tự động đăng lên Instagram, Facebook, TikTok, YouTube

Toàn bộ quy trình mất khoảng **3–5 phút**, không cần kỹ năng thiết kế hay viết lách.

---

## Bắt đầu sử dụng

Mở trình duyệt, truy cập: **http://localhost:3000**

Đăng ký tài khoản → Đăng nhập → Vào **Dashboard**.

---

## Tạo nội dung mới

### Bước 1 — Upload ảnh

Nhấn **New Job** → Kéo thả hoặc chọn ảnh kiến trúc từ máy tính.

Định dạng hỗ trợ: JPG, PNG, WEBP. Kích thước tối đa: 20MB.

> Mẹo: Ảnh rõ nét, đủ sáng, thể hiện được phong cách thiết kế sẽ cho kết quả tốt nhất.

### Bước 1b — Mô tả yêu cầu sáng tạo (tuỳ chọn nhưng khuyến nghị)

Bên dưới khung upload, có ô **Mô tả yêu cầu sáng tạo**. Điền vào đây để AI bám sát ý định của bạn thay vì tự đoán hoàn toàn.

**Nên mô tả gì?**

| Chủ đề | Ví dụ |
|--------|-------|
| Phong cách thiết kế | "Phong cách Japandi, tối giản, đường nét sạch" |
| Vật liệu & màu sắc | "Gỗ tự nhiên, bê tông thô, tone màu trung tính ấm" |
| Ánh sáng & thời điểm | "Ánh sáng tự nhiên ban ngày, không dùng ánh đèn vàng" |
| Đối tượng khách hàng | "Hướng đến khách hàng 30–45 tuổi, quan tâm thiết kế cao cấp" |
| Mục tiêu nội dung | "Caption cần nhấn mạnh sự yên tĩnh, thư giãn của không gian" |

Bạn cũng có thể nhấn vào **các chip gợi ý** có sẵn để điền nhanh.

> Lưu ý: Nếu bạn mô tả nội dung không liên quan đến kiến trúc (ví dụ: ẩm thực, du lịch), hệ thống sẽ hiển thị cảnh báo nhắc bạn điều chỉnh lại.

### Bước 2 — Chọn platform

Tick chọn nơi bạn muốn đăng:

- **Instagram** — Reels, Feed
- **TikTok** — Video ngắn
- **Facebook** — Page post
- **YouTube** — Shorts, video

### Bước 3 — Nhấn Generate

Nhấn nút **Generate** và chờ. Thanh tiến độ sẽ cập nhật realtime qua từng bước:

```
Phân tích ảnh... → Viết prompt... → Tạo ảnh... → Tạo video... → Viết caption...
```

Thời gian: khoảng **3–5 phút** tùy tốc độ kết nối.

### Bước 4 — Xem kết quả

Sau khi xong, tab **Outputs** hiển thị:

| Mục | Nội dung |
|-----|---------|
| Ảnh render | 4–6 ảnh 9:16 chất lượng cao |
| Video | 1 video cinematic |
| Caption EN | Caption tiếng Anh — đây là bản được đăng thật |
| Caption VI | Bản dịch tiếng Việt để bạn đọc hiểu nội dung |
| Hashtags | Danh sách hashtag theo từng platform |

---

## Chỉnh sửa kết quả trước khi đăng

Sau khi có kết quả, bạn có thể chỉnh sửa bất kỳ phần nào trước khi đăng bài.

### Chỉnh sửa caption

Trong tab **Captions** → nhấn nút **Edit** ở góc phải mỗi platform.

Màn hình chỉnh sửa cho phép bạn thay đổi:

| Trường | Mô tả |
|--------|-------|
| **Title** | Tiêu đề bài đăng |
| **Caption** | Nội dung caption tiếng Anh (bản được đăng thật) |
| **Hashtags** | Danh sách hashtag, cách nhau bằng dấu phẩy |
| **Call to Action** | Câu kêu gọi hành động cuối bài |

Sau khi sửa xong → nhấn **Save Changes**.

**Tái tạo caption bằng AI (với hướng dẫn cụ thể):**

Nếu bạn muốn AI viết lại caption theo một phong cách khác, nhập yêu cầu vào ô *"Regenerate with AI instruction"* rồi nhấn **Regenerate Caption**.

Ví dụ yêu cầu:
- `"More formal tone, less casual"`
- `"Shorter and punchier, start with a question"`
- `"Emphasize luxury and exclusivity"`
- `"Add sense of urgency in the call to action"`

### Tái tạo ảnh

Trong tab **Images** → nhấn biểu tượng **↻** (refresh) ở góc phải mỗi ảnh.

Panel chỉnh sửa hiện ra với:
- **Image Prompt** — mô tả hình ảnh muốn tạo (có thể sửa từ prompt gốc)
- **Negative Prompt** — những gì không muốn xuất hiện trong ảnh

Sửa prompt theo ý muốn → nhấn **Regenerate**. Ảnh mới sẽ thay thế ảnh cũ tại đúng vị trí đó.

> Mẹo: Thêm vào prompt các từ như "golden hour lighting", "ultra sharp focus", "8K resolution" để cải thiện chất lượng ảnh.

### Cắt video

Trong tab **Video** → nhấn nút **Trim**.

Nhập thời điểm bắt đầu và kết thúc (tính bằng giây) → nhấn **Apply Trim**.

> Lưu ý: Tính năng cắt video chỉ hoạt động với video được lưu trên server (được tạo bằng FFmpeg cục bộ). Video từ Runway hoặc Veo CDN bên ngoài không hỗ trợ cắt trực tiếp — cần tải về máy trước.

---

## Đăng bài lên mạng xã hội

### Đăng ngay lập tức

Từ màn hình Outputs → nhấn **Post Now** → chọn platform → xác nhận.

### Lên lịch đăng sau

1. Nhấn **Schedule Post**
2. Chọn platform (Instagram / Facebook / TikTok / YouTube)
3. Nhấn **Gợi ý giờ tốt nhất** — hệ thống đề xuất khung giờ có engagement cao nhất
4. Chọn ngày giờ mong muốn → nhấn **Confirm**

Bài sẽ tự động được đăng đúng giờ bạn đặt, không cần mở máy tính.

### Xem lịch đăng

Menu **Schedule** → danh sách tất cả bài đã lên lịch.

| Trạng thái | Ý nghĩa |
|-----------|---------|
| Đang chờ | Chưa đến giờ đăng |
| Đã đăng | Thành công |
| Thất bại | Có lỗi — xem chi tiết để biết nguyên nhân |

Để huỷ hoặc đổi giờ: nhấn vào bài → **Reschedule** hoặc **Cancel**.

---

## Tính năng nâng cao

### Video Before / After

Tạo video so sánh hiện trạng và bản thiết kế — rất hiệu quả để showcase công trình cải tạo, nội thất trước và sau.

1. Menu **Before/After** → nhấn **Create**
2. Upload 2 ảnh: ảnh **Trước** (hiện trạng) và ảnh **Sau** (render/hoàn thiện)
3. Chọn hiệu ứng chuyển cảnh:

| Hiệu ứng | Mô tả |
|----------|-------|
| **Reveal** | Ảnh "Sau" trượt dần từ trái sang phải che ảnh "Trước" |
| **Split** | Hai ảnh hiện song song trái-phải |
| **Slideshow** | Fade chuyển cảnh mượt mà |

4. Chọn thêm nhãn BEFORE / AFTER (tuỳ chọn)
5. Nhấn **Create Video** → nhận video ~8 giây sẵn sàng đăng

### Export đa định dạng

Từ 1 video/ảnh 9:16, tự động tạo thêm các phiên bản cho từng platform:

| Format | Kích thước | Dùng cho |
|--------|-----------|---------|
| 9:16 | Dọc | TikTok, Instagram Reels, YouTube Shorts |
| 1:1 | Vuông | Instagram Feed, Facebook post |
| 16:9 | Ngang | YouTube, Facebook video cover |

Menu **Export** → upload file gốc → chọn format → nhấn **Export**.

Nền 16:9 dùng hiệu ứng blur phần trống thay vì viền đen — trông chuyên nghiệp hơn.

### Watermark thương hiệu

Tất cả ảnh và video được tự động đóng watermark tên công ty + số điện thoại ở góc mà bạn cấu hình.

Để thay đổi thông tin watermark: liên hệ admin cập nhật trong file cấu hình hệ thống.

---

## Xem Analytics

Menu **Analytics** → tổng quan hiệu suất:

- Tổng số bài đã đăng / thất bại / chờ đăng
- Tỉ lệ thành công theo từng platform
- Likes, comments, reach từng bài (kéo trực tiếp từ Instagram / Facebook)

Nhấn vào từng bài để xem số liệu chi tiết.

---

## Gợi ý giờ đăng tốt nhất

Hệ thống phân tích dữ liệu engagement theo múi giờ Việt Nam và gợi ý khung giờ tối ưu:

| Platform | Giờ tốt | Ngày tốt |
|----------|---------|---------|
| Instagram | 11h, 14h, 17h, 20h | Thứ Ba, Tư, Sáu |
| TikTok | 7h, 12h, 17h, 21h | Thứ Ba, Năm, Sáu |
| Facebook | 9h, 13h, 16h | Thứ Tư, Năm, Sáu |
| YouTube | 14h, 17h, 20h | Thứ Sáu – Chủ Nhật |

Xem tại: **Analytics → Best Posting Times**.

---

## Câu hỏi thường gặp

**Ảnh render trông không giống phong cách tôi muốn?**

AI căn cứ vào ảnh bạn upload để phân tích phong cách. Hãy upload ảnh thể hiện rõ phong cách thiết kế mong muốn — góc chụp rõ, đủ sáng, tập trung vào đặc trưng thiết kế.

**Caption tiếng Anh — tôi không biết tiếng Anh có dùng được không?**

Được. Caption tiếng Anh được viết bởi AI để đăng lên mạng xã hội quốc tế. Cột **Caption VI** bên cạnh là bản dịch tiếng Việt để bạn đọc và kiểm tra nội dung trước khi đăng. Bạn có thể sửa caption trước khi xác nhận đăng.

**Bài đăng tự động không thành công?**

Kiểm tra tab **Schedule** → xem cột **Lý do lỗi**. Nguyên nhân phổ biến: token mạng xã hội hết hạn. Liên hệ admin để cập nhật lại access token.

**Video tạo ra bao lâu?**

Bước tạo video mất 2–4 phút (phụ thuộc vào API Google Veo / Runway). Toàn bộ pipeline: 3–5 phút.

**Tôi có thể sửa caption trước khi đăng không?**

Có. Tab **Captions** → nhấn **Edit** ở platform muốn sửa → chỉnh tiêu đề, nội dung, hashtag, CTA → **Save Changes**. Hoặc dùng tính năng "Regenerate with AI instruction" để yêu cầu AI viết lại hoàn toàn theo hướng của bạn.

**Ảnh render không đúng ý — có thể làm lại không?**

Có. Tab **Images** → nhấn nút **↻** ở ảnh muốn làm lại → sửa prompt → **Regenerate**. Chỉ ảnh đó được làm lại, các ảnh còn lại giữ nguyên.

**Watermark có thể tắt không?**

Watermark được bật/tắt ở cấp hệ thống bởi admin. Nếu bạn không muốn watermark, liên hệ admin để tắt trong cài đặt.

---

## Luồng làm việc gợi ý cho một tuần

```
Thứ Hai sáng (30 phút)
  └─ Upload 5–7 ảnh dự án mới nhất
  └─ Chạy Generate cho tất cả
  └─ Xem kết quả, chỉnh caption nếu cần

Thứ Hai chiều (15 phút)
  └─ Lên lịch đăng cho cả tuần
  └─ Dùng gợi ý "Best Times" để chọn giờ
  └─ Mỗi platform 1–2 bài/ngày

Cuối tuần
  └─ Xem Analytics tuần vừa rồi
  └─ Xem bài nào được reach cao nhất → tập trung phong cách đó
```

Kết quả: mỗi tuần có **5–14 bài** chất lượng cao trên 4 platform, chỉ mất **45 phút** làm việc thủ công.

---

## Chi phí mỗi lần tạo nội dung

Mỗi lần bạn nhấn **Generate** (1 ảnh upload → 4 ảnh + 1 video + caption), hệ thống gọi các API AI có trả phí:

| Bước | Chi phí ước tính |
|------|-----------------|
| Phân tích ảnh (GPT-4o Vision) | ~$0.012 |
| Viết prompt AI (DeepSeek V4) | ~$0.002 |
| 4 ảnh render HD (DALL-E 3) | ~$0.48 |
| 1 video cinematic 10s (Veo 3.1 / Runway) | ~$0.50–1.00 |
| Caption 4 platform (DeepSeek V4) | ~$0.004 |
| **Tổng mỗi lần chạy** | **~$1.00–1.50** |

**Các tính năng miễn phí (chạy trên server, không tốn API):**

- Watermark thương hiệu
- Export 9:16 / 1:1 / 16:9
- Before/After comparison video
- Lên lịch đăng bài tự động
- Xem analytics / metrics

> Chi phí trên tính theo giá API công khai tính đến tháng 5/2026. Admin cấu hình API keys — bạn không cần tự trả trực tiếp nếu đang dùng hệ thống do công ty cung cấp.

---

## Hỗ trợ

Nếu gặp lỗi hoặc cần hỗ trợ, liên hệ admin hoặc xem tài liệu kỹ thuật đầy đủ tại file **DOCS.md**.
