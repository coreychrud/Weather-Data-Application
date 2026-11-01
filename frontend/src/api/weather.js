function buildQuery(latitude, longitude, units, extra = {}) {
  return new URLSearchParams({
    latitude: latitude.toFixed(4),
    longitude: longitude.toFixed(4),
    timezone: "auto",
    units,
    ...extra,
  });
}

async function requestWeather(path, signal, options = {}) {
  const response = await fetch(path, { ...options, signal });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string"
      ? error.detail : `Weather request failed (${response.status})`);
  }

  return response.json();
}

const heatmapCache = new Map();

export async function getHeatmap({ date, points, signal }) {
  const body = JSON.stringify({ weather_date: date, points });
  const cached = heatmapCache.get(body);
  if (cached && cached.expires > Date.now()) return cached.payload;
  const payload = await requestWeather("/api/v1/weather/heatmap", signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  if (!signal?.aborted) {
    heatmapCache.set(body, { payload, expires: Date.now() + 15 * 60 * 1000 });
    if (heatmapCache.size > 20) heatmapCache.delete(heatmapCache.keys().next().value);
  }
  return payload;
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
