import { useEffect, useState } from 'react';

const AGENT_TITLES = {
  data_analyst: '1. Data Analyst Agent',
  marketing: '2. Marketing Agent',
  finance: '3. Finance Agent',
  operations: '4. Operations Agent',
  strategy: '5. Strategy Agent',
  verification: '6. Verification Agent',
};

function statusBadgeClass(status) {
  if (status === 'completed') return 'badge badge-success';
  if (status === 'running') return 'badge badge-info';
  if (status === 'failed') return 'badge badge-danger';
  return 'badge badge-warning';
}

function LiveElapsed({ startedAt }) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!startedAt) return undefined;
    const startMs = new Date(startedAt).getTime();
    const tick = () => setElapsedMs(Math.max(0, Date.now() - startMs));
    tick();
    const timer = setInterval(tick, 250);
    return () => clearInterval(timer);
  }, [startedAt]);

  return <span className="tabular">{(elapsedMs / 1000).toFixed(1)}s elapsed</span>;
}

export default function AgentPipeline({
  agents = [],
  runStatus = 'queued',
  revisionCount = 0,
  verdict = null,
}) {
  const [expandedIds, setExpandedIds] = useState({});

  const toggleExpand = (id) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <section aria-label="CrewAI six-agent execution pipeline">
      <div
        className="card"
        style={{
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <strong>Pipeline Status:</strong>{' '}
          <span className={statusBadgeClass(runStatus)}>{runStatus}</span>
          {revisionCount > 0 && (
            <span className="badge badge-warning" style={{ marginLeft: '8px' }}>
              Revision loops: {revisionCount}
            </span>
          )}
        </div>
        {verdict && (
          <div>
            <strong>Verification Verdict:</strong>{' '}
            <span className={verdict === 'approved' ? 'badge badge-success' : 'badge badge-danger'}>
              {verdict.toUpperCase()}
            </span>
          </div>
        )}
      </div>

      <ol
        style={{
          listStyle: 'none',
          padding: 0,
          margin: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        {agents.map((ag) => {
          const id = ag.id || ag.agent_name;
          const isOpen = Boolean(expandedIds[id]);
          const title = AGENT_TITLES[ag.agent_name] || `Revision Step (${ag.agent_name})`;
          const summary =
            ag.output?.summary ||
            ag.output?.executive_summary ||
            (ag.output?.verdict ? `Verdict: ${ag.output.verdict}` : null);

          return (
            <li key={id} className="card" aria-label={title}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <strong>{title}</strong>
                  <span className={statusBadgeClass(ag.status)}>{ag.status}</span>
                  {ag.context_from?.length > 0 && (
                    <span className="kpi-subvalue">
                      Context from: <code>{ag.context_from.join(', ')}</code>
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  {ag.status === 'running' && <LiveElapsed startedAt={ag.started_at} />}
                  {ag.duration_ms != null && (
                    <span className="kpi-subvalue tabular">{ag.duration_ms} ms</span>
                  )}
                  <span className="kpi-subvalue tabular">Tools: {ag.tool_calls?.length ?? 0}</span>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                    aria-expanded={isOpen}
                    onClick={() => toggleExpand(id)}
                  >
                    {isOpen ? 'Hide logs' : 'View logs'}
                  </button>
                </div>
              </div>

              {summary && (
                <p className="page-subtitle" style={{ marginTop: '8px' }}>
                  {summary}
                </p>
              )}
              {ag.error && (
                <p
                  role="alert"
                  style={{ color: 'var(--status-danger)', fontSize: '0.85rem', marginTop: '8px' }}
                >
                  Error: {ag.error}
                </p>
              )}

              {isOpen && (
                <div className="kpi-tooltip" style={{ marginTop: '12px' }}>
                  {ag.input_summary && (
                    <div style={{ marginBottom: '8px' }}>
                      <strong>Upstream Context Received:</strong> {ag.input_summary}
                    </div>
                  )}

                  <div style={{ marginBottom: '8px' }}>
                    <strong>Tool Calls ({ag.tool_calls?.length ?? 0}):</strong>
                    {ag.tool_calls?.length ? (
                      <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                        {ag.tool_calls.map((tc, idx) => (
                          <li key={idx}>
                            <code>{tc.tool}</code> — <code>{JSON.stringify(tc.args)}</code>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span> None</span>
                    )}
                  </div>

                  {ag.output && (
                    <details>
                      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                        Structured JSON Output
                      </summary>
                      <pre
                        style={{
                          overflowX: 'auto',
                          fontSize: '0.75rem',
                          marginTop: '6px',
                          maxHeight: '240px',
                        }}
                      >
                        {JSON.stringify(ag.output, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
