import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext.jsx';

const DEMO_ACCOUNTS = [
  {
    role: 'Manager',
    email: 'e2e.manager@mediops.example',
    password: 'Sunrise#Ward99!Ops',
    summary:
      'Full workflow: Upload, Dashboard, 6-Agent Analysis, Reports, PDF, HITL Approvals, Chat',
  },
  {
    role: 'Admin',
    email: 'admin@mediops.example',
    password: 'Admin#MediOps2026!',
    summary: 'Admin Console (/admin): User & Role RBAC Management, All Analyses & Reports',
  },
  {
    role: 'Analyst',
    email: 'audit.analyst@mediops.example',
    password: 'Analyst#MediOps2026!',
    summary: 'Read-only access: Dashboard, Reports & Grounded AI Chat (403 on Upload/Approval)',
  },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleQuickFill = (acct) => {
    setError(null);
    setEmail(acct.email);
    setPassword(acct.password);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError('Please enter both email and password.');
      return;
    }
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      const dest = location.state?.from || '/dashboard';
      navigate(dest, { replace: true });
    } catch (err) {
      setError(err.message || 'Sign in failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-layout">
      <div className="card auth-card">
        <div className="brand" style={{ marginBottom: '16px' }}>
          <span className="brand-mark" aria-hidden="true">
            MO
          </span>
          <span>MediOps Intelligence</span>
        </div>
        <h1 className="page-title" style={{ fontSize: '1.3rem', marginBottom: '4px' }}>
          Sign in to MediOps Intelligence
        </h1>
        <p className="page-subtitle" style={{ marginBottom: '20px' }}>
          AI-Powered Hospital Operations &amp; Performance Intelligence.
        </p>

        {error && (
          <div
            role="alert"
            className="badge badge-danger"
            style={{
              display: 'block',
              padding: '10px 12px',
              borderRadius: '8px',
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="login-email" className="form-label">
              Email address
            </label>
            <input
              id="login-email"
              type="email"
              className="input"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="login-password" className="form-label">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="input"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%' }}
            disabled={submitting}
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <section
          aria-label="Quick-fill demo role credentials"
          className="kpi-tooltip"
          style={{ marginTop: '18px', padding: '12px' }}
        >
          <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: '8px' }}>
            Quick-Fill Demo Role Credentials (Pre-Seeded with 01_Healthcare.xlsx):
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
            {DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.role}
                type="button"
                className="btn btn-secondary"
                style={{ padding: '5px 10px', fontSize: '0.78rem' }}
                onClick={() => handleQuickFill(acct)}
              >
                Fill {acct.role}
              </button>
            ))}
          </div>
          <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '0.75rem', lineHeight: 1.45 }}>
            {DEMO_ACCOUNTS.map((acct) => (
              <li key={acct.email} style={{ marginBottom: '4px' }}>
                <strong>{acct.role}:</strong> <code>{acct.email}</code> /{' '}
                <code>{acct.password}</code>
              </li>
            ))}
          </ul>
        </section>

        <p className="page-subtitle" style={{ marginTop: '16px', textAlign: 'center' }}>
          Need a manager account? <Link to="/register">Create account</Link>
        </p>
      </div>
    </main>
  );
}
