import { useEffect, useState } from "react";
import "./App.css";
import JevPanel from "./components/JevPanel";
import OtherLlmPanel from "./components/OtherLlmPanel";
import ComparisonSection from "./components/ComparisonSection";
import CopyCreationPage from "./components/CopyCreationPage";
import { compare, runJevFull, runLlmFull } from "./api/client";
import type {
  Category,
  CompareResponse,
  EngineState,
  JevMode,
  JevResultRow,
  LlmResultRow,
  UploadResponse,
} from "./types";

function makeId() {
  return Math.random().toString(36).slice(2, 10);
}

const idleEngine = <T,>(): EngineState<T> => ({ status: "idle", results: [] });

export default function App() {
  const [fileInfo, setFileInfo] = useState<UploadResponse | null>(null);
  const [categories, setCategories] = useState<Category[]>([
    { id: makeId(), name: "", description: "" },
  ]);
  const [context, setContext] = useState("");
  const [showClassifier, setShowClassifier] = useState(false);

  const [jev, setJev] = useState<EngineState<JevResultRow>>(idleEngine());
  const [llm, setLlm] = useState<EngineState<LlmResultRow>>(idleEngine());

  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState(
    "Should this guardrail be approved? Give a decision and a one-line reason."
  );

  const [comparing, setComparing] = useState(false);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  const hasCategories = categories.some((c) => c.name.trim() !== "");
  const fileId = fileInfo?.file_id ?? null;

  async function handleJevFull(limit: number | null, selectedMode: JevMode) {
    if (!fileId) return;
    setComparison(null);
    setComparisonError(null);
    setJev({ status: "running", results: [] });
    const start = performance.now();
    try {
      const { results, mode: runMode, batch_size, failed, usage_note } = await runJevFull(
        fileId,
        categories,
        context,
        selectedMode,
        limit,
        (progress) => setJev((current) => ({ ...current, progress }))
      );
      setJev({
        status: "done",
        results,
        elapsedMs: performance.now() - start,
        runMode,
        batchSize: batch_size,
        failedCount: failed,
        usageNote: usage_note,
      });
    } catch (err) {
      setJev({
        status: "error",
        results: [],
        error: err instanceof Error ? err.message : "JEV classification failed.",
      });
    }
  }

  async function handleLlmRun(limit: number | null) {
    if (!fileId || !model.trim()) return;
    setComparison(null);
    setComparisonError(null);
    setLlm({ status: "running", results: [] });
    const start = performance.now();
    try {
      const { results, failed, failures } = await runLlmFull(
        fileId,
        categories,
        model,
        prompt,
        context,
        limit,
        (progress) => setLlm((current) => ({ ...current, progress }))
      );
      setLlm({
        status: "done",
        results,
        elapsedMs: performance.now() - start,
        failedCount: failed,
        failures,
      });
    } catch (err) {
      setLlm({
        status: "error",
        results: [],
        error: err instanceof Error ? err.message : "LLM classification failed.",
      });
    }
  }

  useEffect(() => {
    if (jev.status === "done" && llm.status === "done" && fileId) {
      setComparing(true);
      setComparisonError(null);
      compare(fileId, jev.results, llm.results, model)
        .then(setComparison)
        .catch((err) =>
          setComparisonError(err instanceof Error ? err.message : "Comparison failed.")
        )
        .finally(() => setComparing(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jev.status, llm.status]);

  const statusLabel = comparison ? "Compared" : comparing ? "Comparing" : "Awaiting runs";

  return (
    <div className="app-shell">
      {!showClassifier && (
        <CopyCreationPage
          onContinue={(sharedContext) => {
            setContext(sharedContext);
            setShowClassifier(true);
          }}
        />
      )}
      {showClassifier && (
        <>
          <header className="app-header">
            <div className="app-header-title">
              <span className="app-icon">J</span>
              <div>
                <h1>Jev vs LLM Comparison</h1>
                <p className="subtitle">
                  One document, two engines, side by side. Jev returns a constrained
                  choice; a general LLM returns free-form text.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => setShowClassifier(false)}
            >
              Back to Copy Creation
            </button>
            <span className="status-pill">
              <span className="status-pill-dot" /> {statusLabel}
            </span>
          </header>

          <div className="engine-grid">
            <JevPanel
              fileInfo={fileInfo}
              onUploaded={setFileInfo}
              categories={categories}
              onCategoriesChange={setCategories}
              context={context}
              onContextChange={setContext}
              engine={jev}
              onRunFull={handleJevFull}
            />
            <OtherLlmPanel
              fileInfo={fileInfo}
              onUploaded={setFileInfo}
              categories={categories}
              hasCategories={hasCategories}
              model={model}
              onModelChange={setModel}
              prompt={prompt}
              onPromptChange={setPrompt}
              engine={llm}
              onRun={handleLlmRun}
            />
          </div>

          <ComparisonSection
            fileId={fileId}
            jev={jev}
            llm={llm}
            comparing={comparing}
            comparison={comparison}
            comparisonError={comparisonError}
          />
        </>
      )}
    </div>
  );
}
