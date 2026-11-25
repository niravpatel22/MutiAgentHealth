import { useEffect, useState } from 'react';

const AGENT_TITLES = {
  data_analyst: '1. Data Analyst Agent',
  marketing: '2. Marketing Agent',
  finance: '3. Finance Agent',
  operations: '4. Operations Agent',
  strategy: '5. Strategy Agent',
  verification: '6. Verification Agent',
};

const TOPOLOGY_STAGES = [
  {
    id: 1,
    label: 'Stage 1 · Data Foundation',
    nodes: [
      {
        key: 'data_analyst',
        shortTitle: 'Data Analyst Agent',
        role: 'Canonical SQL KPI & Anomaly Baseline',
      },
    ],
  },
  {
    id: 2,
    label: 'Stage 2 · Domain Intelligence',
    nodes: [
      {
        key: 'marketing',
        shortTitle: 'Marketing Agent',
        role: 'Patient Mix, City & Insurance Analysis',
      },
      {
        key: 'finance',
        shortTitle: 'Finance Agent',
        role: 'Invoiced Revenue, Margin & Expense Audit',
      },
      {
        key: 'operations',
        shortTitle: 'Operations Agent',
        role: 'Wait-Time, Utilization & Inventory Risk',
      },
    ],
  },
  {
    id: 3,
    label: 'Stage 3 · Executive Synthesis',
    nodes: [
      {
        key: 'strategy',
        shortTitle: 'Strategy Agent',
        role: 'Cross-Functional KPI Action Roadmap',
      },
    ],
  },
  {
    id: 4,
    label: 'Stage 4 · Two-Layer Guardrail',
    nodes: [
      {
        key: 'verification',
        shortTitle: 'Verification Agent',
        role: 'Deterministic Tolerance (±0.5%) + LLM Gate',
      },
    ],
  },
];

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

  const agentByName = {};
  agents.forEach((ag) => {
    if (ag.agent_name && !agentByName[ag.agent_name]) {
      agentByName[ag.agent_name] = ag;
    }
  });

  const completedCount = Object.keys(AGENT_TITLES).filter(
    (k) => agentByName[k]?.status === 'completed',
  ).length;
  const progressPct =
    runStatus === 'completed' ? 100 : Math.min(95, Math.round((completedCount / 6) * 100));
  const totalTools = agents.reduce((acc, a) => acc + (a.tool_calls?.length ?? 0), 0);
  const totalDurationMs = agents.reduce((acc, a) => acc + (a.duration_ms ?? 0), 0);

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <strong>Pipeline Status:</strong>{' '}
          <span className={statusBadgeClass(runStatus)}>{runStatus}</span>
          {revisionCount > 0 && (
            <span className="badge badge-warning" style={{ marginLeft: '4px' }}>
              Revision loops: {revisionCount}
            </span>
          )}
          <span className="kpi-subvalue tabular">Agents completed: {completedCount}/6</span>
          <span className="kpi-subvalue tabular">Verified tool calls: {totalTools}</span>
          {totalDurationMs > 0 && (
            <span className="kpi-subvalue tabular">
              Execution time: {(totalDurationMs / 1000).toFixed(2)}s
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

        <div style={{ width: '100%' }}>
          <div className="progress-track" aria-hidden="true">
            <div className="progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      </div>

      {/* Interactive 4-Stage Topological Context-Chaining Graph */}
      <div
        className="card"
        style={{ marginBottom: '16px', background: 'var(--bg-subtle)' }}
        aria-label="CrewAI Context Chaining Topology"
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <strong style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            CREWAI MULTI-AGENT CONTEXT-CHAINING TOPOLOGY (CLICK ANY NODE TO INSPECT LOGS)
          </strong>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Deterministic SQL Registry → Context Chaining → Two-Layer Verification Gate
          </span>
        </div>

        <div className="topology-grid">
          {TOPOLOGY_STAGES.map((stage) => (
            <div key={stage.id} className="topology-stage">
              <div className="topology-stage-title">{stage.label}</div>
              {stage.nodes.map((node) => {
                const ag = agentByName[node.key];
                const nodeStatus = ag?.status || 'queued';
                const targetId = ag?.id || node.key;
                return (
                  <div
                    key={node.key}
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleExpand(targetId)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggleExpand(targetId);
                      }
                    }}
                    className={`topology-node status-${nodeStatus}`}
                    title={`Inspect ${node.shortTitle}`}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      <strong style={{ fontSize: '0.8rem' }}>{node.shortTitle}</strong>
                      <span className={statusBadgeClass(nodeStatus)}>{nodeStatus}</span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>
                      {node.role}
                    </div>
                    {ag && (
                      <div
                        className="tabular"
                        style={{
                          fontSize: '0.72rem',
                          color: 'var(--accent-primary)',
                          marginTop: 4,
                          fontWeight: 600,
                        }}
                      >
                        {ag.duration_ms != null ? `${ag.duration_ms} ms · ` : ''}
                        Tools: {ag.tool_calls?.length ?? 0}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
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
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}
                >
                  <strong>{title}</strong>
                  <span className={statusBadgeClass(ag.status)}>{ag.status}</span>
                  {ag.output?._execution?.model && (
                    <span className="badge badge-info" title="Executed via live CrewAI LLM">
                      LLM: {ag.output._execution.model}
                    </span>
                  )}
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
