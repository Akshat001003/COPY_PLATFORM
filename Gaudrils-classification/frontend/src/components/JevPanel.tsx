import { useState } from "react";
import UploadPanel from "./UploadPanel";
import CategoryEditor from "./CategoryEditor";
import ResultsTable from "./ResultsTable";
import EngineSummary from "./EngineSummary";
import type { Category, EngineState, JevResultRow, UploadResponse } from "../types";

interface JevPanelProps {
  fileInfo: UploadResponse | null;
  onUploaded: (response: UploadResponse) => void;
  categories: Category[];
  onCategoriesChange: (categories: Category[]) => void;
  context: string;
  onContextChange: (context: string) => void;
  engine: EngineState<JevResultRow>;
  onRunFull: (limit: number | null) => Promise<void>;
}

export default function JevPanel({
  fileInfo,
  onUploaded,
  categories,
  onCategoriesChange,
  context,
  onContextChange,
  engine,
  onRunFull,
}: JevPanelProps) {
  const [activeRun, setActiveRun] = useState<"custom" | "all" | null>(null);
  const [customLimit, setCustomLimit] = useState("20");
  const running = engine.status === "running";
  const hasCategories = categories.some((c) => c.name.trim() !== "");
  const disabled = !fileInfo || !hasCategories;

  async function handleRun(limit: number | null) {
    setActiveRun(limit === null ? "all" : "custom");
    try {
      await onRunFull(limit);
    } finally {
      setActiveRun(null);
    }
  }

  return (
    <div className="card engine-panel engine-panel-jev">
      <div className="engine-panel-header">
        <span className="status-dot status-dot-jev" />
        <span className="engine-title">Jev · typed Choice</span>
        <span className="pill pill-jev">deterministic</span>
      </div>

      <UploadPanel fileInfo={fileInfo} onUploaded={onUploaded} />

      <div className="field-block">
        <label className="field-label">Context / state</label>
        <textarea
          className="input textarea"
          placeholder="e.g. audience=HCP, channel=email, market=US"
          rows={4}
          value={context}
          onChange={(e) => onContextChange(e.target.value)}
        />
      </div>

      <CategoryEditor categories={categories} onChange={onCategoriesChange} />

      <div className="run-controls">
        <div className="field-block run-count-field">
          <label className="field-label" htmlFor="jev-custom-count">
            Guardrails to classify
          </label>
          <input
            id="jev-custom-count"
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
          className="btn btn-primary"
          disabled={
            disabled ||
            running ||
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
          disabled={disabled || running}
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
              ? `${engine.progress.status === "queued" ? "Queued" : "Processing"} JEV batch (size ${engine.progress.batch_size ?? "unknown"}): ${engine.progress.completed}${engine.progress.total_rows == null ? "" : `/${engine.progress.total_rows}`} rows checked, ${engine.progress.processed} classified, ${engine.progress.failed} failed.`
              : "Starting JEV run…"}
          </p>
          {engine.progress?.total_rows != null && (
            <progress
              className="jev-progress-bar"
              max={Math.max(engine.progress.total_rows, 1)}
              value={engine.progress.completed}
              aria-label="Full JEV classification progress"
            />
          )}
        </div>
      )}

      {engine.status === "done" && (
        <div className="muted">
          {engine.results.length} rows classified in {((engine.elapsedMs ?? 0) / 1000).toFixed(1)}s
          {engine.batchSize && ` (batch size ${engine.batchSize})`}
          {!!engine.failedCount && `; ${engine.failedCount} rows failed`}
          {engine.usageNote && <p>{engine.usageNote}</p>}
        </div>
      )}

      {engine.status === "done" && (
        <EngineSummary
          rows={engine.results}
          categories={categories.map((category) => category.name.trim()).filter(Boolean)}
          elapsedMs={engine.elapsedMs ?? 0}
          engine="jev"
        />
      )}

      <ResultsTable
        rows={engine.results}
        rowKey={(row) => row.GuardrailId}
        emptyText="Run to see results"
        columns={[
          { header: "ID", render: (r) => r.GuardrailId },
          { header: "Rule", render: (r) => r.ShortRule },
          { header: "Category", render: (r) => r.JEV_Category },
          {
            header: "Confidence",
            render: (r) => (r.JEV_Confidence != null ? r.JEV_Confidence.toFixed(2) : "—"),
          },
        ]}
      />
    </div>
  );
}
