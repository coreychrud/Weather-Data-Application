import { useState } from "react";
import {
  formatDateLabel,
  formatTime,
  formatValue,
  hourlyRows,
  weatherDescriptions,
  weatherSymbol,
} from "./weather.js";
import { timeDay, timeMonth, timeSunday } from "d3-time";
import { heatmapScale } from "./heatmap.js";

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ConditionHeading({ code, eyebrow, location, title }) {
  return (
    <div className="condition-heading">
      <div className="weather-symbol" aria-hidden="true">{weatherSymbol(code)}</div>
      <div>
        {location?.name && (
          <p className="weather-place-name">
            {location.name}{location.region ? <span>, {location.region}</span> : null}
          </p>
        )}
        <p className="section-kicker">{eyebrow}</p>
        <h2>{title || weatherDescriptions[code] || "Weather conditions"}</h2>
      </div>
    </div>
  );
}

export function EmptyWeather({ mode }) {
  const copy = {
    current: ["Current conditions", "Select a location to see what it feels like there right now."],
    forecast: ["Seven-day forecast", "Select a location to compare the week ahead and inspect hourly temperatures."],
    historical: ["Weather history", "Choose a date, then select a location to explore that day hour by hour."],
    monthly: ["A month in the past", "Choose a month, then select a location to compare its daily high and low temperatures."],
  }[mode];

  return (
    <section className="weather-card empty-weather">
      <div className="empty-icon" aria-hidden="true">⌖</div>
      <p className="section-kicker">Ready when you are</p>
      <h2>{copy[0]}</h2>
      <p>{copy[1]}</p>
    </section>
  );
}

export function CurrentWeather({ data, location }) {
  const current = data.current;
  const daily = data.daily;
  const temperatureUnit = data.current_units.temperature_2m;

  return (
    <section className="weather-card">
      <ConditionHeading
        code={current.weather_code}
        eyebrow={`Now · ${data.timezone_abbreviation}`}
        location={location}
        title={weatherDescriptions[current.weather_code]}
      />
      <div className="hero-reading">
        <strong>{formatValue(current.temperature_2m, temperatureUnit)}</strong>
        <span>Feels like {formatValue(current.apparent_temperature, temperatureUnit)}</span>
      </div>
      <div className="metrics-grid">
        <Metric label="Humidity" value={formatValue(current.relative_humidity_2m, "%")} />
        <Metric label="Wind" value={formatValue(current.wind_speed_10m, ` ${data.current_units.wind_speed_10m}`)} />
        <Metric label="Precipitation" value={formatValue(current.precipitation, ` ${data.current_units.precipitation}`, 2)} />
        <Metric
          label="High / low"
          value={`${formatValue(daily.temperature_2m_max[0], temperatureUnit)} / ${formatValue(daily.temperature_2m_min[0], temperatureUnit)}`}
        />
        <Metric label="Sunrise" value={formatTime(daily.sunrise[0])} />
        <Metric label="Sunset" value={formatTime(daily.sunset[0])} />
      </div>
    </section>
  );
}

function HourlyChart({ rows, temperatureUnit, precipitationUnit, isProbability = false }) {
  const chartRows = rows.filter((row) => row.temperature != null);
  if (!chartRows.length) return null;

  const width = 720;
  const height = 235;
  const left = 44;
  const right = 16;
  const top = 22;
  const plotBottom = 166;
  const temperatures = chartRows.map((row) => row.temperature);
  const min = Math.floor(Math.min(...temperatures) - 2);
  const max = Math.ceil(Math.max(...temperatures) + 2);
  const span = Math.max(max - min, 1);
  const x = (index) => left + (index / Math.max(chartRows.length - 1, 1)) * (width - left - right);
  const y = (value) => top + ((max - value) / span) * (plotBottom - top);
  const points = chartRows.map((row, index) => `${x(index)},${y(row.temperature)}`).join(" ");
  const secondaryValues = chartRows.map((row) => (
    isProbability ? row.precipitationProbability : row.precipitation
  ));
  const secondaryMax = isProbability
    ? 100
    : Math.max(...secondaryValues.filter((value) => value != null), 1);

  return (
    <div className="chart-wrap">
      <div className="chart-legend">
        <span><i className="legend-line" /> Temperature</span>
        <span><i className="legend-bar" /> {isProbability ? "Precipitation chance" : "Precipitation"}</span>
      </div>
      <svg className="hourly-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Hourly temperature and precipitation chart">
        {[0, 0.5, 1].map((ratio) => {
          const gridY = top + ratio * (plotBottom - top);
          const value = Math.round(max - ratio * span);
          return (
            <g key={ratio}>
              <line x1={left} x2={width - right} y1={gridY} y2={gridY} className="chart-grid" />
              <text x={left - 9} y={gridY + 4} className="chart-axis" textAnchor="end">{value}°</text>
            </g>
          );
        })}
        {chartRows.map((row, index) => {
          const value = secondaryValues[index];
          if (value == null || value <= 0) return null;
          const barHeight = (value / secondaryMax) * 38;
          return (
            <rect
              key={row.time}
              x={x(index) - 4}
              y={plotBottom - barHeight}
              width="8"
              height={barHeight}
              rx="4"
              className="chart-bar"
            />
          );
        })}
        <polyline points={points} className="temperature-line" />
        {chartRows.map((row, index) => (
          <circle key={row.time} cx={x(index)} cy={y(row.temperature)} r="3.2" className="temperature-point" />
        ))}
        {chartRows.map((row, index) => (
          index % 6 === 0 ? (
            <text key={row.time} x={x(index)} y="205" className="chart-axis" textAnchor="middle">
              {formatTime(row.time)}
            </text>
          ) : null
        ))}
        <text x={left} y="228" className="chart-caption">
          {temperatureUnit} · precipitation in {isProbability ? "%" : precipitationUnit}
        </text>
      </svg>
    </div>
  );
}

function DailyMetrics({ data, index = 0, historical = false }) {
  const daily = data.daily;
  const units = data.daily_units;
  return (
    <div className="metrics-grid compact">
      <Metric label="High" value={formatValue(daily.temperature_2m_max[index], units.temperature_2m_max)} />
      <Metric label="Low" value={formatValue(daily.temperature_2m_min[index], units.temperature_2m_min)} />
      <Metric
        label={historical ? "Precipitation" : "Precipitation chance"}
        value={historical
          ? formatValue(daily.precipitation_sum[index], ` ${units.precipitation_sum}`, 2)
          : formatValue(daily.precipitation_probability_max[index], units.precipitation_probability_max)}
      />
      {historical && (
        <Metric label="Peak wind" value={formatValue(daily.wind_speed_10m_max[index], ` ${units.wind_speed_10m_max}`)} />
      )}
      <Metric label="Sunrise" value={formatTime(daily.sunrise[index])} />
      <Metric label="Sunset" value={formatTime(daily.sunset[index])} />
    </div>
  );
}

export function ForecastWeather({ data, location, selectedIndex, onSelectDay }) {
  const selectedDate = data.daily.time[selectedIndex];
  const rows = hourlyRows(data.hourly).filter((row) => row.time.startsWith(selectedDate));
  const code = data.daily.weather_code[selectedIndex];

  return (
    <section className="weather-card forecast-card">
      <div className="card-heading forecast-heading">
        <ConditionHeading
          code={code}
          eyebrow={`Forecast · ${data.timezone_abbreviation}`}
          location={location}
          title={formatDateLabel(selectedDate, { weekday: "long" })}
        />
        <span className="condition-copy">{weatherDescriptions[code]}</span>
      </div>
      <div className="forecast-days" aria-label="Forecast days">
        {data.daily.time.map((date, index) => (
          <button
            type="button"
            className={`forecast-day ${selectedIndex === index ? "selected" : ""}`}
            key={date}
            onClick={() => onSelectDay(index)}
            aria-pressed={selectedIndex === index}
          >
            <span>{formatDateLabel(date)}</span>
            <b aria-hidden="true">{weatherSymbol(data.daily.weather_code[index])}</b>
            <strong>{formatValue(data.daily.temperature_2m_max[index], data.daily_units.temperature_2m_max)}</strong>
            <small>{formatValue(data.daily.temperature_2m_min[index], data.daily_units.temperature_2m_min)}</small>
          </button>
        ))}
      </div>
      <DailyMetrics data={data} index={selectedIndex} />
      <HourlyChart
        rows={rows}
        temperatureUnit={data.hourly_units.temperature_2m}
        precipitationUnit={data.hourly_units.precipitation_probability}
        isProbability
      />
    </section>
  );
}

export function HistoricalWeather({ data, location }) {
  const code = data.daily.weather_code[0];
  const date = data.daily.time[0];
  const rows = hourlyRows(data.hourly);

  return (
    <section className="weather-card forecast-card">
      <div className="card-heading forecast-heading">
        <ConditionHeading
          code={code}
          eyebrow={`Historical · ${data.timezone_abbreviation}`}
          location={location}
          title={formatDateLabel(date, { weekday: "long", year: "numeric" })}
        />
        <span className="condition-copy">{weatherDescriptions[code]}</span>
      </div>
      <DailyMetrics data={data} historical />
      <HourlyChart
        rows={rows}
        temperatureUnit={data.hourly_units.temperature_2m}
        precipitationUnit={data.hourly_units.precipitation}
      />
      <div className="hourly-table" aria-label="Selected hourly historical readings">
        {rows.filter((_, index) => index % 4 === 0).map((row) => (
          <div className="hourly-reading" key={row.time}>
            <span>{formatTime(row.time)}</span>
            <b aria-hidden="true">{weatherSymbol(row.weatherCode)}</b>
            <strong>{formatValue(row.temperature, data.hourly_units.temperature_2m)}</strong>
            <small>{formatValue(row.humidity, "%")} humidity</small>
          </div>
        ))}
      </div>
    </section>
  );
}

export function MonthlyWeather({ data, location }) {
  const [gradientMetric, setGradientMetric] = useState("high");
  const dates = data.daily.time;
  const highs = data.daily.temperature_2m_max;
  const lows = data.daily.temperature_2m_min;
  const entries = dates.map((date, index) => ({
    date,
    high: highs[index],
    low: lows[index],
  }));
  const monthDate = new Date(`${dates[0]}T12:00:00`);
  const gridStart = timeSunday.floor(timeMonth.floor(monthDate));
  const validHighs = highs.filter((value) => value != null);
  const validLows = lows.filter((value) => value != null);
  const average = (values) => values.length
    ? values.reduce((sum, value) => sum + value, 0) / values.length
    : null;
  const gradientValues = gradientMetric === "high" ? highs : lows;
  const validGradientValues = gradientValues.filter((value) => value != null);
  const temperatureScale = heatmapScale("temperature");
  const temperatureUnit = data.daily_units.temperature_2m_max;
  const temperatureColor = (value) => {
    if (value == null || !validGradientValues.length) return "#d9e1e5";
    const celsius = temperatureUnit === "°F" ? (value - 32) * 5 / 9 : value;
    return temperatureScale.color(celsius);
  };
  const calendarGradient = `linear-gradient(to right, ${Array.from(
    { length: 21 },
    (_, index) => temperatureScale.color(
      temperatureScale.min + index / 20 * (temperatureScale.max - temperatureScale.min),
    ),
  ).join(", ")})`;
  const width = 700;
  const cellWidth = width / 7;
  const cellHeight = 82;
  const dayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  return (
    <section className="weather-card monthly-card">
      <div className="card-heading">
        <ConditionHeading
          eyebrow={`Historical month · ${data.timezone_abbreviation}`}
          location={location}
          title={new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(monthDate)}
        />
      </div>
      <div className="metrics-grid compact monthly-summary">
        <Metric label="Average high" value={formatValue(average(validHighs), data.daily_units.temperature_2m_max)} />
        <Metric label="Average low" value={formatValue(average(validLows), data.daily_units.temperature_2m_min)} />
        <Metric label="Days recorded" value={`${validHighs.length} of ${entries.length}`} />
      </div>
      <div className="calendar-controls">
        <span className="calendar-control-label">Gradient based off</span>
        <div className="calendar-toggle" role="group" aria-label="Gradient based off High or Low">
          <button
            type="button"
            className={gradientMetric === "high" ? "active" : ""}
            aria-pressed={gradientMetric === "high"}
            onClick={() => setGradientMetric("high")}
          >
            High
          </button>
          <button
            type="button"
            className={gradientMetric === "low" ? "active" : ""}
            aria-pressed={gradientMetric === "low"}
            onClick={() => setGradientMetric("low")}
          >
            Low
          </button>
        </div>
        <span className="calendar-gradient-key" aria-hidden="true">
        <span>Cooler</span><i style={{ background: calendarGradient }} /><span>Hotter</span>
        </span>
      </div>
      <div className="calendar-wrap">
        <svg className="weather-calendar" viewBox={`0 0 ${width} ${cellHeight * 6 + 30}`} role="img" aria-label="Daily historical high and low temperatures calendar">
          {dayLabels.map((label, index) => (
            <text key={label} x={index * cellWidth + cellWidth / 2} y="18" className="calendar-weekday" textAnchor="middle">{label}</text>
          ))}
          {entries.map((entry) => {
            const dayDate = new Date(`${entry.date}T12:00:00`);
            const dayIndex = timeDay.count(gridStart, dayDate);
            const column = dayIndex % 7;
            const row = Math.floor(dayIndex / 7);
            const x = column * cellWidth;
            const y = row * cellHeight + 30;
            return (
              <g key={entry.date} transform={`translate(${x}, ${y})`} className="calendar-day">
                <rect
                  width={cellWidth - 5}
                  height={cellHeight - 5}
                  rx="10"
                  style={{ fill: temperatureColor(entry[gradientMetric]) }}
                />
                <text x="10" y="21" className="calendar-date">{Number(entry.date.slice(-2))}</text>
                <text x="10" y="46" className="calendar-high">{formatValue(entry.high, data.daily_units.temperature_2m_max)}</text>
                <text x="10" y="65" className="calendar-low">{formatValue(entry.low, data.daily_units.temperature_2m_min)}</text>
                <title>{`${formatDateLabel(entry.date)}: high ${formatValue(entry.high, data.daily_units.temperature_2m_max)}, low ${formatValue(entry.low, data.daily_units.temperature_2m_min)}`}</title>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}

export function LoadingWeather() {
  return (
    <section className="weather-card loading-weather" aria-busy="true">
      <div className="loader" aria-hidden="true" />
      <p className="section-kicker">Gathering weather data</p>
      <h2>Reading the skies…</h2>
    </section>
  );
}

export function ErrorWeather({ message, onRetry }) {
  return (
    <section className="weather-card error-weather" role="alert">
      <div className="empty-icon error-icon" aria-hidden="true">!</div>
      <p className="section-kicker">Request unsuccessful</p>
      <h2>We couldn’t load this weather</h2>
      <p>{message}</p>
      <button className="primary-button" type="button" onClick={onRetry}>Try again</button>
    </section>
  );
}
