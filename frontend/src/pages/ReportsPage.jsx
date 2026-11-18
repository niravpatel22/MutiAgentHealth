import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiDownloadBlob, apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';
import { formatMetricValue } from '../utils/format.js';

const SECTION_META = [
  ['business_performance_insights', '1. Business Performance Insights'],
  ['revenue_and_expense_analysis', '2. Revenue & Expense Analysis'],
  ['customer_behavior_analysis', '3. Customer (Patient) Behavior Analysis'],
  ['operational_problems', '4. Operational Problems'],
  ['business_risk_identification', '5. Business Risk Identification'],
  ['growth_opportunities', '6. Growth Opportunities'],
  ['strategic_recommendations', '7. Strategic Recommendations'],
  ['actionable_business_improvement_plan', '8. Actionable Business Improvement Plan'],
];

export default function ReportsPage() {
  const { activeDatasetId, notify } = useAuth();
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [activeMetricKey, setActiveMetricKey] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const listQuery = useQuery({
    queryKey: ['reports', activeDatasetId],
    queryFn: ({ signal }) =>
      apiRequest(
        `/reports?page=1&page_size=20${activeDatasetId ? `&dataset_id=${activeDatasetId}` : ''}`,
        { signal },
      ),
  });

  const reports = listQuery.data?.items ?? [];
  const effectiveReportId = selectedReportId || reports[0]?.id || null;

  const detailQuery = useQuery({
    queryKey: ['report-detail', effectiveReportId],
    queryFn: ({ signal }) => apiRequest(`/reports/${effectiveReportId}`, { signal }),
    enabled: Boolean(effectiveReportId),
  });

  const handleDownloadPdf = async (reportId) => {
    setDownloading(true);
    try {
      const blob = await apiDownloadBlob(`/reports/${reportId}/pdf`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `careops_report_${reportId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      notify('PDF report downloaded', 'success');
    } catch (err) {
      notify(err.message || 'Failed to download PDF', 'danger');
    } finally {
      setDownloading(false);
    }
  };

  const report = detailQuery.data;
  const content = report?.content || {};
  const sections = content.sections || {};
  const snapshot = report?.metrics_snapshot || {};
  const verification = report?.verification || {};
  const det = verification.deterministic || {};
  const activeMetric = activeMetricKey ? snapshot[activeMetricKey] : null;

  return (
    <section aria-labelledby="reports-heading">
      <div className="page-header">
        <div>
          <h1 id="reports-heading" className="page-title">
            Verified Business Intelligence Reports
          </h1>
          <p className="page-subtitle">
            Eight-section executive reports with two-layer verification, metric evidence chips, and
            reproducible PDF export.
          </p>
        </div>

        {report && (
          <div className="topbar-controls">
            <button
              type="button"
              className="btn btn-primary"
              disabled={downloading}
              onClick={() => handleDownloadPdf(report.id)}
            >
              {downloading ? 'Preparing PDF…' : 'Download PDF'}
            </button>
            <Link to="/approvals" className="btn btn-secondary">
              Review Approvals (HITL)
            </Link>
          </div>
        )}
      </div>

      {reports.length === 0 ? (
        <div className="card">
          <p className="page-subtitle" style={{ marginBottom: '12px' }}>
            No reports generated yet. Run a multi-agent analysis on the New Analysis page first.
          </p>
          <Link to="/analyses" className="btn btn-primary">
            Go to New Analysis
          </Link>
        </div>
      ) : (
        <>
          <div className="card" style={{ marginBottom: '20px' }}>
            <label htmlFor="report-selector" className="form-label" style={{ marginRight: '12px' }}>
              Select Report:
            </label>
            <select
              id="report-selector"
              className="select tabular"
              value={effectiveReportId || ''}
              onChange={(e) => setSelectedReportId(e.target.value || null)}
            >
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 8)} — Verdict: {r.verdict.toUpperCase()} · Confidence:{' '}
                  {r.confidence.toUpperCase()} ({new Date(r.created_at).toLocaleString()})
                </option>
              ))}
            </select>
          </div>

          {report && (
            <>
              {/* ---- Verdict & Verification Summary Banner ---- */}
              <div className="card" style={{ marginBottom: '20px' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <strong>Verification Verdict:</strong>
                    <span
                      className={
                        report.verdict === 'approved' ? 'badge badge-success' : 'badge badge-danger'
                      }
                    >
                      {report.verdict.toUpperCase()}
                    </span>
                    <strong>Confidence:</strong>
                    <span className="badge badge-info">{report.confidence.toUpperCase()}</span>
                  </div>
                  <div className="kpi-subvalue tabular">
                    Deterministic checks: {det.passed ?? 0}/{det.checked ?? 0} passed · Failed:{' '}
                    {det.failed?.length ?? 0} · Unsupported numeric claims:{' '}
                    {det.unsupported?.length ?? 0} · Revisions: {verification.revision_count ?? 0}
                  </div>
                </div>

                {content.executive_summary && (
                  <p style={{ marginTop: '12px', marginBottom: 0 }}>
                    <strong>Executive Summary:</strong> {content.executive_summary}
                  </p>
                )}
              </div>

              {/* ---- Active Metric Definition Popover ---- */}
              {activeMetric && (
                <div
                  className="card"
                  role="region"
                  aria-label="Metric definition inspector"
                  style={{ marginBottom: '20px', borderColor: 'var(--accent-primary)' }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <strong>
                      Metric Evidence: <code>{activeMetric.key}</code>
                    </strong>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                      onClick={() => setActiveMetricKey(null)}
                    >
                      Close
                    </button>
                  </div>
                  <p className="page-subtitle" style={{ marginTop: '6px' }}>
                    <strong>Snapshot Value:</strong>{' '}
                    <span className="tabular">
                      {formatMetricValue(activeMetric.value, activeMetric.unit)}
                    </span>{' '}
                    · <strong>Basis:</strong> <code>{activeMetric.basis}</code> ·{' '}
                    <strong>Definition:</strong> {activeMetric.definition}
                  </p>
                </div>
              )}

              {/* ---- Eight Report Sections ---- */}
              <div className="charts-grid" style={{ marginBottom: '24px' }}>
                {SECTION_META.map(([key, title]) => (
                  <article key={key} className="card">
                    <h2 style={{ margin: '0 0 8px', fontSize: '1.02rem' }}>{title}</h2>
                    <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
                      {sections[key] || 'Not available'}
                    </p>
                  </article>
                ))}
              </div>

              {/* ---- Verified Findings with Evidence Chips ---- */}
              <div className="card" style={{ marginBottom: '24px' }}>
                <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>
                  Verified Analytical Findings &amp; Metric Evidence Chips
                </h2>
                <ul style={{ margin: 0, paddingLeft: '18px' }}>
                  {(content.findings || []).map((f, idx) => (
                    <li key={idx} style={{ marginBottom: '12px' }}>
                      <div>
                        {f.statement}{' '}
                        <span className="badge badge-info">{f.confidence || 'high'}</span>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          gap: '6px',
                          flexWrap: 'wrap',
                          marginTop: '6px',
                        }}
                      >
                        {(f.metric_keys || []).map((mkey) => (
                          <button
                            key={mkey}
                            type="button"
                            className="btn btn-secondary"
                            style={{ padding: '2px 8px', fontSize: '0.74rem' }}
                            onClick={() => setActiveMetricKey(mkey)}
                          >
                            <code>{mkey}</code>
                          </button>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {/* ---- Recommendations Summary ---- */}
              <div className="card">
                <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>
                  Recommendations &amp; Approval Status
                </h2>
                {report.recommendations?.length ? (
                  <div className="data-table-wrapper">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Title</th>
                          <th>Action Type</th>
                          <th>Evidence Metric Keys</th>
                          <th>HITL Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.recommendations.map((rec) => (
                          <tr key={rec.id}>
                            <td>
                              <strong>{rec.title}</strong>
                              <div className="page-subtitle">{rec.rationale}</div>
                            </td>
                            <td>
                              <span className="badge badge-info">{rec.action_type}</span>
                            </td>
                            <td>
                              {(rec.evidence_metric_keys || []).map((mkey) => (
                                <button
                                  key={mkey}
                                  type="button"
                                  className="btn btn-secondary"
                                  style={{
                                    padding: '2px 6px',
                                    fontSize: '0.72rem',
                                    marginRight: '4px',
                                  }}
                                  onClick={() => setActiveMetricKey(mkey)}
                                >
                                  <code>{mkey}</code>
                                </button>
                              ))}
                            </td>
                            <td>
                              <span
                                className={
                                  rec.status === 'approved'
                                    ? 'badge badge-success'
                                    : rec.status === 'rejected'
                                      ? 'badge badge-danger'
                                      : 'badge badge-warning'
                                }
                              >
                                {rec.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="page-subtitle">
                    No recommendations queued for approval on this report.
                  </p>
                )}
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
