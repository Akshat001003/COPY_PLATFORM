import {
  useState,
  type ChangeEvent,
  type Dispatch,
  type SetStateAction,
} from "react";
import { detectCopyMetadata } from "../api/client";
import type { CopyMetadataField, CopyMetadataResponse } from "../types";

const ACCEPTED_FILES = ".pdf,.docx,.xlsx";

interface CopyCreationPageProps {
  onContinue: (context: string) => void;
}

export default function CopyCreationPage({ onContinue }: CopyCreationPageProps) {
  const [projectDescription, setProjectDescription] = useState("");
  const [actualDescription, setActualDescription] = useState("");
  const [referenceDescription, setReferenceDescription] = useState("");
  const [projectFiles, setProjectFiles] = useState<File[]>([]);
  const [actualFiles, setActualFiles] = useState<File[]>([]);
  const [referenceFiles, setReferenceFiles] = useState<File[]>([]);
  const [analysis, setAnalysis] = useState<CopyMetadataResponse | null>(null);
  const [error, setError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  function updateFiles(
    event: ChangeEvent<HTMLInputElement>,
    update: Dispatch<SetStateAction<File[]>>
  ) {
    const selected = Array.from(event.target.files ?? []);
    update((current) => [...current, ...selected]);
    event.target.value = "";
    setAnalysis(null);
    setError("");
  }

  function removeFile(
    target: File,
    files: File[],
    update: Dispatch<SetStateAction<File[]>>
  ) {
    update(files.filter((file) => file !== target));
    setAnalysis(null);
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    setAnalysis(null);
    setError("");
    try {
      const result = await detectCopyMetadata(
        projectDescription,
        actualDescription,
        referenceDescription,
        projectFiles,
        actualFiles,
        referenceFiles
      );
      setAnalysis(result);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Metadata detection failed."
      );
    } finally {
      setAnalyzing(false);
    }
  }

  function renderFiles(
    files: File[],
    update: Dispatch<SetStateAction<File[]>>
  ) {
    if (!files.length) return null;
    return (
      <ul className="copy-file-list">
        {files.map((file, index) => (
          <li key={`${file.name}-${index}`}>
            <span aria-hidden="true">▧</span>
            <span className="copy-file-name">{file.name}</span>
            <button
              type="button"
              className="btn-icon"
              aria-label={`Remove ${file.name}`}
              onClick={() => removeFile(file, files, update)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    );
  }

  function renderInputCard(
    title: string,
    description: string,
    updateDescription: (value: string) => void,
    files: File[],
    updateFilesList: Dispatch<SetStateAction<File[]>>,
    optional = false
  ) {
    return (
      <section className="card copy-input-card">
        <div className="copy-input-card-heading">
          <h2>{title}</h2>
          {optional && <span className="copy-optional">Optional</span>}
        </div>
        <label className="field-label" htmlFor={`${title}-description`}>
          Description
        </label>
        <textarea
          id={`${title}-description`}
          className="input textarea copy-description"
          placeholder={`Add ${title.toLowerCase()} details here`}
          value={description}
          onChange={(event) => {
            updateDescription(event.target.value);
            setAnalysis(null);
          }}
        />
        <div className="copy-or-divider"><span>OR</span></div>
        <label className="copy-upload-drop">
          <input
            type="file"
            accept={ACCEPTED_FILES}
            multiple
            onChange={(event) => updateFiles(event, updateFilesList)}
          />
          <span className="copy-upload-icon" aria-hidden="true">↑</span>
          <strong>Choose documents to upload</strong>
          <small>PDF, DOCX, or XLSX</small>
        </label>
        {renderFiles(files, updateFilesList)}
      </section>
    );
  }

  return (
    <main className="copy-creation-page">
      <header className="copy-creation-header">
        <div className="app-header-title">
          <span className="app-icon">J</span>
          <div>
            <p className="copy-step">STEP 1 OF 2</p>
            <h1>Copy Creation</h1>
            <p className="subtitle">
              Add your project brief and materials to identify the brand,
              market, and asset type.
            </p>
          </div>
        </div>
      </header>

      <div className="copy-input-grid">
        {renderInputCard(
          "Project Brief",
          projectDescription,
          (value) => {
            setProjectDescription(value);
            setAnalysis(null);
          },
          projectFiles,
          setProjectFiles
        )}
        {renderInputCard(
          "Actual Material",
          actualDescription,
          (value) => {
            setActualDescription(value);
            setAnalysis(null);
          },
          actualFiles,
          setActualFiles
        )}
        {renderInputCard(
          "Reference Material",
          referenceDescription,
          (value) => {
            setReferenceDescription(value);
            setAnalysis(null);
          },
          referenceFiles,
          setReferenceFiles,
          true
        )}
      </div>

      <section className="card copy-detection-card">
        <div className="copy-detection-heading">
          <div>
            <p className="section-label">CONTENT ANALYSIS</p>
            <h2>Detected from your materials</h2>
            <p className="hint-text">
              Clear labeled values are read directly. JEV uses one batch to
              resolve any remaining fields.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleAnalyze}
            disabled={
              analyzing ||
              (!projectDescription.trim() && projectFiles.length === 0) ||
              (!actualDescription.trim() && actualFiles.length === 0)
            }
          >
            {analyzing ? "Analysing…" : "Analyse"}
          </button>
        </div>
        {error && <p className="error-text copy-detection-error">{error}</p>}
        {analysis && (
          <>
            {analysis.warnings?.map((warning) => (
              <p className="hint-text copy-detection-warning" key={warning}>
                {warning}
              </p>
            ))}
            <div className="copy-metadata-grid">
              {([
                { label: "Brand", field: analysis.metadata.brand },
                { label: "Market", field: analysis.metadata.market },
                { label: "Asset Type", field: analysis.metadata.asset_type },
              ] satisfies { label: string; field: CopyMetadataField }[]).map(
                ({ label, field }) => {
                  return (
                    <div className="copy-metadata-field" key={label}>
                      <span className="section-label">{label}</span>
                      <strong>{field.value}</strong>
                      <small>
                        {field.source === "No source found"
                          ? "No source found"
                          : `Source: ${field.source}`}
                      </small>
                    </div>
                  );
                }
              )}
            </div>
            <div className="copy-continue-row">
              <span className="muted">Review the detected details, then continue.</span>
              <button
                type="button"
                className="btn btn-primary copy-continue-button"
                onClick={() => {
                  const detectedContext = [
                    `Brand: ${analysis.metadata.brand.value}`,
                    `Market: ${analysis.metadata.market.value}`,
                    `Asset Type: ${analysis.metadata.asset_type.value}`,
                  ].join("\n");
                  onContinue(
                    `${detectedContext}\n\n${analysis.classification_context}`
                  );
                }}
              >
                Continue to JEV vs LLM
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
