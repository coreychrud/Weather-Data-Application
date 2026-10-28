export const weatherDescriptions = {
  0: "Clear sky",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Rime fog",
  51: "Light drizzle",
  53: "Moderate drizzle",
  55: "Dense drizzle",
  61: "Slight rain",
  63: "Moderate rain",
  65: "Heavy rain",
  71: "Slight snow",
  73: "Moderate snow",
  75: "Heavy snow",
  77: "Snow grains",
  80: "Light showers",
  81: "Moderate showers",
  82: "Heavy showers",
  85: "Snow showers",
  86: "Heavy snow showers",
  95: "Thunderstorm",
  96: "Storm with hail",
  99: "Severe storm with hail",
};

export function weatherSymbol(code) {
  if (code === 0) return "☀";
  if ([1, 2].includes(code)) return "◒";
  if (code === 3) return "☁";
  if ([45, 48].includes(code)) return "≋";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "✻";
  if ([95, 96, 99].includes(code)) return "ϟ";
  if (code != null) return "☂";
  return "—";
}

export function formatDateLabel(dateString, options = {}) {
  if (!dateString) return "—";
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    ...options,
  }).format(new Date(`${dateString}T12:00:00`));
}

export function formatTime(dateTime) {
  if (!dateTime) return "—";
  return new Intl.DateTimeFormat("en-US", { hour: "numeric" }).format(new Date(dateTime));
}

export function formatValue(value, unit = "", digits = 0) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Number(value).toFixed(digits)}${unit}`;
}

export function offsetDate(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function hourlyRows(hourly) {
  if (!hourly?.time) return [];
  return hourly.time.map((time, index) => ({
    time,
    temperature: hourly.temperature_2m?.[index] ?? null,
    precipitationProbability: hourly.precipitation_probability?.[index] ?? null,
    precipitation: hourly.precipitation?.[index] ?? null,
    humidity: hourly.relative_humidity_2m?.[index] ?? null,
    weatherCode: hourly.weather_code?.[index] ?? null,
    windSpeed: hourly.wind_speed_10m?.[index] ?? null,
  }));
}
