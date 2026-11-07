import { apiPost } from './client';

export function analyzeTrip(request) {
  return apiPost('/api/v1/routes/analyze/', request);
}

export function fetchHeatmap(request) {
  return apiPost('/api/v1/routes/heatmap/', request);
}
