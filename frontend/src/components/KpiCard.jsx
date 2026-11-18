import { useState } from 'react';
import { formatINR, formatMetricValue } from '../utils/format.js';

export default function KpiCard({ card }) {
  const [showDefinition, setShowDefinition] = useState(false);
  const {
    key,
    label,
    value,
    unit,
    definition,
    basis,
    mom_change_pct: momChangePct,
    latest_month: latestMonth,
    previous_month: previousMonth,
  } = card;

  const primaryText = formatMetricValue(value, unit, { compact: unit === 'INR' });
  const secondaryText = unit === 'INR' ? formatINR(value, { precise: true }) : null;

  let badgeClass = 'badge badge-info';
  if (typeof momChangePct === 'number') {
    const lowerIsBetter =
      key.includes('no_show') ||
      key.includes('wait') ||
      key.includes('expenses') ||
      key.includes('cancelled');
    const isGood = lowerIsBetter ? momChangePct <= 0 : momChangePct >= 0;
    badgeClass = isGood ? 'badge badge-success' : 'badge badge-warning';
  }

  const tooltipId = `kpi-def-${key.replace(/\./g, '-')}`;

  return (
    <article className="card kpi-card" aria-label={label}>
      <div className="kpi-header">
        <span className="kpi-label">{label}</span>
        <button
          type="button"
          className="btn btn-secondary"
          style={{ padding: '2px 8px', fontSize: '0.74rem' }}
          aria-expanded={showDefinition}
          aria-controls={tooltipId}
          onClick={() => setShowDefinition((v) => !v)}
          title="Show metric definition and basis"
        >
          Info
        </button>
      </div>

      <div className="kpi-value tabular">{primaryText}</div>
      {secondaryText && <div className="kpi-subvalue tabular">{secondaryText}</div>}

      <div className="kpi-footer">
        {typeof momChangePct === 'number' ? (
          <span className={badgeClass} title={`Change from ${previousMonth} to ${latestMonth}`}>
            {momChangePct > 0 ? `+${momChangePct.toFixed(2)}%` : `${momChangePct.toFixed(2)}%`} MoM
          </span>
        ) : (
          <span className="badge badge-info">Snapshot</span>
        )}
        <code style={{ fontSize: '0.72rem' }}>{key}</code>
      </div>

      {showDefinition && (
        <div
          id={tooltipId}
          role="region"
          aria-label={`${label} definition`}
          className="kpi-tooltip"
        >
          <div>
            <strong>Definition:</strong> {definition}
          </div>
          <div>
            <strong>Basis:</strong> <code>{basis}</code>
          </div>
        </div>
      )}
    </article>
  );
}
