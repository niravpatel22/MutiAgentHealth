import { useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';

const NAV_ITEMS = [
  {
    to: '/dashboard',
    label: 'Dashboard',
    section: 'Analytics & Data',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <rect x="3" y="3" width="7" height="9" rx="1.5" />
        <rect x="14" y="3" width="7" height="5" rx="1.5" />
        <rect x="14" y="12" width="7" height="9" rx="1.5" />
        <rect x="3" y="16" width="7" height="5" rx="1.5" />
      </svg>
    ),
  },
  {
    to: '/datasets',
    label: 'Datasets',
    section: 'Analytics & Data',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
        <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
      </svg>
    ),
  },
  {
    to: '/analyses',
    label: 'New Analysis & Monitor',
    section: 'Multi-Agent AI',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <circle cx="6" cy="6" r="3" />
        <circle cx="18" cy="6" r="3" />
        <circle cx="12" cy="18" r="3" />
        <path d="M8.5 7.5L10.5 15.5M15.5 7.5L13.5 15.5M9 6h6" />
      </svg>
    ),
  },
  {
    to: '/reports',
    label: 'Reports',
    section: 'Multi-Agent AI',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="13" y2="17" />
      </svg>
    ),
  },
  {
    to: '/approvals',
    label: 'Approvals (HITL)',
    section: 'Multi-Agent AI',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <polyline points="9 12 11 14 15 10" />
      </svg>
    ),
  },
  {
    to: '/chat',
    label: 'AI Chat',
    section: 'Multi-Agent AI',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    to: '/history',
    label: 'History',
    section: 'Governance',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <circle cx="12" cy="12" r="9" />
        <polyline points="12 7 12 12 15 15" />
      </svg>
    ),
  },
  {
    to: '/profile',
    label: 'Business Profile',
    section: 'Governance',
    icon: (
      <svg
        className="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M3 3v18h18" />
        <path d="M7 16l4-4 4 4 5-6" />
      </svg>
    ),
  },
];

export default function AppShell() {
  const { user, logout, activeDatasetId, setActiveDatasetId, theme, toggleTheme, toasts } =
    useAuth();
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

  const currentNav =
    NAV_ITEMS.find((item) => location.pathname.startsWith(item.to)) ||
    (location.pathname.startsWith('/admin')
      ? { label: 'Admin Console', section: 'Governance' }
      : null);

  return (
    <div className={`app-shell${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className="sidebar" aria-label="Primary navigation">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          <NavLink to="/dashboard" className="brand" title="MediOps Intelligence">
            <span className="brand-mark" aria-hidden="true">
              MO
            </span>
            <span className="brand-text">
              MediOps Intelligence
              <span className="brand-subtitle">
                AI-Powered Hospital Operations &amp; Performance Intelligence.
              </span>
            </span>
          </NavLink>
          <button
            type="button"
            className="btn btn-secondary mobile-menu-btn"
            style={{ padding: '4px 10px', fontSize: '0.78rem' }}
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? '✕ Close' : '☰ Menu'}
          </button>
        </div>

        <nav>
          <ul className={`nav-list${mobileMenuOpen ? ' mobile-open' : ''}`}>
            {NAV_ITEMS.map((item, idx) => {
              const prevSection = idx > 0 ? NAV_ITEMS[idx - 1].section : null;
              const showSection = item.section !== prevSection;
              return (
                <li key={item.to}>
                  {showSection && <div className="sidebar-section-label">{item.section}</div>}
                  <NavLink
                    to={item.to}
                    title={item.label}
                    onClick={() => setMobileMenuOpen(false)}
                    className="nav-link"
                  >
                    {item.icon}
                    <span className="nav-label">{item.label}</span>
                  </NavLink>
                </li>
              );
            })}
            {user?.role === 'admin' && (
              <li>
                <NavLink
                  to="/admin"
                  title="Admin Console"
                  onClick={() => setMobileMenuOpen(false)}
                  className="nav-link"
                >
                  <svg
                    className="nav-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                  <span className="nav-label">Admin Console</span>
                </NavLink>
              </li>
            )}
          </ul>
        </nav>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span className="status-pulse" aria-hidden="true" />
            <span style={{ fontWeight: 600, color: '#e2e8f0' }}>6-Agent CrewAI Engine Live</span>
          </div>
          <div>Deterministic KPI Registry · v1.0</div>
          <div style={{ marginTop: 2 }}>Cut-off anchor: 2026-10-31</div>
        </div>
      </aside>

      <div className="shell-main">
        <header className="topbar">
          <div className="topbar-controls">
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '0.8rem' }}
              onClick={() => setSidebarCollapsed((prev) => !prev)}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {sidebarCollapsed ? '»' : '«'}
            </button>
            {currentNav && (
              <span className="badge badge-info">
                {currentNav.section} / {currentNav.label}
              </span>
            )}
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
