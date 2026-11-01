import { geoContains } from "d3-geo";

export const MAP_WIDTH = 960;
export const MAP_HEIGHT = 600;
export const CELL_SIZE = 40;

// Sample in displayed map space, so a state gets finer geographic detail.
// Coastal cells use a nearby land point within the same displayed square.
export function createHeatmapGrid(projection, features, zoom) {
  const cells = [];
  const offsets = [[0.5, 0.5], [0.15, 0.15], [0.85, 0.15], [0.15, 0.85],
    [0.85, 0.85], [0.5, 0.05], [0.5, 0.95], [0.05, 0.5], [0.95, 0.5]];
  for (let y = 0; y < MAP_HEIGHT; y += CELL_SIZE) {
    for (let x = 0; x < MAP_WIDTH; x += CELL_SIZE) {
      for (const [dx, dy] of offsets) {
        const p = [(x + dx * CELL_SIZE - zoom.x) / zoom.scale,
          (y + dy * CELL_SIZE - zoom.y) / zoom.scale];
        const coordinate = projection.invert(p);
        if (!coordinate?.every(Number.isFinite)) continue;
        const roundTrip = projection(coordinate);
        if (!roundTrip || Math.hypot(roundTrip[0] - p[0], roundTrip[1] - p[1]) > 0.01) continue;
        const state = features.find((feature) => geoContains(feature, coordinate));
        if (!state) continue;
        cells.push({
          id: `${x}:${y}`, x, y, stateId: state.id,
          latitude: Number(coordinate[1].toFixed(4)),
          longitude: Number(coordinate[0].toFixed(4)),
        });
        break;
      }
    }
  }
  return cells;
}

export function heatmapReading(sample, metric, units) {
  const value = sample?.[metric];
  if (value == null || !Number.isFinite(value)) return null;
  if (units !== "imperial") return value;
  return metric === "temperature" ? value * 9 / 5 + 32 : value / 25.4;
}

const temperatureColors = ["#364b9b", "#3d91c2", "#9bd5d5", "#f8edb0", "#ef9b54", "#b73c43"];
const precipitationColors = ["#f0f5eb", "#b8ded0", "#67b6bb", "#3689af", "#3c559d", "#503273"];

export function heatmapScale(metric) {
  // Fixed SI domains keep colors comparable across dates, views, and unit changes.
  const colors = metric === "temperature" ? temperatureColors : precipitationColors;
  const min = metric === "temperature" ? -30 : 0;
  const max = metric === "temperature" ? 45 : 100;
  return {
    min, max, colors,
    color(value) {
      if (value == null || !Number.isFinite(value)) return "#d9e1e5";
      const fraction = Math.max(0, Math.min(1, (value - min) / (max - min)));
      // Precipitation gets more color detail near zero without changing the legend domain.
      const t = metric === "precipitation" ? Math.sqrt(fraction) : fraction;
      const index = t * (colors.length - 1);
      const low = Math.min(Math.floor(index), colors.length - 2);
      const mix = index - low;
      const rgb = (hex) => [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16));
      const a = rgb(colors[low]);
      const b = rgb(colors[low + 1]);
      return `rgb(${a.map((part, i) => Math.round(part + (b[i] - part) * mix)).join(", ")})`;
    },
  };
}
