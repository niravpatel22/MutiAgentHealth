import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { apiRequest } from '../api/client.js';
import ChartCard from '../components/ChartCard.jsx';
import KpiCard from '../components/KpiCard.jsx';
import { useAuth } from '../features/auth/AuthContext.jsx';
import { formatCompactINR, formatINR } from '../utils/format.js';

const MONTHS = ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'];

export default function DashboardPage() {
  const { activeDatasetId } = useAuth();
  const [fromMonth, setFromMonth] = useState('2026-05');
  const [toMonth, setToMonth] = useState('2026-10');

  const querySuffix = `?from=${fromMonth}&to=${toMonth}`;

  const kpisQuery = useQuery({
    queryKey: ['kpis', activeDatasetId, fromMonth, toMonth],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${activeDatasetId}/kpis${querySuffix}`, { signal }),
    enabled: Boolean(activeDatasetId),
  });

  const trendsQuery = useQuery({
    queryKey: ['trends', activeDatasetId, fromMonth, toMonth],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${activeDatasetId}/trends${querySuffix}`, { signal }),
    enabled: Boolean(activeDatasetId),
  });

  const deptQuery = useQuery({
    queryKey: ['breakdown', activeDatasetId, 'department', fromMonth, toMonth],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${activeDatasetId}/breakdowns/department${querySuffix}`, { signal }),
    enabled: Boolean(activeDatasetId),
  });

  const paymentQuery = useQuery({
    queryKey: ['breakdown', activeDatasetId, 'payment_status', fromMonth, toMonth],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${activeDatasetId}/breakdowns/payment_status${querySuffix}`, {
        signal,
      }),
    enabled: Boolean(activeDatasetId),
  });

  const cityQuery = useQuery({
    queryKey: ['breakdown', activeDatasetId, 'city', fromMonth, toMonth],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${activeDatasetId}/breakdowns/city${querySuffix}`, { signal }),
    enabled: Boolean(activeDatasetId),
  });

  const insuranceQuery = useQuery({
    queryKey: ['breakdown', activeDatasetId, 'insurance_provider', fromMonth, toMonth],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${activeDatasetId}/breakdowns/insurance_provider${querySuffix}`, {
        signal,
      }),
    enabled: Boolean(activeDatasetId),
  });

  const inventoryCatQuery = useQuery({
    queryKey: ['breakdown', activeDatasetId, 'category'],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${activeDatasetId}/breakdowns/category`, { signal }),
    enabled: Boolean(activeDatasetId),
  });

  if (!activeDatasetId) {
    return (
      <section className="card">
        <h1 className="page-title">No Dataset Selected</h1>
        <p className="page-subtitle" style={{ marginBottom: '16px' }}>
          Upload <code>01_Healthcare.xlsx</code> on the Datasets page to view live hospital KPIs and
          operational charts.
        </p>
        <Link to="/datasets" className="btn btn-primary">
          Go to Datasets
        </Link>
      </section>
    );
  }

  const cards = kpisQuery.data?.cards ?? [];
  const revVsExp = trendsQuery.data?.revenue_vs_expenses ?? [];
  const apptTrends = trendsQuery.data?.appointments_by_status ?? [];
  const deptItems = deptQuery.data?.items ?? [];
  const paymentItems = paymentQuery.data?.items ?? [];
  const cityItems = cityQuery.data?.items ?? [];
  const insuranceItems = insuranceQuery.data?.items ?? [];
  const inventoryItems = inventoryCatQuery.data?.items ?? [];

  return (
    <section aria-labelledby="dashboard-heading">
      <div className="page-header">
        <div>
          <h1 id="dashboard-heading" className="page-title">
            Hospital Operations &amp; Performance Dashboard
          </h1>
          <p className="page-subtitle">
            Deterministic figures from the metrics registry · Reference date:{' '}
            <strong className="tabular">{kpisQuery.data?.as_of || '2026-10-31'}</strong>
          </p>
        </div>

        <div className="topbar-controls" aria-label="Month range filter">
          <label htmlFor="from-month" className="form-label" style={{ margin: 0 }}>
            From
          </label>
          <select
            id="from-month"
            className="select tabular"
            value={fromMonth}
            onChange={(e) => {
              const v = e.target.value;
              setFromMonth(v);
              if (v > toMonth) setToMonth(v);
            }}
          >
            {MONTHS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>

          <label htmlFor="to-month" className="form-label" style={{ margin: 0 }}>
            To
          </label>
          <select
            id="to-month"
            className="select tabular"
            value={toMonth}
            onChange={(e) => {
              const v = e.target.value;
              setToMonth(v);
              if (v < fromMonth) setFromMonth(v);
            }}
          >
            {MONTHS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ---- 9 KPI Cards ---- */}
      {kpisQuery.isLoading ? (
        <div className="kpi-grid" aria-busy="true">
          {Array.from({ length: 9 }).map((_, idx) => (
            <div key={idx} className="skeleton" />
          ))}
        </div>
      ) : (
        <div className="kpi-grid">
          {cards.map((card) => (
            <KpiCard key={card.key} card={card} />
          ))}
        </div>
      )}

      {/* ---- Recharts Visualizations ---- */}
      <div className="charts-grid">
        <ChartCard
          title="Invoiced Net Revenue vs Expenses by Month (INR)"
          subtitle="Expenses split by approval status: Approved (cost basis), Pending (exposure), Rejected (non-cost)"
          rows={revVsExp}
          columns={[
            { key: 'month', label: 'Month' },
            { key: 'net_revenue', label: 'Net Revenue', format: (v) => formatINR(v) },
            { key: 'approved_expenses', label: 'Approved Expenses', format: (v) => formatINR(v) },
            { key: 'pending_expenses', label: 'Pending Exposure', format: (v) => formatINR(v) },
            { key: 'rejected_expenses', label: 'Rejected (Non-Cost)', format: (v) => formatINR(v) },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={revVsExp}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hairline)" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={(v) => formatCompactINR(v)} />
              <Tooltip formatter={(val) => formatINR(val)} />
              <Legend />
              <Bar dataKey="net_revenue" name="Invoiced Net Revenue" fill="#0e7c86" />
              <Bar dataKey="approved_expenses" name="Approved Expenses" fill="#b91c1c" />
              <Line
                type="monotone"
                dataKey="pending_expenses"
                name="Pending Exposure"
                stroke="#b45309"
                strokeWidth={2}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Appointments by Month Stacked by Status"
          subtitle="Scheduled appointments are treated as pipeline and excluded from outcome rate denominators"
          rows={apptTrends}
          columns={[
            { key: 'month', label: 'Month' },
            { key: 'completed', label: 'Completed' },
            { key: 'scheduled', label: 'Scheduled (Pipeline)' },
            { key: 'cancelled', label: 'Cancelled' },
            { key: 'no_show', label: 'No Show' },
            { key: 'total', label: 'Total' },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={apptTrends}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hairline)" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="completed" name="Completed" stackId="a" fill="#15803d" />
              <Bar dataKey="scheduled" name="Scheduled" stackId="a" fill="#0e7c86" />
              <Bar dataKey="cancelled" name="Cancelled" stackId="a" fill="#b45309" />
              <Bar dataKey="no_show" name="No Show" stackId="a" fill="#b91c1c" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Appointments & Average Wait Time by Department"
          subtitle="Identifies volume load vs clinic wait-time bottlenecks across the 8 departments"
          rows={deptItems}
          columns={[
            { key: 'department', label: 'Department' },
            { key: 'appointments', label: 'Appointments' },
            { key: 'avg_wait_minutes', label: 'Avg Wait (min)' },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={deptItems}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hairline)" />
              <XAxis dataKey="department" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" unit="m" />
              <Tooltip />
              <Legend />
              <Bar yAxisId="left" dataKey="appointments" name="Appointments" fill="#0e7c86" />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="avg_wait_minutes"
                name="Avg Wait (min)"
                stroke="#b45309"
                strokeWidth={2}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Invoiced Value by Payment Status (No Amount-Paid Column)"
          subtitle="Reported strictly as invoiced Billing.net_amount by status — never claimed as collected cash"
          rows={paymentItems}
          columns={[
            { key: 'payment_status', label: 'Payment Status' },
            { key: 'invoice_count', label: 'Invoice Count' },
            {
              key: 'invoiced_net_amount',
              label: 'Invoiced Net Value',
              format: (v) => formatINR(v),
            },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={paymentItems}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hairline)" />
              <XAxis dataKey="payment_status" />
              <YAxis yAxisId="left" tickFormatter={(v) => formatCompactINR(v)} />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip formatter={(val, name) => (name.includes('Value') ? formatINR(val) : val)} />
              <Legend />
              <Bar
                yAxisId="left"
                dataKey="invoiced_net_amount"
                name="Invoiced Net Value (INR)"
                fill="#0e7c86"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="invoice_count"
                name="Invoice Count"
                stroke="#334155"
                strokeWidth={2}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="No-Show Rate by Department (%)"
          subtitle="No-show share of resolved appointments (Scheduled excluded from denominator)"
          rows={deptItems}
          columns={[
            { key: 'department', label: 'Department' },
            { key: 'no_show_rate', label: 'No-Show Rate (%)', format: (v) => `${v}%` },
            { key: 'completion_rate', label: 'Completion Rate (%)', format: (v) => `${v}%` },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={deptItems}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hairline)" />
              <XAxis dataKey="department" tick={{ fontSize: 11 }} />
              <YAxis unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <Legend />
              <Bar dataKey="no_show_rate" name="No-Show Rate (%)" fill="#b91c1c" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Registered Patients by City & Insurance Provider"
          subtitle="Patient segmentation (dataset contains no marketing spend or campaign attribution)"
          rows={insuranceItems}
          columns={[
            { key: 'insurance_provider', label: 'Insurance Provider' },
            { key: 'patients', label: 'Registered Patients' },
            { key: 'no_show_rate', label: 'No-Show Rate (%)', format: (v) => `${v}%` },
            {
              key: 'invoiced_net_revenue',
              label: 'Invoiced Net Revenue',
              format: (v) => formatINR(v),
            },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={cityItems}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hairline)" />
              <XAxis dataKey="city" tick={{ fontSize: 11 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="patients" name="Patients by City" fill="#0e7c86" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Inventory Risk by Medicine Category (Point-in-Time Snapshot)"
          subtitle="Items at/below reorder level (111 total) and expiring within 90 days of 2026-10-31 (20 total)"
          rows={inventoryItems}
          columns={[
            { key: 'category', label: 'Category' },
            { key: 'total_items', label: 'Total Items' },
            { key: 'low_stock_items', label: 'Low Stock (≤ Reorder)' },
            { key: 'expiring_90d_items', label: 'Expiring ≤ 90 Days' },
            { key: 'value_at_cost', label: 'Inventory Value at Cost', format: (v) => formatINR(v) },
          ]}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={inventoryItems}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-hairline)" />
              <XAxis dataKey="category" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="low_stock_items" name="At/Below Reorder Level" fill="#b45309" />
              <Bar dataKey="expiring_90d_items" name="Expiring ≤ 90 Days" fill="#b91c1c" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </section>
  );
}
