from flask import Flask, render_template, request, jsonify
from server.main import mcp  # Import the configured MCP server from main.py
import asyncio
import inspect
import json
from PIL import Image
import io
from flask import send_file
from base64 import b64encode
from markupsafe import Markup
import re
import uuid
import sys
import os


# ====================================================
# SAFE EXE MODE FIX (Does NOT break dev mode)
# ====================================================
IS_EXE = getattr(sys, 'frozen', False)
EXE_BASE = sys._MEIPASS if IS_EXE else None


app = Flask(__name__)
SERVER_BOOT_ID = str(uuid.uuid4())

if IS_EXE:
    app.template_folder = os.path.join(EXE_BASE, "templates")
    app.static_folder = os.path.join(EXE_BASE, "static")


# A dictionary to map user intent (keywords/tags) to the MCP tool function name
TOOL_MAPPING = {
    "weather": "check_rain_status", # From weather.py

    "currency": "convert_currency", # Assuming this tool exists

    "calculate": "calculate_math", # Assuming this tool exists

    "translate": "translate_text", # Assuming this tool exists

    "qrgenerator": "generate_qr_code",

    "calendar": "generate_calendar",

    "reviews": "fetch_reviews",

    "search": "fetch_web_links",

    "news": "fetch_news",

    "dictionary": "eng_dictionary",

    "imageconvert": "convert_image_web",

    "geocode": "mcp_geocode",

    "route&distance": "mcp_distance_and_route",

    "timezone": "timezone_convert",
}

# def get_tool_and_args(query: str) -> tuple[str | None, str | None]:
#     """
#     Detects the tool keyword from the start of the query and extracts the arguments.
#     """
    
#     normalized_query = query.lower().strip()
#     print(normalized_query)
#     parts = normalized_query.split(maxsplit=1)
    
#     if not parts:
#         return None, None
    
#     tool_keyword = parts[0]
#     tool_args = parts[1].strip() if len(parts) > 1 else ""

#     if tool_keyword in TOOL_MAPPING:
#         tool_name = TOOL_MAPPING[tool_keyword]
#         return tool_name, tool_args

#     return None, None

def get_tool_and_args(query: str) -> tuple[str | None, str | None]:
    """
    Parse a command like:
      'Geo Code chennai'
      'QR Code hello'
      'RouteANDdistance chennai to trichy'

    into: (tool_name, args)
    """

    query = query.strip()
    if not query:
        return None, None

    # Split words but keep original casing for args
    words = query.split()
    if not words:
        return None, None

    # Lowercase copy for matching
    lwords = [w.lower() for w in words]

    # We support up to first 3 words as command phrase
    max_cmd_words = min(3, len(lwords))

    # Try longest phrase first: 3 -> 2 -> 1 words
    for n in range(max_cmd_words, 0, -1):
        key = "".join(lwords[:n])  # 'geo' + 'code' -> 'geocode', 'qr' + 'code' -> 'qrcode'
        if key in TOOL_MAPPING:
            tool_name = TOOL_MAPPING[key]
            # Remaining words are the arguments, with original casing
            args = " ".join(words[n:])
            return tool_name, args.strip()

    # No matching tool
    return None, None



@app.template_filter('urlize')
def urlize_filter(text, target="_blank"):
    if not text:
        return text
    pattern = r'(https?://[^\s]+)'
    return Markup(re.sub(
        pattern,
        r'<a class="result-link" href="\1" target="_blank">\1</a>',
        text
    ))

@app.route("/", methods=["GET", "POST"])
async def index():
    result = None
    query = ""
    persistent_command = ""
    tool_name = ""
    if request.method == "POST":
        # CRITICAL CHANGE: Read the data from the new hidden field name
        query = request.form.get("reliable_query", "").strip() 
        persistent_command = request.form.get("persistent_command", "").strip()
        tool_name = request.form.get("tool_name", "")
        # --- DEBUGGING LINE ---
        # print(f"--- DEBUG: Received Query: '{query}' ---")
        # --- END DEBUGGING LINE ---
        
        tool_name, tool_args = get_tool_and_args(query)
        
        if tool_name and tool_args:
            try:
                tool_fn = mcp._tool_manager.get_tool(tool_name).fn
                sig = inspect.signature(tool_fn)
                param_names = list(sig.parameters.keys())
                
                if len(param_names) == 1:
                    result = await tool_fn(tool_args)
                else:
                    result = f"🤖 Tool call: **{tool_name}** with arguments: **'{tool_args}'**. Need LLM to parse arguments for this tool."
                # --- NEW LOGIC START: Check for image output ---

                if isinstance(result, dict) and result.get("is_image"):
                    # Pass the entire dictionary to the template if it's an image
                    result = result 
                else:
                    # Otherwise, treat it as a standard text result 
                    result = result
                # --- NEW LOGIC END ---

            except Exception as e:
                result = f"❌ Error executing tool '{tool_name}': {str(e)}"
        else:
            # This is the exact error message from your screenshot, now triggered only when NO valid tool is found.
            result = f"🔍 Unknown command: '{query}'. 💡 Try a valid tool keyword."

    # 🖼 If result is an image
    # 🖼 If result is an image → DO NOT FORMAT OR CONVERT
    if isinstance(result, dict) and result.get("is_image"):
        pass  # Leave it as dict for Jinja to render
    else:
        # ✨ Beautified text formatting for non-image output
        if isinstance(result, dict):
            formatted = ""
            for key, value in result.items():
                formatted += f"{key.ljust(15)} : {value}\n"
            result = formatted

    return render_template("index.html", query=query, result=result, tool_name=tool_name,persistent_command=persistent_command, server_boot_id = SERVER_BOOT_ID)


@app.route("/mcp-image-convert", methods=["POST"])
async def mcp_image_convert():
    file = request.files["image"]
    convert_to = request.form.get("convert_to")

    # Read file as base64
    base64_data = b64encode(file.read()).decode()

    # Call MCP tool
    tool_fn = mcp._tool_manager.get_tool("convert_image_web").fn
    result = await tool_fn(base64_data, convert_to)

    if "error" in result:
        return {"error": result["error"]}, 500

    # Extract base64 result for download
    return {
        "download_name": result["download_name"],
        "mime_type": result["mime_type"],
        "base64_data": result["base64_data"]
    }

from server.exe_converter import build_exe_from_uploads

@app.post("/mcp-exe-convert")
def mcp_exe_convert():
    return build_exe_from_uploads()



if __name__ == "__main__":
    import server.main 
    app.run(debug=True)
    # app.run(host="0.0.0.0", port=5000, debug=True)
