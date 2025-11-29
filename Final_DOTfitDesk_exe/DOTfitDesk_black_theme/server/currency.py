import httpx
import re
import asyncio
import time
from typing import Dict, Any, Optional

def register(mcp):
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    PRIMARY_API_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1"
    FALLBACK_API_URL = "https://api.frankfurter.dev/v1"
    CACHE_TTL_SECONDS = 3600

    # =========================================================================
    # 🌍 MASTER SYMBOL LIST (180+ Currencies)
    # =========================================================================
    SYMBOLS = {
        # Major
        "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥", "INR": "₹",
        "RUB": "₽", "KRW": "₩", "BRL": "R$", "TRY": "₺", "IDR": "Rp", "ZAR": "R",
        
        # Americas
        "CAD": "C$", "MXN": "$", "ARS": "$", "CLP": "$", "COP": "$", "PEN": "S/",
        "UYU": "$U", "CRC": "₡", "GTQ": "Q", "HNL": "L", "NIO": "C$", "PYG": "Gs",
        "BOB": "Bs.", "VES": "Bs.", "JMD": "J$", "TTD": "TT$", "XCD": "$", "BZD": "BZ$",
        
        # Europe
        "CHF": "Fr", "SEK": "kr", "NOK": "kr", "DKK": "kr", "PLN": "zł", "CZK": "Kč",
        "HUF": "Ft", "ISK": "kr", "RSD": "din", "BGN": "лв", "RON": "lei", "UAH": "₴",
        "BYN": "Br", "GEL": "₾", "ALL": "L", "HNL": "L", "MDL": "L", "MKD": "ден",
        
        # Asia / Pacific
        "AUD": "A$", "NZD": "NZ$", "SGD": "S$", "HKD": "HK$", "TWD": "NT$", "THB": "฿",
        "VND": "₫", "PHP": "₱", "MYR": "RM", "PKR": "₨", "BDT": "৳", "LKR": "₨",
        "NPR": "₨", "AFN": "؋", "KZT": "₸", "UZS": "so'm", "MNT": "₮", "MMK": "K",
        "LAK": "₭", "KHR": "៛", "PGK": "K", "MVR": "Rf",
        
        # Middle East / Africa
        "AED": "د.إ", "SAR": "﷼", "QAR": "﷼", "KWD": "د.ك", "BHD": ".د.ب", "OMR": "﷼",
        "JOD": "د.ا", "ILS": "₪", "EGP": "E£", "NGN": "₦", "GHS": "₵", "KES": "KSh",
        "TZS": "TSh", "UGX": "USh", "ETB": "Br", "MAD": "د.م.", "ZMW": "ZK",
        
        # Crypto (Top Assets)
        "BTC": "₿", "ETH": "Ξ", "USDT": "₮", "BNB": "BNB", "SOL": "◎", "XRP": "XRP",
        "USDC": "$", "ADA": "₳", "DOGE": "Ð", "AVAX": "AVAX", "DOT": "●", "LTC": "Ł"
    }

    # =========================================================================
    # DATA ENGINE (Caching Layer)
    # =========================================================================
    class DataEngine:
        def __init__(self):
            self._cache = {}
            self._expiry = {}
            self.supported = {} 
        
        def get(self, key):
            if key in self._cache and time.time() < self._expiry[key]:
                return self._cache[key]
            return None
            
        def set(self, key, value, ttl=CACHE_TTL_SECONDS):
            self._cache[key] = value
            self._expiry[key] = time.time() + ttl

    engine = DataEngine()

    async def fetch_json(url: str) -> Optional[Dict]:
        """Robust network fetcher with timeout handling"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except Exception:
                return None

    async def get_available_currencies():
        """Downloads the master list of all active currencies."""
        if engine.supported: return engine.supported
        
        # Fetch dynamic list from CDN
        url = f"{PRIMARY_API_URL}/currencies.min.json"
        data = await fetch_json(url)
        if data:
            engine.supported = data
            return data
        return {}

    async def get_rates(base: str):
        """Fetches exchange rates using Cache -> Primary -> Fallback strategy"""
        base = base.lower()
        key = f"rates_{base}"
        
        # 1. Check Cache
        if cached := engine.get(key): return cached

        # 2. Try Primary API (FawazAhmed0 CDN)
        url = f"{PRIMARY_API_URL}/currencies/{base}.min.json"
        if data := await fetch_json(url):
            if base in data:
                engine.set(key, data[base])
                return data[base]
        
        # 3. Try Fallback API (Frankfurter)
        url_fb = f"{FALLBACK_API_URL}/latest?base={base.upper()}"
        if data_fb := await fetch_json(url_fb):
            if "rates" in data_fb:
                # Normalize keys to lowercase
                norm = {k.lower(): v for k, v in data_fb["rates"].items()}
                engine.set(key, norm)
                return norm
        return None

    # =========================================================================
    # THE TOOL
    # =========================================================================
    @mcp.tool()
    async def convert_currency(query: str) -> str:
        """
        Converts currency. Example: "2,000 INR to USD"
        """
        # 1. Parse Input (Allows commas: 1,000.50)
        pattern = r"([\d,]+(?:\.\d+)?)\s*([a-zA-Z]{3,4})\s*(?:to|in|->)?\s*([a-zA-Z]{3,4})"
        match = re.search(pattern, query, re.IGNORECASE)

        if not match:
            return "⚠️ Invalid format. Try: '100 USD to INR'"

        # Clean number (remove commas)
        val_str = match.group(1).replace(",", "")
        try:
            amount = float(val_str)
        except:
            return "⚠️ Invalid number."

        from_curr = match.group(2).lower()
        to_curr = match.group(3).lower()

        # 2. Validate Logic (Check if currency actually exists in the world)
        all_currencies = await get_available_currencies()
        if all_currencies:
            if from_curr not in all_currencies:
                return f"❌ Error: '{from_curr.upper()}' is not a supported currency."
            if to_curr not in all_currencies:
                return f"❌ Error: '{to_curr.upper()}' is not a supported currency."

        # 3. Conversion Logic
        rates = await get_rates(from_curr)
        if not rates or to_curr not in rates:
             return f"❌ Error: Exchange rate not found for {from_curr.upper()} -> {to_curr.upper()}"

        rate = rates[to_curr]
        converted = amount * rate
        
        # 4. Final Formatting (Added Input Line)
        symbol = SYMBOLS.get(to_curr.upper(), "")
        
        return (
            f"💱 Currency Conversion\n"
            f"────────────────────────\n"
            f"📥 Input  : {amount:,.2f} {from_curr.upper()}\n"
            f"📤 Output : {symbol}{converted:,.2f} {to_curr.upper()}\n"
            f"📊 Rate   : 1 {from_curr.upper()} = {rate:,.5f} {to_curr.upper()}"
        )

    return convert_currency

# =========================================================================
# TEST EXECUTION
# =========================================================================
# if __name__ == "__main__":
#     import asyncio
#     from mcp.server import FastMCP # type: ignore
    
#     # Create test server
#     test = FastMCP("test_currency")
    
#     # Register the tools
#     register(test)
    
#     # Get the tool function to test it manually
#     # (We select the first tool in the list)
#     tool = test._tool_manager.list_tools()[0]
    
#     # Run the test
#     print(asyncio.run(tool.fn("100 aed to inr")))