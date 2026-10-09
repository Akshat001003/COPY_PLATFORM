import { useEffect, useState } from "react";
import { getModels } from "../api/client";
import type { ModelOption } from "../types";

interface ModelDropdownProps {
  value: string;
  onChange: (modelId: string) => void;
}

export default function ModelDropdown({ value, onChange }: ModelDropdownProps) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getModels()
      .then(({ models: availableModels }) => {
        if (!cancelled) setModels(availableModels);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Could not retrieve the model catalog."
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = models.reduce<Record<string, ModelOption[]>>((acc, model) => {
    const providerId = model.id.split("/")[0];
    const provider = model.provider ?? providerId;
    const key = provider
      ? provider
          .split(/[-_]/)
          .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
          .join(" ")
      : "Other";
    (acc[key] ??= []).push(model);
    return acc;
  }, {});

  return (
    <div className="field-block">
      <label className="field-label">Model</label>
      <select
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="" disabled>
          Select a model…
        </option>
        {Object.entries(grouped).map(([provider, items]) => (
          <optgroup label={provider} key={provider}>
            {items.map((model) => (
              <option value={model.id} key={model.id}>
                {model.name}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {error && <p className="error-text">Could not load models: {error}</p>}
    </div>
  );
}
