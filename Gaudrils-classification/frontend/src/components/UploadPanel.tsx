import { useRef, useState } from "react";
import { uploadFile } from "../api/client";
import type { UploadResponse } from "../types";

interface UploadPanelProps {
  fileInfo: UploadResponse | null;
  onUploaded: (response: UploadResponse) => void;
}

export default function UploadPanel({ fileInfo, onUploaded }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setError(null);

    try {
      const response = await uploadFile(file);
      setStatus("idle");
      onUploaded(response);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  const label =
    status === "uploading"
      ? "Uploading…"
      : fileInfo
      ? `${fileInfo.original_filename} (${fileInfo.total_guardrails} rows)`
      : "Upload document";

  return (
    <div className="field-block">
      <button
        type="button"
        className="input input-button"
        onClick={() => inputRef.current?.click()}
      >
        {label}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls"
        hidden
        onChange={handleFileChange}
      />
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
