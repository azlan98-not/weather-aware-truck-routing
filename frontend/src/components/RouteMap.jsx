import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { formatDateTime } from '../utils/format';
import { RISK_LABELS, ROUTE_COLORS, riskColor } from '../utils/risk';

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function checkpointPopup(route, checkpoint) {
  const weather = checkpoint.weather_available
    ? `Wind: ${checkpoint.wind_mph} mph<br/>Rain: ${checkpoint.rain_in_per_hr} in/hr<br/>Snow: ${checkpoint.snow_in_per_hr} in/hr`
    : 'Weather forecast unavailable at this point';
  return (
    `<strong>Route ${route.id} — mile ${checkpoint.distance_miles}</strong><br/>` +
    `ETA: ${escapeHtml(formatDateTime(checkpoint.eta))}<br/>${weather}<br/>` +
    `Risk: <strong>${escapeHtml(RISK_LABELS[checkpoint.risk_level] || checkpoint.risk_level)}</strong>`
  );
}

/**
 * Leaflet map used imperatively (no react-leaflet). Draws all routes with
 * distinct styles, the recommended route boldest, risk-colored checkpoint
 * markers for the selected route, and — when provided — the heatmap
 * corridor as thick risk-colored segments under the routes.
 */
export default function RouteMap({
  routes,
  recommendedRouteId,
  selectedRouteId,
  onSelectRoute,
  heatmapPoints,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerGroupRef = useRef(null);
  const selectRef = useRef(onSelectRoute);
  selectRef.current = onSelectRoute;

  // Create the map once; tear it down on unmount.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const map = L.map(containerRef.current).setView([39.5, -89.5], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);
    layerGroupRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      layerGroupRef.current = null;
    };
  }, []);

  // Redraw data layers whenever inputs change.
  useEffect(() => {
    const map = mapRef.current;
    const group = layerGroupRef.current;
    if (!map || !group || !routes || routes.length === 0) return;
    group.clearLayers();

    // Heatmap corridor segments (below the route lines).
    if (heatmapPoints && heatmapPoints.length > 1) {
      for (let i = 0; i < heatmapPoints.length - 1; i += 1) {
        const a = heatmapPoints[i];
        const b = heatmapPoints[i + 1];
        L.polyline(
          [
            [a.latitude, a.longitude],
            [b.latitude, b.longitude],
          ],
          { color: riskColor(a.risk_level), weight: 13, opacity: 0.45 }
        ).addTo(group);
      }
    }

    const bounds = [];
    routes.forEach((route, index) => {
      const isRecommended = route.id === recommendedRouteId;
      const isSelected = route.id === selectedRouteId;
      const line = L.polyline(route.geometry, {
        color: ROUTE_COLORS[index % ROUTE_COLORS.length],
        weight: isRecommended ? 7 : isSelected ? 6 : 4,
        opacity: isSelected || isRecommended ? 0.95 : 0.55,
      }).addTo(group);
      line.on('click', () => selectRef.current(route.id));
      line.bindTooltip(
        `Route ${route.id} — ${route.distance_miles} mi, ETA ${formatDateTime(route.arrival_time)}`
      );
      route.geometry.forEach((point) => bounds.push(point));

      if (isSelected) {
        route.checkpoints.forEach((checkpoint) => {
          L.circleMarker([checkpoint.latitude, checkpoint.longitude], {
            radius: 6,
            color: '#ffffff',
            weight: 1.5,
            fillColor: riskColor(checkpoint.risk_level),
            fillOpacity: 1,
          })
            .bindPopup(checkpointPopup(route, checkpoint))
            .addTo(group);
        });
      }
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [24, 24] });
    }
  }, [routes, recommendedRouteId, selectedRouteId, heatmapPoints]);

  return <div ref={containerRef} className="route-map" data-testid="route-map" />;
}
