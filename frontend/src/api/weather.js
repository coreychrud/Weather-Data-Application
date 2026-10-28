function buildQuery(latitude, longitude, units, extra = {}) {
  return new URLSearchParams({
    latitude: latitude.toFixed(4),
    longitude: longitude.toFixed(4),
    timezone: "auto",
    units,
    ...extra,
  });
}

async function requestWeather(path, signal) {
  const response = await fetch(path, { signal });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Weather request failed (${response.status})`);
  }

  return response.json();
}

export function getForecast({ latitude, longitude, days, units, signal }) {
  const query = buildQuery(latitude, longitude, units, {
    forecast_days: String(days),
  });
  return requestWeather(`/api/v1/forecast?${query}`, signal);
}

export function getDayWeather({ category, date, latitude, longitude, units, signal }) {
  const query = buildQuery(latitude, longitude, units);
  return requestWeather(`/api/v1/weather/${category}/${date}?${query}`, signal);
}
