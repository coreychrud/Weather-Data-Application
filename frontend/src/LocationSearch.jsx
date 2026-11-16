
import { useEffect, useState } from "react";
import { searchLocations } from "./api/weather.js";

export default function LocationSearch({ onSelect }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchCount, setSearchCount] = useState(0);

  useEffect(() => {
    if (!searchTerm) return undefined;

    const controller = new AbortController();
    let active = true;

    searchLocations(searchTerm, controller.signal)
      .then((locations) => {
        if (!active) return;
        setResults(locations);
      })
      .catch((err) => {
        if (!active || err.name === "AbortError") return;
        setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [searchTerm, searchCount]);

  function handleSearch(event) {
    event.preventDefault();

    const name = query.trim();
    if (name.length < 2) {
      setError("Enter at least two characters.");
      setResults([]);
      setSearched(false);
      return;
    }

    setError("");
    setResults([]);
    setSearched(true);
    setLoading(true);
    setSearchTerm(name);
    setSearchCount((count) => count + 1);
  }

  function handleSelect(location) {
    onSelect({
      name: location.name,
      region: location.admin1 || location.country || "",
      detail: [location.admin1, location.country]
        .filter(Boolean)
        .join(", "),
      latitude: location.latitude,
      longitude: location.longitude,
    });

    setQuery(location.name);
    setResults([]);
    setSearched(false);
    setSearchTerm("");
  }

  return (
    <section className="location-search">
      <h2>Search for a location</h2>
      <p>Enter a city or place name to find its coordinates.</p>

      <form onSubmit={handleSearch} className="location-search-form">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. Austin, Seattle, College Station"
          aria-label="Location name"
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && (
        <p className="location-search-error" role="alert">
          {error}
        </p>
      )}

      {loading && <p role="status">Searching for locations...</p>}

      {!loading && searched && !error && results.length === 0 && (
        <p role="status">No matching locations found.</p>
      )}

      {results.length > 0 && (
        <div className="location-search-results">
          <h3>Select a location</h3>
          <ul>
            {results.map((location, index) => (
              <li key={`${location.latitude}-${location.longitude}-${index}`}>
                <button
                  type="button"
                  onClick={() => handleSelect(location)}
                >
                  <strong>{location.name}</strong>
                  <span>
                    {[location.admin1, location.country]
                      .filter(Boolean)
                      .join(", ")}
                  </span>
                  <small>
                    {location.latitude.toFixed(4)}°,
                    {" "}{location.longitude.toFixed(4)}°
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
