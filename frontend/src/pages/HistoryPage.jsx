import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiDownloadBlob, apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';

export default function HistoryPage() {
  const { activeDatasetId, notify } = useAuth();

  const analysesQuery = useQuery({
    queryKey: ['analyses-history', activeDatasetId],
    queryFn: ({ signal }) =>
      apiRequest(
        `/analyses?page=1&page_size=50${activeDatasetId ? `&dataset_id=${activeDatasetId}` : ''}`,
        { signal },
      ),
  });

  const reportsQuery = useQuery({
    queryKey: ['reports-history', activeDatasetId],
    queryFn: ({ signal }) =>
      apiRequest(
        `/reports?page=1&page_size=50${activeDatasetId ? `&dataset_id=${activeDatasetId}` : ''}`,
        { signal },
      ),
  });

  const handleDownload = async (reportId) => {
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
      notify('PDF downloaded', 'success');
    } catch (err) {
      notify(err.message || 'Download failed', 'danger');
    }
  };

  const runs = analysesQuery.data?.items ?? [];
  const reports = reportsQuery.data?.items ?? [];
  const reportByAnalysis = Object.fromEntries(reports.map((r) => [r.analysis_id, r]));

  return (
    <section aria-labelledby="history-heading">
      <div className="page-header">
        <div>
          <h1 id="history-heading" className="page-title">
            Analysis &amp; Report History
          </h1>
          <p className="page-subtitle">
            Retrieve previous multi-agent analysis runs, revision counts, verification verdicts, and
            downloadable PDF reports.
          </p>
        </div>
      </div>

      <div className="card">
        {runs.length === 0 ? (
          <p className="page-subtitle">No previous analysis runs recorded yet.</p>
        ) : (
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Created At</th>
                  <th>Run Status</th>
                  <th>Revision Loops</th>
                  <th>Report Verdict</th>
                  <th>Confidence</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => {
                  const rep = reportByAnalysis[run.id];
                  return (
                    <tr key={run.id}>
                      <td>
                        <code>{run.id.slice(0, 8)}</code>
                      </td>
                      <td className="tabular">{new Date(run.created_at).toLocaleString()}</td>
                      <td>
                        <span
                          className={
                            run.status === 'completed'
                              ? 'badge badge-success'
                              : run.status === 'failed'
                                ? 'badge badge-danger'
                                : 'badge badge-warning'
                          }
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="tabular">{run.revision_count}</td>
                      <td>
                        {rep ? (
                          <span
                            className={
                              rep.verdict === 'approved'
                                ? 'badge badge-success'
                                : 'badge badge-danger'
                            }
                          >
                            {rep.verdict.toUpperCase()}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        {rep ? (
                          <span className="badge badge-info">{rep.confidence.toUpperCase()}</span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <Link to="/analyses" className="btn btn-secondary">
                          Agent Logs
                        </Link>
                        {rep && (
                          <>
                            <Link to="/reports" className="btn btn-secondary">
                              Open Report
                            </Link>
                            <button
                              type="button"
                              className="btn btn-primary"
                              onClick={() => handleDownload(rep.id)}
                            >
                              PDF
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
