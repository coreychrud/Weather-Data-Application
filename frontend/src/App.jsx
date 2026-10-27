import { useEffect, useMemo, useRef, useState } from "react";
import { geoAlbersUsa, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import us from "us-atlas/states-10m.json";

const states = feature(us, us.objects.states).features;

const weatherDescriptions = {
  0: "Clear sky",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Depositing rime fog",
  51: "Light drizzle",
  53: "Moderate drizzle",
  55: "Dense drizzle",
  61: "Slight rain",
  63: "Moderate rain",
  65: "Heavy rain",
  71: "Slight snow",
  73: "Moderate snow",
  75: "Heavy snow",
  80: "Slight rain showers",
  81: "Moderate rain showers",
  82: "Violent rain showers",
  95: "Thunderstorm",
  96: "Thunderstorm with slight hail",
  99: "Thunderstorm with heavy hail",
};

function App() {
  const mapRef = useRef(null);
  const [mapSize, setMapSize] = useState({ width: 800, height: 500 });
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [weather, setWeather] = useState(null);
  const [status, setStatus] = useState("Click anywhere on the map to get current weather.");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!mapRef.current) {
      return undefined;
    }

    const updateSize = () => {
      const { width, height } = mapRef.current.getBoundingClientRect();
      setMapSize({ width, height: Math.max(360, Math.min(width * 0.65, 560)) });
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(mapRef.current);
    return () => observer.disconnect();
  }, []);

  const projection = useMemo(
    () => geoAlbersUsa().fitSize([mapSize.width, mapSize.height], { type: "FeatureCollection", features: states }),
    [mapSize],
  );
  const path = useMemo(() => geoPath(projection), [projection]);

  async function loadWeather(latitude, longitude) {
    setSelectedLocation({ latitude, longitude });
    setWeather(null);
    setIsLoading(true);
    setStatus("Loading current weather...");

    const params = new URLSearchParams({
      latitude: latitude.toFixed(4),
      longitude: longitude.toFixed(4),
      forecast_days: "1",
      timezone: "auto",
      units: "imperial",
    });

    try {
      const response = await fetch(`/api/v1/forecast?${params}`);
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Weather request failed (${response.status})`);
      }
      setWeather(await response.json());
      setStatus("Current weather loaded.");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setIsLoading(false);
    }
  }

  function handleMapClick(event) {
    const svg = event.currentTarget.ownerSVGElement;
    const bounds = svg.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * mapSize.width;
    const y = ((event.clientY - bounds.top) / bounds.height) * mapSize.height;
    const location = projection.invert([x, y]);
    if (location) {
      loadWeather(location[1], location[0]);
    }
  }

  const current = weather?.current;
  const temperatureUnit = weather?.current_units?.temperature_2m || "°F";

  return (
    <main className="app-shell">
      <header>
        <p className="eyebrow">Weather Data Application</p>
        <h1>Explore current weather across the US</h1>
        <p className="subtitle">Click a state to retrieve live weather for that location.</p>
      </header>

      <section className="content-grid">
        <div className="map-card" ref={mapRef}>
          <svg
            className="us-map"
            viewBox={`0 0 ${mapSize.width} ${mapSize.height}`}
            role="img"
            aria-label="Clickable map of the United States"
          >
            <rect
              width={mapSize.width}
              height={mapSize.height}
              className="map-background"
              onClick={handleMapClick}
            />
            {states.map((state) => (
              <path
                key={state.id}
                d={path(state)}
                className="state"
                onClick={handleMapClick}
                tabIndex="0"
                aria-label="Select this state"
              />
            ))}
            {selectedLocation && projection(selectedLocation) && (
              <circle
                className="location-pin"
                cx={projection(selectedLocation)[0]}
                cy={projection(selectedLocation)[1]}
                r="7"
              />
            )}
          </svg>
        </div>

        <aside className="weather-card">
          <p className="status">{status}</p>
          {isLoading && <div className="loader" aria-label="Loading" />}
          {current && (
            <div className="weather-details">
              <p className="location">
                {weather.latitude.toFixed(2)}°, {weather.longitude.toFixed(2)}°
              </p>
              <p className="condition">{weatherDescriptions[current.weather_code] || "Current conditions"}</p>
              <p className="temperature">
                {Math.round(current.temperature_2m)}
                {temperatureUnit}
              </p>
              <div className="details-grid">
                <span>Feels like <strong>{Math.round(current.apparent_temperature)}{temperatureUnit}</strong></span>
                <span>Humidity <strong>{current.relative_humidity_2m}%</strong></span>
                <span>Wind <strong>{Math.round(current.wind_speed_10m)} mph</strong></span>
                <span>Precipitation <strong>{current.precipitation} in</strong></span>
              </div>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

export default App;
