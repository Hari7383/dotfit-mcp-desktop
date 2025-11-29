import os
import tempfile
import subprocess
from flask import request, jsonify, send_file
import shutil
import re
import sys

# ----------------------------------------------------
# 1. SMART MODULE INSTALLER (Fixed version of your code)
# ----------------------------------------------------

def detect_imports_from_file(filepath):
    """Extracts import statements from a .py file."""
    imports = set()
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # match: import x
            matches_import = re.findall(r"^import\s+([a-zA-Z0-9_]+)", content, re.MULTILINE)
            imports.update(matches_import)

            # match: from x import y
            matches_from = re.findall(r"^from\s+([a-zA-Z0-9_]+)", content, re.MULTILINE)
            imports.update(matches_from)
    except Exception:
        pass
    return imports

def auto_install_missing_modules(work_dir):
    print("\n🔍 Scanning for missing modules...")

    # 1. Detect imports from .py files
    detected_imports = set()
    for root, dirs, files in os.walk(work_dir):
        for file in files:
            if file.endswith(".py"):
                imports = detect_imports_from_file(os.path.join(root, file))
                detected_imports.update(imports)

    # 2. Define the Map (Import Name -> Pip Name)
    pip_name_map = {
        "PIL": "Pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "dotenv": "python-dotenv",
        "pynput": "pynput",
        "pyautogui": "pyautogui",
        "yaml": "pyyaml"
    }

    # 3. Define Built-ins (Ignore these)
    builtin_modules = {
        "os", "sys", "json", "math", "time", "datetime", "io", "re",
        "random", "base64", "calendar", "statistics", "typing",
        "traceback", "logging", "pathlib", "urllib", "zoneinfo",
        "inspect", "importlib", "webbrowser", "asyncio", "shutil",
        "subprocess", "tempfile", "uuid", "sqlite3", "tkinter", 
        "ctypes", "threading", "queue", "copy", "server" 
    }

    # 4. Prepare final list to install
    final_install_list = []

    # Process auto-detected imports
    for module in detected_imports:
        if module in builtin_modules:
            continue
        
        # Use map if available, otherwise use the module name itself
        install_name = pip_name_map.get(module, module)
        final_install_list.append(install_name)

    # ---------------------------------------------------------
    # 🌶️ THE SPICE: Load from requirements.txt (Dynamic Way)
    # ---------------------------------------------------------
    req_file_path = None
    
    # Look for requirements.txt in the root or subfolders
    for root, dirs, files in os.walk(work_dir):
        if "requirements.txt" in files:
            req_file_path = os.path.join(root, "requirements.txt")
            break
    
    if req_file_path:
        print(f"📄 Found requirements.txt at: {req_file_path}")
        try:
            with open(req_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    # Clean line (remove comments, whitespace)
                    line = line.split('#')[0].strip()
                    if line:
                        # Add exactly what is in the file (e.g., "pandas==1.5.0")
                        final_install_list.append(line)
        except Exception as e:
            print(f"⚠️ Error reading requirements.txt: {e}")

    # 5. Deduplicate list
    # (Set removes exact duplicates, but 'pandas' and 'pandas==1.0' might both stay. 
    # Pip usually handles this fine by taking the versioned one.)
    final_install_list = list(set(final_install_list))

    # 6. Install
    if final_install_list:
        print(f"📦 Installing dependencies: {final_install_list}")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install"] + final_install_list, check=False)
            print("   ✅ Installation attempt finished.")
        except Exception as e:
            print(f"   ⚠️ Installation warning: {e}")
    else:
        print("   ✅ No external dependencies found to install.")

# ----------------------------------------------------
# 2. BUILD EXE (Enhanced for your MCP Project)
# ----------------------------------------------------

def build_exe_from_uploads():
    work_dir = None
    try:
        uploaded_files = request.files.getlist("files")

        if not uploaded_files:
            return jsonify({"error": "No files were uploaded"}), 400

        # Create work directory
        work_dir = tempfile.mkdtemp()

        # Save uploaded file structure
        for file in uploaded_files:
            filename = file.filename
            # Security check for filename
            if ".." in filename or filename.startswith("/"):
                continue
                
            abs_path = os.path.join(work_dir, filename)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            file.save(abs_path)

        # 1. AUTO-INSTALL DEPENDENCIES (Your logic, improved)
        auto_install_missing_modules(work_dir)

        # 2. Detect Entry Point and Folders
        entry = None
        templates_dir = None
        static_dir = None
        server_dir = None

        # Helper to find entry
        possible_entries = ["app.py", "main.py", "gui.py", "run.py"]

        for root, dirs, files in os.walk(work_dir):
            # Check for folders
            if "templates" in dirs: templates_dir = os.path.join(root, "templates")
            if "static" in dirs: static_dir = os.path.join(root, "static")
            if "server" in dirs: server_dir = os.path.join(root, "server")

            # Check for entry file
            for e in possible_entries:
                if e in files and entry is None:
                    entry = os.path.join(root, e)

        # If no standard entry found, check if it's a single script
        if not entry:
            py_files = [f for f in os.listdir(work_dir) if f.endswith(".py")]
            if len(py_files) == 1:
                entry = os.path.join(work_dir, py_files[0])

        if not entry:
            return jsonify({"error": "No app.py, main.py, or single python file found"}), 400

        # 3. Build EXE Command
        output_dir = os.path.join(work_dir, "dist")
        
        # Basic PyInstaller command
        cmd = [
            "pyinstaller",
            "--onefile",
            "--clean",
            f"--distpath={output_dir}",
            "--name=MyProject" # Generic name
        ]

        # Handle Data Folders (Windows use ;, Linux use :)
        sep = ";" if os.name == 'nt' else ":"

        if templates_dir:
            cmd += ["--add-data", f"{templates_dir}{sep}templates"]
        if static_dir:
            cmd += ["--add-data", f"{static_dir}{sep}static"]
        
        # ---------------------------------------------------------------
        # CRITICAL FIX FOR YOUR MCP PROJECT
        # ---------------------------------------------------------------
        # Because main.py uses 'importlib' to load files in server/,
        # PyInstaller ignores them. We must force them as 'hidden imports'.
        if server_dir:
            cmd += ["--add-data", f"{server_dir}{sep}server"]
            cmd += [f"--paths={work_dir}"] # Ensure it sees the server module
            
            # Scan server directory for .py files and add them as hidden imports
            for f in os.listdir(server_dir):
                if f.endswith(".py") and f != "__init__.py":
                    module_name = f"server.{f[:-3]}" # e.g., server.weather
                    cmd += [f"--hidden-import={module_name}"]

        # Add the entry point last
        cmd.append(entry)

        # 4. Run PyInstaller
        process = subprocess.run(cmd, capture_output=True, text=True)

        if process.returncode != 0:
            print(process.stderr) # Print error to your console for debugging
            return jsonify({"error": f"Build Failed. Missing modules? Log: {process.stderr[-200:]}"}), 500

        # 5. Find and Return EXE
        exe_file = None
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith(".exe"):
                    exe_file = os.path.join(output_dir, f)
                    break

        if not exe_file:
            return jsonify({"error": "Build finished but EXE file not found"}), 500

        # Send response
        response = send_file(
            exe_file,
            as_attachment=True,
            download_name=os.path.basename(exe_file)
        )

        # Cleanup handled by tempfile but good practice to delete
        # shutil.rmtree(work_dir, ignore_errors=True) 
        
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500