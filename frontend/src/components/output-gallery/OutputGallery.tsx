"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Download, Video, FileText, Copy, Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

interface OutputData {
  job_id: string;
  style_analysis: Record<string, unknown>;
  prompts: Record<string, string>;
  images: string[];
  video_url: string | null;
  captions: Record<string, { title: string; caption: string; hashtags: string[] }>;
  cost_usd: number;
  created_at: string;
}

interface OutputGalleryProps {
  jobId: string;
}

export function OutputGallery({ jobId }: OutputGalleryProps) {
  const [output, setOutput] = useState<OutputData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);

  useEffect(() => {
    loadOutput();
  }, [jobId]);

  async function loadOutput() {
    try {
      const data = await api.getOutput(jobId);
      setOutput(data as unknown as OutputData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load output");
    } finally {
      setLoading(false);
    }
  }

  const copyToClipboard = async (text: string, key: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedIndex(key);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-neutral-300 border-t-neutral-900" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-red-500">{error}</p>
          <Button variant="outline" className="mt-4" onClick={loadOutput}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!output) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-neutral-500">No output available yet.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Generated Content</h1>
        <p className="text-neutral-500 mt-2">
          Created on {formatDate(output.created_at)} &middot; ${output.cost_usd.toFixed(3)} total cost
        </p>
      </div>

      <Tabs defaultValue="images" className="space-y-6">
        <TabsList>
          <TabsTrigger value="images">Images ({output.images.length})</TabsTrigger>
          {output.video_url && <TabsTrigger value="video">Video</TabsTrigger>}
          <TabsTrigger value="captions">Captions</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
        </TabsList>

        {/* Images Tab */}
        <TabsContent value="images">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {output.images.map((url, idx) => (
              <Card key={idx} className="overflow-hidden group">
                <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-900">
                  <Image
                    src={url}
                    alt={`Generated architecture ${idx + 1}`}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                </div>
                <CardContent className="p-3 flex justify-between items-center">
                  <span className="text-sm text-neutral-500">Image {idx + 1}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open(url, "_blank")}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Video Tab */}
        {output.video_url && (
          <TabsContent value="video">
            <Card className="overflow-hidden">
              <div className="relative aspect-video bg-neutral-100 dark:bg-neutral-900">
                <video
                  src={output.video_url}
                  controls
                  className="w-full h-full"
                  poster={output.images[0]}
                >
                  Your browser does not support video playback.
                </video>
              </div>
              <CardContent className="p-4 flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <Video className="h-5 w-5 text-neutral-500" />
                  <span className="text-sm">Cinematic Architecture Video</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => output.video_url && window.open(output.video_url, "_blank")}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Captions Tab */}
        <TabsContent value="captions">
          <div className="space-y-6">
            {Object.entries(output.captions).map(([platform, data]) => (
              <Card key={platform}>
                <CardHeader>
                  <CardTitle className="capitalize">{platform}</CardTitle>
                  <CardDescription>{data.title}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="relative">
                    <pre className="whitespace-pre-wrap text-sm p-4 rounded-lg bg-neutral-50 dark:bg-neutral-900 border dark:border-neutral-800">
                      {data.caption}
                    </pre>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute top-2 right-2"
                      onClick={() =>
                        copyToClipboard(data.caption, `caption-${platform}`)
                      }
                    >
                      {copiedIndex === `caption-${platform}` ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {data.hashtags.map((tag, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      copyToClipboard(
                        `${data.caption}\n\n${data.hashtags.join(" ")}`,
                        `full-${platform}`
                      )
                    }
                  >
                    {copiedIndex === `full-${platform}` ? (
                      <>
                        <Check className="h-4 w-4 mr-2 text-green-500" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4 mr-2" />
                        Copy All
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Details Tab */}
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
