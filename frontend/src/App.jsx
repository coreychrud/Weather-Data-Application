import { useEffect, useState } from "react";
import { getDayWeather, getForecast } from "./api/weather.js";
import MapPicker from "./MapPicker.jsx";
import {
  CurrentWeather,
  EmptyWeather,
  ErrorWeather,
  ForecastWeather,
  HistoricalWeather,
  LoadingWeather,
} from "./WeatherViews.jsx";
import { offsetDate } from "./weather.js";

const modes = [
  { id: "current", label: "Current", description: "Conditions right now" },
  { id: "forecast", label: "Forecast", description: "The next seven days" },
  { id: "historical", label: "History", description: "A day in the past" },
];

function App() {
  const [mode, setMode] = useState("current");
  const [units, setUnits] = useState("imperial");
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [historyDate, setHistoryDate] = useState(() => offsetDate(-7));
  const [dataRecord, setDataRecord] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedForecastIndex, setSelectedForecastIndex] = useState(0);
  const [retryCount, setRetryCount] = useState(0);

  const requestKey = selectedLocation
    ? [mode, units, historyDate, selectedLocation.latitude, selectedLocation.longitude].join("|")
    : "";

  useEffect(() => {
    if (!selectedLocation) {
      setDataRecord(null);
      return undefined;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError("");
    setSelectedForecastIndex(0);

    const request = mode === "historical"
      ? getDayWeather({
        category: "historical",
        date: historyDate,
        units,
        signal: controller.signal,
        ...selectedLocation,
      })
      : getForecast({
        days: mode === "forecast" ? 7 : 1,
        units,
        signal: controller.signal,
        ...selectedLocation,
      });

    request
      .then((payload) => setDataRecord({ key: requestKey, payload }))
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [historyDate, mode, requestKey, retryCount, selectedLocation, units]);

  const selectedMode = modes.find((item) => item.id === mode);
  const data = dataRecord?.key === requestKey ? dataRecord.payload : null;

  let weatherContent = <EmptyWeather mode={mode} />;
  if (selectedLocation && isLoading) weatherContent = <LoadingWeather />;
  if (selectedLocation && error) {
    weatherContent = <ErrorWeather message={error} onRetry={() => setRetryCount((count) => count + 1)} />;
  }
  if (selectedLocation && data && !isLoading && !error) {
    if (mode === "current") weatherContent = <CurrentWeather data={data} />;
    if (mode === "forecast") {
      weatherContent = (
        <ForecastWeather
          data={data}
          selectedIndex={selectedForecastIndex}
          onSelectDay={setSelectedForecastIndex}
        />
      );
    }
    if (mode === "historical") weatherContent = <HistoricalWeather data={data} />;
  }

  return (
    <main className="app-shell">
      <header className="site-header">
        <div>
          <p className="eyebrow">Weather Data Application</p>
          <h1>Weather across time.</h1>
          <p className="subtitle">Explore live conditions, the week ahead, or a day from the past.</p>
        </div>
        <div className="unit-toggle" aria-label="Measurement units">
          <button type="button" className={units === "imperial" ? "active" : ""} onClick={() => setUnits("imperial")} aria-pressed={units === "imperial"}>°F</button>
          <button type="button" className={units === "metric" ? "active" : ""} onClick={() => setUnits("metric")} aria-pressed={units === "metric"}>°C</button>
        </div>
      </header>

      <nav className="mode-tabs" aria-label="Weather data mode">
        {modes.map((item) => (
          <button
            type="button"
            key={item.id}
            className={mode === item.id ? "active" : ""}
            onClick={() => setMode(item.id)}
            aria-current={mode === item.id ? "page" : undefined}
          >
            <strong>{item.label}</strong>
            <span>{item.description}</span>
          </button>
        ))}
      </nav>

      <div className="mode-toolbar">
        <p><strong>{selectedMode.label}</strong> · {selectedMode.description}</p>
        {mode === "historical" && (
          <label className="date-control">
            <span>Historical date</span>
            <input
              type="date"
              value={historyDate}
              min="1940-01-01"
              max={offsetDate(-1)}
              onChange={(event) => setHistoryDate(event.target.value)}
            />
            <small>Archive data can lag by several days.</small>
          </label>
        )}
      </div>

      <section className="content-grid">
        <MapPicker selectedLocation={selectedLocation} onSelect={setSelectedLocation} />
        <div className="weather-region" aria-live="polite">{weatherContent}</div>
      </section>
    </main>
  );
}

export default App;
