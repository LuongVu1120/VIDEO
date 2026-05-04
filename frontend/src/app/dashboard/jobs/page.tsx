"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Clock, CheckCircle2, XCircle, Loader2, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useJobStore } from "@/store/job-store";
import { formatDate } from "@/lib/utils";

export default function JobsPage() {
  const { jobs, isLoading, loadJobs } = useJobStore();

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const statusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case "failed":
        return <XCircle className="h-5 w-5 text-red-500" />;
      case "processing":
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
      default:
        return <Clock className="h-5 w-5 text-yellow-500" />;
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">My Jobs</h1>
        <p className="text-neutral-500 mt-2">Track your content generation requests.</p>
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-neutral-400" />
          </CardContent>
        </Card>
      ) : jobs.length === 0 ? (
        <Card>
          <CardContent className="text-center py-12">
            <p className="text-neutral-500 mb-4">No jobs yet.</p>
            <Link href="/dashboard/upload">
              <Button>Create Your First Job</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Link key={job.job_id} href={`/dashboard/jobs/${job.job_id}`}>
              <Card className="hover:border-neutral-300 transition-colors cursor-pointer dark:hover:border-neutral-700">
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    {statusIcon(job.status)}
                    <div>
                      <p className="text-sm font-medium capitalize">{job.status}</p>
                      <p className="text-xs text-neutral-500">
                        {formatDate(job.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {job.status === "processing" && (
                      <span className="text-sm text-neutral-500">{job.progress}%</span>
                    )}
                    <ArrowRight className="h-4 w-4 text-neutral-400" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
