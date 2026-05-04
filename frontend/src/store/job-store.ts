import { create } from "zustand";
import { api } from "@/lib/api";

interface JobState {
  currentJobId: string | null;
  jobs: Array<{
    job_id: string;
    status: string;
    progress: number;
    created_at: string;
  }>;
  isLoading: boolean;
  isUploading: boolean;

  uploadImage: (formData: FormData) => Promise<string>;
  loadJobs: () => Promise<void>;
  setCurrentJob: (jobId: string | null) => void;
  setUploading: (uploading: boolean) => void;
}

export const useJobStore = create<JobState>((set) => ({
  currentJobId: null,
  jobs: [],
  isLoading: false,
  isUploading: false,

  uploadImage: async (formData) => {
    set({ isUploading: true });
    try {
      const result = await api.uploadImage(formData);
      set({ currentJobId: result.job_id, isUploading: false });
      return result.job_id;
    } catch (error) {
      set({ isUploading: false });
      throw error;
    }
  },

  loadJobs: async () => {
    set({ isLoading: true });
    try {
      const jobs = await api.listJobs();
      set({ jobs, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  setCurrentJob: (jobId) => set({ currentJobId: jobId }),
  setUploading: (uploading) => set({ isUploading: uploading }),
}));
