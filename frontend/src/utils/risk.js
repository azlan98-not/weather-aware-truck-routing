// Display metadata for risk levels. Thresholds themselves live ONLY in the
// backend risk engine; this file only maps labels to colors/names.
export const RISK_COLORS = {
  LOW: '#22c55e',
  MODERATE: '#eab308',
  HIGH: '#f97316',
  SEVERE: '#ef4444',
  NO_TRAVEL: '#111827',
  UNKNOWN: '#9ca3af',
};

export const RISK_LABELS = {
  LOW: 'Low',
  MODERATE: 'Moderate',
  HIGH: 'High',
  SEVERE: 'Severe',
  NO_TRAVEL: 'No Travel',
  UNKNOWN: 'Unknown',
};

export const ROUTE_COLORS = ['#2563eb', '#9333ea', '#0d9488'];

export function riskColor(level) {
  return RISK_COLORS[level] || RISK_COLORS.UNKNOWN;
}
