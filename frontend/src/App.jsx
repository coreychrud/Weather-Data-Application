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
import LocationSearch from "./LocationSearch.jsx";
import { forecastIndex, stateIdForRegion, toSelectedLocation } from "./search.js";

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
  const [selectedLocations, setSelectedLocations] = useState([]);
  const [selectionLimit, setSelectionLimit] = useState(1);
  const [historyDate, setHistoryDate] = useState(() => offsetDate(-7));
  const [historyMonth, setHistoryMonth] = useState(() => offsetMonth(-1));
  const [weatherRecords, setWeatherRecords] = useState({});
  const [loadingKeys, setLoadingKeys] = useState([]);
  const [selectedForecastIndex, setSelectedForecastIndex] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  // Set by search: the forecast day to open, and the heatmap's date/metric/state.
  const [forecastFocusDate, setForecastFocusDate] = useState(null);
  const [heatmapRequest, setHeatmapRequest] = useState(null);
  const requestKey = [mode, units, historyDate, historyMonth, retryCount].join("|");

  useEffect(() => {
    if (!selectedLocations.length || mode === "heatmap") {
      setWeatherRecords({});
      setLoadingKeys([]);
      return undefined;
    }

    const controller = new AbortController();
    setSelectedForecastIndex(0);
    const locationKeys = selectedLocations.map((location) => recordKey(requestKey, location));
    setLoadingKeys(locationKeys);
    setWeatherRecords({});

    Promise.all(selectedLocations.map((location) => {
      const request = mode === "historical"
        ? getDayWeather({
          category: "historical",
          date: historyDate,
          units,
          signal: controller.signal,
          ...location,
        })
        : mode === "monthly"
          ? getMonthWeather({
            month: historyMonth,
            units,
            signal: controller.signal,
            ...location,
          })
          : getForecast({
            days: mode === "forecast" ? 7 : 1,
            units,
            signal: controller.signal,
            ...location,
          });

      return request
        .then((payload) => ({ key: recordKey(requestKey, location), payload }))
        .catch((requestError) => {
          if (requestError.name === "AbortError") return null;
          return { key: recordKey(requestKey, location), error: requestError.message };
        });
    })).then((records) => {
      if (controller.signal.aborted) return;
      setWeatherRecords(Object.fromEntries(records.filter(Boolean).map((record) => [
        record.key,
        record,
      ])));
      setLoadingKeys([]);
      if (mode === "forecast" && forecastFocusDate) {
        const firstPayload = records.find((record) => record?.payload)?.payload;
        setSelectedForecastIndex(forecastIndex(firstPayload, forecastFocusDate));
      }
    });

    return () => controller.abort();
  }, [forecastFocusDate, historyDate, historyMonth, mode, requestKey, selectedLocations, units]);

  function selectLocation(location, additive = false) {
    setSelectedLocations((current) => {
      const next = current.filter((item) => locationKey(item) !== locationKey(location));
      const limit = additive
        ? Math.min(3, Math.max(selectionLimit, current.length + 1))
        : selectionLimit;
      if (additive && limit !== selectionLimit) setSelectionLimit(limit);
      if (!additive && limit === 1) return [location];
      return [...next, location].slice(-limit);
    });
  }

    function changeMode(nextMode) {
    // Clicking a tab yourself cancels anything a search asked for.
    setForecastFocusDate(null);
    setHeatmapRequest(null);
    setMode(nextMode);
  }

  function resetSearchState() {
    setForecastFocusDate(null);
    setHeatmapRequest(null);
    setHistoryDate(offsetDate(-7));
    setHistoryMonth(offsetMonth(-1));
  }

  function selectLocations(locations) {
    setSelectionLimit(Math.min(3, Math.max(1, locations.length)));
    setSelectedLocations(locations.slice(0, 3));
  }

  // Picking a city from the search results: the map isn't shown on the
  // heatmap tab, so switch to current conditions first.
  function selectFromSearch(location) {
    resetSearchState();
    if (mode === "heatmap") changeMode("current");
    selectLocation(location);
  }

  function showSearchLocations(locations) {
    resetSearchState();
    if (mode === "heatmap") changeMode("current");
    selectLocations(locations);
  }

  // A search that named its places and dates: open that view directly.
  function applySearch(result) {
    resetSearchState();
    setUnits(result.units);
    if (result.mode === "heatmap") {
      setHeatmapRequest({
        date: result.date,
        metric: result.metric,
        stateId: stateIdForRegion(result.region),
        id: Date.now(),
      });
      setMode("heatmap");
      return;
    }
    setForecastFocusDate(result.mode === "forecast" ? result.date : null);
    if (result.mode === "historical" && result.date) setHistoryDate(result.date);
    if (result.mode === "monthly" && result.month) setHistoryMonth(result.month);
    setMode(result.mode);
    if (result.locations.length) {
      selectLocations(result.locations.map((location) => toSelectedLocation(location)));
    }
  }

  function changeSelectionLimit(event) {
    const limit = Number(event.target.value);
    setSelectionLimit(limit);
    setSelectedLocations((current) => limit === 1 ? current.slice(-1) : current.slice(-limit));
  }

  function removeLocation(location) {
    setSelectedLocations((current) => current.filter((item) => locationKey(item) !== locationKey(location)));
  }

  const selectedMode = modes.find((item) => item.id === mode);

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
            onClick={() => changeMode(item.id)}
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
      <LocationSearch
        units={units}
        onSelect={selectFromSearch}
        onShowLocations={showSearchLocations}
        onApply={applySearch}
      />
      
       {mode === "heatmap" ? <Heatmap units={units} request={heatmapRequest} /> : <section className="content-grid">
        <MapPicker
          selectedLocations={selectedLocations}
          selectionLimit={selectionLimit}
          onSelectionLimitChange={changeSelectionLimit}
          onSelect={selectLocation}
          onRemove={removeLocation}
        />
        <div className="weather-region" aria-live="polite">
          {!selectedLocations.length && <EmptyWeather mode={mode} />}
          {selectedLocations.map((location, index) => {
            const key = locationKey(location);
            const requestRecordKey = recordKey(requestKey, location);
            const record = weatherRecords[requestRecordKey];
            let content = <LoadingWeather />;
            if (!loadingKeys.includes(requestRecordKey) && record?.error) {
              content = <ErrorWeather message={record.error} onRetry={() => setRetryCount((count) => count + 1)} />;
            } else if (!loadingKeys.includes(requestRecordKey) && record?.payload) {
              const { payload } = record;
              if (mode === "current") content = <CurrentWeather data={payload} location={location} />;
              if (mode === "forecast") {
                content = (
                  <ForecastWeather
                    data={payload}
                    location={location}
                    selectedIndex={selectedForecastIndex}
                    onSelectDay={setSelectedForecastIndex}
                  />
                );
              }
              if (mode === "historical") content = <HistoricalWeather data={payload} location={location} />;
              if (mode === "monthly") content = <MonthlyWeather data={payload} location={location} />;
            }
            return (
              <div className="weather-panel" key={key}>
                <div className="weather-panel-card">
                  <div className="weather-panel-heading">
                    <strong>Point {index + 1}</strong>
                    <span>{location.name || `${location.latitude.toFixed(2)}°, ${location.longitude.toFixed(2)}°`}</span>
                  </div>
                  {content}
                </div>
              </div>
            );
          })}
        </div>
      </section>}
    </main>
  );
}

function locationKey(location) {
  return `${location.latitude.toFixed(4)}:${location.longitude.toFixed(4)}`;
}

function recordKey(request, location) {
  return `${request}|${locationKey(location)}`;
}

export default App;
