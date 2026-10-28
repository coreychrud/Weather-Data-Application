// Population classifications use U.S. Census Bureau Vintage 2025 estimates.
// Coordinates use 2025 Census Gazetteer internal points.

const statePlaceRecords = [
  ["01", "AL", "Alabama", ["Montgomery", 32.348503, -86.267307], ["Huntsville", 34.69772, -86.67667]],
  ["02", "AK", "Alaska", ["Juneau", 58.37291, -134.178445], ["Anchorage", 61.17425, -149.284329]],
  ["04", "AZ", "Arizona", ["Phoenix", 33.572154, -112.090132], ["Phoenix", 33.572154, -112.090132]],
  ["05", "AR", "Arkansas", ["Little Rock", 34.725393, -92.358556], ["Little Rock", 34.725393, -92.358556]],
  ["06", "CA", "California", ["Sacramento", 38.567694, -121.468161], ["Los Angeles", 34.019394, -118.410825]],
  ["08", "CO", "Colorado", ["Denver", 39.76185, -104.881105], ["Denver", 39.76185, -104.881105]],
  ["09", "CT", "Connecticut", ["Hartford", 41.765933, -72.681579], ["Bridgeport", 41.187393, -73.195757]],
  ["10", "DE", "Delaware", ["Dover", 39.160602, -75.521659], ["Wilmington", 39.735651, -75.532104]],
  ["12", "FL", "Florida", ["Tallahassee", 30.453529, -84.252272], ["Jacksonville", 30.336864, -81.661603]],
  ["13", "GA", "Georgia", ["Atlanta", 33.762909, -84.422675], ["Atlanta", 33.762909, -84.422675]],
  ["15", "HI", "Hawaii", ["Honolulu", 21.324347, -157.84764], ["Honolulu", 21.324347, -157.84764]],
  ["16", "ID", "Idaho", ["Boise", 43.59805, -116.231596], ["Boise", 43.59805, -116.231596]],
  ["17", "IL", "Illinois", ["Springfield", 39.791063, -89.644572], ["Chicago", 41.837045, -87.684939]],
  ["18", "IN", "Indiana", ["Indianapolis", 39.776664, -86.145935], ["Indianapolis", 39.776664, -86.145935]],
  ["19", "IA", "Iowa", ["Des Moines", 41.57259, -93.610243], ["Des Moines", 41.57259, -93.610243]],
  ["20", "KS", "Kansas", ["Topeka", 39.034673, -95.696191], ["Wichita", 37.690638, -97.345836]],
  ["21", "KY", "Kentucky", ["Frankfort", 38.194966, -84.865877], ["Louisville", 38.165376, -85.647377]],
  ["22", "LA", "Louisiana", ["Baton Rouge", 30.442174, -91.130894], ["New Orleans", 30.05342, -89.934502]],
  ["23", "ME", "Maine", ["Augusta", 44.334904, -69.734199], ["Portland", 43.633157, -70.185305]],
  ["24", "MD", "Maryland", ["Annapolis", 38.972152, -76.505332], ["Baltimore", 39.300032, -76.610476]],
  ["25", "MA", "Massachusetts", ["Boston", 42.338551, -71.018253], ["Boston", 42.338551, -71.018253]],
  ["26", "MI", "Michigan", ["Lansing", 42.714341, -84.560889], ["Detroit", 42.383037, -83.102237]],
  ["27", "MN", "Minnesota", ["St. Paul", 44.948901, -93.104063], ["Minneapolis", 44.963324, -93.26832]],
  ["28", "MS", "Mississippi", ["Jackson", 32.315834, -90.21285], ["Jackson", 32.315834, -90.21285]],
  ["29", "MO", "Missouri", ["Jefferson City", 38.567461, -92.175254], ["Kansas City", 39.125155, -94.550313]],
  ["30", "MT", "Montana", ["Helena", 46.595465, -112.018746], ["Billings", 45.788538, -108.552475]],
  ["31", "NE", "Nebraska", ["Lincoln", 40.810284, -96.674856], ["Omaha", 41.262705, -96.053475]],
  ["32", "NV", "Nevada", ["Carson City", 39.15306, -119.747368], ["Las Vegas", 36.233499, -115.264037]],
  ["33", "NH", "New Hampshire", ["Concord", 43.232493, -71.561252], ["Manchester", 42.984941, -71.444131]],
  ["34", "NJ", "New Jersey", ["Trenton", 40.223841, -74.763624], ["Newark", 40.72422, -74.172574]],
  ["35", "NM", "New Mexico", ["Santa Fe", 35.661981, -105.981815], ["Albuquerque", 35.10478, -106.646809]],
  ["36", "NY", "New York", ["Albany", 42.665745, -73.798353], ["New York City", 40.662712, -73.938677]],
  ["37", "NC", "North Carolina", ["Raleigh", 35.831868, -78.641042], ["Charlotte", 35.209045, -80.83099]],
  ["38", "ND", "North Dakota", ["Bismarck", 46.814572, -100.768568], ["Fargo", 46.8647, -96.82908]],
  ["39", "OH", "Ohio", ["Columbus", 39.985531, -82.985594], ["Columbus", 39.985531, -82.985594]],
  ["40", "OK", "Oklahoma", ["Oklahoma City", 35.467079, -97.513657], ["Oklahoma City", 35.467079, -97.513657]],
  ["41", "OR", "Oregon", ["Salem", 44.9239, -123.023007], ["Portland", 45.536951, -122.649971]],
  ["42", "PA", "Pennsylvania", ["Harrisburg", 40.275891, -76.88502], ["Philadelphia", 40.009376, -75.133346]],
  ["44", "RI", "Rhode Island", ["Providence", 41.823056, -71.418784], ["Providence", 41.823056, -71.418784]],
  ["45", "SC", "South Carolina", ["Columbia", 34.040519, -80.906099], ["Charleston", 32.828017, -79.972896]],
  ["46", "SD", "South Dakota", ["Pierre", 44.375163, -100.319996], ["Sioux Falls", 43.540696, -96.731962]],
  ["47", "TN", "Tennessee", ["Nashville", 36.1718, -86.785002], ["Nashville", 36.1718, -86.785002]],
  ["48", "TX", "Texas", ["Austin", 30.298622, -97.754134], ["Houston", 29.785743, -95.388806]],
  ["49", "UT", "Utah", ["Salt Lake City", 40.776928, -111.930991], ["Salt Lake City", 40.776928, -111.930991]],
  ["50", "VT", "Vermont", ["Montpelier", 44.266448, -72.571524], ["Burlington", 44.491927, -73.238882]],
  ["51", "VA", "Virginia", ["Richmond", 37.531399, -77.476009], ["Virginia Beach", 36.779525, -76.029142]],
  ["53", "WA", "Washington", ["Olympia", 47.040604, -122.895], ["Seattle", 47.619335, -122.351538]],
  ["54", "WV", "West Virginia", ["Charleston", 38.348692, -81.632324], ["Charleston", 38.348692, -81.632324]],
  ["55", "WI", "Wisconsin", ["Madison", 43.087815, -89.429856], ["Milwaukee", 43.063348, -87.966695]],
  ["56", "WY", "Wyoming", ["Cheyenne", 41.128275, -104.799155], ["Cheyenne", 41.128275, -104.799155]],
];

function slugify(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function buildStatePlaces([stateId, region, state, capital, largest]) {
  const places = new Map();

  for (const [role, entry] of [["State capital", capital], ["Largest city", largest]]) {
    const [name, latitude, longitude] = entry;
    const key = name.toLowerCase();
    const existing = places.get(key);
    if (existing) {
      existing.roles.push(role);
    } else {
      places.set(key, {
        id: `state-${stateId}-${slugify(name)}`,
        name,
        region,
        state,
        stateId,
        latitude,
        longitude,
        kind: "state-city",
        roles: [role],
      });
    }
  }

  return [...places.values()];
}

export const statePlacesById = Object.fromEntries(
  statePlaceRecords.map((record) => [record[0], buildStatePlaces(record)]),
);

export const majorMetros = [
  ["New York", "NY", "36", 40.662712, -73.938677, 20112448],
  ["Los Angeles", "CA", "06", 34.019394, -118.410825, 12844441],
  ["Chicago", "IL", "17", 41.837045, -87.684939, 9434123],
  ["Dallas–Fort Worth", "TX", "48", 32.793333, -96.766513, 8477157],
  ["Houston", "TX", "48", 29.785743, -95.388806, 7904627],
  ["Atlanta", "GA", "13", 33.762909, -84.422675, 6482182],
  ["Washington", "DC", "11", 38.904243, -77.016524, 6465724],
  ["Miami", "FL", "12", 25.775163, -80.208615, 6391072],
  ["Philadelphia", "PA", "42", 40.009376, -75.133346, 6329118],
  ["Phoenix", "AZ", "04", 33.572154, -112.090132, 5228938],
  ["Boston", "MA", "25", 42.338551, -71.018253, 5034221],
  ["Riverside–San Bernardino", "CA", "06", 33.938143, -117.393168, 4769007],
  ["San Francisco Bay Area", "CA", "06", 37.727239, -123.032229, 4630041],
  ["Detroit", "MI", "26", 42.383037, -83.102237, 4390913],
  ["Seattle", "WA", "53", 47.619335, -122.351538, 4161883],
  ["Minneapolis–St. Paul", "MN", "27", 44.963324, -93.26832, 3790295],
  ["Tampa Bay", "FL", "12", 27.970086, -82.479673, 3418895],
  ["San Diego", "CA", "06", 32.830391, -117.120923, 3282248],
  ["Denver", "CO", "08", 39.76185, -104.881105, 3092037],
  ["Orlando", "FL", "12", 28.472818, -81.320242, 2957672],
  ["Charlotte", "NC", "37", 35.209045, -80.83099, 2938830],
  ["Baltimore", "MD", "24", 39.300032, -76.610476, 2857781],
  ["St. Louis", "MO", "29", 38.635699, -90.244582, 2814421],
  ["San Antonio", "TX", "48", 29.462809, -98.524635, 2813140],
  ["Austin", "TX", "48", 30.298622, -97.754134, 2620945],
  ["Portland", "OR", "41", 45.536951, -122.649971, 2542282],
  ["Sacramento", "CA", "06", 38.567694, -121.468161, 2477274],
  ["Pittsburgh", "PA", "42", 40.439936, -79.975676, 2421992],
  ["Las Vegas", "NV", "32", 36.233499, -115.264037, 2407226],
  ["Cincinnati", "OH", "39", 39.140183, -84.505829, 2312858],
].map(([name, region, stateId, latitude, longitude, population], index) => ({
  id: `metro-${index + 1}-${slugify(name)}`,
  name,
  region,
  stateId,
  latitude,
  longitude,
  population,
  kind: "metro",
  roles: ["Major metro"],
}));

export function placeRoleLabel(place) {
  const labels = place.roles.filter((role) => role !== "Major metro");
  if (place.roles.includes("Major metro")) {
    labels.push(`Major metro · ${(place.population / 1_000_000).toFixed(1)}M people`);
  }
  return labels.join(" · ");
}
