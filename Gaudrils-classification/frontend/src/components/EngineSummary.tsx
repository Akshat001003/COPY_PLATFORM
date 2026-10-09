import type { JevResultRow, LlmResultRow } from "../types";

type ResultRow = JevResultRow | LlmResultRow;

interface EngineSummaryProps {
  rows: ResultRow[];
  categories: string[];
  elapsedMs: number;
  engine: "jev" | "llm";
}

function getCategory(row: ResultRow): string {
  return "JEV_Category" in row ? row.JEV_Category : row.LLM_Category;
}

function getTokens(row: ResultRow): number {
  if ("JEV_Usage" in row) {
    return (row.JEV_Usage.input_tokens ?? 0) + (row.JEV_Usage.output_tokens ?? 0);
  }
  return (row.LLM_Usage.prompt_tokens ?? 0) + (row.LLM_Usage.completion_tokens ?? 0);
}

function getCost(row: ResultRow): number {
  return "JEV_Usage" in row
    ? row.JEV_Usage.cost ?? 0
    : row.LLM_Usage.cost ?? 0;
}

export default function EngineSummary({
  rows,
  categories,
  elapsedMs,
  engine,
}: EngineSummaryProps) {
  if (rows.length === 0) return null;

  const counts = new Map(categories.map((category) => [category, 0]));
  let unmatched = 0;
  for (const row of rows) {
    const resultCategory = getCategory(row).trim();
    const match = categories.find(
      (category) => category.toLocaleLowerCase() === resultCategory.toLocaleLowerCase()
    );
    if (match) counts.set(match, (counts.get(match) ?? 0) + 1);
    else unmatched += 1;
  }
  if (unmatched > 0) counts.set("Other / unmatched", unmatched);

  const totalTokens = rows.reduce((sum, row) => sum + getTokens(row), 0);
  const totalCost = rows.reduce((sum, row) => sum + getCost(row), 0);
  const sampleRow =
    engine === "llm"
      ? rows.find(
          (row): row is LlmResultRow =>
            "LLM_Answer" in row && typeof row.LLM_Answer === "string"
        )
      : undefined;
  const sampleAnswer = sampleRow?.LLM_Answer;

  return (
    <section className={`engine-summary engine-summary-${engine}`} aria-label={`${engine} run summary`}>
      <div className="engine-summary-chart">
        <h3>Category distribution · {rows.length} guardrails</h3>
        {[...counts].map(([category, count]) => {
          const percentage = (count / rows.length) * 100;
          return (
            <div className="category-bar-row" key={category}>
              <span className="category-bar-label" title={category}>{category}</span>
              <div
                className="category-bar-track"
                role="img"
                aria-label={`${category}: ${percentage.toFixed(1)} percent`}
              >
                <div className="category-bar-fill" style={{ width: `${percentage}%` }} />
              </div>
              <span className="category-bar-value">{percentage.toFixed(0)}%</span>
            </div>
          );
        })}
      </div>

      {sampleAnswer && (
        <div className="engine-answer">
          <h3>Sample generated answer · first guardrail</h3>
          <p>{sampleAnswer}</p>
        </div>
      )}

      <div className="engine-summary-metrics">
        <div className="engine-summary-metric">
          <span>Response</span>
          <strong>{elapsedMs.toLocaleString()}<small> ms</small></strong>
        </div>
        <div className="engine-summary-metric">
          <span>Tokens</span>
          <strong>{totalTokens.toLocaleString()}</strong>
        </div>
        <div className="engine-summary-metric">
          <span>Cost</span>
          <strong>${totalCost.toFixed(4)}</strong>
        </div>
      </div>
    </section>
  );
}
