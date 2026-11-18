import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AgentPipeline from '../src/components/AgentPipeline.jsx';
import ChartCard from '../src/components/ChartCard.jsx';
import KpiCard from '../src/components/KpiCard.jsx';
import { AuthProvider } from '../src/features/auth/AuthContext.jsx';
import RequireAuth from '../src/features/auth/RequireAuth.jsx';
import { ApprovalCard } from '../src/pages/ApprovalsPage.jsx';
import LoginPage from '../src/pages/LoginPage.jsx';
import RegisterPage from '../src/pages/RegisterPage.jsx';
import { formatCompactINR, formatINR } from '../src/utils/format.js';

describe('INR and metric formatters', () => {
  it('formats Indian Rupee numbers with en-IN grouping and compact Cr/L notation', () => {
    expect(formatINR(22256456.76)).toBe('₹2,22,56,457');
    expect(formatINR(22256456.76, { precise: true })).toBe('₹2,22,56,456.76');
    expect(formatCompactINR(22256456.76)).toBe('₹2.23 Cr');
    expect(formatCompactINR(-4295331.32)).toBe('-₹42.95 L');
  });
});

describe('KpiCard', () => {
  it('renders KPI figure, MoM badge, and toggles definition/basis panel', () => {
    const card = {
      key: 'finance.net_revenue',
      label: 'Invoiced Net Revenue',
      value: 22256456.76,
      unit: 'INR',
      definition: 'Sum of Billing.net_amount only.',
      basis: 'invoiced_billing_net_amount_only',
      as_of: '2026-10-31',
      dataset_id: 'ds-1',
      mom_change_pct: 5.74,
      latest_month: '2026-10',
      previous_month: '2026-09',
    };

    render(<KpiCard card={card} />);
    expect(screen.getByText('Invoiced Net Revenue')).toBeInTheDocument();
    expect(screen.getByText('₹2.23 Cr')).toBeInTheDocument();
    expect(screen.getByText('₹2,22,56,456.76')).toBeInTheDocument();
    expect(screen.getByText('+5.74% MoM')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Info' }));
    expect(screen.getByText(/Sum of Billing\.net_amount only\./)).toBeInTheDocument();
    expect(screen.getByText('invoiced_billing_net_amount_only')).toBeInTheDocument();
  });
});

describe('ChartCard', () => {
  it('switches to accessible data-table fallback view', () => {
    render(
      <ChartCard
        title="Payment Status Breakdown"
        columns={[
          { key: 'payment_status', label: 'Status' },
          { key: 'invoice_count', label: 'Invoices' },
        ]}
        rows={[
          { payment_status: 'Paid', invoice_count: 896 },
          { payment_status: 'Pending', invoice_count: 444 },
        ]}
      >
        <div>Chart graphic</div>
      </ChartCard>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Table view' }));
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('896')).toBeInTheDocument();
  });
});

describe('RequireAuth guard', () => {
  it('redirects unauthenticated visitors to /login', () => {
    render(
      <AuthProvider initialUser={null} skipBootstrap>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route path="/login" element={<h1>Sign In Screen</h1>} />
            <Route
              path="/dashboard"
              element={
                <RequireAuth>
                  <h1>Protected Dashboard</h1>
                </RequireAuth>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(screen.getByRole('heading', { name: 'Sign In Screen' })).toBeInTheDocument();
  });

  it('blocks users whose role is not in allowedRoles', () => {
    const analystUser = { id: 'u1', email: 'analyst@careops.example', role: 'analyst' };
    render(
      <AuthProvider initialUser={analystUser} skipBootstrap>
        <MemoryRouter initialEntries={['/admin']}>
          <Routes>
            <Route
              path="/admin"
              element={
                <RequireAuth allowedRoles={['admin']}>
                  <h1>Admin Console</h1>
                </RequireAuth>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(screen.getByRole('heading', { name: 'Access Restricted' })).toBeInTheDocument();
  });
});

describe('AgentPipeline monitor', () => {
  it('renders agent statuses, revision count, verdict, and expands agent tool logs', () => {
    const agents = [
      {
        id: 'a1',
        agent_name: 'data_analyst',
        sequence: 1,
        status: 'completed',
        duration_ms: 420,
        context_from: [],
        input_summary: 'Baseline KPI scan',
        tool_calls: [{ tool: 'get_metric', args: { key: 'appointments.total' } }],
        output: { summary: 'Recorded 2,500 appointments.' },
      },
      {
        id: 'a2',
        agent_name: 'marketing',
        sequence: 2,
        status: 'running',
        started_at: new Date().toISOString(),
        context_from: ['data_analyst'],
        tool_calls: [],
        output: null,
      },
    ];

    render(
      <AgentPipeline agents={agents} runStatus="running" revisionCount={1} verdict="approved" />,
    );

    expect(screen.getByText('1. Data Analyst Agent')).toBeInTheDocument();
    expect(screen.getByText('2. Marketing Agent')).toBeInTheDocument();
    expect(screen.getByText('Revision loops: 1')).toBeInTheDocument();
    expect(screen.getByText('APPROVED')).toBeInTheDocument();

    const logButtons = screen.getAllByRole('button', { name: 'View logs' });
    fireEvent.click(logButtons[0]);
    expect(screen.getByText(/Baseline KPI scan/)).toBeInTheDocument();
    expect(screen.getByText('get_metric')).toBeInTheDocument();
  });
});

describe('ApprovalCard HITL flow', () => {
  const sampleRec = {
    id: 'rec-1',
    title: 'Freeze non-clinical equipment spend pending audit',
    rationale: 'Approved expenses exceed invoiced net revenue.',
    action_type: 'budget',
    status: 'pending_approval',
    evidence_metric_keys: ['finance.net_revenue', 'finance.approved_expenses'],
    evidence_metrics: [
      {
        key: 'finance.net_revenue',
        value: 22256456.76,
        unit: 'INR',
        definition: 'Billing.net_amount sum',
        basis: 'invoiced_billing_net_amount_only',
      },
    ],
    approval_history: [],
  };

  it('allows managers to approve or reject with a comment and blocks analysts', () => {
    const decisions = [];
    const { rerender } = render(
      <ApprovalCard
        rec={sampleRec}
        canDecide={true}
        isPending={false}
        onDecide={(id, dec, comment) => decisions.push({ id, dec, comment })}
      />,
    );

    fireEvent.change(screen.getByLabelText('Governance Decision Comment'), {
      target: { value: 'Approved for Q4 audit' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Approve Proposal' }));
    expect(decisions).toEqual([{ id: 'rec-1', dec: 'approved', comment: 'Approved for Q4 audit' }]);

    // Analyst view (`canDecide=false`) hides decision buttons and shows read-only notice
    rerender(
      <ApprovalCard rec={sampleRec} canDecide={false} isPending={false} onDecide={() => {}} />,
    );
    expect(screen.queryByRole('button', { name: 'Approve Proposal' })).not.toBeInTheDocument();
    expect(screen.getByText(/Read-only view/i)).toBeInTheDocument();
  });
});

describe('MediOps Intelligence product identity & auth screens', () => {
  it('renders MediOps Intelligence branding, subtitle, and inline validation on Login and Register', () => {
    render(
      <AuthProvider initialUser={null} skipBootstrap>
        <MemoryRouter initialEntries={['/login']}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(
      screen.getByRole('heading', { name: 'Sign in to MediOps Intelligence' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('AI-Powered Hospital Operations & Performance Intelligence.'),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Please enter both email and password.');

    // Quick-fill demo role buttons populate email and password
    fireEvent.click(screen.getByRole('button', { name: 'Fill Manager' }));
    expect(screen.getByLabelText('Email address')).toHaveValue('e2e.manager@mediops.example');
    expect(screen.getByLabelText('Password')).toHaveValue('Sunrise#Ward99!Ops');

    fireEvent.click(screen.getByRole('button', { name: 'Fill Admin' }));
    expect(screen.getByLabelText('Email address')).toHaveValue('admin@mediops.example');

    fireEvent.click(screen.getByRole('button', { name: 'Fill Analyst' }));
    expect(screen.getByLabelText('Email address')).toHaveValue('audit.analyst@mediops.example');
  });
});
