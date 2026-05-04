"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Upload, ImageIcon, Video, Hash, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/use-toast";
import { useJobStore } from "@/store/job-store";
import { cn } from "@/lib/utils";

export function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [numImages, setNumImages] = useState(4);
  const [generateVideo, setGenerateVideo] = useState(true);
  const [platforms, setPlatforms] = useState<string[]>(["instagram"]);
  const [autoPost, setAutoPost] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const router = useRouter();
  const { toast } = useToast();
  const { uploadImage, isUploading } = useJobStore();

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
    setPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    );
  };

  const handleSubmit = async () => {
    if (!file) {
      toast({ title: "Error", description: "Please select an image first", variant: "destructive" });
      return;
    }

    const formData = new FormData();
    formData.append("image", file);
    formData.append("num_images", numImages.toString());
    formData.append("generate_video", generateVideo.toString());
    formData.append("platforms", platforms.join(","));
    formData.append("auto_post", autoPost.toString());

    try {
      const jobId = await uploadImage(formData);
      toast({
        title: "Job Created",
        description: "Your architecture video generation has started!",
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

      {/* Options */}
      <Card>
        <CardHeader>
          <CardTitle>Generation Options</CardTitle>
          <CardDescription>Customize how your content will be created</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Number of Images */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5 text-neutral-500" />
              <Label>Number of Images</Label>
            </div>
            <div className="flex items-center gap-2">
              {[2, 4, 6].map((n) => (
                <Button
                  key={n}
                  variant={numImages === n ? "default" : "outline"}
                  size="sm"
                  onClick={() => setNumImages(n)}
                >
                  {n}
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
