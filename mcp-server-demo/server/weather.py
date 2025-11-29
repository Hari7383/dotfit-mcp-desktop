import httpx

def register(mcp):
    GEO_API_BASE = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_API_BASE = "https://api.open-meteo.com/v1/forecast"

    def get_weather_description(code: int) -> tuple[str, bool]:
        """Converts WMO weather code to text and returns a boolean for rain."""
        if code == 0: return "Clear sky ☀️", False
        if code in [1, 2, 3]: return "Partly cloudy ⛅", False
        if code in [45, 48]: return "Foggy 🌫️", False
        if code in [51, 53, 55]: return "Drizzle 🌧️", True
        if code in [56, 57]: return "Freezing Drizzle ❄️🌧️", True
        if code in [61, 63, 65]: return "Rain 🌧️", True
        if code in [66, 67]: return "Freezing Rain ❄️🌧️", True
        if code in [71, 73, 75]: return "Snow fall ❄️", True
        if code == 77: return "Snow grains ❄️", True
        if code in [80, 81, 82]: return "Rain showers ☔", True
        if code in [85, 86]: return "Snow showers ❄️", True
        if code == 95: return "Thunderstorm ⚡", True
        if code in [96, 99]: return "Thunderstorm with hail ⚡❄️", True
        return "Unknown weather code", False

    async def get_coordinates(city_name: str) -> dict[str, float] | None:
        """Finds the latitude and longitude for a city name."""
        params = {"name": city_name, "count": 1, "language": "en", "format": "json"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(GEO_API_BASE, params=params)
                data = response.json()
                if "results" in data and data["results"]:
                    result = data["results"][0]
                    return {
                        "lat": result["latitude"],
                        "lon": result["longitude"],
                        "name": result["name"],
                        "country": result.get("country", "Unknown")
                    }
            except Exception:
                return None
        return None

    @mcp.tool()
    async def check_rain_status(city: str) -> str:
        """Check if it is currently raining in a specific city.
        
        Args:
            city: Name of the city (e.g., "London", "Tiruchirappalli")
        """
        location = await get_coordinates(city)
        if not location:
            return f"Could not find location: {city}"

        # --- FIX: Added 'timezone' to get the city's local time ---
        params = {
            "latitude": location['lat'],
            "longitude": location['lon'],
            "current": "precipitation,weather_code,temperature_2m",
            "timezone": "auto"  # This gets the local time for the requested city
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(WEATHER_API_BASE, params=params)
                data = response.json()
                
                current = data["current"]
                
                # Extract and format time (Replace "T" with a space for readability)
                local_time = current['time'].replace("T", " ")
                
                precip_amount = current['precipitation']
                w_code = current['weather_code']
                temp = current['temperature_2m']
                
                desc, is_raining = get_weather_description(w_code)
                status_emoji = "YES ☔" if is_raining else "NO ☀️"
                
                return (
                    f"🌍 Weather Report for {location['name']}, {location['country']}\n"
                    f"───────────────────────────────────\n"
                    f"🕒 Time of Report : {local_time}\n"
                    f"❓ Is it raining? : {status_emoji}\n"
                    f"📝 Condition      : {desc}\n"
                    f"💧 Precipitation  : {precip_amount} mm\n"
                    f"🌡️ Temperature    : {temp}°C"
                )
            except Exception as e:
                return f"Error fetching weather: {str(e)}"

# if __name__ == "__main__":
#     import asyncio
#     from mcp.server import FastMCP # type: ignore
   

#     test = FastMCP("test_weather")
#     register(test)
#     tool = test._tool_manager.list_tools()[0]
#     print(asyncio.run(tool.fn("artic")))