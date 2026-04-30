import io
import os
import asyncio
import httpx
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIG ---
INFO_API_URL = "https://mafuuuu-info-api.vercel.app/mafu-info"
FONT_FILE = "NotoSans-Bold.ttf"
ITEM_API_URL = "https://mafu-icon-api.onrender.com/icon?key=MAFU=item_id"  # Fixed URL

client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10.0,
    follow_redirects=True
)

process_pool = ThreadPoolExecutor(max_workers=4)

# --- UTILS ---

def load_unicode_font(size):
    """Load font with fallback"""
    try:
        font_path = os.path.join(os.path.dirname(__file__), FONT_FILE)
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

async def fetch_image_bytes(item_id):
    """Fetch image bytes from your API or return None."""
    if not item_id or str(item_id) == "0" or item_id is None:
        return None

    item_id = str(item_id)
    # Fixed URL construction - replace item_id placeholder
    url = ITEM_API_URL.replace("item_id", item_id)
    
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"Error fetching image {item_id}: {e}")
        return None
    
    return None

def bytes_to_image(img_bytes):
    """Convert bytes to PIL Image or return transparent placeholder"""
    if img_bytes:
        try:
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except:
            pass
    return Image.new('RGBA', (100, 100), (0, 0, 0, 0))

def process_banner_image(data, avatar_bytes, banner_bytes, pin_bytes):
    """Combine avatar, banner, pin, and text into final PNG."""
    avatar_img = bytes_to_image(avatar_bytes)
    banner_img = bytes_to_image(banner_bytes)
    pin_img = bytes_to_image(pin_bytes) if pin_bytes else None

    level = str(data.get("AccountLevel", "0"))
    name = data.get("AccountName", "Unknown")
    guild = data.get("GuildName", "")

    TARGET_HEIGHT = 400 
    avatar_img = avatar_img.resize((TARGET_HEIGHT, TARGET_HEIGHT), Image.LANCZOS)
    
    b_w, b_h = banner_img.size
    if b_w > 50 and b_h > 50:
        banner_img = banner_img.rotate(3, resample=Image.BICUBIC, expand=True)
        b_w, b_h = banner_img.size
        
        crop_top, crop_bottom, crop_sides = 0.23, 0.32, 0.17
        left, top = b_w * crop_sides, b_h * crop_top
        right, bottom = b_w * (1 - crop_sides), b_h * (1 - crop_bottom)
        banner_img = banner_img.crop((left, top, right, bottom))

    b_w, b_h = banner_img.size
    if b_h > 0:
        new_banner_w = int(TARGET_HEIGHT * (b_w / b_h) * 2.0)
        banner_img = banner_img.resize((new_banner_w, TARGET_HEIGHT), Image.LANCZOS)
    else:
        banner_img = Image.new("RGBA", (800, 400), (50, 50, 50, 255))
        new_banner_w = 800

    final_w = TARGET_HEIGHT + new_banner_w
    final_h = TARGET_HEIGHT
    combined = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
    combined.paste(avatar_img, (0, 0))
    combined.paste(banner_img, (TARGET_HEIGHT, 0))
    
    draw = ImageDraw.Draw(combined)
    
    font_large = load_unicode_font(60)  # Reduced from 125 for safety
    font_small = load_unicode_font(40)  # Reduced from 95 for safety
    font_level = load_unicode_font(36)  # Reduced from 50 for safety

    text_x = TARGET_HEIGHT + 40 
    text_y = 40 
    
    stroke_col, text_col = "black", "white"
    
    def draw_text_with_stroke(x, y, text, font, stroke_width=3):
        """Draw text with outline/stroke effect"""
        if not text:
            return
        # Draw stroke
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=stroke_col)
        # Draw main text
        draw.text((x, y), text, font=font, fill=text_col)

    # Draw name
    if name:
        draw_text_with_stroke(text_x + 25, text_y, name, font_large)
    
    # Draw guild name
    if guild:
        draw_text_with_stroke(text_x + 25, text_y + 100, guild, font_small)

    # Draw pin/icon if available
    if pin_img and pin_img.size != (100, 100):
        pin_size = 130 
        pin_img = pin_img.resize((pin_size, pin_size), Image.LANCZOS)
        combined.paste(pin_img, (0, TARGET_HEIGHT - pin_size), pin_img)

    # Draw level badge
    level_txt = f"Lvl.{level}"
    try:
        # Get text dimensions
        temp_img = Image.new('RGBA', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), level_txt, font=font_level)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except:
        text_w = len(level_txt) * 20
        text_h = 30

    padding_x, padding_y = 25, 16
    box_x = final_w - (text_w + padding_x * 2)
    box_y = final_h - (text_h + padding_y * 2)
    
    # Draw black background for level
    draw.rectangle([box_x, box_y, final_w, final_h], fill="black")
    draw.text((box_x + padding_x, box_y + padding_y - 6), level_txt, font=font_level, fill="white")

    # Convert to bytes
    img_io = io.BytesIO()
    combined.save(img_io, 'PNG', optimize=True)
    img_io.seek(0)
    return img_io

# --- ROUTES ---

@app.get("/")
async def home():
    return {
        "message": "⚡ Ultra Fast Banner API Running",
        "Made By": "MAFU",
        "Telegram": "@mahfuj_offcial_143",
        "Your Info Api": INFO_API_URL,
        "Api Endpoint": "/profile?uid={uid}",
        "Note": "Join To Us For More 💝"
    }

@app.get("/profile")
async def get_banner(uid: str):
    if not uid:
        raise HTTPException(status_code=400, detail="UID required")

    try:
        # Fetch user data from info API
        resp = await client.get(f"{INFO_API_URL}?uid={uid}")
        resp.raise_for_status()
        data = resp.json()

        print(f"API Response for UID {uid}: {data}")  # Debug log

        # Extract data - adjust keys based on actual API response
        basic_info = data.get("basicInfo", {})
        profile_info = data.get("profileInfo", {})
        clan_info = data.get("clanBasicInfo", {})

        # Get IDs for images
        avatar_id = profile_info.get("headPic") or basic_info.get("headPic")
        banner_id = basic_info.get("bannerId")
        pin_id = basic_info.get("pinId") or basic_info.get("title")

        # Fetch images concurrently
        tasks = [
            fetch_image_bytes(avatar_id),
            fetch_image_bytes(banner_id),
            fetch_image_bytes(pin_id) if pin_id else asyncio.sleep(0)
        ]
        
        results = await asyncio.gather(*tasks)
        avatar_bytes = results[0]
        banner_bytes = results[1]
        pin_bytes = results[2] if len(results) > 2 and results[2] is not None else None

        # Prepare banner data
        banner_data = {
            "AccountLevel": basic_info.get("level") or basic_info.get("AccountLevel") or 0,
            "AccountName": basic_info.get("nickname") or basic_info.get("AccountName") or "Unknown",
            "GuildName": clan_info.get("GuildName") or clan_info.get("guildName") or ""
        }

        # Process image in thread pool
        loop = asyncio.get_event_loop()
        img_io = await loop.run_in_executor(
            process_pool,
            process_banner_image,
            banner_data, avatar_bytes, banner_bytes, pin_bytes
        )

        return Response(
            content=img_io.getvalue(),
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=300",
                "X-UID": uid
            }
        )

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e}")
        raise HTTPException(status_code=e.response.status_code, 
                          detail=f"Info API returned error: {e.response.status_code}")
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        raise HTTPException(status_code=502, detail=f"Info API request failed: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- SHUTDOWN ---
@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()
    process_pool.shutdown()

# --- RUN SERVER ---
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
