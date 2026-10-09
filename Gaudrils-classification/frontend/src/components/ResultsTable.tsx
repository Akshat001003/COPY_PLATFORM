import { useState } from "react";

export interface ResultsColumn<T> {
  header: string;
  render: (row: T) => React.ReactNode;
}

interface ResultsTableProps<T> {
  rows: T[];
  columns: ResultsColumn<T>[];
  emptyText: string;
  rowKey: (row: T) => string;
}

const PAGE_SIZE = 20;

export default function ResultsTable<T>({
  rows,
  columns,
  emptyText,
  rowKey,
}: ResultsTableProps<T>) {
  const [viewState, setViewState] = useState({
    rows,
    expanded: false,
    page: 0,
  });
  const currentView =
    viewState.rows === rows ? viewState : { rows, expanded: false, page: 0 };

  if (rows.length === 0) {
    return <p className="muted results-empty">{emptyText}</p>;
  }

  const pageCount = Math.ceil(rows.length / PAGE_SIZE);
  const pageRows = rows.slice(
    currentView.page * PAGE_SIZE,
    (currentView.page + 1) * PAGE_SIZE
  );
  const firstRow = currentView.page * PAGE_SIZE + 1;
  const lastRow = Math.min((currentView.page + 1) * PAGE_SIZE, rows.length);

  return (
    <section className="results-section">
      <button
        type="button"
        className="results-toggle"
        aria-expanded={currentView.expanded}
        onClick={() =>
          setViewState({ ...currentView, expanded: !currentView.expanded })
        }
      >
        <span>{currentView.expanded ? "Hide results" : "Show results"}</span>
        <span className="results-count">{rows.length} rows</span>
        <span aria-hidden="true">{currentView.expanded ? "−" : "+"}</span>
      </button>

      {currentView.expanded && (
        <>
          <div className="results-table-wrap">
            <table className="results-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col.header}>{col.header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row) => (
                  <tr key={rowKey(row)}>
                    {columns.map((col) => (
                      <td key={col.header}>{col.render(row)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pageCount > 1 && (
            <div className="results-pagination">
              <span className="muted">
                Showing {firstRow}–{lastRow} of {rows.length}
              </span>
              <div className="results-pagination-controls">
                <button
                  type="button"
                  className="btn btn-outline btn-small"
                  disabled={currentView.page === 0}
                  onClick={() =>
                    setViewState({ ...currentView, page: currentView.page - 1 })
                  }
                >
                  Previous
                </button>
                <span className="muted">
                  Page {currentView.page + 1} of {pageCount}
                </span>
                <button
                  type="button"
                  className="btn btn-outline btn-small"
                  disabled={currentView.page === pageCount - 1}
                  onClick={() =>
                    setViewState({ ...currentView, page: currentView.page + 1 })
                  }
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
