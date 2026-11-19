import { useRef, useState } from "react";
import { searchLocations } from "./api/weather.js";
import { naturalSearch } from "./api/search.js";
import { SEARCH_EXAMPLES, geocodedLocation, toSelectedLocation } from "./search.js";

// One search bar for two kinds of input:
// - a place name ("Austin")      -> pick-list of matching places, click to select
// - a question ("sunny cities")  -> the backend interprets it:
//     a lookup ("weather in Boise tomorrow") is applied right away,
//     a discover search shows a ranked list to pick from.
export default function LocationSearch({ units, onSelect, onShowLocations, onApply }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState({ state: "idle" });
  const controllerRef = useRef(null);
  const loading = status.state === "loading";

  async function run(text) {
    const trimmed = text.trim();
    if (trimmed.length < 2) {
      setStatus({ state: "error", message: "Enter at least two characters." });
      return;
    }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setQuery(trimmed);
    setStatus({ state: "loading" });

    try {
      const result = await naturalSearch({ query: trimmed, units, signal: controller.signal });
      if (result.place_only) {
        const places = await searchLocations(result.place_query, controller.signal);
        setStatus({ state: "places", places, placeQuery: result.place_query });
      } else if (result.mode === "discover") {
        setStatus({ state: "ranked", result });
      } else {
        onApply(result);
        setStatus({ state: "applied", result });
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      setStatus({ state: "error", message: error.message });
    }
  }

  function choose(location) {
    onSelect(location);
    setStatus({ state: "idle" });
  }

  return (
    <section className="location-search" aria-label="Search">
      <h2>Find a city or ask a question</h2>
      <p>
        Type a city to pick it on the map, or ask in plain English and the app will
        open the right view or suggest cities.
      </p>

      <form
        onSubmit={(event) => { event.preventDefault(); run(query); }}
        className="location-search-form"
        role="search"
      >
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Austin, or “somewhere sunny most of the year”"
          aria-label="City name or weather question"
          maxLength={300}
        />
        <button type="submit" disabled={loading}>{loading ? "Searching..." : "Search"}</button>
      </form>

      <div className="search-examples" aria-label="Examples">
        <span>City:</span>
        {SEARCH_EXAMPLES.cities.map((example) => (
          <button type="button" key={example} onClick={() => run(example)}>{example}</button>
        ))}
        <span>Question:</span>
        {SEARCH_EXAMPLES.questions.map((example) => (
          <button type="button" key={example} onClick={() => run(example)}>{example}</button>
        ))}
      </div>

      <div aria-live="polite">
        {loading && <p role="status">Searching...</p>}

        {status.state === "error" && (
          <p className="location-search-error" role="alert">{status.message}</p>
        )}

        {status.state === "applied" && (
          <p className="search-answer">{status.result.summary}</p>
        )}

        {status.state === "places" && status.places.length === 0 && (
          <p role="status">No places named “{status.placeQuery}” were found.</p>
        )}

        {status.state === "places" && status.places.length > 0 && (
          <div className="location-search-results">
            <h3>Select a location</h3>
            <ul>
              {status.places.map((place, index) => (
                <li key={`${place.latitude}-${place.longitude}-${index}`}>
                  <button type="button" onClick={() => choose(geocodedLocation(place))}>
                    <strong>{place.name}</strong>
                    <span>{[place.admin1, place.country].filter(Boolean).join(", ")}</span>
                    <small>{place.latitude.toFixed(4)}°, {place.longitude.toFixed(4)}°</small>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {status.state === "ranked" && (
          <div className="location-search-results">
            <p className="search-answer">{status.result.summary}</p>
            {status.result.results.length > 0 && (
              <>
                <div className="ranked-heading">
                  <h3>Select a city</h3>
                  <button
                    type="button"
                    className="show-top"
                    onClick={() => {
                      onShowLocations(status.result.locations.map((location) => toSelectedLocation(location)));
                      setStatus({ state: "idle" });
                    }}
                  >
                    Show top {status.result.locations.length} on map
                  </button>
                </div>
                <ol className="ranked-list">
                  {status.result.results.map((city) => (
                    <li key={city.id || city.name}>
                      <button type="button" onClick={() => choose(toSelectedLocation(city, city.highlight))}>
                        <strong>{city.rank}. {city.name}, {city.region}</strong>
                        <span>
                          {city.highlight}
                          {/* All-year searches rank by how many months qualify, so show it. */}
                          {city.month_count === 12 && ` · ${city.good_months} of 12 months qualify`}
                        </span>
                        <small>High {city.high} · Low {city.low} · {city.precipitation} rain a month</small>
                      </button>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}