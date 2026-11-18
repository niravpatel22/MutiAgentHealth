import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';

export default function AdminPage() {
  const { user: currentUser, notify } = useAuth();
  const queryClient = useQueryClient();

  const usersQuery = useQuery({
    queryKey: ['admin-users'],
    queryFn: ({ signal }) => apiRequest('/admin/users?page=1&page_size=50', { signal }),
  });

  const analysesQuery = useQuery({
    queryKey: ['admin-analyses'],
    queryFn: ({ signal }) => apiRequest('/admin/analyses?page=1&page_size=50', { signal }),
  });

  const reportsQuery = useQuery({
    queryKey: ['admin-reports'],
    queryFn: ({ signal }) => apiRequest('/admin/reports?page=1&page_size=50', { signal }),
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, payload }) =>
      apiRequest(`/admin/users/${userId}`, { method: 'PATCH', body: payload }),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      notify(`Updated ${updated.email} (${updated.role})`, 'success');
    },
    onError: (err) => {
      notify(err.message || 'Update failed', 'danger');
    },
  });

  const users = usersQuery.data?.items ?? [];
  const analyses = analysesQuery.data?.items ?? [];
  const reports = reportsQuery.data?.items ?? [];

  return (
    <section aria-labelledby="admin-heading">
      <div className="page-header">
        <div>
          <h1 id="admin-heading" className="page-title">
            Admin Governance Console
          </h1>
          <p className="page-subtitle">
            Manage user roles and account status, and audit all analysis runs and generated BI
            reports across the hospital.
          </p>
        </div>
      </div>

      {/* ---- User Management ---- */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>
          Users &amp; Role-Based Access Control ({users.length})
        </h2>
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <tr key={u.id}>
                    <td>
                      <strong>{u.email}</strong>
                    </td>
                    <td>
                      <select
                        aria-label={`Role for ${u.email}`}
                        className="select"
                        disabled={isSelf || updateUserMutation.isPending}
                        value={u.role}
                        onChange={(e) =>
                          updateUserMutation.mutate({
                            userId: u.id,
                            payload: { role: e.target.value },
                          })
                        }
                      >
                        <option value="admin">admin</option>
                        <option value="manager">manager</option>
                        <option value="analyst">analyst</option>
                      </select>
                    </td>
                    <td>
                      <span className={u.is_active ? 'badge badge-success' : 'badge badge-danger'}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="tabular">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={isSelf || updateUserMutation.isPending}
                        onClick={() =>
                          updateUserMutation.mutate({
                            userId: u.id,
                            payload: { is_active: !u.is_active },
                          })
                        }
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ---- All Analysis Runs ---- */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>
          All Analysis Runs ({analyses.length})
        </h2>
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Analysis ID</th>
                <th>Dataset ID</th>
                <th>Status</th>
                <th>Revision Loops</th>
                <th>Created At</th>
              </tr>
            </thead>
            <tbody>
              {analyses.map((a) => (
                <tr key={a.id}>
                  <td>
                    <code>{a.id.slice(0, 8)}</code>
                  </td>
                  <td>
                    <code>{a.dataset_id.slice(0, 8)}</code>
                  </td>
                  <td>
                    <span className="badge badge-info">{a.status}</span>
                  </td>
                  <td className="tabular">{a.revision_count}</td>
                  <td className="tabular">{new Date(a.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ---- All Generated Reports ---- */}
      <div className="card">
        <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>
          All Generated BI Reports ({reports.length})
        </h2>
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Analysis ID</th>
                <th>Verdict</th>
                <th>Confidence</th>
                <th>Created At</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id}>
                  <td>
                    <code>{r.id.slice(0, 8)}</code>
                  </td>
                  <td>
                    <code>{r.analysis_id.slice(0, 8)}</code>
                  </td>
                  <td>
                    <span
                      className={
                        r.verdict === 'approved' ? 'badge badge-success' : 'badge badge-danger'
                      }
                    >
                      {r.verdict.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <span className="badge badge-info">{r.confidence.toUpperCase()}</span>
                  </td>
                  <td className="tabular">{new Date(r.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
