import { exportUrl } from "../api/client";
import type { CompareResponse, EngineState, JevResultRow, LlmResultRow } from "../types";

interface ComparisonSectionProps {
  fileId: string | null;
  jev: EngineState<JevResultRow>;
  llm: EngineState<LlmResultRow>;
  comparing: boolean;
  comparison: CompareResponse | null;
  comparisonError: string | null;
}

function MeterTile({
  label,
  jevValue,
  llmValue,
  format,
  jevReady,
  llmReady,
}: {
  label: string;
  jevValue: number;
  llmValue: number;
  format: (value: number) => string;
  jevReady: boolean;
  llmReady: boolean;
}) {
  const total = jevValue + llmValue;
  const bothReady = jevReady && llmReady;
  const jevPct = bothReady && total > 0 ? (jevValue / total) * 100 : 0;
  const llmPct = bothReady && total > 0 ? (llmValue / total) * 100 : 0;
  const delta = (() => {
    if (!bothReady || jevValue <= 0 || llmValue <= 0 || jevValue === llmValue) {
      return null;
    }
    const winner = jevValue < llmValue ? "JEV" : "LLM";
    const ratio = Math.max(jevValue, llmValue) / Math.min(jevValue, llmValue);
    if (label === "RESPONSE TIME") return `${winner} ${ratio.toFixed(1)}× faster`;
    const percent = Math.round(
      (Math.abs(jevValue - llmValue) / Math.max(jevValue, llmValue)) * 100
    );
    return label === "COST"
      ? `${winner} ${percent}% cheaper`
      : `${winner} ${percent}% fewer`;
  })();
  const readiness = [
    jevReady ? "JEV ready" : "JEV pending",
    llmReady ? "LLM ready" : "LLM pending",
  ].join(" · ");

  return (
    <div className="meter-tile">
      <div className="meter-tile-header">
        <span className="muted">{label}</span>
        {delta ? (
          <span className="comparison-delta">{delta}</span>
        ) : (
          <span className="muted">{bothReady ? "" : readiness}</span>
        )}
      </div>
      <div className="meter-labels">
        <span>JEV</span>
        <span>LLM</span>
      </div>
      <div className="meter-values">
        <span>{jevReady ? format(jevValue) : "—"}</span>
        <span>{llmReady ? format(llmValue) : "—"}</span>
      </div>
      <div className="meter-track">
        <div className="meter-fill-jev" style={{ width: `${jevPct}%` }} />
        <div className="meter-fill-llm" style={{ width: `${llmPct}%` }} />
      </div>
      {!bothReady && (
        <p className="hint-text meter-tile-footer">
          {jevReady || llmReady ? "Metrics update as each engine finishes" : "Run either engine to compare metrics"}
        </p>
      )}
    </div>
  );
}

export default function ComparisonSection({
  fileId,
  jev,
  llm,
  comparing,
  comparison,
  comparisonError,
}: ComparisonSectionProps) {
  const jevReady = jev.status === "done";
  const llmReady = llm.status === "done";

  const jevTokens = jev.results.reduce(
    (sum, r) => sum + (r.JEV_Usage.input_tokens ?? 0) + (r.JEV_Usage.output_tokens ?? 0),
    0
  );
  const llmTokens = llm.results.reduce(
    (sum, r) => sum + (r.LLM_Usage.prompt_tokens ?? 0) + (r.LLM_Usage.completion_tokens ?? 0),
    0
  );
  const jevCost = jev.results.reduce((sum, r) => sum + (r.JEV_Usage.cost ?? 0), 0);
  const llmCost = llm.results.reduce((sum, r) => sum + (r.LLM_Usage.cost ?? 0), 0);

  return (
    <div className="card comparison-section">
      <div className="comparison-header">
        <span className="section-label">Comparison</span>
        {comparing && <span className="muted"> · Comparing…</span>}
      </div>

      {comparisonError && <p className="error-text">{comparisonError}</p>}

      {comparison && (
        <div className="agreement-banner">
          <strong>{comparison.agreement_percentage}%</strong> agreement across{" "}
          {comparison.total_compared} compared guardrails ({comparison.agreements} agree,{" "}
          {comparison.disagreements} disagree).
          <div className="hint-text">
            Agreement between JEV and the Other LLM is not a measure of correctness —
            it is not ground truth, just how often the two engines picked the same category.
          </div>
        </div>
      )}

      <div className="meter-grid">
        <MeterTile
          label="RESPONSE TIME"
          jevValue={jev.elapsedMs ?? 0}
          llmValue={llm.elapsedMs ?? 0}
          format={(v) => `${Math.round(v).toLocaleString()} ms`}
          jevReady={jevReady}
          llmReady={llmReady}
        />
        <MeterTile
          label="TOKENS"
          jevValue={jevTokens}
          llmValue={llmTokens}
          format={(v) => v.toLocaleString()}
          jevReady={jevReady}
          llmReady={llmReady}
        />
        <MeterTile
          label="COST"
          jevValue={jevCost}
          llmValue={llmCost}
          format={(v) => `$${v.toFixed(5)}`}
          jevReady={jevReady}
          llmReady={llmReady}
        />
      </div>

      {!!comparison && fileId && (
        <a className="btn btn-outline btn-small comparison-download" href={exportUrl(fileId)}>
          Download comparison Excel →
        </a>
      )}
    </div>
  );
}
