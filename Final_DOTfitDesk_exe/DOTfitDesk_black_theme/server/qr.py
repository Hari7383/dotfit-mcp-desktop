import qrcode # type: ignore
import asyncio
import base64
import io # <-- Import the in-memory buffer

# ... (rest of imports and register function wrapper) ...

def register(mcp):
    @mcp.tool()
    async def generate_qr_code(text_to_encode: str) -> dict | str: # Change return type hint to dict | str
        """
        Generates a QR code image (.png) as a Base64 string for web display.
        Example: "Generate QR code for 'https://www.example.com'"
        """
        
        if not text_to_encode or len(text_to_encode.strip()) == 0:
            return "⚠️ Input Error: Please provide the text or URL to encode in the QR code."
            
        clean_text = text_to_encode.strip().strip("'\"")

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(clean_text)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # --- CRITICAL CHANGE: In-Memory Processing ---
            
            # 1. Create an in-memory file buffer
            buffer = io.BytesIO()
            
            # 2. Save the image to the buffer (Blocking operation)
            # Use asyncio.to_thread for safe execution in an async environment
            await asyncio.to_thread(img.save, buffer, format='PNG')
            
            # 3. Get the binary content and encode it to Base64
            img_bytes = buffer.getvalue()
            base64_data = base64.b64encode(img_bytes).decode('utf-8')
            
            # 4. Return a structured dictionary for the Flask template
            return {
                "is_image": True,
                "base64_data": base64_data,
                "mime_type": "image/png",
                "message": f"✅ QR Code generated for: {clean_text}"
            }
            
        except Exception as e:
            return f"❌ QR Code Generation Failed: An unexpected error occurred: {e}"