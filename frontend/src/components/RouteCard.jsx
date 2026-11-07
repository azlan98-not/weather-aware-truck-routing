import { formatDateTime, formatDuration, formatMiles } from '../utils/format';
import { RISK_LABELS, ROUTE_COLORS, riskColor } from '../utils/risk';

function RiskMilesBar({ summary }) {
  const segments = [
    ['low_miles', 'LOW'],
    ['moderate_miles', 'MODERATE'],
    ['high_miles', 'HIGH'],
    ['severe_miles', 'SEVERE'],
    ['no_travel_miles', 'NO_TRAVEL'],
    ['unknown_miles', 'UNKNOWN'],
  ];
  const total = segments.reduce((sum, [key]) => sum + (summary[key] || 0), 0);
  if (total <= 0) return null;
  return (
    <div className="risk-bar" aria-label="Risk miles breakdown">
      {segments.map(([key, level]) =>
        summary[key] > 0 ? (
          <div
            key={key}
            className="risk-bar-segment"
            style={{
              width: `${(summary[key] / total) * 100}%`,
              backgroundColor: riskColor(level),
            }}
            title={`${RISK_LABELS[level]}: ${formatMiles(summary[key])}`}
          />
        ) : null
      )}
    </div>
  );
}

export default function RouteCard({ route, index, isRecommended, isSelected, reasons, onSelect }) {
  const summary = route.risk_summary;
  return (
    <article
      className={
        'route-card card' +
        (isRecommended ? ' recommended' : '') +
        (isSelected ? ' selected' : '')
      }
      onClick={() => onSelect(route.id)}
      data-testid={`route-card-${route.id}`}
    >
      <header className="route-card-header">
        <span
          className="route-swatch"
          style={{ backgroundColor: ROUTE_COLORS[index % ROUTE_COLORS.length] }}
        />
        <h3>Route {route.id}: {route.summary}</h3>
        {isRecommended && <span className="badge badge-recommended">★ Recommended</span>}
      </header>

      {route.has_no_travel && (
        <p className="unsafe-warning" role="alert">
          ⚠ Unsafe — {route.unsafe_reason}
        </p>
      )}

      <dl className="route-stats">
        <div><dt>Distance</dt><dd>{formatMiles(route.distance_miles)}</dd></div>
        <div><dt>Travel time</dt><dd>{formatDuration(route.duration_minutes)}</dd></div>
        <div><dt>Arrival</dt><dd>{formatDateTime(route.arrival_time)}</dd></div>
        <div>
          <dt>Highest risk</dt>
          <dd>
            {summary.highest_risk ? (
              <span className="risk-chip" style={{ backgroundColor: riskColor(summary.highest_risk) }}>
                {RISK_LABELS[summary.highest_risk]}
              </span>
            ) : 'Unknown'}
          </dd>
        </div>
        <div><dt>Severe miles</dt><dd>{formatMiles(summary.severe_miles)}</dd></div>
        <div><dt>High miles</dt><dd>{formatMiles(summary.high_miles)}</dd></div>
        <div><dt>No-travel miles</dt><dd>{formatMiles(summary.no_travel_miles)}</dd></div>
        <div>
          <dt>Average risk</dt>
          <dd>{summary.average_risk == null ? 'n/a' : summary.average_risk.toFixed(2)}</dd>
        </div>
        <div><dt>Risky checkpoints</dt><dd>{summary.risky_checkpoint_count}</dd></div>
        {summary.unknown_miles > 0 && (
          <div><dt>Unknown-risk miles</dt><dd>{formatMiles(summary.unknown_miles)}</dd></div>
        )}
      </dl>

      <RiskMilesBar summary={summary} />

      {isRecommended && reasons && reasons.length > 0 && (
        <div className="recommendation-reasons">
          <h4>Why this route?</h4>
          <ul>
            {reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
