import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';
import { formatMetricValue } from '../utils/format.js';

export function ApprovalCard({ rec, canDecide, onDecide, isPending }) {
  const [comment, setComment] = useState('');

  return (
    <article className="card" aria-label={rec.title} style={{ marginBottom: '16px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '12px',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: '1.05rem' }}>{rec.title}</h2>
          <p className="page-subtitle" style={{ margin: 0 }}>
            {rec.rationale}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="badge badge-info">{rec.action_type}</span>
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
        </div>
      </div>

      {/* Evidence metrics */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          flexWrap: 'wrap',
          marginTop: '12px',
        }}
      >
        {(rec.evidence_metrics?.length ? rec.evidence_metrics : rec.evidence_metric_keys || []).map(
          (item) => {
            const isObj = typeof item === 'object' && item !== null;
            const key = isObj ? item.key : item;
            const valText = isObj ? `: ${formatMetricValue(item.value, item.unit)}` : '';
            return (
              <span
                key={key}
                className="badge badge-info"
                title={isObj ? `${item.definition} (basis: ${item.basis})` : key}
              >
                <code>{key}</code>
                {valText}
              </span>
            );
          },
        )}
      </div>

      {/* Manager / Admin Decision Controls */}
      {canDecide ? (
        <div
          style={{
            marginTop: '16px',
            borderTop: '1px solid var(--border-hairline)',
            paddingTop: '12px',
          }}
        >
          <div className="form-group" style={{ marginBottom: '10px' }}>
            <label htmlFor={`comment-${rec.id}`} className="form-label">
              Governance Decision Comment
            </label>
            <input
              id={`comment-${rec.id}`}
              className="input"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Record reason for approving or rejecting this proposal…"
            />
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={isPending}
              onClick={() => onDecide(rec.id, 'approved', comment)}
            >
              Approve Proposal
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={isPending}
              onClick={() => onDecide(rec.id, 'rejected', comment)}
            >
              Reject Proposal
            </button>
          </div>
        </div>
      ) : (
        <p className="page-subtitle" style={{ marginTop: '12px' }}>
          Read-only view: only <strong>manager</strong> and <strong>admin</strong> roles can record
          approval decisions.
        </p>
      )}

      {/* Approval Audit Trail */}
      {rec.approval_history?.length > 0 && (
        <div className="kpi-tooltip" style={{ marginTop: '12px' }}>
          <strong>Approval History (Audit Trail — Recorded Decision Only):</strong>
          <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
            {rec.approval_history.map((h) => (
              <li key={h.id}>
                <strong>{h.decision.toUpperCase()}</strong> at{' '}
                <span className="tabular">{new Date(h.decided_at).toLocaleString()}</span>
                {h.comment ? ` — "${h.comment}"` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

export default function ApprovalsPage() {
  const { user, notify } = useAuth();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('');

  const canDecide = user?.role === 'admin' || user?.role === 'manager';

  const recsQuery = useQuery({
    queryKey: ['recommendations', statusFilter],
    queryFn: ({ signal }) =>
      apiRequest(
        `/recommendations?page=1&page_size=50${statusFilter ? `&status=${statusFilter}` : ''}`,
        { signal },
      ),
  });

  const decisionMutation = useMutation({
    mutationFn: ({ id, decision, comment }) =>
      apiRequest(`/recommendations/${id}/decision`, {
        method: 'POST',
        body: { decision, comment },
      }),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
      queryClient.invalidateQueries({ queryKey: ['report-detail'] });
      notify(`Recommendation ${updated.status}`, 'success');
    },
    onError: (err) => {
      notify(err.message || 'Decision failed', 'danger');
    },
  });

  const items = recsQuery.data?.items ?? [];

  return (
    <section aria-labelledby="approvals-heading">
      <div className="page-header">
        <div>
          <h1 id="approvals-heading" className="page-title">
            Human-in-the-Loop (HITL) Governance &amp; Approvals
          </h1>
          <p className="page-subtitle">
            Consequential recommendations (budget, staffing, purchasing, vendor) from verified
            reports require human approval. Decisions are recorded in <code>approval_history</code>;
            nothing is executed automatically.
          </p>
        </div>

        <div className="topbar-controls">
          <label htmlFor="status-filter" className="form-label" style={{ margin: 0 }}>
            Status:
          </label>
          <select
            id="status-filter"
            className="select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="pending_approval">Pending Approval</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="card">
          <p className="page-subtitle">No recommendations match the current filter.</p>
        </div>
      ) : (
        items.map((rec) => (
          <ApprovalCard
            key={rec.id}
            rec={rec}
            canDecide={canDecide}
            isPending={decisionMutation.isPending}
            onDecide={(id, decision, comment) => decisionMutation.mutate({ id, decision, comment })}
          />
        ))
      )}
    </section>
  );
}
