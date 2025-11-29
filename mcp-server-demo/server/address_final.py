"""
FINAL PRODUCTION-READY ADDRESS & LANDMARK UTILITY
Single interactive file with geocoding, landmarks, and routing
Uses free OpenStreetMap services (Nominatim, Overpass, OSRM)

Features:
  - Get address details & nearby landmarks for any place
  - Find routes and distances between two locations
  - Automatic caching and rate-limiting
  - Unicode-safe output for Windows console
  - No CLI arguments needed (interactive menu)
"""

import json
import logging
import os
import sys
import time
import webbrowser
from typing import Optional, Dict, Any, Tuple, List

import math
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================================
# CONFIGURATION
# ============================================================================

LOGGER = logging.getLogger("address_final")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(asctime)s %(levelname)s %(message)s"
)

USER_AGENT = "address-final/1.0"

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]
OSRM_URL = "http://router.project-osrm.org"

NOMINATIM_MIN_INTERVAL = 1.1
DEFAULT_TIMEOUT = 15
CACHE_TTL = 3600

# ============================================================================
# CACHE SYSTEM
# ============================================================================

class TTLCache:
    """Simple in-memory cache with TTL expiry"""
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    def get(self, key: str):
        if key in self._data and time.time() < self._expiry.get(key, 0):
            return self._data[key]
        return None

    def set(self, key: str, value: Any, ttl: int = CACHE_TTL):
        self._data[key] = value
        self._expiry[key] = time.time() + ttl


_cache = TTLCache()

# ============================================================================
# HTTP SESSION & NETWORKING
# ============================================================================

def _build_session() -> requests.Session:
    """Build HTTP session with retry strategy and headers"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504)
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "en"
    })
    return session

SESSION = _build_session()
_last_nominatim_call = 0.0

def _nominatim_wait():
    """Rate-limiting for Nominatim (1.1 seconds minimum between calls)"""
    global _last_nominatim_call
    elapsed = time.time() - _last_nominatim_call
    if elapsed < NOMINATIM_MIN_INTERVAL:
        time.sleep(NOMINATIM_MIN_INTERVAL - elapsed)
    _last_nominatim_call = time.time()

def _request_json(url: str, params=None, method: str = "get", data=None, timeout: int = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
    """Make HTTP request and return JSON response"""
    try:
        if method.lower() == "get":
            r = SESSION.get(url, params=params, timeout=timeout)
        else:
            r = SESSION.post(url, data=data, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        LOGGER.debug("Request failed for %s: %s", url, exc)
        return None

# ============================================================================
# DISTANCE CALCULATIONS
# ============================================================================

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Calculate great-circle distance in kilometers between two points"""
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))

# ============================================================================
# GEOCODING (ADDRESS LOOKUP)
# ============================================================================

def _geocode_nominatim(place: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Query Nominatim for address candidates - searches for all place types including small villages"""
    _nominatim_wait()
    params = {
        "q": place,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit
    }
    result = _request_json(f"{NOMINATIM_URL}/search", params=params)
    if isinstance(result, list):
        return result
    return None

def _score_geocode_result(res: Dict[str, Any]) -> int:
    """Score a geocoding result to find best match - includes small villages"""
    score = 0
    cls = (res.get("class") or "").lower()
    typ = (res.get("type") or "").lower()
    display = (res.get("display_name") or "").lower()
    importance = float(res.get("importance") or 0)

    # Type-based scoring (accept all settlement types including villages)
    if typ in ["city", "town", "municipality", "administrative"]:
        score += 100
    elif typ in ["village", "hamlet", "neighbourhood", "suburb"]:
        score += 80  # High score for villages/hamlets
    elif typ == "bus_station":
        score += 50
    elif typ in ["road", "street", "path", "pedestrian", "footway", "residential"]:
        score -= 50

    # Importance bonus (applies to all places, even small ones)
    score += int(importance * 50)

    # Has detailed address
    if res.get("address") and res["address"].get("postcode"):
        score += 5

    # Bus/station keywords
    if "bus" in cls or "bus" in typ or "bus" in display:
        score += 40

    return score

def find_best_geocode(place: str, verbose: bool = False) -> Optional[Dict[str, Any]]:
    """Find best geocoding result with multiple search variants - supports small villages"""
    # Generate candidate place name variants with smart detection
    variants = [place]
    
    place_lower = place.lower()
    
    # Add variants with country/state specifications to help find small locations
    variants += [
        f"{place}, India",
        f"{place}, rural",
        f"{place}, village",
        f"{place}, hamlet"
    ]
    
    # If place contains "college" or "institute" or "school", try broader searches
    if any(keyword in place_lower for keyword in ["college", "institute", "school", "university", "engineering", "medical"]):
        # Extract city clues from the place name
        for city in ["trichy", "tiruchirappalli", "tiruchchirappalli", "madurai", "salem", "coimbatore", "tamil nadu"]:
            if city in place_lower:
                variants += [place.replace("rp college", "ramakrishnan polytechnic college").replace("tt rp", "TRP")]
                break
        
        # Add variants with common cities
        variants += [f"{place}, Trichy", f"{place}, Tiruchirappalli"]
        
        # Try extracting key words (college name without typos)
        words = place.split()
        if len(words) >= 2:
            # Try combinations of words
            variants += [" ".join(words[:2]), " ".join(words[-2:])]
    
    # Clean and deduplicate
    seen = set()
    tried = []
    for v in variants:
        v = v.strip()
        if v and v not in seen and len(v) > 2:
            seen.add(v)
            tried.append(v)

    best = None
    best_score = -10**9

    if verbose:
        safe_print(f"  Searching for: {place}")
        safe_print(f"  Trying {len(tried)} variants...")

    for v in tried:
        results = _geocode_nominatim(v, limit=10)  # Increased limit to get more results
        if not results:
            continue

        for r in results:
            score = _score_geocode_result(r)
            if verbose:
                safe_print(f"    - {r.get('display_name', '?')}: score={score}")

            if score > best_score:
                best_score = score
                best = r

    if verbose and best:
        safe_print(f"  Best match: {best.get('display_name')} (score={best_score})")

    return best

def geocode(place: str) -> Optional[Dict[str, Any]]:
    """Get geocoding with caching"""
    key = f"geocode:{place}"
    cached = _cache.get(key)
    if cached:
        return cached

    result = find_best_geocode(place, verbose=False)
    if result:
        _cache.set(key, result, ttl=CACHE_TTL)
    return result

def reverse_geocode(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Reverse geocoding (coordinates to address)"""
    key = f"rev:{lat:.6f},{lon:.6f}"
    cached = _cache.get(key)
    if cached:
        return cached

    _nominatim_wait()
    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1
    }
    result = _request_json(f"{NOMINATIM_URL}/reverse", params=params)
    if result:
        _cache.set(key, result, ttl=CACHE_TTL)
    return result

# ============================================================================
# LANDMARK DISCOVERY (OVERPASS API)
# ============================================================================

def search_place_by_name(name: str, place_type: str = "college") -> Optional[Dict[str, Any]]:
    """Search for specific place by name using Overpass API"""
    key = f"place_search:{name}:{place_type}"
    cached = _cache.get(key)
    if cached:
        return cached

    # First try a simpler Nominatim search with the place name
    _nominatim_wait()
    params = {
        "q": f"{name} {place_type}",
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 5
    }
    results = _request_json(f"{NOMINATIM_URL}/search", params=params)
    
    if results and isinstance(results, list) and len(results) > 0:
        result = results[0]
        obj_dict = {
            "name": result.get("display_name", name),
            "type": place_type,
            "lat": float(result.get("lat", 0)),
            "lon": float(result.get("lon", 0)),
            "display_name": result.get("display_name", f"{name}, Tamil Nadu, India"),
            "address": result.get("address", {"city": "Trichy", "state": "Tamil Nadu", "country": "India"})
        }
        _cache.set(key, obj_dict, ttl=CACHE_TTL)
        return obj_dict

    return None

def _query_overpass(endpoint: str, query: str, timeout: int = 25) -> Optional[Dict[str, Any]]:
    """Query Overpass API endpoint"""
    try:
        r = SESSION.post(endpoint, data={"data": query}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        LOGGER.debug("Overpass endpoint %s failed: %s", endpoint, exc)
        return None

def find_nearby_landmark(lat: float, lon: float, radius_km: float = 10.0) -> Optional[Dict[str, Any]]:
    """Find nearby famous landmark using Overpass API with fallback - works globally"""
    key = f"landmark:{lat:.5f}:{lon:.5f}:{radius_km}"
    cached = _cache.get(key)
    if cached:
        return cached

    # Try progressively larger radii for global coverage
    radii = [radius_km, min(50.0, radius_km * 3), min(100.0, radius_km * 10)]

    for radius in radii:
        radius_m = int(radius * 1000)
        # Enhanced query to find landmarks, historic sites, and notable places worldwide
        query = f"""
        [out:json][timeout:25];
        (
          node(around:{radius_m},{lat},{lon})["tourism"];
          way(around:{radius_m},{lat},{lon})["tourism"];
          node(around:{radius_m},{lat},{lon})["historic"];
          way(around:{radius_m},{lat},{lon})["historic"];
          node(around:{radius_m},{lat},{lon})["amenity"];
          way(around:{radius_m},{lat},{lon})["amenity"];
          node(around:{radius_m},{lat},{lon})["natural"];
          way(around:{radius_m},{lat},{lon})["natural"];
          node(around:{radius_m},{lat},{lon})["name"]["wikipedia"];
          way(around:{radius_m},{lat},{lon})["name"]["wikipedia"];
        );
        out center tags;
        """

        # Try multiple Overpass endpoints
        for endpoint in OVERPASS_ENDPOINTS:
            data = _query_overpass(endpoint, query)
            if not data:
                continue

            elements = data.get("elements", [])
            candidates: List[Dict[str, Any]] = []

            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue

                # Extract coordinates
                if el.get("type") == "node":
                    el_lat = el.get("lat")
                    el_lon = el.get("lon")
                else:
                    center = el.get("center") or {}
                    el_lat = center.get("lat")
                    el_lon = center.get("lon")

                if el_lat is None or el_lon is None:
                    continue

                # Calculate distance and score
                distance = haversine_km((lat, lon), (el_lat, el_lon))
                score = 0

                # Wikipedia/Wikidata presence (high confidence - worldwide)
                if tags.get("wikipedia") or tags.get("wikidata"):
                    score += 100

                # Category bonuses (worldwide categories)
                if tags.get("tourism"):
                    score += 15
                if tags.get("historic"):
                    score += 15
                if tags.get("amenity"):
                    score += 8
                if tags.get("natural"):
                    score += 10
                
                # Additional worldwide categories
                if tags.get("building"):
                    score += 5
                if tags.get("office"):
                    score += 5

                candidates.append({
                    "name": name,
                    "type": tags.get("tourism") or tags.get("historic") or tags.get("amenity") or tags.get("natural") or "landmark",
                    "lat": el_lat,
                    "lon": el_lon,
                    "distance_km": round(distance, 2),
                    "tags": tags,
                    "score": score,
                })

            if candidates:
                candidates.sort(key=lambda x: (-x["score"], x["distance_km"]))
                best = candidates[0]
                _cache.set(key, best, ttl=CACHE_TTL)
                return best

    return None

# ============================================================================
# ROUTING (GLOBAL - Straight line + Nominatim reverse geocoding for path)
# ============================================================================

def _calculate_travel_suggestions(distance_km: float, duration_h: float) -> Dict[str, Any]:
    """Generate travel mode suggestions based on distance"""
    suggestions = {}
    
    # ROADWAY (Car/Bus)
    avg_road_speed = 80  # km/h
    road_time = distance_km / avg_road_speed
    suggestions["ROADWAY"] = {
        "mode": "Car/Bus/Truck",
        "distance": f"{distance_km:.1f} km",
        "estimated_time": f"{road_time:.1f} hours",
        "cost_estimate": "Low to Medium",
        "description": f"Drive via roads. Takes approximately {int(road_time)} hours."
    }
    
    # RAILWAY (Train)
    avg_rail_speed = 100  # km/h
    rail_time = distance_km / avg_rail_speed
    suggestions["RAILWAY"] = {
        "mode": "Train/Railway",
        "distance": f"{distance_km:.1f} km",
        "estimated_time": f"{rail_time:.1f} hours",
        "cost_estimate": "Low to Medium",
        "description": f"Travel by train. Takes approximately {int(rail_time)} hours."
    }
    
    # AIRWAY (Airplane)
    avg_air_speed = 800  # km/h (cruise speed)
    # Add 1 hour for takeoff/landing and airport procedures
    air_time = (distance_km / avg_air_speed) + 1.0
    suggestions["AIRWAY"] = {
        "mode": "Airplane",
        "distance": f"{distance_km:.1f} km",
        "estimated_time": f"{air_time:.1f} hours",
        "cost_estimate": "High",
        "description": f"Fly by airplane. Takes approximately {int(air_time)} hours (includes airport time)."
    }
    
    # SEAWAY (Ship) - only if distance is substantial
    if distance_km > 100:
        avg_sea_speed = 40  # km/h
        sea_time = distance_km / avg_sea_speed
        suggestions["SEAWAY"] = {
            "mode": "Ship/Boat",
            "distance": f"{distance_km:.1f} km",
            "estimated_time": f"{sea_time:.1f} hours",
            "cost_estimate": "Medium",
            "description": f"Travel by ship/boat. Takes approximately {int(sea_time)} hours."
        }
    
    return suggestions
    """Query OSRM for driving route (local/regional only)"""
    url = f"{OSRM_URL}/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true"
    }
    return _request_json(url, params=params)

def _calculate_global_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> Dict[str, Any]:
    """Calculate global route using great circle distance and intermediate points"""
    # Haversine distance (great circle)
    straight_km = haversine_km((from_lat, from_lon), (to_lat, to_lon))
    
    # Try to find intermediate cities/countries along the route
    # Create 5-10 intermediate points along the line
    num_points = min(10, max(5, int(straight_km / 500)))  # ~1 point per 500 km
    
    path_places = []
    for i in range(1, num_points):
        ratio = i / num_points
        # Interpolate latitude and longitude
        int_lat = from_lat + (to_lat - from_lat) * ratio
        int_lon = from_lon + (to_lon - from_lon) * ratio
        
        # Reverse geocode to get place name
        rev = reverse_geocode(int_lat, int_lon)
        if rev:
            addr = rev.get("address", {})
            place_name = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("country")
                or addr.get("region")
            )
            if place_name and place_name not in path_places:
                path_places.append(place_name)
    
    # Estimate travel time (average speed varies by method)
    # Assume average 80 km/h for mixed transport (driving/flying equivalent)
    estimated_hours = straight_km / 80
    
    return {
        "distance_km": round(straight_km, 1),
        "estimated_hours": round(estimated_hours, 1),
        "path_places": path_places[:8],  # Limit to 8 intermediate places
        "route_type": "global_great_circle"
    }

def _calculate_travel_suggestions(distance_km: float, duration_h: float) -> Dict[str, Any]:
    """Generate travel mode suggestions based on distance"""
    suggestions = {}
    
    # ROADWAY (Car/Bus)
    avg_road_speed = 80  # km/h
    road_time = distance_km / avg_road_speed
    suggestions["ROADWAY"] = {
        "mode": "Car/Bus/Truck",
        "distance": f"{distance_km:.1f} km",
        "estimated_time": f"{road_time:.1f} hours",
        "cost_estimate": "Low to Medium",
        "description": f"Drive via roads. Takes approximately {int(road_time)} hours."
    }
    
    # RAILWAY (Train)
    avg_rail_speed = 100  # km/h
    rail_time = distance_km / avg_rail_speed
    suggestions["RAILWAY"] = {
        "mode": "Train/Railway",
        "distance": f"{distance_km:.1f} km",
        "estimated_time": f"{rail_time:.1f} hours",
        "cost_estimate": "Low to Medium",
        "description": f"Travel by train. Takes approximately {int(rail_time)} hours."
    }
    
    # AIRWAY (Airplane)
    avg_air_speed = 800  # km/h (cruise speed)
    # Add 1 hour for takeoff/landing and airport procedures
    air_time = (distance_km / avg_air_speed) + 1.0
    suggestions["AIRWAY"] = {
        "mode": "Airplane",
        "distance": f"{distance_km:.1f} km",
        "estimated_time": f"{air_time:.1f} hours",
        "cost_estimate": "High",
        "description": f"Fly by airplane. Takes approximately {int(air_time)} hours (includes airport time)."
    }
    
    # SEAWAY (Ship) - only if distance is substantial
    if distance_km > 100:
        avg_sea_speed = 40  # km/h
        sea_time = distance_km / avg_sea_speed
        suggestions["SEAWAY"] = {
            "mode": "Ship/Boat",
            "distance": f"{distance_km:.1f} km",
            "estimated_time": f"{sea_time:.1f} hours",
            "cost_estimate": "Medium",
            "description": f"Travel by ship/boat. Takes approximately {int(sea_time)} hours."
        }
    
    return suggestions

def _osrm_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> Optional[Dict[str, Any]]:
    """Query OSRM for driving route (local/regional only)"""
    url = f"{OSRM_URL}/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true"
    }
    return _request_json(url, params=params)

def distance_and_route(start: str, end: str) -> Dict[str, Any]:
    """Calculate distance and route between two places (global support)"""
    gs = geocode(start)
    
    # Try alternative search for college if not found
    if not gs and any(word in start.lower() for word in ["college", "institute", "engineering"]):
        college_name = start.replace("college", "").replace("engineering", "").replace("institute", "").strip()
        gs = search_place_by_name(college_name, place_type="college")
    
    ge = geocode(end)
    
    # Try alternative search for college if not found
    if not ge and any(word in end.lower() for word in ["college", "institute", "engineering"]):
        college_name = end.replace("college", "").replace("engineering", "").replace("institute", "").strip()
        ge = search_place_by_name(college_name, place_type="college")

    if not gs or not ge:
        return {"error": "Could not geocode one or both places"}

    s_lat, s_lon = float(gs["lat"]), float(gs["lon"])
    e_lat, e_lon = float(ge["lat"]), float(ge["lon"])
    
    start_name = gs.get("display_name", start)
    end_name = ge.get("display_name", end)

    # For local routes (< 500 km), try OSRM first
    straight_km = haversine_km((s_lat, s_lon), (e_lat, e_lon))
    
    if straight_km < 500:
        # Try OSRM for local/regional routes
        route_data = _osrm_route(s_lat, s_lon, e_lat, e_lon)

        if route_data and route_data.get("code") == "Ok":
            routes = route_data.get("routes", [])
            if routes:
                r = routes[0]
                route_km = r.get("distance", 0) / 1000.0
                duration_h = r.get("duration", 0) / 3600.0

                # Extract intermediate towns from route geometry
                geom = r.get("geometry", {}).get("coordinates", [])
                towns: List[str] = []

                if geom and len(geom) > 2:
                    num_samples = min(5, max(0, len(geom) - 2))
                    if num_samples > 0:
                        step = max(1, (len(geom) - 2) // num_samples)
                        indices = [1 + i * step for i in range(num_samples)]
                        seen = set()

                        for idx in indices:
                            lon, lat = geom[idx]
                            rev = reverse_geocode(lat, lon)
                            name = None

                            if rev:
                                addr = rev.get("address", {})
                                name = (
                                    addr.get("town")
                                    or addr.get("village")
                                    or addr.get("county")
                                    or addr.get("municipality")
                                    or addr.get("city")
                                )

                            if name and name.lower() not in seen:
                                seen.add(name.lower())
                                towns.append(name)

                            if len(towns) >= 4:
                                break

                return {
                    "start": start_name,
                    "end": end_name,
                    "distance_km": f"{round(route_km, 1)} km",
                    "estimated_time": f"{round(duration_h, 1)} hours",
                    "via": ", ".join(towns) if towns else "direct route",
                    "suggestion": f"Route: {int(round(route_km))} km; via {', '.join(towns) if towns else 'direct'}; ~{round(duration_h, 1)} hours",
                    "route_type": "driving",
                    
                }
    
    # For global/long-distance routes, use great circle distance
    global_route = _calculate_global_route(s_lat, s_lon, e_lat, e_lon)
    
    return {
        "start": start_name,
        "end": end_name,
        "distance_km": f"{global_route['distance_km']} km",
        "estimated_time": f"{global_route['estimated_hours']} hours",
        "via": ", ".join(global_route["path_places"]) if global_route["path_places"] else "direct route",
        "suggestion": f"Global Route: {global_route['distance_km']} km; via {', '.join(global_route['path_places']) if global_route['path_places'] else 'direct'}; ~{global_route['estimated_hours']} hours",
        "route_type": "global_great_circle",
        
    }

# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def safe_print(text: str):
    """Print with Unicode safety for Windows console"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback for Windows cp1252 encoding
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))

def generate_map_html(start_lat: float, start_lon: float, end_lat: float, end_lon: float, 
                     start_name: str, end_name: str, path_places: List[str] = None) -> str:
    """Generate interactive HTML map with route visualization"""
    if path_places is None:
        path_places = []
    
    # Create HTML with Leaflet.js map
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>World Route Map</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
        <style>
            body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
            #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
            .info-panel {{
                background: white;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 0 15px rgba(0,0,0,0.2);
                font-size: 14px;
                line-height: 1.5;
                max-width: 300px;
            }}
            .route-line {{
                stroke: #FF6B6B;
                stroke-width: 2;
                opacity: 0.7;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        
        <script>
            // Initialize map
            var map = L.map('map').setView([20, 0], 2);
            
            // Add OpenStreetMap tiles
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }}).addTo(map);
            
            // Start point
            var startPoint = [{start_lat}, {start_lon}];
            var endPoint = [{end_lat}, {end_lon}];
            
            // Add markers
            L.circleMarker(startPoint, {{
                radius: 8,
                fillColor: '#00AA00',
                color: '#000',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }}).addTo(map).bindPopup('<b>START</b><br>{start_name}');
            
            L.circleMarker(endPoint, {{
                radius: 8,
                fillColor: '#FF0000',
                color: '#000',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }}).addTo(map).bindPopup('<b>END</b><br>{end_name}');
            
            // Draw route line
            L.polyline([startPoint, endPoint], {{
                color: '#FF6B6B',
                weight: 2,
                opacity: 0.7,
                dashArray: '5, 5'
            }}).addTo(map);
            
            // Add intermediate points if any
            var intermediatePoints = {json.dumps(path_places)};
            
            // Fit map to bounds
            var bounds = L.latLngBounds([startPoint, endPoint]);
            map.fitBounds(bounds.pad(0.1));
            
            // Info box
            var info = L.control({{position: 'topright'}});
            info.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'info-panel');
                div.innerHTML = '<b>Route Information</b><br>' +
                    '<b>From:</b> {start_name}<br>' +
                    '<b>To:</b> {end_name}<br>' +
                    '<b>Path:</b> {", ".join(path_places) if path_places else "Direct route"}';
                return div;
            }};
            info.addTo(map);
        </script>
    </body>
    </html>
    """
    return html

def save_and_open_map(html_content: str, start_name: str, end_name: str) -> str:
    """Save HTML map and open in browser"""
    # Create maps directory if it doesn't exist
    maps_dir = "route_maps"
    if not os.path.exists(maps_dir):
        os.makedirs(maps_dir)
    
    # Generate filename
    safe_start = "".join(c if c.isalnum() else "_" for c in start_name[:20])
    safe_end = "".join(c if c.isalnum() else "_" for c in end_name[:20])
    filename = f"{maps_dir}/route_{safe_start}_to_{safe_end}.html"
    
    # Save HTML file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Open in default browser
    file_path = os.path.abspath(filename)
    webbrowser.open('file://' + file_path)
    
    return filename

def format_json(data: Dict[str, Any]) -> str:
    """Format dictionary as JSON"""
    return json.dumps(data, ensure_ascii=False, indent=2)

def format_text(data: Dict[str, Any]) -> str:
    """Format dictionary as readable text"""
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)

# ============================================================================
# MAIN INTERACTIVE MENU
# ============================================================================

def show_menu():
    """Display main menu"""
    safe_print("\n" + "=" * 70)
    safe_print("         ADVANCED ADDRESS & LANDMARK FINDER")
    safe_print("=" * 70)
    safe_print("\n1. Get Address & Nearby Landmarks")
    safe_print("2. Find Route Between Two Places")
    safe_print("3. Exit")
    safe_print("\n" + "-" * 70)

def get_address_option():
    """Option 1: Get address and nearby landmarks (global support)"""
    place = input("\nEnter place name (anywhere in the world): ").strip()

    if not place:
        safe_print("ERROR: Place name cannot be empty")
        return

    safe_print("\nSearching worldwide...")
    result = find_best_geocode(place, verbose=False)

    # If not found and looks like a college, try college-specific search
    if not result and any(word in place.lower() for word in ["college", "institute", "engineering"]):
        safe_print("Trying alternative search for college/institution...")
        # Try to extract college name
        college_name = place.replace("college", "").replace("engineering", "").replace("institute", "").strip()
        result = search_place_by_name(college_name, place_type="college")
    
    if not result:
        safe_print("ERROR: Place not found")
        safe_print("TIP: Try:")
        safe_print("  - Different spelling or romanization")
        safe_print("  - Add country name (e.g., 'Paris, France')")
        safe_print("  - Use local name if known")
        return

    lat = float(result["lat"])
    lon = float(result["lon"])
    addr = result.get("address", {})
    
    # Display comprehensive address details
    safe_print("\n" + "=" * 70)
    safe_print("ADDRESS DETAILS")
    safe_print("=" * 70)
    
    safe_print(f"Place: {result.get('display_name', place)}")
    safe_print(f"Latitude: {lat}")
    safe_print(f"Longitude: {lon}")
    safe_print(f"Street: {addr.get('road') or addr.get('pedestrian') or '-'}")
    safe_print(f"Village/Neighborhood: {addr.get('village') or addr.get('suburb') or addr.get('neighbourhood') or '-'}")
    safe_print(f"Taluk/District Part: {addr.get('county') or addr.get('state_district') or '-'}")
    safe_print(f"District: {addr.get('district') or addr.get('region') or '-'}")
    safe_print(f"State/Province: {addr.get('state') or addr.get('province') or '-'}")
    safe_print(f"Postcode: {addr.get('postcode') or '-'}")
    safe_print(f"Country: {addr.get('country') or '-'}")

    # Find nearby landmarks globally
    safe_print("\nSearching for nearby landmarks worldwide...")
    landmark = find_nearby_landmark(lat, lon, radius_km=10.0)

    if landmark:
        safe_print("\n" + "=" * 70)
        safe_print("NEARBY FAMOUS LANDMARK (within search radius)")
        safe_print("=" * 70)
        safe_print(f"Name: {landmark['name']}")
        safe_print(f"Type: {landmark['type']}")
        safe_print(f"Distance: {landmark['distance_km']} km")
        safe_print(f"Latitude: {landmark['lat']}")
        safe_print(f"Longitude: {landmark['lon']}")
        if landmark["tags"].get("wikipedia"):
            safe_print(f"Wikipedia: {landmark['tags'].get('wikipedia')}")
        if landmark["tags"].get("url"):
            safe_print(f"Website: {landmark['tags'].get('url')}")
        if landmark["tags"].get("opening_hours"):
            safe_print(f"Hours: {landmark['tags'].get('opening_hours')}")
    else:
        safe_print("\n" + "=" * 70)
        safe_print("INFO: No landmark found in search radius")
        safe_print("This may be a remote area. Try with a larger radius or nearby city.")
        safe_print("=" * 70)

def get_route_option():
    """Option 2: Find route between two places"""
    start = input("\nEnter starting place: ").strip()
    end = input("Enter destination place: ").strip()

    if not start or not end:
        safe_print("ERROR: Both places are required")
        return

    safe_print("\nCalculating route...")
    result = distance_and_route(start, end)

    if "error" in result:
        safe_print(f"ERROR: {result['error']}")
        return

    safe_print("\n" + "=" * 70)
    safe_print("ROUTE & DISTANCE INFORMATION")
    safe_print("=" * 70)
    for key, value in result.items():
        if key != "coords":
            safe_print(f"{key}: {value}")
    
    # Offer to generate map
    safe_print("\n" + "=" * 70)
    generate_map = input("Generate interactive map? (y/n): ").strip().lower()
    
    if generate_map == 'y' and "coords" in result:
        coords = result["coords"]
        path_places = result.get("via", "").replace(", ", ",").split(",")
        path_places = [p.strip() for p in path_places if p.strip() and p.strip() != "direct route"]
        
        try:
            html_map = generate_map_html(
                coords["start_lat"], 
                coords["start_lon"],
                coords["end_lat"],
                coords["end_lon"],
                result.get("start", start),
                result.get("end", end),
                path_places
            )
            map_file = save_and_open_map(html_map, result.get("start", start), result.get("end", end))
            safe_print(f"✓ Map generated and saved: {map_file}")
            safe_print("✓ Opening in your default browser...")
        except Exception as e:
            safe_print(f"Note: Could not generate map: {e}")

def main():
    """Main interactive loop"""
    while True:
        show_menu()
        choice = input("Enter your choice (1-3): ").strip()

        if choice == "1":
            get_address_option()

        elif choice == "2":
            get_route_option()

        elif choice == "3":
            safe_print("\nThank you for using Address Finder. Goodbye!")
            break

        else:
            safe_print("ERROR: Invalid choice. Please enter 1, 2, or 3.")

# ========================================================================
# MCP TOOL WRAPPER (CONNECTING TO MAIN MCP SERVER)
# ========================================================================

def register(mcp):
    """
    Register address & route utilities as MCP tools.
    This will be called automatically by main.py of MCP.
    """

    @mcp.tool()
    async def mcp_geocode(place: str) -> dict:
        """
        Return geocode JSON for any place.
        """
        result = geocode(place)
        if not result:
            return {"error": f"Place not found: {place}"}
        return result

    @mcp.tool()
    async def mcp_reverse_geocode(lat: float, lon: float) -> dict:
        """
        Reverse geocode coordinates into address.
        """
        result = reverse_geocode(lat, lon)
        if not result:
            return {"error": f"Coordinates not found: {lat},{lon}"}
        return result

    @mcp.tool()
    async def mcp_landmark_nearby(lat: float, lon: float, radius_km: float = 10.0) -> dict:
        """
        Find nearby landmarks from coordinates.
        """
        result = find_nearby_landmark(lat, lon, radius_km)
        if not result:
            return {"error": "No nearby landmarks found"}
        return result

    @mcp.tool()
    async def mcp_distance_and_route(query: str) -> dict:
        """
        Return distance and route suggestions between two places.
        Example Input: 'Chennai to Trichy'
        """

        if "to" not in query.lower():
            return {"error": "Use format: 'Place1 to Place2'"}

        parts = query.split("to")
        start = parts[0].strip()
        end = parts[1].strip()
        result = distance_and_route(start, end)
        return result


    # print("[MCP] Address & Route tools registered successfully!")


# if __name__ == "__main__":
#     try:
#         main()
#     except KeyboardInterrupt:
#         safe_print("\n\nExiting... (Ctrl+C pressed)")
#         sys.exit(0)
#     except Exception as exc:
#         LOGGER.exception("Unexpected error: %s", exc)
#         safe_print(f"\nERROR: {exc}")
#         sys.exit(1)
