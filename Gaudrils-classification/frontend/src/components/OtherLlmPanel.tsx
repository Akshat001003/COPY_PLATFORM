import UploadPanel from "./UploadPanel";
import ModelDropdown from "./ModelDropdown";
import ResultsTable from "./ResultsTable";
import EngineSummary from "./EngineSummary";
import { useState } from "react";
import type { Category, EngineState, LlmResultRow, UploadResponse } from "../types";

interface OtherLlmPanelProps {
  fileInfo: UploadResponse | null;
  onUploaded: (response: UploadResponse) => void;
  categories: Category[];
  hasCategories: boolean;
  model: string;
  onModelChange: (model: string) => void;
  prompt: string;
  onPromptChange: (prompt: string) => void;
  engine: EngineState<LlmResultRow>;
  onRun: (limit: number | null) => Promise<void>;
}

export default function OtherLlmPanel({
  fileInfo,
  onUploaded,
  categories,
  hasCategories,
  model,
  onModelChange,
  prompt,
  onPromptChange,
  engine,
  onRun,
}: OtherLlmPanelProps) {
  const [customLimit, setCustomLimit] = useState("20");
  const [activeRun, setActiveRun] = useState<"custom" | "all" | null>(null);
  const running = engine.status === "running";
  const canRun =
    !!fileInfo &&
    hasCategories &&
    !running &&
    model.trim() !== "" &&
    prompt.trim() !== "";

  async function handleRun(limit: number | null) {
    setActiveRun(limit === null ? "all" : "custom");
    try {
      await onRun(limit);
    } finally {
      setActiveRun(null);
    }
  }

  return (
    <div className="card engine-panel engine-panel-llm">
      <div className="engine-panel-header">
        <span className="status-dot status-dot-llm" />
        <span className="engine-title">General LLM · free-form</span>
        <span className="pill pill-llm">unbounded</span>
      </div>

      <UploadPanel fileInfo={fileInfo} onUploaded={onUploaded} />

      <ModelDropdown value={model} onChange={onModelChange} />

      <div className="field-block">
        <label className="field-label">Context / state / prompt</label>
        <textarea
          className="input textarea"
          placeholder="Should this guardrail be approved? Give a decision and a one-line reason."
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          rows={6}
        />
      </div>

      <div className="run-controls">
        <div className="field-block run-count-field">
          <label className="field-label" htmlFor="llm-custom-count">
            Guardrails to classify
          </label>
          <input
            id="llm-custom-count"
            className="input run-count-input"
            type="number"
            min={1}
            max={fileInfo?.total_guardrails ?? undefined}
            value={customLimit}
            onChange={(event) => setCustomLimit(event.target.value)}
          />
        </div>
        <button
          type="button"
          className="btn btn-dark"
          disabled={
            !canRun ||
            !Number.isInteger(Number(customLimit)) ||
            Number(customLimit) < 1 ||
            Number(customLimit) > (fileInfo?.total_guardrails ?? 0)
          }
          onClick={() => void handleRun(Number(customLimit))}
        >
          {running && activeRun === "custom" ? "Running custom…" : "Run custom →"}
        </button>
        <button
          type="button"
          className="btn btn-outline run-all-button"
          disabled={!canRun}
          onClick={() => void handleRun(null)}
        >
          {running && activeRun === "all" ? "Running all…" : "Run all guardrails →"}
        </button>
      </div>

      {engine.error && <p className="error-text">{engine.error}</p>}

      {engine.status === "running" && (
        <div className="jev-run-progress">
          <p className="muted">
            {engine.progress
              ? `${engine.progress.status === "queued" ? "Queued" : "Processing"} ${engine.progress.completed}${engine.progress.total_rows == null ? "" : `/${engine.progress.total_rows}`} guardrails; ${engine.progress.processed} classified, ${engine.progress.failed} failed.`
              : "Starting LLM classification…"}
          </p>
          {engine.progress?.total_rows != null && (
            <progress
              className="jev-progress-bar"
              max={Math.max(engine.progress.total_rows, 1)}
              value={engine.progress.completed}
              aria-label="Full LLM classification progress"
            />
          )}
        </div>
      )}

      {engine.status === "done" && (
        <>
          <p className="muted">
            {engine.results.length} rows classified in {((engine.elapsedMs ?? 0) / 1000).toFixed(1)}s
            {!!engine.failedCount && `; ${engine.failedCount} rows failed`}
          </p>
          {!!engine.failures?.length && (
            <div className="llm-failure-details" role="alert">
              <strong>Provider error details</strong>
              {Array.from(
                new Map(
                  engine.failures.map((failure) => [failure.error, failure])
                ).values()
              )
                .slice(0, 3)
                .map((failure) => (
                  <p key={`${failure.GuardrailId}-${failure.error}`}>
                    Guardrail {failure.GuardrailId ?? "unknown"}: {failure.error}
                  </p>
                ))}
            </div>
          )}
          <EngineSummary
            rows={engine.results}
            categories={categories.map((category) => category.name.trim()).filter(Boolean)}
            elapsedMs={engine.elapsedMs ?? 0}
            engine="llm"
          />
        </>
      )}

      <ResultsTable
        rows={engine.results}
        rowKey={(row) => row.GuardrailId}
        emptyText="Run to see results"
        columns={[
          { header: "ID", render: (r) => r.GuardrailId },
          { header: "Rule", render: (r) => r.ShortRule },
          { header: "Category", render: (r) => r.LLM_Category },
        ]}
      />
    </div>
  );
}
