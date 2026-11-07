import { useCallback, useMemo, useState } from 'react';
import { analyzeTrip } from './api/routesApi';
import HeatmapPanel from './components/HeatmapPanel';
import RouteComparison from './components/RouteComparison';
import RouteMap from './components/RouteMap';
import { EmptyState, ErrorState, LoadingState } from './components/States';
import TripForm from './components/TripForm';

export default function App() {
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [serverFieldErrors, setServerFieldErrors] = useState({});
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [lastRequest, setLastRequest] = useState(null);
  const [heatmapPoints, setHeatmapPoints] = useState(null);

  const handleSubmit = useCallback(async (request) => {
    setStatus('loading');
    setErrorMessage(null);
    setServerFieldErrors({});
    setLastRequest(request);
    try {
      const payload = await analyzeTrip(request);
      setResult(payload);
      setSelectedRouteId(payload.recommendation.route_id);
      setHeatmapPoints(null);
      setStatus('success');
    } catch (error) {
      setErrorMessage(error.message || 'The analysis request failed.');
      setServerFieldErrors(error.fields || {});
      setStatus('error');
    }
  }, []);

  const handleRetry = useCallback(() => {
    if (lastRequest) handleSubmit(lastRequest);
  }, [lastRequest, handleSubmit]);

  const selectedRoute = useMemo(() => {
    if (!result) return null;
    return result.routes.find((route) => route.id === selectedRouteId) || result.routes[0];
  }, [result, selectedRouteId]);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Weather-Aware Truck Routing</h1>
          <p className="app-subtitle">
            Compare up to three real routes with live weather risk at every checkpoint.
          </p>
        </div>
        <nav className="app-nav" aria-label="Application">
          <span className="nav-pill">Spotter AI Assessment</span>
        </nav>
      </header>

      <main className="app-main">
        <TripForm
          onSubmit={handleSubmit}
          loading={status === 'loading'}
          serverFieldErrors={serverFieldErrors}
        />

        {status === 'loading' && <LoadingState />}
        {status === 'error' && <ErrorState message={errorMessage} onRetry={handleRetry} />}
        {status === 'idle' && <EmptyState />}

        {status === 'success' && result && (
          <>
            {result.warnings?.length > 0 && (
              <div className="warnings" role="status">
                {result.warnings.map((warning, i) => (
                  <p key={i}>⚠ {warning}</p>
                ))}
              </div>
            )}
            <RouteComparison
              result={result}
              selectedRouteId={selectedRouteId}
              onSelectRoute={setSelectedRouteId}
            />
            <section className="card map-card" aria-label="Route map">
              <RouteMap
                routes={result.routes}
                recommendedRouteId={result.recommendation.route_id}
                selectedRouteId={selectedRouteId}
                onSelectRoute={setSelectedRouteId}
                heatmapPoints={selectedRoute ? heatmapPoints : null}
              />
              <p className="map-hint">
                Click a route line or a route card to inspect it. Checkpoint markers show the
                selected route; click one for weather, ETA and risk.
              </p>
            </section>
            <HeatmapPanel
              route={selectedRoute}
              request={lastRequest}
              onPointsChange={setHeatmapPoints}
            />
          </>
        )}
      </main>

      <footer className="app-footer">
        Routing: OSRM · Geocoding: OpenStreetMap Nominatim · Weather: Open-Meteo. Weather is
        evaluated at each checkpoint&apos;s estimated arrival time; missing forecast data is
        shown as unknown risk, never as safe.
      </footer>
    </div>
  );
}
