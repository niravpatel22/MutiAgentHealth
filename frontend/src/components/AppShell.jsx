import { useEffect, useMemo } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/datasets', label: 'Datasets' },
  { to: '/analyses', label: 'New Analysis & Monitor' },
  { to: '/reports', label: 'Reports' },
  { to: '/approvals', label: 'Approvals (HITL)' },
  { to: '/chat', label: 'AI Chat' },
  { to: '/history', label: 'History' },
  { to: '/profile', label: 'Business Profile' },
];

export default function AppShell() {
  const { user, logout, activeDatasetId, setActiveDatasetId, theme, toggleTheme, toasts } =
    useAuth();

  const datasetsQuery = useQuery({
    queryKey: ['datasets'],
    queryFn: ({ signal }) => apiRequest('/datasets?page=1&page_size=50', { signal }),
    enabled: Boolean(user),
  });

  const datasets = useMemo(() => datasetsQuery.data?.items ?? [], [datasetsQuery.data]);

  useEffect(() => {
    if (!activeDatasetId && datasets.length > 0) {
      setActiveDatasetId(datasets[0].id);
    }
  }, [activeDatasetId, datasets, setActiveDatasetId]);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <NavLink to="/dashboard" className="brand">
          <span className="brand-mark" aria-hidden="true">
            MO
          </span>
          <span>
            MediOps Intelligence
            <span className="brand-subtitle">
              AI-Powered Hospital Operations &amp; Performance Intelligence.
            </span>
          </span>
        </NavLink>

        <nav>
          <ul className="nav-list">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} className="nav-link">
                  {item.label}
                </NavLink>
              </li>
            ))}
            {user?.role === 'admin' && (
              <li>
                <NavLink to="/admin" className="nav-link">
                  Admin Console
                </NavLink>
              </li>
            )}
          </ul>
        </nav>
      </aside>

      <div className="shell-main">
        <header className="topbar">
          <div className="topbar-controls">
            <label htmlFor="active-dataset-select" className="form-label" style={{ margin: 0 }}>
              Active Dataset:
            </label>
            <select
              id="active-dataset-select"
              className="select"
              value={activeDatasetId || ''}
              onChange={(e) => setActiveDatasetId(e.target.value || null)}
              aria-label="Active dataset"
            >
              {datasets.length === 0 ? (
                <option value="">No dataset uploaded</option>
              ) : (
                datasets.map((ds) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name} ({ds.period_start} to {ds.period_end})
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="topbar-controls">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={toggleTheme}
              aria-label="Toggle color theme"
            >
              {theme === 'light' ? 'Dark mode' : 'Light mode'}
            </button>
            {user && (
              <>
                <span className="badge badge-info" title="Role">
                  {user.role}
                </span>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {user.email}
                </span>
                <button type="button" className="btn btn-secondary" onClick={logout}>
                  Sign out
                </button>
              </>
            )}
          </div>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </div>

      {toasts.length > 0 && (
        <div className="toast-region" role="status" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className="toast">
              {t.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
