# file: server/timezone.py
import logging
logging.getLogger("httpx").setLevel(logging.CRITICAL)

import httpx
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones


def register(mcp):

    GEO_API = "https://geocoding-api.open-meteo.com/v1/search"

    # ----------------------------------------------------------
    # 1️⃣ FULL COUNTRY → TIMEZONE MAPPING (simple default choice)
    # ----------------------------------------------------------

    COUNTRY_TZ = {
        # Africa
        "algeria": "Africa/Algiers",
        "angola": "Africa/Luanda",
        "benin": "Africa/Porto-Novo",
        "botswana": "Africa/Gaborone",
        "burkina faso": "Africa/Ouagadougou",
        "burundi": "Africa/Bujumbura",
        "cameroon": "Africa/Douala",
        "cape verde": "Atlantic/Cape_Verde",
        "central african republic": "Africa/Bangui",
        "chad": "Africa/Ndjamena",
        "comoros": "Indian/Comoro",
        "congo": "Africa/Brazzaville",
        "dr congo": "Africa/Kinshasa",
        "djibouti": "Africa/Djibouti",
        "egypt": "Africa/Cairo",
        "eritrea": "Africa/Asmara",
        "eswatini": "Africa/Mbabane",
        "ethiopia": "Africa/Addis_Ababa",
        "gabon": "Africa/Libreville",
        "gambia": "Africa/Banjul",
        "ghana": "Africa/Accra",
        "guinea": "Africa/Conakry",
        "guinea-bissau": "Africa/Bissau",
        "ivory coast": "Africa/Abidjan",
        "kenya": "Africa/Nairobi",
        "lesotho": "Africa/Maseru",
        "liberia": "Africa/Monrovia",
        "libya": "Africa/Tripoli",
        "madagascar": "Indian/Antananarivo",
        "malawi": "Africa/Blantyre",
        "mali": "Africa/Bamako",
        "mauritania": "Africa/Nouakchott",
        "mauritius": "Indian/Mauritius",
        "morocco": "Africa/Casablanca",
        "mozambique": "Africa/Maputo",
        "namibia": "Africa/Windhoek",
        "niger": "Africa/Niamey",
        "nigeria": "Africa/Lagos",
        "rwanda": "Africa/Kigali",
        "senegal": "Africa/Dakar",
        "seychelles": "Indian/Mahe",
        "sierra leone": "Africa/Freetown",
        "somalia": "Africa/Mogadishu",
        "south africa": "Africa/Johannesburg",
        "south sudan": "Africa/Juba",
        "sudan": "Africa/Khartoum",
        "tanzania": "Africa/Dar_es_Salaam",
        "togo": "Africa/Lome",
        "tunisia": "Africa/Tunis",
        "uganda": "Africa/Kampala",
        "zambia": "Africa/Lusaka",
        "zimbabwe": "Africa/Harare",

        # Asia
        "afghanistan": "Asia/Kabul",
        "armenia": "Asia/Yerevan",
        "azerbaijan": "Asia/Baku",
        "bahrain": "Asia/Bahrain",
        "bangladesh": "Asia/Dhaka",
        "bhutan": "Asia/Thimphu",
        "brunei": "Asia/Brunei",
        "cambodia": "Asia/Phnom_Penh",
        "china": "Asia/Shanghai",
        "cyprus": "Asia/Nicosia",
        "georgia": "Asia/Tbilisi",
        "india": "Asia/Kolkata",
        "indonesia": "Asia/Jakarta",
        "iran": "Asia/Tehran",
        "iraq": "Asia/Baghdad",
        "israel": "Asia/Jerusalem",
        "japan": "Asia/Tokyo",
        "jordan": "Asia/Amman",
        "kazakhstan": "Asia/Almaty",
        "kuwait": "Asia/Kuwait",
        "kyrgyzstan": "Asia/Bishkek",
        "laos": "Asia/Vientiane",
        "lebanon": "Asia/Beirut",
        "malaysia": "Asia/Kuala_Lumpur",
        "maldives": "Indian/Maldives",
        "mongolia": "Asia/Ulaanbaatar",
        "myanmar": "Asia/Yangon",
        "nepal": "Asia/Kathmandu",
        "north korea": "Asia/Pyongyang",
        "oman": "Asia/Muscat",
        "pakistan": "Asia/Karachi",
        "philippines": "Asia/Manila",
        "qatar": "Asia/Qatar",
        "saudi arabia": "Asia/Riyadh",
        "singapore": "Asia/Singapore",
        "south korea": "Asia/Seoul",
        "sri lanka": "Asia/Colombo",
        "syria": "Asia/Damascus",
        "taiwan": "Asia/Taipei",
        "tajikistan": "Asia/Dushanbe",
        "thailand": "Asia/Bangkok",
        "timor-leste": "Asia/Dili",
        "turkey": "Europe/Istanbul",
        "turkmenistan": "Asia/Ashgabat",
        "uae": "Asia/Dubai",
        "united arab emirates": "Asia/Dubai",
        "uzbekistan": "Asia/Tashkent",
        "vietnam": "Asia/Ho_Chi_Minh",
        "yemen": "Asia/Aden",

        # Europe
        "albania": "Europe/Tirane",
        "andorra": "Europe/Andorra",
        "austria": "Europe/Vienna",
        "belarus": "Europe/Minsk",
        "belgium": "Europe/Brussels",
        "bosnia": "Europe/Sarajevo",
        "bulgaria": "Europe/Sofia",
        "croatia": "Europe/Zagreb",
        "czechia": "Europe/Prague",
        "denmark": "Europe/Copenhagen",
        "estonia": "Europe/Tallinn",
        "finland": "Europe/Helsinki",
        "france": "Europe/Paris",
        "germany": "Europe/Berlin",
        "greece": "Europe/Athens",
        "hungary": "Europe/Budapest",
        "iceland": "Atlantic/Reykjavik",
        "ireland": "Europe/Dublin",
        "italy": "Europe/Rome",
        "latvia": "Europe/Riga",
        "liechtenstein": "Europe/Vaduz",
        "lithuania": "Europe/Vilnius",
        "luxembourg": "Europe/Luxembourg",
        "malta": "Europe/Malta",
        "moldova": "Europe/Chisinau",
        "monaco": "Europe/Monaco",
        "montenegro": "Europe/Podgorica",
        "netherlands": "Europe/Amsterdam",
        "norway": "Europe/Oslo",
        "poland": "Europe/Warsaw",
        "portugal": "Europe/Lisbon",
        "romania": "Europe/Bucharest",
        "serbia": "Europe/Belgrade",
        "slovakia": "Europe/Bratislava",
        "slovenia": "Europe/Ljubljana",
        "spain": "Europe/Madrid",
        "sweden": "Europe/Stockholm",
        "switzerland": "Europe/Zurich",
        "ukraine": "Europe/Kyiv",
        "united kingdom": "Europe/London",
        "england": "Europe/London",
        "scotland": "Europe/London",
        "wales": "Europe/London",
        "uk": "Europe/London",

        # North America
        "canada": "America/Toronto",
        "mexico": "America/Mexico_City",
        "united states": "America/New_York",
        "usa": "America/New_York",
        "america": "America/New_York",

        # South America
        "argentina": "America/Argentina/Buenos_Aires",
        "bolivia": "America/La_Paz",
        "brazil": "America/Sao_Paulo",
        "chile": "America/Santiago",
        "colombia": "America/Bogota",
        "ecuador": "America/Guayaquil",
        "paraguay": "America/Asuncion",
        "peru": "America/Lima",
        "uruguay": "America/Montevideo",
        "venezuela": "America/Caracas",

        # Oceania
        "australia": "Australia/Sydney",
        "fiji": "Pacific/Fiji",
        "kiribati": "Pacific/Tarawa",
        "marshall islands": "Pacific/Majuro",
        "micronesia": "Pacific/Chuuk",
        "nauru": "Pacific/Nauru",
        "new zealand": "Pacific/Auckland",
        "palau": "Pacific/Palau",
        "papua new guinea": "Pacific/Port_Moresby",
        "samoa": "Pacific/Apia",
        "tonga": "Pacific/Tongatapu",

        # Generic region shortcuts
        "asia": "Asia/Singapore",
        "europe": "Europe/Paris",
        "africa": "Africa/Cairo",
        "north america": "America/New_York",
        "south america": "America/Sao_Paulo",
        "australasia": "Australia/Sydney",
        "middle east": "Asia/Dubai",
    }

    # ----------------------------------------------------------
    # 2️⃣ Geocoding for cities
    # ----------------------------------------------------------

    async def city_to_timezone(city: str) -> str | None:
        params = {"name": city, "count": 1, "language": "en"}
        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(GEO_API, params=params, timeout=10)
                data = r.json()
                if "results" in data and data["results"]:
                    return data["results"][0]["timezone"]
                return None
            except Exception:
                return None

    # ----------------------------------------------------------
    # 3️⃣ Parse user time input
    # ----------------------------------------------------------

    def parse_user_time(t: str) -> datetime | None:
        formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]
        for f in formats:
            try:
                return datetime.strptime(t, f)
            except:
                continue
        return None

    # ----------------------------------------------------------
    # 4️⃣ Local time for "current time" usage
    # ----------------------------------------------------------

    def get_local_current_time(tz: str) -> datetime:
        return datetime.now(ZoneInfo(tz))

    # ----------------------------------------------------------
    # 5️⃣ Resolve city/country/region to timezone
    # ----------------------------------------------------------

    async def resolve_timezone(input_str: str) -> str | None:
        s = input_str.lower().strip()

        # 1. Country/Region direct mapping
        if s in COUNTRY_TZ:
            return COUNTRY_TZ[s]

        # 2. Valid timezone string
        if s in available_timezones():
            return s

        # 3. Fallback to city lookup
        return await city_to_timezone(s)

    # ----------------------------------------------------------
    # 6️⃣ Main MCP tool
    # ----------------------------------------------------------

    @mcp.tool()
    async def timezone_convert(query: str) -> str:
        """
        Accepts:
        - "chennai to new york"
        - "tokyo to london 2025-05-01 12:30"
        - "india to australia"
        - "usa to dubai"
        """

        if not query or " to " not in query.lower():
            return "❌ Format error.\nUse: timezone <from> to <to> [optional datetime]"

        from_part, rest = query.split(" to ", 1)
        tokens = rest.split()

        if len(tokens) > 2:
            to_part = " ".join(tokens[:2])
            time_str = " ".join(tokens[2:])
        else:
            to_part = rest.strip()
            time_str = None

        return await timezone_convert_internal(from_part, to_part, time_str)

    # ----------------------------------------------------------
    # 7️⃣ Internal conversion logic
    # ----------------------------------------------------------

    async def timezone_convert_internal(from_place: str, to_place: str, time_str: str = None):

        from_tz = await resolve_timezone(from_place)
        to_tz = await resolve_timezone(to_place)

        if not from_tz:
            return f"❌ Could not detect timezone for `{from_place}`"
        if not to_tz:
            return f"❌ Could not detect timezone for `{to_place}`"

        if not time_str:
            dt = get_local_current_time(from_tz)
        else:
            dt = parse_user_time(time_str)
            if not dt:
                return (
                    "❌ Invalid time format.\n"
                    "Use:\n"
                    "• YYYY-MM-DD\n"
                    "• YYYY-MM-DD HH:MM\n"
                    "• YYYY-MM-DD HH:MM:SS"
                )
            dt = dt.replace(tzinfo=ZoneInfo(from_tz))

        converted = dt.astimezone(ZoneInfo(to_tz))

        return (
            f"🕒 Time Zone Conversion\n"
            f"---------------------------------------\n"
            f"🌍 From           : {from_place}  →  {from_tz}\n"
            f"🎯 To             : {to_place}    →  {to_tz}\n"
            f"⏳ Original Time  : {dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"➡️ Converted Time : {converted.strftime('%Y-%m-%d %H:%M')}"
        )
