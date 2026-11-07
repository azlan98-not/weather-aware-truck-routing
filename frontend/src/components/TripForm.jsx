import { useState } from 'react';
import { defaultDepartureLocal } from '../utils/format';
import { toAnalyzeRequest, validateTripInput } from '../utils/validation';

const INITIAL_VALUES = {
  origin: 'Chicago, IL',
  destination: 'St Louis, MO',
  departureLocal: defaultDepartureLocal(),
  loadWeightLb: '35000',
  checkpointIntervalMiles: '25',
};

export default function TripForm({ onSubmit, loading, serverFieldErrors }) {
  const [values, setValues] = useState(INITIAL_VALUES);
  const [errors, setErrors] = useState({});

  const fieldErrors = { ...errors, ...(serverFieldErrors || {}) };

  function update(field) {
    return (event) => {
      setValues((prev) => ({ ...prev, [field]: event.target.value }));
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    };
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (loading) return; // prevent duplicate submissions while processing
    const validation = validateTripInput(values);
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;
    onSubmit(toAnalyzeRequest(values));
  }

  return (
    <form className="trip-form card" onSubmit={handleSubmit} noValidate>
      <h2>Plan a trip</h2>
      <div className="form-grid">
        <label className="field">
          <span>Origin</span>
          <input
            aria-label="Origin"
            type="text"
            value={values.origin}
            onChange={update('origin')}
            placeholder="e.g. Chicago, IL"
            autoComplete="off"
          />
          {fieldErrors.origin && <span className="field-error" role="alert">{fieldErrors.origin}</span>}
        </label>
        <label className="field">
          <span>Destination</span>
          <input
            aria-label="Destination"
            type="text"
            value={values.destination}
            onChange={update('destination')}
            placeholder="e.g. St Louis, MO"
            autoComplete="off"
          />
          {fieldErrors.destination && (
            <span className="field-error" role="alert">{fieldErrors.destination}</span>
          )}
        </label>
        <label className="field">
          <span>Departure date &amp; time</span>
          <input
            aria-label="Departure date and time"
            type="datetime-local"
            value={values.departureLocal}
            onChange={update('departureLocal')}
          />
          {fieldErrors.departure_datetime && (
            <span className="field-error" role="alert">{fieldErrors.departure_datetime}</span>
          )}
        </label>
        <label className="field">
          <span>Load weight (lb)</span>
          <input
            aria-label="Load weight in pounds"
            type="number"
            min="1"
            step="any"
            value={values.loadWeightLb}
            onChange={update('loadWeightLb')}
          />
          {fieldErrors.load_weight_lb && (
            <span className="field-error" role="alert">{fieldErrors.load_weight_lb}</span>
          )}
        </label>
        <label className="field">
          <span>Weather checkpoint interval</span>
          <select
            aria-label="Checkpoint interval in miles"
            value={values.checkpointIntervalMiles}
            onChange={update('checkpointIntervalMiles')}
          >
            <option value="10">Every 10 miles</option>
            <option value="25">Every 25 miles</option>
            <option value="50">Every 50 miles</option>
          </select>
          {fieldErrors.checkpoint_interval_miles && (
            <span className="field-error" role="alert">
              {fieldErrors.checkpoint_interval_miles}
            </span>
          )}
        </label>
      </div>
      <button type="submit" className="primary-button" disabled={loading}>
        {loading ? 'Generating routes…' : 'Generate Routes'}
      </button>
    </form>
  );
}
