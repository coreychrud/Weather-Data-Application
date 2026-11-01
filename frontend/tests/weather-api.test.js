import assert from "node:assert/strict";
import test from "node:test";
import { getHeatmap } from "../src/api/weather.js";

test("heatmap requests cache by date and coordinates, fetching both metrics together", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const payload = { samples: [{ temperature: 12, precipitation: 0 }] };
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    return { ok: true, json: async () => payload };
  };
  try {
    const options = { date: "2020-01-01", points: [{ latitude: 41, longitude: -87 }], signal: new AbortController().signal };
    assert.deepEqual(await getHeatmap(options), payload);
    assert.deepEqual(await getHeatmap(options), payload);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].path, "/api/v1/weather/heatmap");
    assert.equal(calls[0].options.method, "POST");
    assert.deepEqual(JSON.parse(calls[0].options.body), { weather_date: options.date, points: options.points });
    await getHeatmap({ ...options, date: "2020-01-02" });
    await getHeatmap({ ...options, points: [{ latitude: 42, longitude: -87 }] });
    assert.equal(calls.length, 3);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("failed requests are retryable and validation arrays become readable errors", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return { ok: false, status: 422, json: async () => ({ detail: [{ msg: "Invalid date" }] }) };
  };
  try {
    const options = { date: "2020-02-02", points: [{ latitude: 41, longitude: -87 }], signal: new AbortController().signal };
    await assert.rejects(getHeatmap(options), /Weather request failed \(422\)/);
    await assert.rejects(getHeatmap(options), /Weather request failed \(422\)/);
    assert.equal(calls, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
