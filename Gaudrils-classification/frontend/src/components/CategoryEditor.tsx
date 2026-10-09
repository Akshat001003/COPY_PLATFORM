import type { Category } from "../types";

interface CategoryEditorProps {
  categories: Category[];
  onChange: (categories: Category[]) => void;
}

function makeId() {
  return Math.random().toString(36).slice(2, 10);
}

export default function CategoryEditor({ categories, onChange }: CategoryEditorProps) {
  function updateRow(id: string, field: "name" | "description", value: string) {
    onChange(
      categories.map((category) =>
        category.id === id ? { ...category, [field]: value } : category
      )
    );
  }

  function setCount(count: number) {
    const next = [...categories];
    while (next.length < count) next.push({ id: makeId(), name: "", description: "" });
    while (next.length > count && next.length > 1) next.pop();
    onChange(next);
  }

  function removeRow(id: string) {
    if (categories.length <= 1) return;
    onChange(categories.filter((category) => category.id !== id));
  }

  return (
    <>
      <div className="field-row">
        <div className="field-block">
          <label className="field-label">Choice name</label>
          <input className="input" value="category" disabled />
        </div>
        <div className="field-block">
          <label className="field-label">Number of choices</label>
          <input
            className="input"
            type="number"
            min={1}
            max={20}
            value={categories.length}
            onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
          />
        </div>
      </div>

      <div className="field-block">
        <label className="field-label">Choice values</label>
        <div className="choice-values-grid">
          {categories.map((category, index) => (
            <div className="choice-value-cell" key={category.id}>
              {categories.length > 1 && (
                <button
                  type="button"
                  className="btn btn-icon choice-value-remove"
                  onClick={() => removeRow(category.id)}
                  aria-label="Remove category"
                >
                  ×
                </button>
              )}
              <input
                className="input"
                placeholder={`category_${index + 1}`}
                value={category.name}
                onChange={(e) => updateRow(category.id, "name", e.target.value)}
              />
              <div className="choice-description-field">
                <input
                  className="input"
                  placeholder="description"
                  value={category.description}
                  onChange={(e) => updateRow(category.id, "description", e.target.value)}
                />
                {category.description && (
                  <button
                    type="button"
                    className="btn btn-icon choice-description-remove"
                    onClick={() => updateRow(category.id, "description", "")}
                    aria-label={`Remove description for ${category.name || `choice ${index + 1}`}`}
                    title="Remove description"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
