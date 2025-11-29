# file: server/dictionary.py
import httpx
from typing import Dict, Any, Optional

def register(mcp):

    DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en/"

    async def fetch_definition(word: str):
        """Fetch word definition, example, part of speech, phonetics."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(DICT_API + word, timeout=20)
                if response.status_code != 200:
                    return None
                return response.json()
            except Exception:
                return None

    @mcp.tool()
    async def eng_dictionary(word: str) -> str:
        """
        Get definitions, phonetics, part of speech, and examples for any English word.
        Example: "dictionary('hello')"
        """
        if not word.strip():
            return "❌ Word cannot be empty."

        data = await fetch_definition(word)

        if not data:
            return f"⚠️ No definitions found for '{word}'."

        entry = data[0]

        word_text = entry.get("word", word)
        phonetics = entry.get("phonetics", [])
        meanings = entry.get("meanings", [])

        phonetic_text = ""
        for ph in phonetics:
            if "text" in ph:
                phonetic_text = ph["text"]
                break

        out = [
            f"📘 Dictionary for: {word_text}",
            "----------------------------------------------"
        ]

        if phonetic_text:
            out.append(f"🔡 Pronunciation: {phonetic_text}")

        for m in meanings:
            part = m.get("partOfSpeech", "unknown")
            out.append(f"\n📝 Part of Speech: {part}")

            for d in m.get("definitions", []):
                definition = d.get("definition", "No definition")
                example = d.get("example", None)

                out.append(f"• {definition}")
                if example:
                    out.append(f"\n   💬 _Example_: {example}")

        return "\n".join(out)

    return eng_dictionary


# -------------------------------------------------------------------
# ✔ MANUAL TESTING BLOCK (same style as weather.py)
# -------------------------------------------------------------------
# if __name__ == "__main__":
#     import asyncio
#     from mcp.server import FastMCP #type:ignore

#     test = FastMCP("test_dictionary")
#     register(test)

#     tool = test._tool_manager.list_tools()[0]

#     print("--- 📘 RUNNING DICTIONARY TEST ---")
#     word = "hello"
#     print(f"Word: {word}")

#     print(asyncio.run(tool.fn(word)))
