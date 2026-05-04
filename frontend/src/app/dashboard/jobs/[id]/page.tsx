"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { JobTracker } from "@/components/job-status/JobTracker";
import { OutputGallery } from "@/components/output-gallery/OutputGallery";

export default function JobDetailPage() {
  const params = useParams();
  const [jobId, setJobId] = useState<string>("");
  const [showOutput, setShowOutput] = useState(false);

  useEffect(() => {
    if (params?.id) {
      setJobId(params.id as string);
    }
  }, [params]);

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <JobTracker jobId={jobId} onComplete={() => setShowOutput(true)} />
      {showOutput && <OutputGallery jobId={jobId} />}
    </div>
  );
}
