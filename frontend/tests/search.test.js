import assert from "node:assert/strict";
import test from "node:test";
import { naturalSearch } from "../src/api/search.js";
import {
  forecastIndex,
  geocodedLocation,
  regionCode,
  stateIdForRegion,
  toSelectedLocation,
} from "../src/search.js";

test("search posts the query, units and the local date", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, body: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ mode: "current" }) };
  };
  try {
    await naturalSearch({ query: "Austin", units: "imperial" });
    assert.equal(calls[0].path, "/api/v1/search");
    assert.equal(calls[0].body.query, "Austin");
    assert.equal(calls[0].body.units, "imperial");
    assert.match(calls[0].body.today, /^\d{4}-\d{2}-\d{2}$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("search errors show the API's message", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: false, status: 422, json: async () => ({ detail: "Couldn't find a US place called “Atlantis”." }),
  });
  try {
    await assert.rejects(naturalSearch({ query: "Atlantis tomorrow", units: "imperial" }), /Atlantis/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("state codes convert to heatmap ids and back from names", () => {
  assert.equal(stateIdForRegion("TX"), "48");
  assert.equal(stateIdForRegion("DC"), "11");
  assert.equal(stateIdForRegion(null), "");
  assert.equal(regionCode("Texas"), "TX");
  assert.equal(regionCode("Ontario"), "Ontario");
});

test("search locations become map selections", () => {
  assert.deepEqual(
    toSelectedLocation({ id: "metro-10-phoenix", name: "Phoenix", region: "AZ", latitude: 33.57, longitude: -112.09 },
      "9.8 hours of sun a day"),
    { id: "metro-10-phoenix", name: "Phoenix", region: "AZ", detail: "9.8 hours of sun a day",
      latitude: 33.57, longitude: -112.09 },
  );
  assert.deepEqual(
    geocodedLocation({ name: "Springfield", admin1: "Illinois", country: "United States", latitude: 39.8, longitude: -89.6 }),
    { name: "Springfield", region: "IL", detail: "Illinois, United States", latitude: 39.8, longitude: -89.6 },
  );
});

test("forecast opens on the requested day", () => {
  const payload = { daily: { time: ["2026-11-18", "2026-11-19", "2026-11-20"] } };
  assert.equal(forecastIndex(payload, "2026-11-20"), 2);
  assert.equal(forecastIndex(payload, "2026-12-25"), 0);
  assert.equal(forecastIndex(null, "2026-11-20"), 0);
});