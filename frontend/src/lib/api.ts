const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    // Don't set Content-Type for FormData (let browser set it)
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Jobs
  async uploadImage(formData: FormData) {
    return this.request<{
      job_id: string;
      status: string;
      estimated_time_seconds: number;
    }>("/jobs/upload", {
      method: "POST",
      body: formData,
    });
  }

  async getDefaultVideoDirections() {
    return this.request<{
      message: string;
      directions: Array<{
        key: string;
        label_vi: string;
        prompt_vi: string;
      }>;
      preview: {
        variation_1: { key: string; label_vi: string; prompt_vi: string };
        variation_2: { key: string; label_vi: string; prompt_vi: string };
      };
    }>("/jobs/default-directions");
  }

  async getJobStatus(jobId: string) {
    return this.request<{
      job_id: string;
      status: string;
      progress: number;
      current_step: string | null;
      steps_completed: string[];
      estimated_remaining_seconds: number | null;
      error_message: string | null;
    }>(`/jobs/${jobId}`);
  }

  async cancelJob(jobId: string) {
    return this.request<{ job_id: string; cancelled: boolean }>(
      `/jobs/${jobId}/cancel`,
      { method: "POST" }
    );
  }

  async listJobs(skip = 0, limit = 20) {
    return this.request<
      Array<{
        job_id: string;
        status: string;
        progress: number;
        created_at: string;
      }>
    >(`/jobs/?skip=${skip}&limit=${limit}`);
  }

  // Outputs
  async getOutput(jobId: string) {
    return this.request<{
      job_id: string;
      style_analysis: Record<string, unknown>;
      prompts: Record<string, unknown>[];
      images: string[];
      videos: string[];
      video_url: string | null;
      video_requested: boolean;
      video_duration: number;
      video_error: string | null;
      captions: Record<string, {
        en: { title: string; caption: string; hashtags: string[]; call_to_action: string };
        vi: { title: string; caption: string; hashtags: string[]; call_to_action: string };
      }>;
      cost_usd: number;
      created_at: string;
    }>(`/outputs/${jobId}`);
  }

  async updateCaption(
    jobId: string,
    platform: string,
    fields: { title?: string; caption?: string; hashtags?: string[]; call_to_action?: string }
  ) {
    return this.request<{ success: boolean; platform: string; en: unknown }>(
      `/outputs/${jobId}/captions`,
      { method: "PATCH", body: JSON.stringify({ platform, ...fields }) }
    );
  }

  async regenerateImage(jobId: string, imagePrompt: string, imageIndex: number, negativePrompt = "") {
    return this.request<{ success: boolean; image_url: string; image_index: number }>(
      `/outputs/${jobId}/regenerate-image`,
      {
        method: "POST",
        body: JSON.stringify({ image_prompt: imagePrompt, negative_prompt: negativePrompt, image_index: imageIndex }),
      }
    );
  }

  async trimVideo(jobId: string, startSec: number, endSec: number) {
    return this.request<{ success: boolean; video_url: string; duration_sec: number }>(
      `/outputs/${jobId}/trim-video`,
      { method: "POST", body: JSON.stringify({ start_sec: startSec, end_sec: endSec }) }
    );
  }

  async regenerateCaption(jobId: string, platform: string, extraInstruction = "") {
    return this.request<{ success: boolean; platform: string; caption: unknown }>(
      `/outputs/${jobId}/regenerate-caption`,
      { method: "POST", body: JSON.stringify({ platform, extra_instruction: extraInstruction }) }
    );
  }

  async publishToSocial(jobId: string, platform: "instagram" | "youtube") {
    return this.request<{
      success: boolean;
      platform: string;
      status: string;
      post_url: string | null;
      result: Record<string, unknown>;
    }>(`/outputs/${jobId}/publish`, {
      method: "POST",
      body: JSON.stringify({ platform }),
    });
  }
}

export const api = new ApiClient();
