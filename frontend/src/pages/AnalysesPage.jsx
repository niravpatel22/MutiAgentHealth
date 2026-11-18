import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import AgentPipeline from '../components/AgentPipeline.jsx';
import { useAuth } from '../features/auth/AuthContext.jsx';

export default function AnalysesPage() {
  const { user, activeDatasetId, notify } = useAuth();
  const queryClient = useQueryClient();
  const [selectedAnalysisId, setSelectedAnalysisId] = useState(null);

  const canRun = user?.role === 'admin' || user?.role === 'manager';

  const listQuery = useQuery({
    queryKey: ['analyses', activeDatasetId],
    queryFn: ({ signal }) =>
      apiRequest(
        `/analyses?page=1&page_size=20${activeDatasetId ? `&dataset_id=${activeDatasetId}` : ''}`,
        { signal },
      ),
    enabled: Boolean(user),
  });

  const runs = listQuery.data?.items ?? [];
  const effectiveAnalysisId = selectedAnalysisId || runs[0]?.id || null;

  const detailQuery = useQuery({
    queryKey: ['analysis-detail', effectiveAnalysisId],
    queryFn: ({ signal }) => apiRequest(`/analyses/${effectiveAnalysisId}`, { signal }),
    enabled: Boolean(effectiveAnalysisId),
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      return st === 'queued' || st === 'running' ? 2000 : false;
    },
  });

  const startMutation = useMutation({
    mutationFn: () =>
      apiRequest('/analyses?run_inline=true', {
        method: 'POST',
        body: { dataset_id: activeDatasetId },
      }),
    onSuccess: (created) => {
      setSelectedAnalysisId(created.id);
      queryClient.invalidateQueries({ queryKey: ['analyses'] });
      notify('Multi-agent analysis started', 'success');
    },
    onError: (err) => {
      notify(err.message || 'Could not start analysis', 'danger');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id) => apiRequest(`/analyses/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis-detail', effectiveAnalysisId] });
      queryClient.invalidateQueries({ queryKey: ['analyses'] });
      notify('Analysis cancelled', 'info');
    },
  });

  const detail = detailQuery.data;
  const isActive = detail?.status === 'queued' || detail?.status === 'running';

  return (
    <section aria-labelledby="analyses-heading">
      <div className="page-header">
        <div>
          <h1 id="analyses-heading" className="page-title">
            CrewAI Multi-Agent Analysis &amp; Live Monitor
          </h1>
          <p className="page-subtitle">
            Data Analyst → Marketing → Finance → Operations → Strategy → Verification (with up to 2
            revision loops). Polls every 2 seconds while active.
          </p>
        </div>

        <div className="topbar-controls">
          {canRun && activeDatasetId && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={startMutation.isPending || isActive}
              onClick={() => startMutation.mutate()}
            >
              {startMutation.isPending ? 'Enqueueing…' : 'Run New Analysis'}
            </button>
          )}
          {canRun && isActive && detail && (
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => cancelMutation.mutate(detail.id)}
            >
              Cancel Run
            </button>
          )}
          {detail?.report_id && (
            <Link to="/reports" className="btn btn-secondary">
              View Generated Report
            </Link>
          )}
        </div>
      </div>

      {runs.length > 0 && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <label htmlFor="run-selector" className="form-label" style={{ marginRight: '12px' }}>
            Select Analysis Run:
          </label>
          <select
            id="run-selector"
            className="select tabular"
            value={effectiveAnalysisId || ''}
            onChange={(e) => setSelectedAnalysisId(e.target.value || null)}
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id.slice(0, 8)} — {r.status.toUpperCase()} (
                {new Date(r.created_at).toLocaleString()})
              </option>
            ))}
          </select>
        </div>
      )}

      {detail ? (
        <AgentPipeline
          agents={detail.agents}
          runStatus={detail.status}
          revisionCount={detail.revision_count}
          verdict={detail.verdict}
        />
      ) : (
        <div className="card">
          <p className="page-subtitle">
            No analysis runs yet for this dataset. Click <strong>Run New Analysis</strong> to launch
            the 6-agent CrewAI pipeline.
          </p>
        </div>
      )}
    </section>
  );
}
