"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import {
  Check, Copy, Download, Edit2, RefreshCw,
  Scissors, Video, X, Wand2, AlertCircle, Camera, Clapperboard,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
import { useToast } from "@/components/ui/use-toast";

const BACKEND_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/api\/v1$/, "");

function toDisplayUrl(url: string): string {
  if (!url) return url;
  if (url.startsWith("http")) return url;
  return `${BACKEND_BASE}${url}`;
}

/** Posted caption: fewer than 20 words (max 19). */
const MAX_CAPTION_WORDS = 19;
const MIN_HASHTAGS = 10;
const MAX_HASHTAGS = 15;

function countWords(text: string): number {
  const t = text.trim();
  if (!t) return 0;
  return t.split(/\s+/).length;
}

function limitWords(text: string, maxWords: number = MAX_CAPTION_WORDS): string {
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length <= maxWords) return text.trim();
  return words.slice(0, maxWords).join(" ");
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface CaptionLang {
  title: string;
  caption: string;
  hashtags: string[];
  call_to_action: string;
}

interface PlatformCaption {
  en: CaptionLang;
  vi: CaptionLang;
}

interface OutputData {
  job_id: string;
  style_analysis: Record<string, unknown>;
  prompts: Record<string, unknown>[];
  images: string[];
  videos: string[];
  video_url: string | null;
  video_requested: boolean;
  video_duration: number;
  video_error: string | null;
  captions: Record<string, PlatformCaption>;
  cost_usd: number;
  created_at: string;
}

// ─── Caption edit state ───────────────────────────────────────────────────────

interface CaptionEditState {
  platform: string;
  title: string;
  caption: string;
  hashtags: string;   // comma-separated for easy editing
  call_to_action: string;
  instruction: string;
  saving: boolean;
  regenerating: boolean;
  error: string | null;
}

// ─── Image regenerate state ───────────────────────────────────────────────────

interface ImageRegenState {
  index: number;
  prompt: string;
  negativePrompt: string;
  loading: boolean;
  error: string | null;
}

// ─── Video trim state ─────────────────────────────────────────────────────────

interface TrimState {
  startSec: number;
  endSec: number;
  loading: boolean;
  error: string | null;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function OutputGallery({ jobId }: { jobId: string }) {
  const [output, setOutput] = useState<OutputData | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Edit states
  const [captionEdit, setCaptionEdit] = useState<CaptionEditState | null>(null);
  const [imageRegen, setImageRegen] = useState<ImageRegenState | null>(null);
  const [trim, setTrim] = useState<TrimState | null>(null);
  const [publishing, setPublishing] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => { loadOutput(); }, [jobId]);

  async function loadOutput() {
    try {
      setFetchError(null);
      const data = await api.getOutput(jobId);
      setOutput(data as unknown as OutputData);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : "Failed to load output");
    } finally {
      setLoading(false);
    }
  }

  const copy = async (text: string, key: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // ── Caption edit helpers ────────────────────────────────────────────────────

  function openCaptionEdit(platform: string) {
    const data = output?.captions?.[platform]?.en;
    setCaptionEdit({
      platform,
      title: data?.title ?? "",
      caption: data?.caption ?? "",
      hashtags: (data?.hashtags ?? []).join(", "),
      call_to_action: data?.call_to_action ?? "",
      instruction: "",
      saving: false,
      regenerating: false,
      error: null,
    });
  }

  async function saveCaption() {
    if (!captionEdit || !output) return;
    const caption = limitWords(captionEdit.caption);
    const callToAction = limitWords(captionEdit.call_to_action);
    setCaptionEdit((s) => s && { ...s, saving: true, error: null });
    try {
      await api.updateCaption(jobId, captionEdit.platform, {
        title: captionEdit.title,
        caption,
        hashtags: captionEdit.hashtags.split(",").map((h) => h.trim()).filter(Boolean),
        call_to_action: callToAction,
      });
      // Update local state
      setOutput((prev) => {
        if (!prev) return prev;
        const newCaptions = { ...prev.captions };
        newCaptions[captionEdit.platform] = {
          ...newCaptions[captionEdit.platform],
          en: {
            title: captionEdit.title,
            caption,
            hashtags: captionEdit.hashtags.split(",").map((h) => h.trim()).filter(Boolean),
            call_to_action: callToAction,
          },
        };
        return { ...prev, captions: newCaptions };
      });
      setCaptionEdit(null);
    } catch (e) {
      setCaptionEdit((s) => s && { ...s, saving: false, error: (e as Error).message });
    }
  }

  async function publishToPlatform(platform: "instagram" | "youtube") {
    setPublishing(platform);
    try {
      const res = await api.publishToSocial(jobId, platform);
      toast({
        title: platform === "instagram" ? "Đã đăng Instagram" : "Đã đăng YouTube",
        description: res.post_url
          ? `Link: ${res.post_url}`
          : "Đăng bài thành công.",
        variant: "success",
      });
    } catch (e) {
      toast({
        title: "Đăng thất bại",
        description: e instanceof Error ? e.message : "Kiểm tra token Instagram/YouTube trong .env",
        variant: "destructive",
      });
    } finally {
      setPublishing(null);
    }
  }

  async function regenerateCaptionWithInstruction() {
    if (!captionEdit || !output) return;
    setCaptionEdit((s) => s && { ...s, regenerating: true, error: null });
    try {
      const result = await api.regenerateCaption(jobId, captionEdit.platform, captionEdit.instruction);
      const cap = result.caption as PlatformCaption;
      const en = cap?.en ?? {};
      setOutput((prev) => {
        if (!prev) return prev;
        const newCaptions = { ...prev.captions };
        newCaptions[captionEdit.platform] = cap;
        return { ...prev, captions: newCaptions };
      });
      setCaptionEdit((s) =>
        s && {
          ...s,
          title: en.title ?? "",
          caption: en.caption ?? "",
          hashtags: (en.hashtags ?? []).join(", "),
          call_to_action: en.call_to_action ?? "",
          regenerating: false,
        }
      );
    } catch (e) {
      setCaptionEdit((s) => s && { ...s, regenerating: false, error: (e as Error).message });
    }
  }

  // ── Image regenerate helpers ────────────────────────────────────────────────

  function openImageRegen(index: number) {
    const promptObj = Array.isArray(output?.prompts) ? output.prompts[0] : output?.prompts;
    const prompt = (promptObj as Record<string, string>)?.image_prompt ?? "";
    const negative = (promptObj as Record<string, string>)?.negative_prompt ?? "";
    setImageRegen({ index, prompt, negativePrompt: negative, loading: false, error: null });
  }

  async function doRegenerateImage() {
    if (!imageRegen || !output) return;
    setImageRegen((s) => s && { ...s, loading: true, error: null });
    try {
      const res = await api.regenerateImage(jobId, imageRegen.prompt, imageRegen.index, imageRegen.negativePrompt);
      setOutput((prev) => {
        if (!prev) return prev;
        const imgs = [...prev.images];
        imgs[imageRegen.index] = res.image_url;
        return { ...prev, images: imgs };
      });
      setImageRegen(null);
    } catch (e) {
      setImageRegen((s) => s && { ...s, loading: false, error: (e as Error).message });
    }
  }

  // ── Video trim helpers ──────────────────────────────────────────────────────

  async function doTrimVideo() {
    if (!trim || !output) return;
    setTrim((s) => s && { ...s, loading: true, error: null });
    try {
      const res = await api.trimVideo(jobId, trim.startSec, trim.endSec);
      setOutput((prev) => prev && { ...prev, video_url: res.video_url });
      setTrim(null);
    } catch (e) {
      setTrim((s) => s && { ...s, loading: false, error: (e as Error).message });
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-neutral-300 border-t-neutral-900" />
        </CardContent>
      </Card>
    );
  }

  if (fetchError) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-red-500">{fetchError}</p>
          <Button variant="outline" className="mt-4" onClick={loadOutput}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  if (!output) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Generated Content</h1>
        <p className="text-neutral-500 mt-2">
          Created on {formatDate(output.created_at)} · ${output.cost_usd.toFixed(3)} total cost
        </p>
      </div>

      {output.video_requested && !output.video_url && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30">
          <CardContent className="flex gap-3 p-4 text-sm text-amber-800 dark:text-amber-300">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="space-y-1">
              <p className="font-medium">Video was requested, but no video URL was returned.</p>
              <p className="whitespace-pre-wrap text-xs">
                {output.video_error || "The video provider did not return a usable video. Check backend logs for the provider error."}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="images" className="space-y-6">
        <TabsList>
          <TabsTrigger value="images">Images ({output.images.length})</TabsTrigger>
          {output.video_url && <TabsTrigger value="video">Video</TabsTrigger>}
          <TabsTrigger value="captions">Captions</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
        </TabsList>

        {/* ── Images Tab ─────────────────────────────────────────────────── */}
        <TabsContent value="images">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {output.images.map((url, idx) => {
              const displayUrl = toDisplayUrl(url);
              return (
              <div key={idx}>
                <Card className="overflow-hidden group">
                  <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-900">
                    <Image
                      src={displayUrl}
                      alt={`Generated architecture ${idx + 1}`}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                  </div>
                  <CardContent className="p-3 flex justify-between items-center">
                    <span className="text-sm text-neutral-500">Image {idx + 1}</span>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => window.open(displayUrl, "_blank")} title="Download">
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          imageRegen?.index === idx ? setImageRegen(null) : openImageRegen(idx)
                        }
                        title="Regenerate this image"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Inline regenerate panel */}
                {imageRegen?.index === idx && (
                  <Card className="mt-2 border-blue-200 dark:border-blue-800">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Wand2 className="h-4 w-4 text-blue-500" />
                        Regenerate Image {idx + 1}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div>
                        <label className="text-xs text-neutral-500 mb-1 block">Image Prompt</label>
                        <textarea
                          rows={4}
                          value={imageRegen.prompt}
                          onChange={(e) => setImageRegen((s) => s && { ...s, prompt: e.target.value })}
                          className="w-full resize-none rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-blue-400"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-neutral-500 mb-1 block">Negative Prompt</label>
                        <textarea
                          rows={2}
                          value={imageRegen.negativePrompt}
                          onChange={(e) => setImageRegen((s) => s && { ...s, negativePrompt: e.target.value })}
                          className="w-full resize-none rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-blue-400"
                        />
                      </div>
                      {imageRegen.error && (
                        <p className="text-xs text-red-500 flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" /> {imageRegen.error}
                        </p>
                      )}
                      <div className="flex gap-2 justify-end">
                        <Button variant="outline" size="sm" onClick={() => setImageRegen(null)}>
                          Cancel
                        </Button>
                        <Button size="sm" onClick={doRegenerateImage} disabled={imageRegen.loading}>
                          {imageRegen.loading ? (
                            <><div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent mr-1" /> Generating...</>
                          ) : (
                            <><RefreshCw className="h-3 w-3 mr-1" /> Regenerate</>
                          )}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            );
          })}
          </div>
        </TabsContent>

        {/* ── Video Tab ──────────────────────────────────────────────────── */}
        {output.video_url && (
          <TabsContent value="video">
            <div className="space-y-4">
              <Card className="overflow-hidden">
                <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-900">
                  <video
                    key={output.video_url}
                    src={toDisplayUrl(output.video_url!)}
                    controls
                    className="w-full h-full"
                    poster={output.images[0] ? toDisplayUrl(output.images[0]) : undefined}
                  />
                </div>
                <CardContent className="p-4 flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <Video className="h-5 w-5 text-neutral-500" />
                    <span className="text-sm">Cinematic Architecture Video</span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => output.video_url && window.open(toDisplayUrl(output.video_url), "_blank")}
                    >
                      <Download className="h-4 w-4 mr-2" /> Download
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setTrim(trim ? null : { startSec: 0, endSec: 10, loading: false, error: null })}
                    >
                      <Scissors className="h-4 w-4 mr-2" /> Trim
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Trim panel */}
              {trim && (
                <Card className="border-amber-200 dark:border-amber-800">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Scissors className="h-4 w-4 text-amber-500" />
                      Trim Video
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Only works for locally generated videos. External video URLs (Runway/Veo CDN) are not supported.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex gap-6">
                      <div className="flex-1">
                        <label className="text-xs text-neutral-500 mb-1 block">Start (seconds)</label>
                        <input
                          type="number"
                          min={0}
                          step={0.5}
                          value={trim.startSec}
                          onChange={(e) => setTrim((s) => s && { ...s, startSec: Number(e.target.value) })}
                          className="w-full rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-amber-400"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="text-xs text-neutral-500 mb-1 block">End (seconds)</label>
                        <input
                          type="number"
                          min={0.5}
                          step={0.5}
                          value={trim.endSec}
                          onChange={(e) => setTrim((s) => s && { ...s, endSec: Number(e.target.value) })}
                          className="w-full rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-amber-400"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-neutral-400">
                      New duration: {Math.max(0, trim.endSec - trim.startSec).toFixed(1)}s
                    </p>
                    {trim.error && (
                      <p className="text-xs text-red-500 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" /> {trim.error}
                      </p>
                    )}
                    <div className="flex gap-2 justify-end">
                      <Button variant="outline" size="sm" onClick={() => setTrim(null)}>Cancel</Button>
                      <Button
                        size="sm"
                        onClick={doTrimVideo}
                        disabled={trim.loading || trim.endSec <= trim.startSec}
                      >
                        {trim.loading ? (
                          <><div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent mr-1" /> Trimming...</>
                        ) : (
                          <><Scissors className="h-3 w-3 mr-1" /> Apply Trim</>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
        )}

        {/* ── Captions Tab ───────────────────────────────────────────────── */}
        <TabsContent value="captions">
          <div className="space-y-6">
            {Object.entries(output.captions).map(([platform, data]) => {
              const en = data?.en ?? (data as unknown as CaptionLang);
              const vi = data?.vi;
              const isEditing = captionEdit?.platform === platform;

              return (
                <Card key={platform} className={cn(isEditing && "border-blue-300 dark:border-blue-700")}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="capitalize">{platform}</CardTitle>
                        <CardDescription>{en.title}</CardDescription>
                      </div>
                      {!isEditing && (
                        <Button variant="outline" size="sm" onClick={() => openCaptionEdit(platform)}>
                          <Edit2 className="h-3.5 w-3.5 mr-1" /> Edit
                        </Button>
                      )}
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    {isEditing && captionEdit ? (
                      /* ── Edit mode ── */
                      <div className="space-y-4">
                        <div>
                          <label className="text-xs text-neutral-500 mb-1 block">Title</label>
                          <input
                            type="text"
                            value={captionEdit.title}
                            onChange={(e) => setCaptionEdit((s) => s && { ...s, title: e.target.value })}
                            className="w-full rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-blue-400"
                          />
                        </div>

                        <div>
                          <label className="text-xs text-neutral-500 mb-1 flex items-center justify-between">
                            <span>Caption (English — will be posted)</span>
                            <span
                              className={cn(
                                countWords(captionEdit.caption) >= MAX_CAPTION_WORDS
                                  ? "text-amber-600 dark:text-amber-400"
                                  : "text-neutral-400"
                              )}
                            >
                              {countWords(captionEdit.caption)}/{MAX_CAPTION_WORDS} từ
                            </span>
                          </label>
                          <textarea
                            rows={4}
                            value={captionEdit.caption}
                            onChange={(e) =>
                              setCaptionEdit(
                                (s) => s && { ...s, caption: limitWords(e.target.value) }
                              )
                            }
                            className="w-full resize-none rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-blue-400"
                          />
                          <p className="text-xs text-neutral-400 mt-1">
                            Tối đa dưới 20 từ khi đăng (hashtag tách riêng).
                          </p>
                        </div>

                        <div>
                          <label className="text-xs text-neutral-500 mb-1 block">
                            Hashtags (phân tách bằng dấu phẩy, gợi ý {MIN_HASHTAGS}–{MAX_HASHTAGS})
                          </label>
                          <input
                            type="text"
                            value={captionEdit.hashtags}
                            onChange={(e) => setCaptionEdit((s) => s && { ...s, hashtags: e.target.value })}
                            className="w-full rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-blue-400"
                            placeholder="#KienTruc, #NoiThat, #MinimalistDesign, #ArchitecturePhotography, ..."
                          />
                        </div>

                        <div>
                          <label className="text-xs text-neutral-500 mb-1 block">Call to Action</label>
                          <input
                            type="text"
                            value={captionEdit.call_to_action}
                            onChange={(e) =>
                              setCaptionEdit(
                                (s) => s && { ...s, call_to_action: limitWords(e.target.value) }
                              )
                            }
                            className="w-full rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-blue-400"
                            placeholder="Follow us for more..."
                          />
                        </div>

                        {/* Regenerate with instruction */}
                        <div className="rounded-md border border-dashed border-neutral-300 dark:border-neutral-700 p-3 space-y-2">
                          <label className="text-xs font-medium text-neutral-500 block">
                            Or — Regenerate with AI instruction
                          </label>
                          <input
                            type="text"
                            value={captionEdit.instruction}
                            onChange={(e) => setCaptionEdit((s) => s && { ...s, instruction: e.target.value })}
                            placeholder='e.g. "More formal tone", "Shorter, punchy hook", "Add urgency"'
                            className="w-full rounded-md border px-3 py-2 text-sm bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 focus:outline-none focus:border-blue-400"
                          />
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={regenerateCaptionWithInstruction}
                            disabled={captionEdit.regenerating}
                          >
                            {captionEdit.regenerating ? (
                              <><div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent mr-1" /> Regenerating...</>
                            ) : (
                              <><Wand2 className="h-3 w-3 mr-1" /> Regenerate Caption</>
                            )}
                          </Button>
                        </div>

                        {captionEdit.error && (
                          <p className="text-xs text-red-500 flex items-center gap-1">
                            <AlertCircle className="h-3 w-3" /> {captionEdit.error}
                          </p>
                        )}

                        <div className="flex gap-2 justify-end pt-2 border-t dark:border-neutral-800">
                          <Button variant="outline" size="sm" onClick={() => setCaptionEdit(null)}>
                            <X className="h-3.5 w-3.5 mr-1" /> Cancel
                          </Button>
                          <Button size="sm" onClick={saveCaption} disabled={captionEdit.saving}>
                            {captionEdit.saving ? (
                              <><div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent mr-1" /> Saving...</>
                            ) : (
                              <><Check className="h-3.5 w-3.5 mr-1" /> Save Changes</>
                            )}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      /* ── View mode ── */
                      <>
                        {/* EN caption */}
                        <div>
                          <p className="text-xs text-neutral-400 mb-1">English (will be posted)</p>
                          <div className="relative">
                            <pre className="whitespace-pre-wrap text-sm p-4 rounded-lg bg-neutral-50 dark:bg-neutral-900 border dark:border-neutral-800">
                              {en.caption}
                            </pre>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="absolute top-2 right-2"
                              onClick={() => copy(en.caption, `en-${platform}`)}
                            >
                              {copiedKey === `en-${platform}` ? (
                                <Check className="h-4 w-4 text-green-500" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </div>

                        {/* VI caption */}
                        {vi && (
                          <div>
                            <p className="text-xs text-neutral-400 mb-1">Tiếng Việt (dịch tham khảo)</p>
                            <pre className="whitespace-pre-wrap text-sm p-4 rounded-lg bg-neutral-50/50 dark:bg-neutral-900/50 border border-dashed dark:border-neutral-800 text-neutral-600 dark:text-neutral-400">
                              {vi.caption}
                            </pre>
                          </div>
                        )}

                        {/* Hashtags */}
                        <p className="text-xs text-neutral-400">
                          {(en.hashtags ?? []).length} hashtag
                          {(en.hashtags ?? []).length < MIN_HASHTAGS
                            ? ` — gợi ý ${MIN_HASHTAGS}–${MAX_HASHTAGS} (bấm Edit hoặc Regenerate)`
                            : ""}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {(en.hashtags ?? []).map((tag, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 cursor-pointer hover:bg-blue-100"
                              onClick={() => copy(tag, `tag-${platform}-${i}`)}
                            >
                              {copiedKey === `tag-${platform}-${i}` ? <Check className="h-3 w-3 mr-1 text-green-500" /> : null}
                              {tag}
                            </span>
                          ))}
                        </div>

                        <div className="flex flex-wrap gap-2 items-center">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              copy(`${en.caption}\n\n${(en.hashtags ?? []).join(" ")}`, `full-${platform}`)
                            }
                          >
                            {copiedKey === `full-${platform}` ? (
                              <><Check className="h-4 w-4 mr-2 text-green-500" /> Đã copy!</>
                            ) : (
                              <><Copy className="h-4 w-4 mr-2" /> Copy All</>
                            )}
                          </Button>

                          {platform === "instagram" && (
                            <Button
                              size="sm"
                              className="bg-gradient-to-r from-purple-600 to-pink-600 text-white hover:from-purple-700 hover:to-pink-700"
                              disabled={publishing !== null}
                              onClick={() => publishToPlatform("instagram")}
                            >
                              {publishing === "instagram" ? (
                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2" />
                              ) : (
                                <Camera className="h-4 w-4 mr-2" />
                              )}
                              Đăng Instagram
                            </Button>
                          )}

                          {platform === "youtube" && (
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={publishing !== null || !output.video_url}
                              title={
                                output.video_url
                                  ? "Upload video lên YouTube"
                                  : "Cần có video trong tab Video"
                              }
                              onClick={() => publishToPlatform("youtube")}
                            >
                              {publishing === "youtube" ? (
                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2" />
                              ) : (
                                <Clapperboard className="h-4 w-4 mr-2" />
                              )}
                              Đăng YouTube
                            </Button>
                          )}
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* ── Details Tab ────────────────────────────────────────────────── */}
        <TabsContent value="details">
          <Card>
            <CardHeader>
              <CardTitle>Generation Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-neutral-500 mb-2">Style Analysis</h3>
                <pre className="text-sm p-4 rounded-lg bg-neutral-50 dark:bg-neutral-900 border dark:border-neutral-800 overflow-auto">
                  {JSON.stringify(output.style_analysis, null, 2)}
                </pre>
              </div>
              <div>
                <h3 className="text-sm font-medium text-neutral-500 mb-2">Prompts Used</h3>
                <pre className="text-sm p-4 rounded-lg bg-neutral-50 dark:bg-neutral-900 border dark:border-neutral-800 overflow-auto">
                  {JSON.stringify(output.prompts, null, 2)}
                </pre>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
