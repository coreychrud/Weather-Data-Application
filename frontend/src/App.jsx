import { useEffect, useState } from "react";
import { getDayWeather, getForecast, getMonthWeather } from "./api/weather.js";
import MapPicker from "./MapPicker.jsx";
import Heatmap from "./Heatmap.jsx";
import {
  CurrentWeather,
  EmptyWeather,
  ErrorWeather,
  ForecastWeather,
  HistoricalWeather,
  MonthlyWeather,
  LoadingWeather,
} from "./WeatherViews.jsx";
import { offsetDate, offsetMonth } from "./weather.js";

const modes = [
  { id: "current", label: "Current", description: "Conditions right now" },
  { id: "forecast", label: "Forecast", description: "The next seven days" },
  { id: "historical", label: "History By Day", description: "A day in the past" },
  { id: "monthly", label: "History By Month", description: "A month in the past" },
  { id: "heatmap", label: "Heatmap", description: "Daily weather across the map" },
];

function App() {
  const [mode, setMode] = useState("current");
  const [units, setUnits] = useState("imperial");
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [historyDate, setHistoryDate] = useState(() => offsetDate(-7));
  const [historyMonth, setHistoryMonth] = useState(() => offsetMonth(-1));
  const [dataRecord, setDataRecord] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedForecastIndex, setSelectedForecastIndex] = useState(0);
  const [retryCount, setRetryCount] = useState(0);

  const requestKey = selectedLocation
    ? [mode, units, historyDate, historyMonth, selectedLocation.latitude, selectedLocation.longitude].join("|")
    : "";

  useEffect(() => {
    if (!selectedLocation || mode === "heatmap") {
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
      : mode === "monthly"
        ? getMonthWeather({
          month: historyMonth,
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
  }, [historyDate, historyMonth, mode, requestKey, retryCount, selectedLocation, units]);

  const selectedMode = modes.find((item) => item.id === mode);
  const data = dataRecord?.key === requestKey ? dataRecord.payload : null;

  let weatherContent = mode === "heatmap" ? null : <EmptyWeather mode={mode} />;
  if (selectedLocation && isLoading) weatherContent = <LoadingWeather />;
  if (selectedLocation && error) {
    weatherContent = <ErrorWeather message={error} onRetry={() => setRetryCount((count) => count + 1)} />;
  }
  if (selectedLocation && data && !isLoading && !error) {
    if (mode === "current") {
      weatherContent = <CurrentWeather data={data} location={selectedLocation} />;
    }
    if (mode === "forecast") {
      weatherContent = (
        <ForecastWeather
          data={data}
          location={selectedLocation}
          selectedIndex={selectedForecastIndex}
          onSelectDay={setSelectedForecastIndex}
        />
      );
    }
    if (mode === "historical") {
      weatherContent = <HistoricalWeather data={data} location={selectedLocation} />;
    }
    if (mode === "monthly") {
      weatherContent = <MonthlyWeather data={data} location={selectedLocation} />;
    }
  }

  return (
    <main className="app-shell">
      <header className="site-header">
        <div>
          <p className="eyebrow">Weather Data Application</p>
          <h1>Weather across time.</h1>
          <p className="subtitle">Explore live conditions, the week ahead, or daily weather across the map.</p>
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
        {mode === "monthly" && (
          <label className="date-control">
            <span>Historical month</span>
            <input
              type="month"
              value={historyMonth}
              min="1940-01"
              max={offsetMonth(-1)}
              onChange={(event) => setHistoryMonth(event.target.value)}
            />
            <small>Daily highs and lows are from historical reanalysis.</small>
          </label>
        )}
      </div>

      {mode === "heatmap" ? <Heatmap units={units} /> : <section className="content-grid">
        <MapPicker selectedLocation={selectedLocation} onSelect={setSelectedLocation} />
        <div className="weather-region" aria-live="polite">{weatherContent}</div>
      </section>}
    </main>
  );
}

export default App;
