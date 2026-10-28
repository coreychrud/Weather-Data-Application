import { useEffect, useMemo, useRef, useState } from "react";
import { geoAlbersUsa, geoCentroid, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import us from "us-atlas/states-10m.json";

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
          {projectedLocation && (
            <g className="location-marker" aria-hidden="true">
              <circle cx={projectedLocation[0]} cy={projectedLocation[1]} r={13 / zoom.scale} />
              <circle cx={projectedLocation[0]} cy={projectedLocation[1]} r={5 / zoom.scale} />
            </g>
          )}
        </g>
      </svg>
      <p className="map-help">
        {activeStateName
          ? `Viewing ${activeStateName}. Click again to refine the weather location.`
          : "Click a state to select a location and zoom in, or focus it and press Enter."}
      </p>
    </section>
  );
}
