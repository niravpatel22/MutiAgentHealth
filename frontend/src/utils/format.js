/**
 * Deterministic number & INR currency formatters (`en-IN` grouping).
 */

const inrFull = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

const inrPrecise = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const numFormat = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 2,
});

export function formatINR(value, { precise = false } = {}) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return '₹0';
  return precise ? inrPrecise.format(num) : inrFull.format(Math.round(num));
}

export function formatCompactINR(value) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return '₹0';
  const sign = num < 0 ? '-' : '';
  const abs = Math.abs(num);
  if (abs >= 1e7) {
    return `${sign}₹${(abs / 1e7).toFixed(2)} Cr`;
  }
  if (abs >= 1e5) {
    return `${sign}₹${(abs / 1e5).toFixed(2)} L`;
  }
  return formatINR(num);
}

export function formatMetricValue(value, unit, { compact = false } = {}) {
  const num = Number(value ?? 0);
  if (unit === 'INR') {
    return compact ? formatCompactINR(num) : formatINR(num);
  }
  if (unit === 'percent') {
    return `${num.toFixed(2)}%`;
  }
  if (unit === 'minutes') {
    return `${num.toFixed(2)} min`;
  }
  return numFormat.format(num);
}
