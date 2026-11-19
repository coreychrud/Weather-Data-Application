import { offsetDate } from "../weather.js";

// Ask the backend to interpret a question. Sends the browser's local date so
// "tomorrow" means the user's tomorrow, not the server's (which runs on UTC).
export async function naturalSearch({ query, units, signal }) {
  const response = await fetch("/api/v1/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, units, today: offsetDate(0) }),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `Search failed (${response.status})`);
  }
  return response.json();
}