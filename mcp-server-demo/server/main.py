import importlib
import os
from mcp.server import FastMCP # type: ignore


# Create MCP server (shared instance)
mcp = FastMCP("tool_hub")


def load_tools():
    tools_dir = "server"

    for filename in os.listdir(tools_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            module = importlib.import_module(f"{tools_dir}.{module_name}")
            #print(module_name) # debug processing...
            
            # If the module has a register function, call it
            if hasattr(module, "register"):
                module.register(mcp)


load_tools()

if __name__ == "__main__":
    mcp.run(transport="stdio")