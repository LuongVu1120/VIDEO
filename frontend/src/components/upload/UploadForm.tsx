"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Upload, ImageIcon, Video, Hash, Send, Lightbulb, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/use-toast";
import { useJobStore } from "@/store/job-store";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const MAX_DESC = 300;

const ARCH_KEYWORDS = [
  "phong cách", "style", "vật liệu", "ánh sáng", "nội thất", "ngoại thất",
  "minimalist", "hiện đại", "modern", "tropical", "japandi", "industrial",
  "luxury", "sang trọng", "màu", "color", "không gian", "công trình",
  "villa", "căn hộ", "văn phòng", "khách hàng", "target", "tiktok",
  "instagram", "video", "render", "thiết kế", "design", "architecture",
];

function isOffTopic(text: string): boolean {
  if (text.length < 20) return false;
  const lower = text.toLowerCase();
  return !ARCH_KEYWORDS.some((kw) => lower.includes(kw));
}

const EXAMPLE_HINTS = [
  "Phong cách Japandi tối giản, vật liệu gỗ tự nhiên và bê tông, ánh sáng ban ngày mềm",
  "Biệt thự nhiệt đới hiện đại, nhấn cây xanh và hồ bơi, tone xanh lá",
  "Nội thất luxury màu trung tính, đèn vàng ấm, khách hàng cao cấp",
  "Mặt tiền công trình thương mại industrial, ánh nắng vàng chiều",
];

type DefaultDirection = {
  key: string;
  label_vi: string;
  prompt_vi: string;
};

export function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [numImages, setNumImages] = useState<number>(0);
  const [generateVideo, setGenerateVideo] = useState(true);
  const [videoDuration, setVideoDuration] = useState(5);
  const [maxVideoVariations, setMaxVideoVariations] = useState(1);
  const [economyMode, setEconomyMode] = useState(true);
  const [platforms, setPlatforms] = useState<string[]>(["instagram"]);
  const [autoPost, setAutoPost] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [userDescription, setUserDescription] = useState("");
  const [autoDirections, setAutoDirections] = useState<DefaultDirection[]>([]);
  const [autoPreviewLabel, setAutoPreviewLabel] = useState<string>("");
  const router = useRouter();
  const { toast } = useToast();
  const { uploadImage, isUploading } = useJobStore();

  useEffect(() => {
    api.getDefaultVideoDirections()
      .then((data) => {
        setAutoDirections(data.directions);
        setAutoPreviewLabel(data.preview.variation_1.label_vi);
      })
      .catch(() => {
        setAutoPreviewLabel("Ngày → đêm, chuyển mùa, room-in / room-out…");
      });
  }, []);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile && droppedFile.type.startsWith("image/")) {
      setFile(droppedFile);
      setPreview(URL.createObjectURL(droppedFile));
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPreview(URL.createObjectURL(selectedFile));
    }
  };

  const togglePlatform = (platform: string) => {
    if (economyMode) return;
    setPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    );
  };

  const applyEconomyMode = (enabled: boolean) => {
    setEconomyMode(enabled);
    if (enabled) {
      setNumImages(0);
      setMaxVideoVariations(1);
      setVideoDuration(5);
      setPlatforms(["instagram"]);
      setGenerateVideo(true);
    }
  };

  const estimatedCostUsd =
    generateVideo
      ? 0.08 + maxVideoVariations * (videoDuration <= 5 ? 0.21 : 0.21 + (videoDuration - 5) * 0.042) +
        numImages * (economyMode ? 0.02 : 0.04)
      : numImages * (economyMode ? 0.02 : 0.04);

  const handleVideoDurationChange = (value: string) => {
    const next = Number.parseInt(value, 10);
    if (Number.isNaN(next)) {
      setVideoDuration(5);
      return;
    }
    setVideoDuration(Math.max(3, Math.min(15, next)));
  };

  const handleSubmit = async () => {
    if (!file) {
      toast({ title: "Error", description: "Please select an image first", variant: "destructive" });
      return;
    }

    if (numImages === 0 && !generateVideo) {
      toast({
        title: "Thiếu tùy chọn",
        description: "Chọn ít nhất một: tạo ảnh (2/4/6) hoặc bật Generate Cinematic Video.",
        variant: "destructive",
      });
      return;
    }

    const formData = new FormData();
    formData.append("image", file);
    formData.append("num_images", numImages.toString());
    formData.append("generate_video", generateVideo.toString());
    formData.append("video_duration", videoDuration.toString());
    formData.append("max_video_variations", maxVideoVariations.toString());
    formData.append("platforms", platforms.join(","));
    formData.append("auto_post", autoPost.toString());
    formData.append("user_description", userDescription.trim());

    try {
      const jobId = await uploadImage(formData);
      toast({
        title: "Job Created",
        description: "Your architecture content generation has started!",
        variant: "success",
      });
      router.push(`/dashboard/jobs/${jobId}`);
    } catch (error) {
      toast({
        title: "Upload Failed",
        description: error instanceof Error ? error.message : "Something went wrong",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Create New Content</h1>
        <p className="text-neutral-500 mt-2">
          Upload an architecture photo, and AI will generate images, videos, and captions.
        </p>
      </div>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Architecture Photo</CardTitle>
          <CardDescription>Drag & drop or click to select (JPEG, PNG, WebP)</CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={cn(
              "relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors",
              dragActive
                ? "border-neutral-900 bg-neutral-50 dark:border-neutral-50 dark:bg-neutral-900/20"
                : "border-neutral-300 dark:border-neutral-700",
              preview && "p-4"
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            {preview ? (
              <div className="relative w-full max-w-lg aspect-video rounded-lg overflow-hidden">
                <Image
                  src={preview}
                  alt="Preview"
                  fill
                  className="object-cover"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  className="absolute top-2 right-2"
                  onClick={() => {
                    setFile(null);
                    setPreview(null);
                  }}
                >
                  Change
                </Button>
              </div>
            ) : (
              <>
                <Upload className="h-12 w-12 text-neutral-400 mb-4" />
                <p className="text-sm text-neutral-500 mb-2">
                  Drop your image here, or{" "}
                  <label className="text-neutral-900 underline cursor-pointer dark:text-neutral-50">
                    browse
                    <input
                      type="file"
                      className="hidden"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileChange}
                    />
                  </label>
                </p>
                <p className="text-xs text-neutral-400">JPEG, PNG, or WebP up to 10MB</p>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Creative Direction */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-amber-500" />
            Mô tả yêu cầu sáng tạo
            <span className="text-sm font-normal text-neutral-400">(tuỳ chọn)</span>
          </CardTitle>
          <CardDescription>
            Tuỳ chọn — để trống thì AI tự chọn kịch bản video sinh động (ngày/đêm, mùa, room-in/out, drone orbit…).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="relative">
            <textarea
              value={userDescription}
              onChange={(e) => setUserDescription(e.target.value.slice(0, MAX_DESC))}
              placeholder="Để trống = AI tự chọn (vd: ngày→đêm, xuân→hè, từ trong ra ngoài, drone orbit…). Hoặc mô tả phong cách, ánh sáng, chuyển camera bạn muốn."
              rows={3}
              className={cn(
                "w-full resize-none rounded-md border px-3 py-2 text-sm outline-none transition-colors",
                "bg-white dark:bg-neutral-900",
                "border-neutral-200 dark:border-neutral-700",
                "focus:border-neutral-500 dark:focus:border-neutral-400",
                "placeholder:text-neutral-400"
              )}
            />
            <span
              className={cn(
                "absolute bottom-2 right-3 text-xs",
                userDescription.length >= MAX_DESC
                  ? "text-red-400"
                  : "text-neutral-400"
              )}
            >
              {userDescription.length}/{MAX_DESC}
            </span>
          </div>

          {!userDescription.trim() && autoPreviewLabel && (
            <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-300">
              <span className="font-medium">Tự động khi để trống:</span> {autoPreviewLabel}
              {maxVideoVariations > 1 && " · Variation 2 sẽ dùng kịch bản khác"}
            </div>
          )}

          {/* Off-topic warning */}
          {isOffTopic(userDescription) && (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-400">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                Mô tả nên liên quan đến kiến trúc và nội dung bạn muốn tạo — ví dụ: phong cách thiết kế, vật liệu, ánh sáng, đối tượng khách hàng, hoặc mục tiêu đăng bài.
              </span>
            </div>
          )}

          {/* Cinematic direction chips */}
          {autoDirections.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-neutral-400">Kịch bản video kiến trúc — nhấn để dùng:</p>
              <div className="flex flex-wrap gap-2">
                {autoDirections.map((d) => (
                  <button
                    key={d.key}
                    type="button"
                    onClick={() => setUserDescription(d.prompt_vi.slice(0, MAX_DESC))}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs transition-colors",
                      "border-sky-200 bg-sky-50 text-sky-800",
                      "hover:border-sky-400 hover:bg-sky-100",
                      "dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-300",
                      userDescription === d.prompt_vi.slice(0, MAX_DESC) &&
                        "border-sky-600 bg-sky-600 text-white dark:bg-sky-500"
                    )}
                  >
                    {d.label_vi}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Style example chips */}
          <div className="space-y-1.5">
            <p className="text-xs text-neutral-400">Gợi ý phong cách — nhấn để dùng:</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_HINTS.map((hint) => (
                <button
                  key={hint}
                  type="button"
                  onClick={() => setUserDescription(hint)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs transition-colors text-left",
                    "border-neutral-200 bg-neutral-50 text-neutral-600",
                    "hover:border-neutral-400 hover:bg-neutral-100",
                    "dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
                    "dark:hover:border-neutral-500 dark:hover:bg-neutral-700",
                    userDescription === hint && "border-neutral-800 bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                  )}
                >
                  {hint.length > 55 ? hint.slice(0, 55) + "…" : hint}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Options */}
      <Card>
        <CardHeader>
          <CardTitle>Generation Options</CardTitle>
          <CardDescription>Customize how your content will be created</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Economy mode */}
          <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50/50 dark:border-emerald-900 dark:bg-emerald-950/30 px-4 py-3">
            <div className="space-y-0.5">
              <Label className="text-emerald-900 dark:text-emerald-100">Chế độ tiết kiệm</Label>
              <p className="text-xs text-emerald-800/80 dark:text-emerald-300/80">
                Video từ ảnh upload, 1 video 5s, không tạo ảnh AI, caption 1 nền tảng
              </p>
            </div>
            <Button
              variant={economyMode ? "default" : "outline"}
              size="sm"
              onClick={() => applyEconomyMode(!economyMode)}
            >
              {economyMode ? "Bật" : "Tắt"}
            </Button>
          </div>

          {/* Number of Images */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <ImageIcon className="h-5 w-5 text-neutral-500" />
                <Label>Number of Images</Label>
              </div>
              <p className="text-xs text-neutral-500">
                Chọn &quot;Không&quot; để chỉ dùng ảnh upload (phù hợp khi chỉ tạo video)
              </p>
            </div>
            <div className="flex items-center gap-2">
              {(
                [
                  { value: 0, label: "Không" },
                  { value: 2, label: "2" },
                  { value: 4, label: "4" },
                  { value: 6, label: "6" },
                ] as const
              ).map(({ value, label }) => (
                <Button
                  key={value}
                  variant={numImages === value ? "default" : "outline"}
                  size="sm"
                  disabled={economyMode && value > 0}
                  onClick={() => setNumImages(value)}
                >
                  {label}
                </Button>
              ))}
            </div>
          </div>

          {/* Video Toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Video className="h-5 w-5 text-neutral-500" />
              <Label>Generate Cinematic Video</Label>
            </div>
            <Button
              variant={generateVideo ? "default" : "outline"}
              size="sm"
              onClick={() => setGenerateVideo(!generateVideo)}
            >
              {generateVideo ? "Yes" : "No"}
            </Button>
          </div>

          {generateVideo && (
            <>
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Số video tạo</Label>
                <p className="text-xs text-neutral-500">
                  Mỗi variation = 1 lần gọi fal. Chọn 1 để giảm ~50% phí video.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {([1, 2] as const).map((n) => (
                  <Button
                    key={n}
                    variant={maxVideoVariations === n ? "default" : "outline"}
                    size="sm"
                    disabled={economyMode && n > 1}
                    onClick={() => setMaxVideoVariations(n)}
                  >
                    {n}
                  </Button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Video Duration</Label>
                <p className="text-xs text-neutral-500">
                  3-15s (O3) hoặc 5/10s (Kling 2.5 Turbo). Mặc định model rẻ ~$0.21/video 5s
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={3}
                  max={15}
                  value={videoDuration}
                  disabled={economyMode}
                  onChange={(e) => handleVideoDurationChange(e.target.value)}
                  className="w-20 text-right"
                />
                <span className="text-sm text-neutral-500">seconds</span>
              </div>
            </div>
            <p className="text-xs text-neutral-500 rounded-md bg-neutral-50 dark:bg-neutral-900 px-3 py-2 border border-neutral-200 dark:border-neutral-800">
              Ước tính job này: ~${estimatedCostUsd.toFixed(2)} USD
              {economyMode && " (tiết kiệm)"} — video fal Kling Turbo 5s ≈ $0.21/clip.
              Trước đây 2 ảnh + 2 video O3 ≈ $1.0+/job.
            </p>
            </>
          )}

          {/* Platforms */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Hash className="h-5 w-5 text-neutral-500" />
              <Label>Platforms</Label>
            </div>
            <div className="flex gap-2">
              {["instagram", "tiktok", "youtube"].map((platform) => (
                <Button
                  key={platform}
                  variant={platforms.includes(platform) ? "default" : "outline"}
                  size="sm"
                  disabled={economyMode && platform !== "instagram"}
                  onClick={() => togglePlatform(platform)}
                  className="capitalize"
                >
                  {platform}
                </Button>
              ))}
            </div>
          </div>

          {/* Auto Post */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Auto Post to Social Media</Label>
              <p className="text-xs text-neutral-500">Schedule posts after generation</p>
            </div>
            <Button
              variant={autoPost ? "default" : "outline"}
              size="sm"
              onClick={() => setAutoPost(!autoPost)}
            >
              {autoPost ? "Enabled" : "Disabled"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Submit */}
      <div className="flex justify-end">
        <Button
          size="lg"
          onClick={handleSubmit}
          disabled={!file || isUploading}
          className="gap-2"
        >
          {isUploading ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              Uploading...
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              Start Generation
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
