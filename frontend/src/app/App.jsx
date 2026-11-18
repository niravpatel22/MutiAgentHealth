import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AppShell from '../components/AppShell.jsx';
import ErrorBoundary from '../components/ErrorBoundary.jsx';
import { AuthProvider } from '../features/auth/AuthContext.jsx';
import RequireAuth from '../features/auth/RequireAuth.jsx';
import LoginPage from '../pages/LoginPage.jsx';
import RegisterPage from '../pages/RegisterPage.jsx';

const DashboardPage = lazy(() => import('../pages/DashboardPage.jsx'));
const DatasetsPage = lazy(() => import('../pages/DatasetsPage.jsx'));
const BusinessProfilePage = lazy(() => import('../pages/BusinessProfilePage.jsx'));
const AnalysesPage = lazy(() => import('../pages/AnalysesPage.jsx'));
const ReportsPage = lazy(() => import('../pages/ReportsPage.jsx'));
const ApprovalsPage = lazy(() => import('../pages/ApprovalsPage.jsx'));
const PlaceholderPage = lazy(() => import('../pages/PlaceholderPage.jsx'));

const defaultQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div className="page-content" role="status" aria-busy="true">
          Loading view…
        </div>
      }
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/profile" element={<BusinessProfilePage />} />
          <Route path="/analyses" element={<AnalysesPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route
            path="/chat"
            element={<PlaceholderPage title="Grounded Business Q&A Chat" phase="Phase 6" />}
          />
          <Route
            path="/history"
            element={<PlaceholderPage title="Analysis History" phase="Phase 6" />}
          />
          <Route
            path="/admin"
            element={
              <RequireAuth allowedRoles={['admin']}>
                <PlaceholderPage title="Admin Console" phase="Phase 6" />
              </RequireAuth>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App({ queryClient = defaultQueryClient }) {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
