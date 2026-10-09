export interface Category {
  id: string;
  name: string;
  description: string;
}

export interface UploadResponse {
  success: boolean;
  file_id: string;
  original_filename: string;
  file_path: string;
  workbook: {
    filename: string;
    sheet_count: number;
    sheets: Record<string, { rows: number; columns: string[] }>;
  };
  total_guardrails: number;
}

export interface CopyMetadataField {
  value: string;
  source: string;
}

export interface CopyMetadataResponse {
  metadata: {
    brand: CopyMetadataField;
    market: CopyMetadataField;
    asset_type: CopyMetadataField;
  };
  model: string;
  classification_context: string;
  warnings?: string[];
}

export interface JevUsage {
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
}

export interface JevResultRow {
  GuardrailId: string;
  ShortRule: string;
  JEV_Category: string;
  JEV_Confidence: number | null;
  JEV_Probabilities?: Record<string, number>;
  JEV_Usage: JevUsage;
}

export interface LlmUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  cost?: number;
}

export interface LlmResultRow {
  GuardrailId: string;
  ShortRule: string;
  LLM_Category: string;
  LLM_Answer?: string;
  LLM_Usage: LlmUsage;
}

export interface LlmFailure {
  GuardrailId: string | number | null;
  error: string;
}

export interface ModelOption {
  id: string;
  name: string;
  provider?: string;
  context_length?: number;
  pricing?: Record<string, unknown>;
}

export interface ComparisonRow {
  GuardrailId: string;
  ShortRule: string;
  JEV_Category: string;
  LLM_Category: string;
  agreement: boolean;
  JEV_Confidence: number | null;
  JEV_Input_Tokens: number;
  JEV_Output_Tokens: number;
  JEV_Cost: number;
  LLM_Input_Tokens: number;
  LLM_Output_Tokens: number;
  LLM_Cost: number;
}

export interface CompareResponse {
  success: boolean;
  file_id: string;
  total_compared: number;
  agreements: number;
  disagreements: number;
  agreement_percentage: number;
  comparisons: ComparisonRow[];
  output_file: string;
}

export type RunStatus = "idle" | "running" | "done" | "error";
export type JevMode = "normal" | "batch";

export interface EngineState<TResult> {
  status: RunStatus;
  results: TResult[];
  error?: string;
  elapsedMs?: number;
  progress?: JevRunProgress;
  runMode?: JevMode;
  batchSize?: number;
  usageNote?: string;
  failedCount?: number;
  failures?: LlmFailure[];
}

export interface JevRunProgress {
  status: "queued" | "running";
  mode: JevMode;
  batch_size: number;
  total_rows: number | null;
  completed: number;
  processed: number;
  failed: number;
}
