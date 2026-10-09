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
  JevResultRow,
  LlmResultRow,
  UploadResponse,
} from "./types";

function makeId() {
  return Math.random().toString(36).slice(2, 10);
}

const DEFAULT_CATEGORIES = [
  {
    name: "claims_evidence",
    description:
      "Claims & Evidence — Guardrails governing the accuracy, substantiation, and presentation of clinical, scientific, efficacy, comparative, promotional, or benefit-related claims. Includes approved claims, scientific tone, clinical evidence, statistical findings, evidence interpretation, and restrictions on unsupported, exaggerated, or misleading claims.",
  },
  {
    name: "product_safety",
    description:
      "Product & Safety — Guardrails governing product-specific information and patient safety. Includes approved indications and uses, prescribing or label information, dosage and administration, contraindications, warnings and precautions, adverse events, safety information, and restrictions on which patients or populations a product-related statement applies to.",
  },
  {
    name: "brand_messaging",
    description:
      "Brand & Messaging — Guardrails governing brand identity and the consistent expression of a brand. Includes logo usage, brand colors, typography, brand assets, visual identity, brand consistency, tone of voice, and brand-specific messaging conventions. Use this category when brand representation is the primary purpose of the rule.",
  },
  {
    name: "structure_formatting",
    description:
      "Structure & Formatting — Guardrails governing how content is organized, displayed, formatted, or visually presented. Includes imagery style, layout and spacing, visual hierarchy, data visualization, content sequencing, headings, formatting, digital specifications, and presentation requirements. Use this category when the main requirement concerns the structure or format rather than the claim itself.",
  },
  {
    name: "cta_references",
    description:
      "CTA & References — Guardrails governing calls to action, links, citations, references, sources, supporting documentation, and required directions or next steps for the reader. Includes required reference attribution and rules about where a user should be directed.",
  },
  {
    name: "others",
    description:
      "Others — Guardrails that do not clearly fit any of the five defined categories, even after considering their full meaning and context. Use only when no category is a reasonable fit; do not use it merely because a rule is ambiguous or mentions several topics.",
  },
];

const idleEngine = <T,>(): EngineState<T> => ({ status: "idle", results: [] });

export default function App() {
  const [fileInfo, setFileInfo] = useState<UploadResponse | null>(null);
  const [categories, setCategories] = useState<Category[]>(
    DEFAULT_CATEGORIES.map((category) => ({ ...category, id: makeId() }))
  );
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

  async function handleJevFull(limit: number | null) {
    if (!fileId) return;
    setComparison(null);
    setComparisonError(null);
    setJev({ status: "running", results: [] });
    const start = performance.now();
    try {
      const { results, batch_size, failed, usage_note } = await runJevFull(
        fileId,
        categories,
        context,
        limit,
        (progress) => setJev((current) => ({ ...current, progress }))
      );
      setJev({
        status: "done",
        results,
        elapsedMs: performance.now() - start,
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
