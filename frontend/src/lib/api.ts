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
      prompts: Record<string, string>;
      images: string[];
      video_url: string | null;
      captions: Record<string, unknown>;
      cost_usd: number;
      created_at: string;
    }>(`/outputs/${jobId}`);
  }
}

export const api = new ApiClient();
