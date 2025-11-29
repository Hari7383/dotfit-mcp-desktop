import httpx
import re
import asyncio
import time
import random
from typing import Dict, Any, Optional
from deep_translator import GoogleTranslator, MyMemoryTranslator # type: ignore

def register(mcp):
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    CACHE_TTL_SECONDS = 86400  # 24 Hours

    # =========================================================================
    # ENGINE: LANGUAGE RESOLVER & CACHING
    # =========================================================================
    class PolyglotEngine:
        def __init__(self):
            self._supported_langs = {}
            
        def get_languages(self):
            # Lazy load languages from Google
            if not self._supported_langs:
                try:
                    self._supported_langs = GoogleTranslator().get_supported_languages(as_dict=True)
                except:
                    pass # Fail silently
            return self._supported_langs

        def resolve_language_code(self, user_input: str) -> Optional[str]:
            """Maps user input (e.g., 'French') to ISO code ('fr')"""
            langs = self.get_languages()
            user_input = user_input.lower().strip()
            
            # 1. Direct Match
            if user_input in langs: return langs[user_input]
            if user_input in langs.values(): return user_input
            
            # 2. Common Overrides
            overrides = {
                "mandarin": "zh-CN", "chinese": "zh-CN", "hindi": "hi",
                "japanese": "ja", "korean": "ko", "vietnamese": "vi",
                "bangla": "bn", "urdu": "ur", "filipino": "tl",
                "tamil": "ta", "telugu": "te", "kannada": "kn", "marathi": "mr"
            }
            return overrides.get(user_input)

    engine = PolyglotEngine()

    # =========================================================================
    # NETWORK HANDLER (Async Execution)
    # =========================================================================
    async def execute_translation(text: str, target_code: str) -> tuple[str, str]:
        """Executes translation with redundancy (Google -> MyMemory)"""
        loop = asyncio.get_running_loop()

        def try_google():
            # Random sleep to mimic human behavior and prevent IP bans
            time.sleep(random.uniform(0.1, 0.4))
            return GoogleTranslator(source='auto', target=target_code).translate(text)

        def try_mymemory():
            return MyMemoryTranslator(source='en', target=target_code).translate(text)

        # 1. Try Google (Primary)
        try:
            result = await loop.run_in_executor(None, try_google)
            if result: return result, "Google API"
        except:
            pass # Fail silently to fallback

        # 2. Try MyMemory (Fallback)
        try:
            result = await loop.run_in_executor(None, try_mymemory)
            if result: return result, "MyMemory API"
        except:
            pass

        return None, None

    # =========================================================================
    # THE TOOL
    # =========================================================================
    @mcp.tool()
    async def translate_text(query: str) -> str:
        """
        Translates text to any language. 
        Format: "Text in Language" (e.g., "Hello world in Spanish")
        """
        # 1. Parse Input
        # FIX: Changed (.+?) to (.+) so it handles "to" inside the sentence correctly.
        # This ensures "come to my home" is treated as the text, not split at the first "to".
        pattern = r"(.+)\s+(?:in|to|into)\s+([a-zA-Z\s\-]+)$"
        match = re.search(pattern, query, re.IGNORECASE)

        if not match:
            return "⚠️ Invalid format. Try: 'Hello world in Spanish'"

        text = match.group(1).strip().replace('"', '').replace("'", "")
        target_name = match.group(2).strip()

        # 2. Validate Language
        target_code = engine.resolve_language_code(target_name)
        
        if not target_code:
            return f"❌ Error: Could not identify language '{target_name}'."

        # 3. Execute Translation
        translated_text, source_used = await execute_translation(text, target_code)

        if not translated_text:
            return "❌ Critical Error: Service unavailable. Please try again later."

        # 4. Final Formatting
        return (
            f"🌍  Translator\n"
            f"────────────────────────\n"
            f"📥 Input  : {text}\n"
            f"📤 Output : {translated_text}\n"
            f"────────────────────────\n"
            f"🎯 Target : {target_name.title()} ({target_code})"
        )

    return translate_text

# =========================================================================
# TEST EXECUTION
# =========================================================================
# if __name__ == "__main__":
#     import asyncio
#     from mcp.server import FastMCP # type: ignore
    
#     # Create test server
#     test = FastMCP("test_translator")
    
#     # Register the tools
#     register(test)
    
#     # Get the tool function to test it manually
#     # (We select the first tool in the list)
#     tool = test._tool_manager.list_tools()[0]
#     huge_text = (
#         "In the rapidly evolving landscape of artificial intelligence, the ability to communicate "
#         "across cultural boundaries has become critical. We strive to build systems that allow us "
#         "to talk to anyone, anywhere, without barriers. From the streets of Tokyo to the villages "
#         "of the Amazon, technology serves as a bridge to connect humanity. When we look to the "
#         "future, we see a world where data flows from server to server to bring knowledge to "
#         "every child. This specific test is designed to verify that our Python script can handle "
#         "long text containing multiple instances of the word 'to' and 'in' without getting "
#         "confused about where the sentence ends. "
#         "in Tamil"
#     )
    
#     # Run translation
#     print(asyncio.run(tool.fn(huge_text)))