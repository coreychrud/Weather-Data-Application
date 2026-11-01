import { useEffect, useId, useMemo, useRef, useState } from "react";
import { geoAlbersUsa, geoPath } from "d3-geo";
import { getHeatmap } from "./api/weather.js";
import { states, stateNames } from "./mapData.js";
import { CELL_SIZE, MAP_HEIGHT, MAP_WIDTH, createHeatmapGrid, heatmapReading, heatmapScale } from "./heatmap.js";
import { formatDateLabel, formatValue, offsetDate } from "./weather.js";

const nationalProjection = geoAlbersUsa().fitExtent([[20, 20], [MAP_WIDTH - 20, MAP_HEIGHT - 20]], {
  type: "FeatureCollection", features: states,
});
const path = geoPath(nationalProjection);
const mappedStates = states.filter((state) => path.area(state) > 0);
const identityZoom = { scale: 1, x: 0, y: 0 };

export default function Heatmap({ units }) {
  const [date, setDate] = useState(() => offsetDate(0));
  const [metric, setMetric] = useState("temperature");
  const [stateId, setStateId] = useState("");
  const [record, setRecord] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [hoveredId, setHoveredId] = useState(null);
  const svgRef = useRef(null);
  const clipId = useId();
  const activeState = mappedStates.find((state) => state.id === stateId);
  const features = useMemo(() => activeState ? [activeState] : mappedStates, [activeState]);
  const zoom = useMemo(() => {
    if (!activeState) return identityZoom;
    const [[x0, y0], [x1, y1]] = path.bounds(activeState);
    const scale = Math.min((MAP_WIDTH - 80) / (x1 - x0), (MAP_HEIGHT - 80) / (y1 - y0));
    return { scale, x: MAP_WIDTH / 2 - scale * (x0 + x1) / 2,
      y: MAP_HEIGHT / 2 - scale * (y0 + y1) / 2 };
  }, [activeState]);
  const cells = useMemo(() => createHeatmapGrid(nationalProjection, features, zoom), [features, zoom]);
  const requestKey = `${date}|${stateId}`;
  const validDate = /^\d{4}-\d{2}-\d{2}$/.test(date) && date >= "1940-01-01" && date <= offsetDate(15);
  const data = record?.key === requestKey ? record.payload : null;
  const error = record?.key === requestKey ? record.error : null;
  const loading = validDate && !data && !error;

  useEffect(() => {
    if (!validDate) return undefined;
    const controller = new AbortController();
    // Avoid spending quota on intermediate dates while a user edits the control.
    const timer = setTimeout(() => {
      getHeatmap({ date, points: cells.map(({ latitude, longitude }) => ({ latitude, longitude })),
        signal: controller.signal })
        .then((payload) => {
          if (!controller.signal.aborted) setRecord({ key: requestKey, payload });
        })
        .catch((requestError) => {
          if (!controller.signal.aborted) setRecord({ key: requestKey, error: requestError.message });
        });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [cells, date, requestKey, retryCount, validDate]);

  const scale = heatmapScale(metric);
  const unit = metric === "temperature" ? (units === "imperial" ? "°F" : "°C")
    : (units === "imperial" ? "in" : "mm");
  const label = metric === "temperature" ? "Daily average temperature" : "Daily total precipitation";
  const reading = (sample) => formatValue(heatmapReading(sample, metric, units), ` ${unit}`, metric === "precipitation" ? 2 : 1);
  const samples = data?.samples || [];
  const availableCount = samples.filter((sample) => sample[metric] != null).length;
  const hoveredIndex = cells.findIndex((cell) => cell.id === hoveredId);
  const hoveredCell = cells[hoveredIndex];
  const transform = `translate(${zoom.x} ${zoom.y}) scale(${zoom.scale})`;
  const sourceLabel = { historical: "Historical reanalysis", recent: "Recent model data", forecast: "Forecast" }[data?.source];

  function selectState(nextStateId) {
    if (nextStateId === stateId) return;
    setHoveredId(null);
    setRecord(null);
    setStateId(nextStateId);
  }

  function inspectCell(event) {
    const bounds = svgRef.current.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width * MAP_WIDTH;
    const y = (event.clientY - bounds.top) / bounds.height * MAP_HEIGHT;
    setHoveredId(`${Math.floor(x / CELL_SIZE) * CELL_SIZE}:${Math.floor(y / CELL_SIZE) * CELL_SIZE}`);
  }

  return (
    <section className="map-card heatmap-card" aria-labelledby="heatmap-heading">
      <div className="card-heading">
        <div>
          <p className="section-kicker">Geographic heatmap</p>
          <h2 id="heatmap-heading">{activeState ? stateNames[stateId] : "Weather across the United States"}</h2>
        </div>
        {activeState && <button className="reset-map-button" type="button" onClick={() => selectState("")}>Reset US view</button>}
      </div>
      <div className="heatmap-controls">
        <label className="date-control">
          <span>Weather value</span>
          <select value={metric} onChange={(event) => setMetric(event.target.value)}>
            <option value="temperature">Daily average temperature</option>
            <option value="precipitation">Daily total precipitation</option>
          </select>
        </label>
        <label className="date-control">
          <span>Date</span>
          <input type="date" value={date} min="1940-01-01" max={offsetDate(15)}
            onChange={(event) => { setRecord(null); setDate(event.target.value); }} />
        </label>
        <label className="date-control">
          <span>Area</span>
          <select value={stateId} onChange={(event) => selectState(event.target.value)}>
            <option value="">United States</option>
            {[...mappedStates].sort((a, b) => stateNames[a.id].localeCompare(stateNames[b.id])).map((state) => (
              <option key={state.id} value={state.id}>{stateNames[state.id]}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="heatmap-status" aria-live="polite">
        {!validDate && <p role="alert">Choose a date from January 1, 1940 through {formatDateLabel(offsetDate(15))}.</p>}
        {loading && <p role="status">Loading daily weather across {activeState ? stateNames[stateId] : "the US"}…</p>}
        {error && <div role="alert"><p>{error}</p><button className="reset-map-button" type="button"
          onClick={() => { setRecord(null); setRetryCount((count) => count + 1); }}>Try again</button></div>}
        {data && <p>{sourceLabel} · {formatDateLabel(date, { year: "numeric" })} · {availableCount} of {cells.length} samples available</p>}
      </div>
      <svg ref={svgRef} className="heatmap-svg" viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
        role="group" aria-label={`${label} map: ${activeState ? stateNames[stateId] : "United States"}, ${date}`}
        aria-describedby="heatmap-help" aria-busy={loading} onPointerLeave={() => setHoveredId(null)}>
        <defs>
          <clipPath id={clipId}>{features.map((state) => <path key={state.id} d={path(state)} transform={transform} />)}</clipPath>
        </defs>
        <g transform={transform} aria-hidden="true">
          {features.map((state) => <path key={state.id} d={path(state)} fill="#d9e1e5" />)}
        </g>
        {data && <g clipPath={`url(#${clipId})`} pointerEvents="none" aria-hidden="true">
          {cells.map((cell, index) => <rect key={cell.id} x={cell.x} y={cell.y} width={CELL_SIZE + 0.2} height={CELL_SIZE + 0.2}
            fill={scale.color(samples[index]?.[metric])} />)}
          {hoveredCell && <rect x={hoveredCell.x} y={hoveredCell.y} width={CELL_SIZE} height={CELL_SIZE}
            fill="none" stroke="#102033" strokeWidth="2" />}
        </g>}
        <g transform={transform}>
          {features.map((state) => <path key={state.id} d={path(state)} className="heatmap-state"
            tabIndex="0" role="button" aria-label={`Zoom heatmap to ${stateNames[state.id]}`}
            onPointerMove={inspectCell} onPointerLeave={() => setHoveredId(null)}
            onClick={() => selectState(state.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectState(state.id); }
            }}><title>{stateNames[state.id]} — select for finer detail</title></path>)}
        </g>
      </svg>
      <div className="heatmap-reading" aria-live="polite">
        {data && hoveredCell ? <>
          <strong>{reading(samples[hoveredIndex])}</strong>
          <span>Sample in {stateNames[hoveredCell.stateId]} · {hoveredCell.latitude.toFixed(2)}°, {hoveredCell.longitude.toFixed(2)}°</span>
        </> : <span>Hover over the grid to inspect a sample. Select a state for finer detail.</span>}
      </div>
      <div className="heatmap-legend" aria-label={`${label} color scale in ${unit}`}>
        <strong>{label} · {unit}</strong>
        <div className="heatmap-gradient" style={{ background: `linear-gradient(to right, ${Array.from({ length: 21 }, (_, i) => scale.color(scale.min + i / 20 * (scale.max - scale.min))).join(", ")})` }} />
        <div className="heatmap-ticks">{Array.from({ length: 6 }, (_, i) => {
          const value = scale.min + i / 5 * (scale.max - scale.min);
          return <span key={i}>{i === 0 && metric === "temperature" ? "≤ " : ""}{formatValue(heatmapReading({ [metric]: value }, metric, units), "", metric === "precipitation" && units === "imperial" ? 2 : 0)}{i === 5 ? "+" : ""}</span>;
        })}</div>
        <span className="heatmap-no-data"><i /> No data</span>
      </div>
      <p id="heatmap-help" className="map-help">Each square shows one sampled location, not an area average. Daily values use each location’s local day. Colors use a fixed scale across dates and areas. Alaska and Hawaii appear as insets.</p>
      <p className="map-help">Recent past dates use model data while the historical archive catches up. Forecast coverage varies by date and location; gray cells have no available reading. Precipitation includes rain and the water equivalent of snow.</p>
      {data && <details className="heatmap-table"><summary>View sampled values ({cells.length})</summary>
        <div className="heatmap-table-scroll" tabIndex="0" role="region" aria-label="Scrollable sampled weather values"><table>
          <caption>{label} · {formatDateLabel(date, { year: "numeric" })}</caption>
          <thead><tr><th scope="col">Sample state</th><th scope="col">Latitude</th><th scope="col">Longitude</th><th scope="col">Value ({unit})</th></tr></thead>
          <tbody>{cells.map((cell, index) => <tr key={cell.id}><td>{stateNames[cell.stateId]}</td><td>{cell.latitude.toFixed(4)}</td><td>{cell.longitude.toFixed(4)}</td><td>{samples[index]?.[metric] == null ? "No data" : reading(samples[index])}</td></tr>)}</tbody>
        </table></div>
      </details>}
      <p className="heatmap-attribution">Weather data: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a></p>
    </section>
  );
}
