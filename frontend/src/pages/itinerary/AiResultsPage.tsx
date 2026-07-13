import { Navigate, useSearchParams } from "react-router-dom";

export function AiResultsPage() {
  const [searchParams] = useSearchParams();
  const tripId = searchParams.get("tripId");
  const destination = tripId ? `/trips/${encodeURIComponent(tripId)}?mode=recommend` : "/trips";

  return <Navigate to={destination} replace />;
}
