import os
import sys
import importlib
from mcp.server import FastMCP  # type: ignore

# ------------------------------------------------------
#  EXE–SAFE PATH RESOLUTION
# ------------------------------------------------------

def get_server_folder():
    """
    Returns the correct path of the 'server' folder,
    whether running normally or inside a PyInstaller EXE.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller runtime directory
        base = sys._MEIPASS
    else:
        # Normal Python environment
        base = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base, "server")


# ------------------------------------------------------
#  LOAD ALL TOOLS FROM server/*.py FILES
# ------------------------------------------------------

def load_tools(mcp: FastMCP):
    tools_dir = get_server_folder()

    if not os.path.exists(tools_dir):
        raise FileNotFoundError(f"Tools folder not found: {tools_dir}")

    for filename in os.listdir(tools_dir):
        if filename.endswith(".py") and filename not in ["__init__.py", "main.py"]:
            module_name = filename[:-3]  # remove .py
            module_path = f"server.{module_name}"

            try:
                module = importlib.import_module(module_path)

                # If the tool file has register(mcp), call it
                if hasattr(module, "register"):
                    module.register(mcp)

            except Exception as e:
                print(f"❌ Error loading tool '{module_path}': {e}")


# ------------------------------------------------------
#  INITIALIZE MCP SERVER & LOAD TOOLS
# ------------------------------------------------------

mcp = FastMCP()

try:
    load_tools(mcp)
except Exception as e:
    print(f"❌ Failed to load tools: {e}")