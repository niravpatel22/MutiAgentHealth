import { useState } from 'react';

/**
 * Accessible chart wrapper with a WCAG 2.1 AA data-table fallback toggle.
 */
export default function ChartCard({ title, subtitle, columns = [], rows = [], children }) {
  const [showTable, setShowTable] = useState(false);

  return (
    <section className="card" aria-label={title}>
      <div className="page-header" style={{ marginBottom: '12px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.02rem', fontWeight: 600 }}>{title}</h2>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {rows.length > 0 && (
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '4px 10px', fontSize: '0.78rem' }}
            aria-expanded={showTable}
            onClick={() => setShowTable((v) => !v)}
          >
            {showTable ? 'Chart view' : 'Table view'}
          </button>
        )}
      </div>

      {showTable ? (
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.key} scope="col">
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx}>
                  {columns.map((col) => (
                    <td key={col.key} className="tabular">
                      {col.format ? col.format(row[col.key], row) : String(row[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ width: '100%', height: 280 }}>{children}</div>
      )}
    </section>
  );
}
