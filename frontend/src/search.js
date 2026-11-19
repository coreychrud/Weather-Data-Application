// Helpers for turning search results into the app's own location and map state.
import { statePlacesById } from "./places.js";

export const SEARCH_EXAMPLES = {
  cities: ["Austin", "Springfield"],
  questions: [
    "Weather in Boise tomorrow",
    "Somewhere sunny most of the year",
    "Snowy cities in January",
    "Rain heatmap of Texas yesterday",
  ],
};

const stateIdsByCode = {};
const stateCodesByName = {};
for (const [stateId, places] of Object.entries(statePlacesById)) {
  stateIdsByCode[places[0].region] = stateId;
  stateCodesByName[places[0].state.toLowerCase()] = places[0].region;
}
stateIdsByCode.DC = "11";
stateCodesByName["district of columbia"] = "DC";

// "TX" -> "48", the FIPS id the heatmap uses for states.
export function stateIdForRegion(code) {
  return (code && stateIdsByCode[code]) || "";
}

// "Texas" -> "TX", so every location reads "Name, XX" like the map's markers.
export function regionCode(stateName) {
  return (stateName && stateCodesByName[stateName.toLowerCase()]) || stateName || "";
}

// A location from /api/v1/search -> the shape App and MapPicker use.
export function toSelectedLocation(location, detail = "From search") {
  return {
    ...(location.id ? { id: location.id } : {}),
    name: location.name,
    region: location.region || "",
    detail,
    latitude: location.latitude,
    longitude: location.longitude,
  };
}

// A result from the location search's geocoder (admin1 is a full state name).
export function geocodedLocation(result) {
  return {
    name: result.name,
    region: regionCode(result.admin1) || result.country || "",
    detail: [result.admin1, result.country].filter(Boolean).join(", "),
    latitude: result.latitude,
    longitude: result.longitude,
  };
}

// Which forecast day to open for a requested date ("2026-11-20"), or the first.
export function forecastIndex(payload, date) {
  const index = payload?.daily?.time?.indexOf(date) ?? -1;
  return index >= 0 ? index : 0;
}