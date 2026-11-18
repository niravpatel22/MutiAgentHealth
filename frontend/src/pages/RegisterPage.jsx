import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext.jsx';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [details, setDetails] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setDetails([]);
    if (password.length < 12) {
      setError('Password must be at least 12 characters long.');
      return;
    }
    setSubmitting(true);
    try {
      await register(email.trim(), password);
      navigate('/profile', { replace: true });
    } catch (err) {
      setError(err.message || 'Registration failed');
      if (Array.isArray(err.details?.password)) {
        setDetails(err.details.password);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-layout">
      <div className="card auth-card">
        <h1 className="page-title" style={{ fontSize: '1.3rem', marginBottom: '4px' }}>
          Create a Manager Account
        </h1>
        <p className="page-subtitle" style={{ marginBottom: '20px' }}>
          Set up your Hospital Operations Intelligence workspace
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
            <div>{error}</div>
            {details.length > 0 && (
              <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
                {details.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="register-email" className="form-label">
              Work email
            </label>
            <input
              id="register-email"
              type="email"
              className="input"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="register-password" className="form-label">
              Password (12+ characters, not containing email name)
            </label>
            <input
              id="register-password"
              type="password"
              className="input"
              autoComplete="new-password"
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
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="page-subtitle" style={{ marginTop: '16px', textAlign: 'center' }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
