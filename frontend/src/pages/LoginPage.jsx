import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext.jsx';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

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

        <p className="page-subtitle" style={{ marginTop: '16px', textAlign: 'center' }}>
          Need a manager account? <Link to="/register">Create account</Link>
        </p>
      </div>
    </main>
  );
}
