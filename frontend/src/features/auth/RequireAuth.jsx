import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

export default function RequireAuth({ allowedRoles, children }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="page-content" role="status" aria-busy="true">
        <p>Checking session…</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <section className="page-content" role="alert">
        <div className="card">
          <h1 className="page-title">Access Restricted</h1>
          <p className="page-subtitle">
            Your role (<strong>{user.role}</strong>) does not have permission to view this page.
          </p>
        </div>
      </section>
    );
  }

  return children;
}
