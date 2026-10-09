import type {
  CompareResponse,
  JevResultRow,
  LlmResultRow,
  ModelOption,
  CopyMetadataResponse,
  RunProgress,
  LlmFailure,
  UploadResponse,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

function categoriesAsDict(categories: { name: string; description: string }[]) {
  const dict: Record<string, string> = {};
  for (const category of categories) {
    if (category.name.trim()) {
      dict[category.name.trim()] = category.description.trim();
    }
  }
  return dict;
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<UploadResponse>("/upload", {
    method: "POST",
    body: formData,
  });
}

export async function detectCopyMetadata(
  projectDescription: string,
  actualMaterialDescription: string,
  referenceDescription: string,
  projectFiles: File[],
  actualMaterialFiles: File[],
  referenceFiles: File[]
): Promise<CopyMetadataResponse> {
  const formData = new FormData();
  formData.append("project_description", projectDescription);
  formData.append("actual_material_description", actualMaterialDescription);
  formData.append("reference_description", referenceDescription);
  projectFiles.forEach((file) => formData.append("project_files", file));
  actualMaterialFiles.forEach((file) => formData.append("actual_material_files", file));
  referenceFiles.forEach((file) => formData.append("reference_files", file));

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 35_000);
  try {
    return await request<CopyMetadataResponse>("/copy-creation/detect", {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(
        "Analysis timed out. Restart the backend and try again; labeled values should return immediately."
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function getModels(): Promise<{ models: ModelOption[] }> {
  return request("/models");
}

export async function getRecommendedModels(): Promise<{ models: ModelOption[] }> {
  return request("/models/recommended");
}

export async function runJevPreview(
  fileId: string,
  categories: { name: string; description: string }[],
  limit: number,
  context: string
): Promise<{ results: JevResultRow[] }> {
  return request(`/classify/${fileId}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      categories: categoriesAsDict(categories),
      limit,
      context,
    }),
  });
}

export async function runJevFull(
  fileId: string,
  categories: { name: string; description: string }[],
  context: string,
  limit: number | null,
  onProgress: (progress: RunProgress) => void
): Promise<{
  results: JevResultRow[];
  batch_size: number;
  failed: number;
  usage_note?: string;
}> {
  const job = await request<{
    job_id: string;
    batch_size: number;
    total_rows: number | null;
    completed: number;
    processed: number;
    failed: number;
    status: "queued" | "running";
  }>(`/classify/${fileId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      categories: categoriesAsDict(categories),
      context,
      limit: limit ?? 0,
    }),
  });

  const reportProgress = (status: {
    status: "queued" | "running";
    batch_size: number;
    total_rows: number | null;
    completed: number;
    processed: number;
    failed: number;
  }) => {
    onProgress({
      status: status.status,
      batch_size: status.batch_size,
      total_rows: status.total_rows,
      completed: status.completed,
      processed: status.processed,
      failed: status.failed,
    });
  };

  reportProgress(job);
  while (true) {
    await new Promise((resolve) => window.setTimeout(resolve, 750));
    const status = await request<{
      status: "queued" | "running" | "done" | "error";
      batch_size: number;
      total_rows: number | null;
      completed: number;
      processed: number;
      failed: number;
      job_id: string;
      results?: JevResultRow[];
      error?: string;
      usage_note?: string;
    }>(`/classify/${fileId}/run/${job.job_id}`);

    if (status.status === "queued") {
      reportProgress({ ...status, status: "queued" });
      continue;
    }
    if (status.status === "running") {
      reportProgress({ ...status, status: "running" });
      continue;
    }
    if (status.status === "error") {
      throw new Error(status.error ?? "Full JEV classification failed.");
    }
    return {
      results: status.results ?? [],
      batch_size: status.batch_size,
      failed: status.failed,
      usage_note: status.usage_note,
    };
  }
}

export async function runLlmFull(
  fileId: string,
  categories: { name: string; description: string }[],
  model: string,
  prompt: string,
  context: string,
  limit: number | null,
  onProgress: (progress: RunProgress) => void
): Promise<{ results: LlmResultRow[]; failed: number; failures: LlmFailure[] }> {
  const job = await request<{
    job_id: string;
    status: "queued" | "running";
    total_rows: number | null;
    completed: number;
    processed: number;
    failed: number;
  }>(`/classify/${fileId}/llm-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      categories: categoriesAsDict(categories),
      model,
      prompt,
      context,
      limit: limit ?? 0,
    }),
  });

  const reportProgress = (
    status: {
      status: "queued" | "running";
      total_rows: number | null;
      completed: number;
      processed: number;
      failed: number;
    },
    mode: "queued" | "running"
  ) => {
    onProgress({
      status: mode,
      total_rows: status.total_rows,
      completed: status.completed,
      processed: status.processed,
      failed: status.failed,
    });
  };

  reportProgress(job, "queued");
  while (true) {
    await new Promise((resolve) => window.setTimeout(resolve, 750));
    const status = await request<{
      status: "queued" | "running" | "done" | "error";
      total_rows: number | null;
      completed: number;
      processed: number;
      failed: number;
      job_id: string;
      results?: LlmResultRow[];
      failures?: LlmFailure[];
      error?: string;
    }>(`/classify/${fileId}/llm-run/${job.job_id}`);

    if (status.status === "queued") {
      reportProgress({ ...status, status: "queued" }, "queued");
      continue;
    }
    if (status.status === "running") {
      reportProgress({ ...status, status: "running" }, "running");
      continue;
    }
    if (status.status === "error") {
      throw new Error(status.error ?? "Full LLM classification failed.");
    }
    return {
      results: status.results ?? [],
      failed: status.failed,
      failures: status.failures ?? [],
    };
  }
}

export async function runLlmPreview(
  fileId: string,
  categories: { name: string; description: string }[],
  model: string,
  prompt: string,
  limit: number,
  context: string
): Promise<{ results: LlmResultRow[] }> {
  return request(`/classify/${fileId}/llm-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      categories: categoriesAsDict(categories),
      model,
      prompt,
      limit,
      context,
    }),
  });
}

export async function compare(
  fileId: string,
  jevResults: JevResultRow[],
  llmResults: LlmResultRow[],
  model: string
): Promise<CompareResponse> {
  return request(`/compare/${fileId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jev_results: jevResults,
      llm_results: llmResults,
      model,
    }),
  });
}

export function exportUrl(fileId: string): string {
  return `${BASE_URL}/export/${fileId}`;
}
