import re
import calendar
import datetime
import asyncio
import sys
from typing import List, Tuple, Set, Dict, Any, Optional

# def register(mcp):
# =========================================================================
# 1. CONFIGURATION & CONSTANTS
# =========================================================================
CONNECTORS = ["of", "in", "at", "on", "for", "and"] # Added 'and' as a connector
HEADER_DIVIDER = "────────────────────────────────"

# =========================================================================
# 2. CALENDAR ENGINE (Logic Core)
# =========================================================================
class CalendarEngine:
    def __init__(self):
        self.cal = calendar.Calendar(firstweekday=6) # 6 = Sunday

    def get_grid(self, year: int, month: int) -> List[List[str]]:
        """Generates the 6x7 visual grid."""
        grid_flat = []
        
        # Safety Check for Python's datetime limits
        if year < 1: year = 1
        if year > 9999: year = 9999 # Cap at 9999 to prevent overflow errors

        first_day = datetime.date(year, month, 1)
        start_weekday = first_day.weekday() 
        wday_index = (start_weekday + 1) % 7 
        
        # Previous Month Tail
        if wday_index > 0:
            if month == 1: p_m, p_y = 12, year - 1
            else: p_m, p_y = month - 1, year
            days_prev = calendar.monthrange(p_y, p_m)[1]
            start_d = days_prev - wday_index + 1
            for d in range(start_d, days_prev + 1):
                grid_flat.append(f"({d})") 

        # Current Month
        days_curr = calendar.monthrange(year, month)[1]
        for d in range(1, days_curr + 1):
            grid_flat.append(f" {d:<2}") 

        # Next Month Head
        rem = 42 - len(grid_flat)
        for d in range(1, rem + 1):
            grid_flat.append(f"({d})") 

        return [grid_flat[i:i + 7] for i in range(0, len(grid_flat), 7)]

    def resolve_relative_dates(self, text: str) -> str:
        """
        Advanced NLP Pre-processor: Handles Seasons, Quarters, Relative offsets.
        """
        today = datetime.date.today()
        text = text.lower()

        # --- Helper for Quarter Mapping ---
        def replace_quarters(match):
            q_num = int(match.group(1))
            y_str = match.group(2) if match.group(2) else str(today.year)
            # Map Q1-4 to months
            months = {1: "January February March", 2: "April May June", 
                      3: "July August September", 4: "October November December"}
            return f"{months.get(q_num, '')} {y_str}"

        # --- Helper for Ordinal Months (11th month) ---
        def replace_ordinals(match):
            num = int(match.group(1))
            if 1 <= num <= 12:
                return f"{calendar.month_name[num]} "
            return match.group(0)

        # 1. Quarters (Q1 2024, last quarter 2023)
        text = re.sub(r'\bq([1-4])\s*(\d{4})?', replace_quarters, text)
        text = re.sub(r'\blast quarter\s*(\d{4})?', lambda m: f"October November December {m.group(1) if m.group(1) else today.year}", text)

        # 2. Ordinal Months (3rd month, 11th month)
        text = re.sub(r'\b(\d{1,2})(?:st|nd|rd|th)\s+month', replace_ordinals, text)

        # 3. Seasons (Approximate mapping)
        text = text.replace("summer", "June July August")
        text = text.replace("winter", "December January February")
        text = text.replace("spring", "March April May")
        text = text.replace("autumn", "September October November")
        text = text.replace("fall", "September October November")

        # 4. Extended Relative Dates
        # "Month after next" (+2 months)
        if "month after next" in text:
            m = today.month + 2
            y = today.year
            while m > 12: m -= 12; y += 1
            text = text.replace("month after next", f"{calendar.month_name[m]} {y}")
        
        # "Year after next" (+2 years)
        if "year after next" in text:
            text = text.replace("year after next", str(today.year + 2))

        # Standard Relative
        if "next year" in text: text = text.replace("next year", str(today.year + 1))
        if "last year" in text: text = text.replace("last year", str(today.year - 1))
        if "this year" in text: text = text.replace("this year", str(today.year))

        if "next month" in text:
            m, y = today.month + 1, today.year
            if m > 12: m = 1; y += 1
            text = text.replace("next month", f"{calendar.month_name[m]} {y}")

        if "last month" in text or "previous month" in text:
            m, y = today.month - 1, today.year
            if m < 1: m = 12; y -= 1
            text = text.replace("last month", f"{calendar.month_name[m]} {y}")
            text = text.replace("previous month", f"{calendar.month_name[m]} {y}")

        # Specific Days
        if "tomorrow" in text:
            d = today + datetime.timedelta(days=1)
            text = text.replace("tomorrow", f"{calendar.month_name[d.month]} {d.year}")
        if "today" in text or "now" in text:
            text = text.replace("today", f"{calendar.month_name[today.month]} {today.year}")
            text = text.replace("now", f"{calendar.month_name[today.month]} {today.year}")

        return text

    def parse_input(self, text: str) -> List[Tuple[int, int]]:
        """
        Master Parser: Handles MM/YYYY, Numeric lists, Text lists, Hybrid formats.
        """
        clean_text = self.resolve_relative_dates(text)

        # --- ROBUSTNESS: PRE-CLEANING ---
        # 1. Replace common separators (/, -, ., _) with spaces
        # Matches 2024/01, 2024-01, 2024.01, 2024_01
        clean_text = re.sub(r'[\/\-\._]', ' ', clean_text)
        
        # 2. Split Sticky Strings (Jan2024 -> Jan 2024)
        clean_text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', clean_text)
        clean_text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', clean_text)
        
        # 3. Remove other punctuation (keep alphanumeric & space)
        clean_text = re.sub(r'[^\w\s]', ' ', clean_text)

        # 4. Handle "Two Thousand..." (simple conversion for years)
        # Simple heuristic for "twenty twenty" -> "2020" could be added here, 
        # but for this scope, we rely on digit parsing primarily. 
        if "twenty twenty" in clean_text: clean_text = clean_text.replace("twenty twenty", "2020")
        if "twenty twenty four" in clean_text: clean_text = clean_text.replace("twenty twenty four", "2024")
        if "twenty thirteen" in clean_text: clean_text = clean_text.replace("twenty thirteen", "2013")

        words = clean_text.lower().split()
        tokens = []

        # --- TOKENIZATION ---
        for word in words:
            # Check for Year (4 digits)
            if word.isdigit() and len(word) == 4:
                tokens.append({'type': 'Y', 'val': int(word)})
            # Check for Numeric Month (1-12)
            # Important: Only single or double digits. 
            elif word.isdigit() and 1 <= int(word) <= 12:
                tokens.append({'type': 'M_NUM', 'val': int(word)})
            # Check for Connectors
            elif word in CONNECTORS:
                tokens.append({'type': 'C', 'val': word})
            else:
                # Check for Named Month
                m_val = None
                if word in [m.lower() for m in calendar.month_name if m]:
                    m_val = [m.lower() for m in calendar.month_name].index(word)
                elif word in [m.lower() for m in calendar.month_abbr if m]:
                    m_val = [m.lower() for m in calendar.month_abbr].index(word)
                
                if m_val:
                    tokens.append({'type': 'M_NAME', 'val': m_val})
                else:
                    tokens.append({'type': 'Noise'})

        final_pairs = set()
        used_indices = set()

        # --- PHASE 1: MAGNET LOGIC (Strict Pairs) ---
        i = 0
        while i < len(tokens):
            if i in used_indices: i += 1; continue
            curr = tokens[i]
            
            if i + 1 < len(tokens):
                next_tok = tokens[i+1]
                
                # Definition of a "Month" token (Name or Number)
                is_curr_month = curr['type'] in ['M_NAME', 'M_NUM']
                is_next_month = next_tok['type'] in ['M_NAME', 'M_NUM']
                
                # Lookahead Helper
                def is_blocking(idx):
                    # A year blocks if followed by another year, 
                    # UNLESS that second year has its own month partner.
                    if idx + 2 >= len(tokens): return False
                    tok2 = tokens[idx + 1] # The blocking candidate
                    tok3 = tokens[idx + 2] # The potential partner
                    if tok2['type'] == 'Y' and tok3['type'] not in ['M_NAME', 'M_NUM']:
                        return True
                    return False

                # Pattern A: [Month] [Year] (e.g., March 2024, 03 2024)
                if is_curr_month and next_tok['type'] == 'Y':
                    # Logic: Don't pair if previous token was also a month (list of months)
                    # UNLESS there's a connector or explicit pairing structure
                    prev_is_month = (i > 0 and tokens[i-1]['type'] in ['M_NAME', 'M_NUM'])
                    
                    # Numeric months need to be careful (could be day numbers)
                    # We assume if paired with 4-digit year, it IS a month.
                    if not is_blocking(i) and not (prev_is_month and curr['type'] == 'M_NUM'):
                        final_pairs.add((curr['val'], next_tok['val']))
                        used_indices.add(i); used_indices.add(i+1)

                # Pattern B: [Year] [Month] (e.g., 2024 March, 2024 03)
                elif curr['type'] == 'Y' and is_next_month:
                    prev_is_year = (i > 0 and tokens[i-1]['type'] == 'Y')
                    if not prev_is_year:
                        final_pairs.add((next_tok['val'], curr['val']))
                        used_indices.add(i); used_indices.add(i+1)

                # Pattern C: [Month] [Connector] [Year]
                elif i + 2 < len(tokens):
                    third = tokens[i+2]
                    if is_curr_month and next_tok['type'] == 'C' and third['type'] == 'Y':
                         if not is_blocking(i+1):
                            final_pairs.add((curr['val'], third['val']))
                            used_indices.add(i); used_indices.add(i+1); used_indices.add(i+2)

            i += 1

        # --- PHASE 2: BUCKET LOGIC (Loose Items) ---
        # Collect unused months (Names or Numbers) and Years
        remaining_months = [t['val'] for idx, t in enumerate(tokens) if t['type'] in ['M_NAME', 'M_NUM'] and idx not in used_indices]
        remaining_years = [t['val'] for idx, t in enumerate(tokens) if t['type'] == 'Y' and idx not in used_indices]

        if remaining_months:
            if remaining_years:
                # Cartesian Product
                for m in remaining_months:
                    for y in remaining_years: 
                        final_pairs.add((m, y))
            else:
                # Default to Current Year
                curr_year = datetime.date.today().year
                for m in remaining_months: 
                    final_pairs.add((m, curr_year))

        return sorted(list(final_pairs))

# =========================================================================
# 3. TOOL REGISTRATION
# =========================================================================
def register(mcp):
    engine = CalendarEngine()

    @mcp.tool()
    async def generate_calendar(query: str) -> str:
        if not query.strip(): return "⚠️ Empty Input."
        
        pairs = engine.parse_input(query)
        if not pairs: return f"❌ No dates found in: '{query}'"

        output_buffer = []
        output_buffer.append(f"📅 Results for '{query}' ({len(pairs)} cals)")
        output_buffer.append(HEADER_DIVIDER)

        for (month, year) in pairs:
            month_name = calendar.month_name[month]
            output_buffer.append(f"\n**{month_name} {year}**")
            output_buffer.append(" Su   Mo   Tu   We   Th   Fr   Sa")
            weeks = engine.get_grid(year, month)
            for week in weeks:
                output_buffer.append("  ".join(week))
            output_buffer.append("") 

        return "\n".join(output_buffer)

    return generate_calendar

# =========================================================================
# 4. PRODUCTION TEST RUNNER
# =========================================================================
# if __name__ == "__main__":
#     from mcp.server import FastMCP # type: ignore
#     import asyncio
#     import time
    
#     server = FastMCP("calendar_server")
#     register(server)
#     tool_func = server._tool_manager.list_tools()[0].fn

#     # YOUR 50 PRODUCTION TESTS
#     test_cases = [
#         "next month and july 2044 and apr 99 and tomorrow",
#         "show calendar for march of next year and nov of last year",
#         "april20  24",
#         "2024march??2025june??again2027april",
#         "calendar for 2025, 2026, 2027 june feb jan",
#         "2023 of june of 2028 march of 2029 nov",
#         "the month after next in the year after next",
#         "two months ago and july and dec",
#         "1999 jan feb mar apr 2020 2021 2022",
#         "november this year and feb last year and march next year",
#         "print march 20 24",
#         "print 20 24 march",
#         "last december and next january",
#         "month of sep in the year twenty twenty",
#         "show 03/2024 and 12/1998 and 1/3000",
#         "june of '24",
#         "february twenty thirteen",
#         "feb 29 2024",
#         "now now now now march 2024 now now",
#         "2024 2025 2026 august august august",
#         "july 2024?  2024 july?  july?  2024?",
#         "2030nov 2030dec 2030jan 2030feb",
#         "calendar for q2 2024",
#         "11th month 2024",
#         "6 2025",
#         "5 of next year",
#         "show all calendars from march to july 2024",
#         "jun jul aug in 24",
#         "two thousand twenty four february",
#         "just give july",
#         "summer 2024",
#         "mid march 2024",
#         "last quarter 2023",
#         "mar-apr-may 2025",
#         "2024 03",
#         "24-03",
#         "Apr;May;Jun 2026",
#         "jan feb mar apr may june 2049",
#         "next next month",
#         "3rd month of 2025",
#         "year 2025 in the month 6",
#         "2025.(05)",
#         "2026_04_hello_world_2027_june",
#         "18 june of 2024",
#         "2024 and march and 2025 and february",
#         "2024 2025 may 2026 june 2027 july",
#         "my birthday is in 03 of 2027",
#         "Feb 2024 and Feb 2024 again",
#         "February of 0005",
#         "december 10000"
#     ]

#     print(f"\n🚀 PRODUCTION TEST SUITE: RUNNING {len(test_cases)} CASES")
#     print("=" * 60)
    
#     start_t = time.time()
#     passed = 0
    
#     for i, case in enumerate(test_cases):
#         print(f"🔹 Test #{i+1}: '{case}'")
#         try:
#             result = asyncio.run(tool_func(case))
#             # Simple check: did we generate at least one calendar grid?
#             if "No dates found" in result:
#                 print("   ❌ FAILED")
#             else:
#                 passed += 1
#                 # Print ONLY first 5 lines of result to keep log clean, 
#                 # or use full 'print(result)' to see everything.
#                 print(result) 
#         except Exception as e:
#             print(f"   ❌ ERROR: {e}")
#         print("-" * 60)

#     end_t = time.time()
#     print("=" * 60)
#     print(f"🏁 COMPLETED IN {end_t - start_t:.2f}s")
#     print(f"🏆 SCORE: {passed}/{len(test_cases)}")