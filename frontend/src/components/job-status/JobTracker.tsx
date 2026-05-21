"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle, Clock, StopCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";

interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  current_step: string | null;
  steps_completed: string[];
  estimated_remaining_seconds: number | null;
  error_message: string | null;
}

const STEP_LABELS: Record<string, string> = {
  vision_analysis: "Analyzing architectural style",
  prompt_writing: "Writing optimized prompts",
  image_generation: "Generating architecture images",
  video_generation: "Creating cinematic video",
  caption_writing: "Writing captions & hashtags",
};

const TOTAL_STEPS = 5;

interface JobTrackerProps {
  jobId: string;
  onComplete?: () => void;
}

export function JobTracker({ jobId, onComplete }: JobTrackerProps) {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const { toast } = useToast();

  const handleStop = async () => {
    if (cancelling) return;
    setCancelling(true);
    try {
      await api.cancelJob(jobId);
      toast({ title: "Đang dừng...", description: "Job sẽ dừng sau bước hiện tại." });
    } catch (e) {
      toast({
        title: "Không thể dừng",
        description: e instanceof Error ? e.message : "Lỗi không xác định",
        variant: "destructive",
      });
      setCancelling(false);
    }
  };

  useEffect(() => {
    // Connect to WebSocket
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/ws";
    const ws = new WebSocket(`${wsUrl}/job/${jobId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // WS sends partial updates — merge into existing state to avoid losing fields
      setJobStatus((prev) => ({
        ...(prev ?? {}),
        ...data,
        steps_completed: Array.isArray(data.steps_completed)
          ? data.steps_completed
          : prev?.steps_completed ?? [],
      } as JobStatus));
      if (data.status === "completed" && onComplete) {
        onComplete();
      }
    };

    ws.onerror = () => {
      // Fallback to polling
      setError("WebSocket connection failed, using polling");
    };

    // Polling fallback
    const pollInterval = setInterval(async () => {
      try {
        const status = await api.getJobStatus(jobId);
        setJobStatus(status);
        setError(null);
        if (status.status === "completed" || status.status === "failed" || status.status === "cancelled") {
          clearInterval(pollInterval);
          setCancelling(false);
          if (status.status === "completed" && onComplete) {
            onComplete();
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to fetch status");
      }
    }, 2000);

    return () => {
      ws.close();
      clearInterval(pollInterval);
    };
  }, [jobId, onComplete]);

  if (!jobStatus) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-neutral-400" />
        </CardContent>
      </Card>
    );
  }

  const stepsCompleted = Array.isArray(jobStatus.steps_completed)
    ? jobStatus.steps_completed.length
    : 0;

  const isActive = jobStatus.status === "queued" || jobStatus.status === "processing";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {jobStatus.status === "completed" && (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          )}
          {jobStatus.status === "failed" && (
            <XCircle className="h-5 w-5 text-red-500" />
          )}
          {jobStatus.status === "cancelled" && (
            <StopCircle className="h-5 w-5 text-orange-500" />
          )}
          {jobStatus.status === "processing" && !cancelling && (
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
          )}
          {jobStatus.status === "processing" && cancelling && (
            <Loader2 className="h-5 w-5 animate-spin text-orange-500" />
          )}
          {jobStatus.status === "queued" && (
            <Clock className="h-5 w-5 text-yellow-500" />
          )}
          <span className="capitalize">
            {cancelling && isActive ? "Đang dừng..." : jobStatus.status}
          </span>

          {isActive && (
            <Button
              variant="outline"
              size="sm"
              className="ml-auto gap-1.5 border-red-200 text-red-600 hover:bg-red-50 hover:border-red-400 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/30"
              onClick={handleStop}
              disabled={cancelling}
            >
              {cancelling ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <StopCircle className="h-3.5 w-3.5" />
              )}
              {cancelling ? "Đang dừng..." : "Dừng job"}
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Progress</span>
            <span className="font-medium">{jobStatus.progress}%</span>
          </div>
          <Progress value={jobStatus.progress} />
        </div>

        {/* Current Step */}
        {jobStatus.current_step && (
          <div className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>{jobStatus.current_step}</span>
          </div>
        )}

        {/* Steps */}
        <div className="space-y-3">
          {Object.entries(STEP_LABELS).map(([key, label]) => {
            const completed = (jobStatus.steps_completed ?? []).includes(key);
            const isCurrent = jobStatus.current_step === label;

            return (
              <div
                key={key}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                  completed
                    ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30"
                    : isCurrent
                    ? "border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30"
                    : "border-neutral-200 dark:border-neutral-800"
                }`}
              >
                {completed ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                ) : isCurrent ? (
                  <Loader2 className="h-5 w-5 animate-spin text-blue-500 shrink-0" />
                ) : (
                  <div className="h-5 w-5 rounded-full border-2 border-neutral-300 shrink-0" />
                )}
                <div className="flex-1">
                  <p
                    className={`text-sm font-medium ${
                      completed
                        ? "text-green-700 dark:text-green-400"
                        : isCurrent
                        ? "text-blue-700 dark:text-blue-400"
                        : "text-neutral-500"
                    }`}
                  >
                    {label}
                  </p>
                </div>
                {completed && (
                  <span className="text-xs text-green-600 dark:text-green-400">Done</span>
                )}
              </div>
            );
          })}
        </div>

        {/* Cancelled banner */}
        {jobStatus.status === "cancelled" && (
          <div className="p-3 rounded-lg bg-orange-50 border border-orange-200 dark:bg-orange-950/30 dark:border-orange-800 flex items-center gap-2">
            <StopCircle className="h-4 w-4 text-orange-500 shrink-0" />
            <p className="text-sm text-orange-700 dark:text-orange-400">
              Job đã được dừng thủ công.
            </p>
          </div>
        )}

        {/* Error */}
        {jobStatus.error_message && jobStatus.status !== "cancelled" && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 dark:bg-red-950/30 dark:border-red-800">
            <p className="text-sm text-red-700 dark:text-red-400">
              {jobStatus.error_message}
            </p>
          </div>
        )}

        {/* Estimated Time */}
        {jobStatus.estimated_remaining_seconds && jobStatus.status === "processing" && (
          <p className="text-xs text-neutral-400 text-center">
            Estimated {Math.ceil(jobStatus.estimated_remaining_seconds / 60)} minutes remaining
          </p>
        )}

        {/* Error display */}
        {error && !jobStatus.error_message && (
          <p className="text-xs text-yellow-600 text-center">{error}</p>
        )}
      </CardContent>
    </Card>
  );
}
