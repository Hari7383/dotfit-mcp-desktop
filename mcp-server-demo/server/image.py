from PIL import Image
import io
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from base64 import b64decode, b64encode 

# List of supported formats for reading and writing
SUPPORTED_FORMATS = [
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'ico', 'icns',
    'ppm', 'pgm', 'pbm', 'pnm', 'pcx'
]

# Formats that are supported for saving (a subset of SUPPORTED_FORMATS)
SAVE_SUPPORTED_FORMATS = [
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'ico', 'ppm', 'pcx'
]

def extract_format_from_input(user_input: str):
    """Extract the target format from user input."""
    user_input = user_input.lower()
    formats_pattern = '|'.join(SAVE_SUPPORTED_FORMATS)
    match = re.search(rf'to\s+({formats_pattern})', user_input)
    if match:
        return match.group(1)
    match = re.search(rf'({formats_pattern})\s+format', user_input)
    if match:
        return match.group(1)
    match = re.search(rf'\b({formats_pattern})\b', user_input)
    if match:
        return match.group(1)
    return None

def convert_image_format(image_bytes: bytes, output_format: str, output_path: str) -> tuple[bool, dict]:
    """Convert the image to the specified format."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        current_format = img.format.lower() if img.format else "unknown"
        original_mode = img.mode

        format_map = {
            'jpg': 'jpeg', 'tif': 'tiff', 'j2k': 'jpeg2000', 'jpf': 'jpeg2000',
            'jpx': 'jpeg2000', 'j2c': 'jpeg2000', 'jpc': 'jpeg2000'
        }
        output_format_normalized = format_map.get(output_format, output_format)

        # Handle color mode conversions for compatibility
        if output_format_normalized.upper() in ['JPEG', 'BMP', 'PPM', 'PCX', 'JPG']:
            if img.mode in ('RGBA', 'LA', 'P', 'PA'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA', 'PA'):
                    rgb_img.paste(img, mask=img.split()[-1])
                img = rgb_img

        # Save with format-specific settings
        save_kwargs = {'format': output_format_normalized.upper()}
        if output_format_normalized.upper() == 'JPEG':
            save_kwargs['quality'] = 100
            save_kwargs['subsampling'] = 0
            save_kwargs['optimize'] = True
        elif output_format_normalized.upper() == 'PNG':
            save_kwargs['compress_level'] = 6
            save_kwargs['optimize'] = True
        elif output_format_normalized.upper() == 'WEBP':
            save_kwargs['quality'] = 100
            save_kwargs['method'] = 6
        elif output_format_normalized.upper() == 'TIFF':
            save_kwargs['compression'] = 'tiff_lzw'
        elif output_format_normalized.upper() == 'GIF':
            save_kwargs['optimize'] = True
        elif output_format_normalized.upper() == 'ICO':
            if max(img.size) > 256:
                img.thumbnail((256, 256), Image.Resampling.LANCZOS)

        img.save(output_path, **save_kwargs)
        output_size = Path(output_path).stat().st_size
        info = {
            "original_format": current_format.upper(),
            "target_format": output_format.upper(),
            "original_mode": original_mode,
            "target_mode": img.mode,
            "image_size": f"{img.size[0]}x{img.size[1]}",
            "original_size_kb": round(len(image_bytes) / 1024, 2),
            "converted_size_kb": round(output_size / 1024, 2),
            "compression_ratio": round(output_size / len(image_bytes) * 100, 2),
            "output_path": output_path
        }
        return True, info
    except Exception as e:
        return False, {"error": str(e)}

def select_and_convert_image():
    """Open a file dialog to select an image and convert it."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Ask for the image file
    file_path = filedialog.askopenfilename(
        title="Select an image file",
        filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.gif;*.bmp;*.tiff;*.webp;*.ico;*.ppm;*.pcx")]
    )
    if not file_path:
        print("No file selected. Exiting.")
        return

    # Ask for the target format
    format_input = input("Enter the target format (e.g., 'to jpg', 'png'): ").strip()
    target_format = extract_format_from_input(format_input)
    if not target_format:
        print(f"Could not detect a supported format from '{format_input}'")
        print(f"Supported formats: {', '.join(SAVE_SUPPORTED_FORMATS)}")
        return

    try:
        input_file = Path(file_path)
        image_bytes = input_file.read_bytes()
        ext = 'jpg' if target_format == 'jpeg' else target_format
        output_path = str(input_file.parent / f"{input_file.stem}_converted.{ext}")

        success, info = convert_image_format(image_bytes, target_format, output_path)
        if success:
            print("\n" + "=" * 60)
            print("✅ Image Conversion Complete!")
            print("=" * 60)
            print(f"📸 Original Format: {info['original_format']}")
            print(f"🎯 Target Format: {info['target_format']}")
            print(f"📐 Image Size: {info['image_size']} pixels")
            print(f"📦 Original Size: {info['original_size_kb']} KB")
            print(f"📦 Converted Size: {info['converted_size_kb']} KB")
            print(f"💾 Saved to: {info['output_path']}")
            print("=" * 60)
        else:
            print(f"\n❌ Conversion failed: {info.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"\n❌ Error: {e}")


def register(mcp):
    @mcp.tool()
    async def convert_image_web(base64_data: str, fmt: str) -> dict:
        """
        Convert uploaded image from UI to selected format.
        """
        try:
            img_bytes = io.BytesIO(b64decode(base64_data)).getvalue() 
            output_path = f"converted_output.{fmt}"

            success, info = convert_image_format(img_bytes, fmt, output_path)
            if not success:
                return {"error": info.get("error", "Conversion failed")}

            with open(output_path, "rb") as f:
                encoded = b64encode(f.read()).decode()

            return {
                "is_image": True,
                "message": f"Converted to .{fmt.upper()} successfully!",
                "download_name": output_path,
                "mime_type": f"image/{fmt}",
                "base64_data": encoded
            }
        except Exception as e:
            return {"error": str(e)}

if __name__ == "__main__":
    print("=" * 60)
    print("IMAGE FORMAT CONVERTER")
    print("=" * 60)
    print("Select an image file and specify the target format.")
    print(f"Supported formats: {', '.join(SAVE_SUPPORTED_FORMATS)}")
    print("=" * 60)
    select_and_convert_image()
