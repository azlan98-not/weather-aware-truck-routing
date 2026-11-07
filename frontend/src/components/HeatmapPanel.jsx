import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchHeatmap } from '../api/routesApi';
import { formatDateTime } from '../utils/format';
import { RISK_LABELS, riskColor } from '../utils/risk';

/**
 * Corridor weather heatmap for the selected route. The slider (0–48 h)
 * re-queries the backend heatmap endpoint, which evaluates REAL forecast
 * weather at departure + offset + travel-time-to-point — nothing here is
 * simulated client-side.
 */
export default function HeatmapPanel({ route, request, onPointsChange }) {
  const [hourOffset, setHourOffset] = useState(0);
  const [points, setPoints] = useState(null);
  const [forecastTime, setForecastTime] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);
  const requestIdRef = useRef(0);

  const geometryKey = useMemo(
    () => (route ? `${route.id}:${route.geometry.length}` : ''),
    [route]
  );

  useEffect(() => {
    if (!route || !request) return undefined;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setError(null);
      fetchHeatmap({
        geometry: route.geometry,
        departure_datetime: request.departure_datetime,
        hour_offset: hourOffset,
        load_weight_lb: request.load_weight_lb,
        checkpoint_interval_miles: request.checkpoint_interval_miles,
        duration_minutes: route.duration_minutes,
      })
        .then((payload) => {
          if (requestId !== requestIdRef.current) return; // stale response
          setPoints(payload.points);
          setForecastTime(payload.forecast_time);
          if (onPointsChange) onPointsChange(payload.points);
        })
        .catch((err) => {
          if (requestId !== requestIdRef.current) return;
          setError(err.message || 'Heatmap request failed.');
          setPoints(null);
          if (onPointsChange) onPointsChange(null);
        })
        .finally(() => {
          if (requestId === requestIdRef.current) setLoading(false);
        });
    }, 350);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // geometryKey stands in for route identity in the dependency list.
  }, [geometryKey, hourOffset, request]);

  // Reset the slider when the selected route changes.
  useEffect(() => {
    setHourOffset(0);
  }, [geometryKey]);

  if (!route) return null;

  const segments = [];
  if (points && points.length > 1) {
    for (let i = 0; i < points.length - 1; i += 1) {
      const span = Math.max(points[i + 1].distance_miles - points[i].distance_miles, 0.1);
      segments.push({ point: points[i], span });
    }
  }

  return (
    <section className="card heatmap-panel" aria-label="Weather heatmap">
      <header className="heatmap-header">
        <h3>Weather heatmap — Route {route.id}</h3>
        {loading && <span className="heatmap-loading" role="status">Updating…</span>}
      </header>

      <div className="heatmap-slider-row">
        <label htmlFor="forecast-offset">
          Forecast offset: <strong>+{hourOffset}h</strong>
        </label>
        <input
          id="forecast-offset"
          aria-label="Forecast hour offset"
          type="range"
          min="0"
          max="48"
          step="1"
          value={hourOffset}
          onChange={(event) => setHourOffset(Number(event.target.value))}
        />
        <span className="forecast-time">
          {forecastTime
            ? `Showing weather for ${formatDateTime(forecastTime)} (+ travel time to each point)`
            : 'Move the slider to load a forecast.'}
        </span>
      </div>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {segments.length > 0 ? (
        <>
          <div className="heatmap-strip" data-testid="heatmap-strip">
            {segments.map(({ point, span }, i) => (
              <div
                key={i}
                className="heatmap-segment"
                style={{ flexGrow: span, backgroundColor: riskColor(point.risk_level) }}
                title={`Mile ${point.distance_miles}: ${RISK_LABELS[point.risk_level]} — wind ${point.wind_mph ?? 'n/a'} mph, rain ${point.rain_in_per_hr ?? 'n/a'} in/hr, snow ${point.snow_in_per_hr ?? 'n/a'} in/hr`}
              />
            ))}
          </div>
          <div className="heatmap-legend">
            {Object.keys(RISK_LABELS).map((level) => (
              <span key={level} className="legend-item">
                <span className="legend-swatch" style={{ backgroundColor: riskColor(level) }} />
                {RISK_LABELS[level]}
              </span>
            ))}
          </div>
        </>
      ) : (
        !loading && !error && <p className="heatmap-empty">No heatmap data yet for this route.</p>
      )}
    </section>
  );
}
