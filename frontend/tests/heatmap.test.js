import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
import { geoAlbersUsa, geoContains, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import { CELL_SIZE, MAP_WIDTH, MAP_HEIGHT, createHeatmapGrid, heatmapReading, heatmapScale } from "../src/heatmap.js";

const require = createRequire(import.meta.url);
const us = require("us-atlas/states-10m.json");
const states = feature(us, us.objects.states).features;
const projection = geoAlbersUsa().fitExtent([[20, 20], [MAP_WIDTH - 20, MAP_HEIGHT - 20]], {
  type: "FeatureCollection", features: states,
});
const path = geoPath(projection);
const mappedStates = states.filter((state) => path.area(state) > 0);
const national = createHeatmapGrid(projection, mappedStates, { scale: 1, x: 0, y: 0 });

test("national grid covers the contiguous US, Alaska, and Hawaii within the API budget", () => {
  assert.equal(mappedStates.length, 51);
  assert.ok(national.length > 100 && national.length <= 384);
  for (const stateId of ["02", "06", "15", "17", "36", "48"]) {
    assert.ok(national.some((cell) => cell.stateId === stateId), stateId);
  }
  assert.equal(new Set(national.map((cell) => cell.id)).size, national.length);
});

test("every state and DC get a valid, more detailed grid contained in their geography", () => {
  for (const state of mappedStates) {
    const [[x0, y0], [x1, y1]] = path.bounds(state);
    const scale = Math.min((MAP_WIDTH - 80) / (x1 - x0), (MAP_HEIGHT - 80) / (y1 - y0));
    const zoom = { scale, x: MAP_WIDTH / 2 - scale * (x0 + x1) / 2, y: MAP_HEIGHT / 2 - scale * (y0 + y1) / 2 };
    const cells = createHeatmapGrid(projection, [state], zoom);
    assert.ok(cells.length > 0 && cells.length <= 384, state.id);
    assert.ok(cells.length > national.filter((cell) => cell.stateId === state.id).length, state.id);
    for (const cell of cells) {
      assert.equal(cell.stateId, state.id);
      assert.ok(geoContains(state, [cell.longitude, cell.latitude]), `${state.id}: rounded sample must stay on land`);
      const point = projection([cell.longitude, cell.latitude]);
      const x = point[0] * zoom.scale + zoom.x;
      const y = point[1] * zoom.scale + zoom.y;
      assert.ok(x >= cell.x - 0.1 && x <= cell.x + CELL_SIZE + 0.1, state.id);
      assert.ok(y >= cell.y - 0.1 && y <= cell.y + CELL_SIZE + 0.1, state.id);
    }
  }
});

test("unit conversions preserve zero precipitation and missing readings", () => {
  assert.equal(heatmapReading({ temperature: 0 }, "temperature", "imperial"), 32);
  assert.equal(heatmapReading({ temperature: -40 }, "temperature", "imperial"), -40);
  assert.equal(heatmapReading({ precipitation: 25.4 }, "precipitation", "imperial"), 1);
  assert.equal(heatmapReading({ precipitation: 0 }, "precipitation", "imperial"), 0);
  assert.equal(heatmapReading({ temperature: 12 }, "temperature", "metric"), 12);
  for (const sample of [null, {}, { temperature: null }, { temperature: NaN }]) {
    assert.equal(heatmapReading(sample, "temperature", "imperial"), null);
  }
});

test("fixed color scales clamp extremes and distinguish dry cells from missing data", () => {
  for (const metric of ["temperature", "precipitation"]) {
    const scale = heatmapScale(metric);
    assert.equal(scale.color(scale.min - 100), scale.color(scale.min));
    assert.equal(scale.color(scale.max + 100), scale.color(scale.max));
    assert.notEqual(scale.color(null), scale.color(0));
    assert.equal(scale.color(undefined), scale.color(null));
    assert.notEqual(scale.color(scale.min), scale.color(scale.max));
  }
});
