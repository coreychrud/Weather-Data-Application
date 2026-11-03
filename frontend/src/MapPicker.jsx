import { useEffect, useMemo, useRef, useState } from "react";
import { geoAlbersUsa, geoCentroid, geoPath } from "d3-geo";
import { states, stateNames } from "./mapData.js";
import { majorMetros, placeRoleLabel, statePlacesById } from "./places.js";

const identityZoom = { scale: 1, x: 0, y: 0 };

function isSameNamedPlace(first, second) {
  return Boolean(
    first?.name
    && second?.name
    && first.name === second.name
    && first.region === second.region,
  );
}

function mergeStatePlacesWithMetros(stateId) {
  const statePlaces = statePlacesById[stateId] || [];
  const stateMetros = majorMetros.filter((place) => place.stateId === stateId);
  const mergedMetroIds = new Set();

  const mergedStatePlaces = statePlaces.map((place) => {
    const metro = stateMetros.find((candidate) => isSameNamedPlace(place, candidate));
    if (!metro) return place;

    mergedMetroIds.add(metro.id);
    return {
      ...place,
      metroId: metro.id,
      population: metro.population,
      roles: [...place.roles, "Major metro"],
    };
  });

  return [
    ...mergedStatePlaces,
    ...stateMetros.filter((metro) => !mergedMetroIds.has(metro.id)),
  ];
}

function PlaceGlyph({ markerType }) {
  return (
    <>
      <circle className="place-badge" r="10" />
      {markerType === "metro" && (
        <g className="place-glyph metro-glyph">
          <rect x="-6" y="-2" width="3.5" height="7" rx="0.7" />
          <rect x="-1.75" y="-6" width="3.5" height="11" rx="0.7" />
          <rect x="2.5" y="-4" width="3.5" height="9" rx="0.7" />
        </g>
      )}
      {markerType === "capital" && (
        <path
          className="place-glyph capital-glyph"
          d="M0-6 1.8-2.1 6-1.7 2.8 1.1 3.8 5.2 0 3-3.8 5.2-2.8 1.1-6-1.7-1.8-2.1Z"
        />
      )}
      {markerType === "largest" && (
        <path className="place-glyph largest-glyph" d="M-5.5 5V-2.8h3V-6h5v3.2h3V5ZM-.8-3.8h1.6v1.6H-.8ZM-.8-.7h1.6V.9H-.8Z" />
      )}
      {markerType === "combined" && (
        <>
          <circle className="combined-ring" r="10" />
          <path
            className="place-glyph combined-glyph"
            d="M0-5.6 1.7-2 5.6-1.6 2.6 1 3.5 4.9 0 2.8-3.5 4.9-2.6 1-5.6-1.6-1.7-2Z"
          />
        </>
      )}
    </>
  );
}

export default function MapPicker({
  selectedLocations,
  selectionLimit,
  onSelectionLimitChange,
  onSelect,
  onRemove,
}) {
  const mapRef = useRef(null);
  const svgRef = useRef(null);
  const [mapSize, setMapSize] = useState({ width: 800, height: 500 });
  const [activeStateId, setActiveStateId] = useState(null);

  useEffect(() => {
    if (!mapRef.current) return undefined;

    const updateSize = () => {
      const { width } = mapRef.current.getBoundingClientRect();
      setMapSize({ width, height: Math.max(340, Math.min(width * 0.7, 520)) });
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(mapRef.current);
    return () => observer.disconnect();
  }, []);

  const projection = useMemo(
    () => geoAlbersUsa().fitSize([mapSize.width, mapSize.height], {
      type: "FeatureCollection",
      features: states,
    }),
    [mapSize],
  );
  const path = useMemo(() => geoPath(projection), [projection]);
  const activeState = useMemo(
    () => states.find((state) => state.id === activeStateId) || null,
    [activeStateId],
  );
  const zoom = useMemo(() => {
    if (!activeState) return identityZoom;

    const [[x0, y0], [x1, y1]] = path.bounds(activeState);
    if (![x0, y0, x1, y1].every(Number.isFinite) || x1 <= x0 || y1 <= y0) {
      return identityZoom;
    }

    const padding = Math.max(28, Math.min(mapSize.width, mapSize.height) * 0.09);
    const scale = Math.min(
      (mapSize.width - padding * 2) / (x1 - x0),
      (mapSize.height - padding * 2) / (y1 - y0),
      9,
    );

    return {
      scale,
      x: mapSize.width / 2 - scale * (x0 + x1) / 2,
      y: mapSize.height / 2 - scale * (y0 + y1) / 2,
    };
  }, [activeState, mapSize, path]);
  const visiblePlaces = useMemo(() => {
    if (!activeStateId) return majorMetros;

    const statePlaces = mergeStatePlacesWithMetros(activeStateId);
    if (
      selectedLocations.some((location) => location.placeId && location.stateId === activeStateId)
      && !selectedLocations.some((location) => statePlaces.some((place) => (
        place.id === location.placeId || isSameNamedPlace(place, location)
      )))
    ) {
      return [...statePlaces, ...selectedLocations.filter((location) => location.stateId === activeStateId)];
    }
    return statePlaces;
  }, [activeStateId, selectedLocations]);
  const projectedLocations = selectedLocations
    .map((location, index) => ({ location, index }))
    .filter(({ location }) => !visiblePlaces.some((place) => (
      place.id === location.placeId || isSameNamedPlace(place, location)
    )))
    .map(({ location, index }) => ({
      location,
      index,
      point: projection([location.longitude, location.latitude]),
    }))
    .filter(({ point }) => point);
  const projectedPlaces = useMemo(
    () => visiblePlaces
      .map((place) => ({ place, point: projection([place.longitude, place.latitude]) }))
      .filter(({ point }) => point),
    [projection, visiblePlaces],
  );
  function locationFromPointer(event) {
    const svg = svgRef.current;
    if (!svg) return null;
    const bounds = svg.getBoundingClientRect();
    const screenPoint = [
      ((event.clientX - bounds.left) / bounds.width) * mapSize.width,
      ((event.clientY - bounds.top) / bounds.height) * mapSize.height,
    ];
    const point = [
      (screenPoint[0] - zoom.x) / zoom.scale,
      (screenPoint[1] - zoom.y) / zoom.scale,
    ];
    const location = projection.invert(point);
    return location ? { latitude: location[1], longitude: location[0] } : null;
  }

  function selectFromPointer(event) {
    const location = locationFromPointer(event);
    if (location) onSelect(location, event.ctrlKey || event.metaKey);
  }

  function selectStateFromPointer(event, state) {
    event.stopPropagation();
    const location = locationFromPointer(event);
    if (location) onSelect(location, event.ctrlKey || event.metaKey);
    setActiveStateId(state.id);
  }

  function selectState(event, state) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    const [longitude, latitude] = geoCentroid(state);
    onSelect({ latitude, longitude }, event.ctrlKey || event.metaKey);
    setActiveStateId(state.id);
  }

  function selectPlace(event, place) {
    event.stopPropagation();
    onSelect({
      latitude: Number(place.latitude),
      longitude: Number(place.longitude),
      name: place.name,
      region: place.region,
      state: place.state,
      stateId: place.stateId,
      roles: place.roles,
      kind: place.kind,
      placeId: place.id,
      detail: placeRoleLabel(place),
    }, event.ctrlKey || event.metaKey);
    if (states.some((state) => state.id === place.stateId)) {
      setActiveStateId(place.stateId);
    }
  }

  function selectPlaceWithKeyboard(event, place) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    selectPlace(event, place);
  }

  const activeStateName = activeState ? stateNames[activeState.id] : null;
  const zoomTransform = `translate(${zoom.x}px, ${zoom.y}px) scale(${zoom.scale})`;

  return (
    <section className="map-card" ref={mapRef} aria-labelledby="map-heading">
      <div className="card-heading">
        <div>
          <p className="section-kicker">Location</p>
          <h2 id="map-heading">Choose a place on the map</h2>
        </div>
        <div className="map-actions">
          {selectedLocations.map((location, index) => (
            <button
              className="selected-place-pill"
              type="button"
              key={`${location.latitude}:${location.longitude}`}
              onClick={() => onRemove(location)}
              title="Remove this location"
            >
              <strong>{index + 1}. {location.name || "Map point"}{location.region ? `, ${location.region}` : ""}</strong>
              <span>{location.detail || `${location.latitude.toFixed(2)}°, ${location.longitude.toFixed(2)}°`} · Remove</span>
            </button>
          ))}
          {activeState && (
            <button className="reset-map-button" type="button" onClick={() => setActiveStateId(null)}>
              Reset US view
            </button>
          )}
        </div>
      </div>
      <svg
        ref={svgRef}
        className="us-map"
        viewBox={`0 0 ${mapSize.width} ${mapSize.height}`}
        role="group"
        aria-label={activeStateName
          ? `Interactive weather map zoomed to ${activeStateName}`
          : "Interactive map of the United States"}
        onClick={selectFromPointer}
      >
        <rect width={mapSize.width} height={mapSize.height} className="map-viewport" />
        <g className="map-zoom-layer" style={{ transform: zoomTransform }}>
          <rect width={mapSize.width} height={mapSize.height} className="map-background" />
          {states.map((state) => (
            <path
              key={state.id}
              d={path(state)}
              className={`state ${activeStateId === state.id ? "active" : ""}`}
              tabIndex="0"
              role="button"
              aria-label={`Select and zoom to ${stateNames[state.id] || `state ${state.id}`}`}
              aria-pressed={activeStateId === state.id}
              onClick={(event) => selectStateFromPointer(event, state)}
              onKeyDown={(event) => selectState(event, state)}
            />
          ))}
          {projectedLocations.map(({ location, index, point }) => (
            <g className="location-marker" key={`${location.latitude}:${location.longitude}`} aria-hidden="true">
              <circle cx={point[0]} cy={point[1]} r={13 / zoom.scale} />
              <circle cx={point[0]} cy={point[1]} r={5 / zoom.scale} />
              <text x={point[0]} y={point[1] - 18 / zoom.scale} className="location-marker-label">{index + 1}</text>
            </g>
          ))}
          {projectedPlaces.map(({ place, point }) => {
            const selectedIndex = selectedLocations.findIndex((location) => (
              location.placeId === place.id || isSameNamedPlace(place, location)
            ));
            const isSelected = selectedIndex !== -1;
            const isCombined = place.roles.includes("State capital")
              && place.roles.includes("Largest city");
            const markerType = place.kind === "metro"
              ? "metro"
              : isCombined
                ? "combined"
                : place.roles.includes("State capital")
                  ? "capital"
                  : "largest";
            const labelWidth = Math.max(76, place.name.length * 6.4 + 20);

            return (
              <g key={place.id} transform={`translate(${point[0]} ${point[1]})`}>
                <g
                  className={`place-marker ${markerType} ${isSelected ? "selected" : ""}`}
                  transform={`scale(${1 / zoom.scale})`}
                  role="button"
                  tabIndex="0"
                  aria-label={`Select ${place.name}, ${place.region}: ${placeRoleLabel(place)}`}
                  onClick={(event) => selectPlace(event, place)}
                  onKeyDown={(event) => selectPlaceWithKeyboard(event, place)}
                >
                  <title>{place.name}, {place.region} — {placeRoleLabel(place)}</title>
                  <circle className="place-hit-area" r="15" />
                  <PlaceGlyph markerType={markerType} />
                  {isSelected && (
                    <text className="place-number" y="24" aria-hidden="true">
                      {selectedIndex + 1}
                    </text>
                  )}
                  <g className="place-tooltip" aria-hidden="true">
                    <rect x={-labelWidth / 2} y="-39" width={labelWidth} height="25" rx="8" />
                    <text y="-22" textAnchor="middle">{place.name}</text>
                  </g>
                </g>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="map-legend" aria-label="Map marker legend">
        {!activeState && <span><i className="legend-marker metro" /> Top 30 metros</span>}
        {activeState && (
          <>
            <span><i className="legend-marker metro" /> Major metro</span>
            <span><i className="legend-marker capital" /> State capital</span>
            <span><i className="legend-marker largest" /> Largest city</span>
            <span><i className="legend-marker combined" /> Capital + largest</span>
          </>
        )}
      </div>
      <label className="selection-control">
        <span>Locations: <strong>{selectionLimit === 1 ? "Single" : `Up to ${selectionLimit}`}</strong></span>
        <input
          type="range"
          min="1"
          max="3"
          step="1"
          value={selectionLimit}
          onChange={onSelectionLimitChange}
          aria-label="Maximum selected locations"
        />
        <small>Ctrl-click to add a point · oldest points leave first</small>
      </label>
      <p className="map-help">
        {activeStateName
          ? `Viewing ${activeStateName}. Choose a metro or city marker, or click the map to refine the location.`
          : "Choose a metro marker, or click a state to zoom in and see its key cities."}
      </p>
    </section>
  );
}
