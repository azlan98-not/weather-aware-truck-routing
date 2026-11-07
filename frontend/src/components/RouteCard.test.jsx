import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import RouteComparison from './RouteComparison';

function makeRoute(id, overrides = {}) {
  return {
    id,
    summary: `I-55 S ${id}`,
    distance_miles: 297.8,
    duration_minutes: 268,
    departure_time: '2026-11-08T08:00:00Z',
    arrival_time: '2026-11-08T12:28:00Z',
    geometry: [[41.87, -87.62], [38.62, -90.19]],
    checkpoints: [],
    risk_summary: {
      low_miles: 250, moderate_miles: 30, high_miles: 10, severe_miles: 5,
      no_travel_miles: 0, unknown_miles: 2.8, average_risk: 1.42,
      highest_risk: 'SEVERE', risky_checkpoint_count: 3,
    },
    has_no_travel: false,
    unsafe_reason: null,
    ...overrides,
  };
}

const RESULT = {
  routes: [makeRoute(1), makeRoute(2)],
  recommendation: {
    route_id: 2,
    reasons: ['Selected because it has no NO TRAVEL segments…', 'Severe miles: 5.0'],
    comparison: [],
  },
  warnings: [],
};

describe('RouteComparison', () => {
  it('highlights the recommended route and shows its reasons', () => {
    render(<RouteComparison result={RESULT} selectedRouteId={2} onSelectRoute={vi.fn()} />);
    const recommendedCard = screen.getByTestId('route-card-2');
    expect(recommendedCard).toHaveTextContent(/recommended/i);
    expect(screen.getByText(/why this route/i)).toBeInTheDocument();
    expect(screen.getByText(/no NO TRAVEL segments/i)).toBeInTheDocument();
    const otherCard = screen.getByTestId('route-card-1');
    expect(otherCard).not.toHaveTextContent(/★ Recommended/);
  });

  it('selects a route when its card is clicked', () => {
    const onSelect = vi.fn();
    render(<RouteComparison result={RESULT} selectedRouteId={2} onSelectRoute={onSelect} />);
    fireEvent.click(screen.getByTestId('route-card-1'));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it('flags a no-travel route as unsafe with its reason', () => {
    const result = {
      ...RESULT,
      routes: [
        makeRoute(1, { has_no_travel: true, unsafe_reason: 'NO TRAVEL conditions at mile 40 (wind 60 mph)' }),
        makeRoute(2),
      ],
    };
    render(<RouteComparison result={result} selectedRouteId={2} onSelectRoute={vi.fn()} />);
    expect(screen.getByText(/unsafe/i)).toBeInTheDocument();
    expect(screen.getByText(/NO TRAVEL conditions at mile 40/)).toBeInTheDocument();
  });
});
