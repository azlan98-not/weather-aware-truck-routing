export const ALLOWED_INTERVALS = [10, 25, 50];

// Frontend mirror of the backend validation rules (the backend remains the
// source of truth; these exist so users get instant feedback).
export function validateTripInput(values) {
  const errors = {};
  if (!values.origin || values.origin.trim().length < 2) {
    errors.origin = 'Enter an origin city or address.';
  }
  if (!values.destination || values.destination.trim().length < 2) {
    errors.destination = 'Enter a destination city or address.';
  }
  if (!values.departureLocal) {
    errors.departure_datetime = 'Choose a departure date and time.';
  } else if (Number.isNaN(new Date(values.departureLocal).getTime())) {
    errors.departure_datetime = 'Departure date and time is not valid.';
  }
  const load = Number(values.loadWeightLb);
  if (values.loadWeightLb === '' || Number.isNaN(load)) {
    errors.load_weight_lb = 'Enter the truck load weight.';
  } else if (load <= 0) {
    errors.load_weight_lb = 'Load weight must be positive.';
  } else if (load > 200000) {
    errors.load_weight_lb = 'Load weight is unrealistically large.';
  }
  if (!ALLOWED_INTERVALS.includes(Number(values.checkpointIntervalMiles))) {
    errors.checkpoint_interval_miles = 'Choose a checkpoint interval of 10, 25 or 50 miles.';
  }
  return errors;
}

export function toAnalyzeRequest(values) {
  return {
    origin: values.origin.trim(),
    destination: values.destination.trim(),
    departure_datetime: new Date(values.departureLocal).toISOString(),
    load_weight_lb: Number(values.loadWeightLb),
    checkpoint_interval_miles: Number(values.checkpointIntervalMiles),
  };
}
