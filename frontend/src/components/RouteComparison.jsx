import RouteCard from './RouteCard';

export default function RouteComparison({ result, selectedRouteId, onSelectRoute }) {
  const { routes, recommendation } = result;
  return (
    <section aria-label="Route comparison">
      <div className="route-cards">
        {routes.map((route, index) => (
          <RouteCard
            key={route.id}
            route={route}
            index={index}
            isRecommended={recommendation.route_id === route.id}
            isSelected={selectedRouteId === route.id}
            reasons={recommendation.route_id === route.id ? recommendation.reasons : null}
            onSelect={onSelectRoute}
          />
        ))}
      </div>
    </section>
  );
}
