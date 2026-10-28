import { useEffect, useMemo, useRef, useState } from "react";
import { geoAlbersUsa, geoCentroid, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import us from "us-atlas/states-10m.json";
import { majorMetros, placeRoleLabel, statePlacesById } from "./places.js";

const states = feature(us, us.objects.states).features;
const stateNames = {
  "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas",
  "06": "California", "08": "Colorado", "09": "Connecticut", "10": "Delaware",
  "11": "District of Columbia", "12": "Florida", "13": "Georgia", "15": "Hawaii",
  "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa", "20": "Kansas",
  "21": "Kentucky", "22": "Louisiana", "23": "Maine", "24": "Maryland",
  "25": "Massachusetts", "26": "Michigan", "27": "Minnesota", "28": "Mississippi",
  "29": "Missouri", "30": "Montana", "31": "Nebraska", "32": "Nevada",
  "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico", "36": "New York",
  "37": "North Carolina", "38": "North Dakota", "39": "Ohio", "40": "Oklahoma",
  "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island", "45": "South Carolina",
  "46": "South Dakota", "47": "Tennessee", "48": "Texas", "49": "Utah",
  "50": "Vermont", "51": "Virginia", "53": "Washington", "54": "West Virginia",
  "55": "Wisconsin", "56": "Wyoming", "60": "American Samoa", "66": "Guam",
  "69": "Northern Mariana Islands", "72": "Puerto Rico", "78": "U.S. Virgin Islands",
};

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

export default function MapPicker({ selectedLocation, onSelect }) {
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
  const projectedLocation = selectedLocation
    ? projection([selectedLocation.longitude, selectedLocation.latitude])
    : null;
  const visiblePlaces = useMemo(() => {
    if (!activeStateId) return majorMetros;

    const statePlaces = mergeStatePlacesWithMetros(activeStateId);
    if (
      selectedLocation?.placeId
      && selectedLocation.stateId === activeStateId
      && !statePlaces.some((place) => (
        place.id === selectedLocation.placeId || isSameNamedPlace(place, selectedLocation)
      ))
    ) {
      return [...statePlaces, selectedLocation];
    }
    return statePlaces;
  }, [activeStateId, selectedLocation]);
  const projectedPlaces = useMemo(
    () => visiblePlaces
      .map((place) => ({ place, point: projection([place.longitude, place.latitude]) }))
      .filter(({ point }) => point),
    [projection, visiblePlaces],
  );
  const selectedPlaceIsVisible = selectedLocation?.placeId
    && visiblePlaces.some((place) => (
      place.id === selectedLocation.placeId || isSameNamedPlace(place, selectedLocation)
    ));

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
    if (location) onSelect(location);
  }

  function selectStateFromPointer(event, state) {
    event.stopPropagation();
    const location = locationFromPointer(event);
    if (location) onSelect(location);
    setActiveStateId(state.id);
  }

  function selectState(event, state) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    const [longitude, latitude] = geoCentroid(state);
    onSelect({ latitude, longitude });
    setActiveStateId(state.id);
  }

  function selectPlace(event, place) {
    event.stopPropagation();
    onSelect({
      ...place,
      placeId: place.id,
      detail: placeRoleLabel(place),
    });
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
          {selectedLocation?.name && (
            <div className="selected-place-pill">
              <strong>{selectedLocation.name}{selectedLocation.region ? `, ${selectedLocation.region}` : ""}</strong>
              <span>{selectedLocation.detail}</span>
            </div>
          )}
          {selectedLocation && (
            <p className="coordinate-pill">
              {selectedLocation.latitude.toFixed(2)}°, {selectedLocation.longitude.toFixed(2)}°
            </p>
          )}
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
          {projectedLocation && !selectedPlaceIsVisible && (
            <g className="location-marker" aria-hidden="true">
              <circle cx={projectedLocation[0]} cy={projectedLocation[1]} r={13 / zoom.scale} />
              <circle cx={projectedLocation[0]} cy={projectedLocation[1]} r={5 / zoom.scale} />
            </g>
          )}
          {projectedPlaces.map(({ place, point }) => {
            const isSelected = selectedLocation?.placeId === place.id
              || isSameNamedPlace(place, selectedLocation);
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
      <p className="map-help">
        {activeStateName
          ? `Viewing ${activeStateName}. Choose a metro or city marker, or click the map to refine the location.`
          : "Choose a metro marker, or click a state to zoom in and see its key cities."}
      </p>
    </section>
  );
}
