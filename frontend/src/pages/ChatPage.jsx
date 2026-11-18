import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';

const SUGGESTED_QUESTIONS = [
  'What is our invoiced net revenue and approved-expense margin?',
  'How many appointments were completed vs scheduled, and what is the average wait time?',
  'Which inventory items are at risk of low stock or expiring within 90 days?',
  'What is our patient repeat-visit rate and doctor load?',
  'What is our marketing campaign ROI and ad spend?',
  'How much cash was collected from Partially Paid invoices?',
];

export default function ChatPage() {
  const { activeDatasetId, notify } = useAuth();
  const queryClient = useQueryClient();
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [question, setQuestion] = useState('');

  const sessionsQuery = useQuery({
    queryKey: ['chat-sessions', activeDatasetId],
    queryFn: ({ signal }) =>
      apiRequest(
        `/chat/sessions?page=1&page_size=20${activeDatasetId ? `&dataset_id=${activeDatasetId}` : ''}`,
        { signal },
      ),
    enabled: Boolean(activeDatasetId),
  });

  const sessions = sessionsQuery.data?.items ?? [];
  const effectiveSessionId = selectedSessionId || sessions[0]?.id || null;

  const messagesQuery = useQuery({
    queryKey: ['chat-messages', effectiveSessionId],
    queryFn: ({ signal }) =>
      apiRequest(`/chat/sessions/${effectiveSessionId}/messages`, { signal }),
    enabled: Boolean(effectiveSessionId),
  });

  const createSessionMutation = useMutation({
    mutationFn: () =>
      apiRequest('/chat/sessions', {
        method: 'POST',
        body: { dataset_id: activeDatasetId, title: 'Hospital Operations Q&A' },
      }),
    onSuccess: (created) => {
      setSelectedSessionId(created.id);
      queryClient.invalidateQueries({ queryKey: ['chat-sessions', activeDatasetId] });
    },
  });

  const sendMessageMutation = useMutation({
    mutationFn: async (text) => {
      let sessionId = effectiveSessionId;
      if (!sessionId) {
        const created = await apiRequest('/chat/sessions', {
          method: 'POST',
          body: { dataset_id: activeDatasetId, title: text.slice(0, 60) },
        });
        sessionId = created.id;
        setSelectedSessionId(sessionId);
        queryClient.invalidateQueries({ queryKey: ['chat-sessions', activeDatasetId] });
      }
      return apiRequest(`/chat/sessions/${sessionId}/messages`, {
        method: 'POST',
        body: { content: text },
      });
    },
    onSuccess: () => {
      setQuestion('');
      queryClient.invalidateQueries({ queryKey: ['chat-messages'] });
    },
    onError: (err) => {
      notify(err.message || 'Could not send question', 'danger');
    },
  });

  if (!activeDatasetId) {
    return (
      <section className="card">
        <h1 className="page-title">No Dataset Selected</h1>
        <p className="page-subtitle" style={{ marginBottom: '16px' }}>
          Select or upload a dataset first to ask grounded business questions.
        </p>
        <Link to="/datasets" className="btn btn-primary">
          Go to Datasets
        </Link>
      </section>
    );
  }

  const messages = messagesQuery.data ?? [];

  return (
    <section aria-labelledby="chat-heading">
      <div className="page-header">
        <div>
          <h1 id="chat-heading" className="page-title">
            Grounded Business Q&amp;A Assistant
          </h1>
          <p className="page-subtitle">
            CrewAI single-agent assistant using the read-only metrics tools. Answers cite exact{' '}
            <code>metric_keys</code> and state honestly when the dataset cannot answer a question.
          </p>
        </div>

        <div className="topbar-controls">
          {sessions.length > 0 && (
            <select
              aria-label="Select chat session"
              className="select"
              value={effectiveSessionId || ''}
              onChange={(e) => setSelectedSessionId(e.target.value || null)}
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title} ({new Date(s.created_at).toLocaleTimeString()})
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            disabled={createSessionMutation.isPending}
            onClick={() => createSessionMutation.mutate()}
          >
            New Session
          </button>
        </div>
      </div>

      {/* Suggested prompts */}
      <div className="card" style={{ marginBottom: '16px' }}>
        <div className="form-label" style={{ marginBottom: '8px' }}>
          Quick Questions (including data-limitation trap checks):
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {SUGGESTED_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '0.78rem', padding: '5px 10px' }}
              disabled={sendMessageMutation.isPending}
              onClick={() => sendMessageMutation.mutate(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Transcript */}
      <div
        className="card"
        role="log"
        aria-label="Conversation transcript"
        style={{
          marginBottom: '16px',
          minHeight: '300px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        {messages.length === 0 ? (
          <p className="page-subtitle">
            Ask a question about hospital appointments, billing revenue, expenses, patient segments,
            or medicine inventory.
          </p>
        ) : (
          messages.map((m) => (
            <article
              key={m.id}
              style={{
                alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '82%',
                background: m.role === 'user' ? 'var(--accent-soft)' : 'var(--bg-subtle)',
                border: '1px solid var(--border-hairline)',
                borderRadius: '12px',
                padding: '10px 14px',
              }}
            >
              <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '4px' }}>
                {m.role === 'user' ? 'You' : 'MediOps Q&A Agent'}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.92rem' }}>{m.content}</div>
              {m.cited_metric_keys?.length > 0 && (
                <div
                  style={{
                    display: 'flex',
                    gap: '6px',
                    flexWrap: 'wrap',
                    marginTop: '8px',
                  }}
                  aria-label="Cited metric keys"
                >
                  {m.cited_metric_keys.map((key) => (
                    <span key={key} className="badge badge-info">
                      <code>{key}</code>
                    </span>
                  ))}
                </div>
              )}
            </article>
          ))
        )}
      </div>

      {/* Input form */}
      <form
        className="card"
        style={{ display: 'flex', gap: '12px' }}
        onSubmit={(e) => {
          e.preventDefault();
          if (!question.trim()) return;
          sendMessageMutation.mutate(question.trim());
        }}
      >
        <input
          aria-label="Ask a business question"
          className="input"
          style={{ flex: 1 }}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about revenue, expenses, wait times, no-shows, or inventory…"
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={sendMessageMutation.isPending || !question.trim()}
        >
          {sendMessageMutation.isPending ? 'Thinking…' : 'Send'}
        </button>
      </form>
    </section>
  );
}
