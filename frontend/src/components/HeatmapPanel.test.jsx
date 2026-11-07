import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HeatmapPanel from './HeatmapPanel';

vi.mock('../api/routesApi', () => ({
  fetchHeatmap: vi.fn(),
}));

import { fetchHeatmap } from '../api/routesApi';

const ROUTE = {
  id: 1,
  summary: 'I-55 S',
  distance_miles: 100,
  duration_minutes: 120,
  geometry: [[41.87, -87.62], [40.5, -89.0], [38.62, -90.19]],
};

const REQUEST = {
  origin: 'Chicago',
  destination: 'St Louis',
  departure_datetime: '2026-11-08T08:00:00Z',
  load_weight_lb: 35000,
  checkpoint_interval_miles: 25,
};

function payload(offsetHours) {
  return {
    forecast_time: `2026-11-08T${String(8 + offsetHours).padStart(2, '0')}:00:00Z`,
    points: [0, 25, 50, 75, 100].map((distance) => ({
      latitude: 41 - distance / 100,
      longitude: -88,
      distance_miles: distance,
      risk_level: 'LOW',
      risk_score: 1,
      wind_mph: 10,
      rain_in_per_hr: 0,
      snow_in_per_hr: 0,
    })),
  };
}

describe('HeatmapPanel', () => {
  beforeEach(() => {
    fetchHeatmap.mockReset();
    fetchHeatmap.mockImplementation((req) => Promise.resolve(payload(req.hour_offset)));
  });

  it('loads the heatmap for offset 0 and renders corridor segments', async () => {
    render(<HeatmapPanel route={ROUTE} request={REQUEST} onPointsChange={vi.fn()} />);
    await waitFor(() => expect(fetchHeatmap).toHaveBeenCalled());
    expect(fetchHeatmap.mock.calls[0][0].hour_offset).toBe(0);
    await waitFor(() => expect(screen.getByTestId('heatmap-strip')).toBeInTheDocument());
    expect(screen.getByText(/showing weather for/i)).toBeInTheDocument();
  });

  it('moving the slider calls the API with the new hour offset', async () => {
    render(<HeatmapPanel route={ROUTE} request={REQUEST} onPointsChange={vi.fn()} />);
    await waitFor(() => expect(fetchHeatmap).toHaveBeenCalled());
    fetchHeatmap.mockClear();
    fireEvent.change(screen.getByLabelText(/forecast hour offset/i), {
      target: { value: '12' },
    });
    await waitFor(() =>
      expect(fetchHeatmap).toHaveBeenCalledWith(
        expect.objectContaining({ hour_offset: 12, duration_minutes: 120 })
      )
    );
    expect(screen.getByText(/\+12h/)).toBeInTheDocument();
  });

  it('surfaces API errors instead of fake data', async () => {
    fetchHeatmap.mockRejectedValue(new Error('Weather provider is unavailable.'));
    render(<HeatmapPanel route={ROUTE} request={REQUEST} onPointsChange={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByText(/weather provider is unavailable/i)).toBeInTheDocument()
    );
    expect(screen.queryByTestId('heatmap-strip')).not.toBeInTheDocument();
  });
});
