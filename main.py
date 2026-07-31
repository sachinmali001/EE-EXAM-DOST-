import asyncio
import os
import cv2
import re
import threading
import datetime 
import subprocess
import sys
from flask import Flask
from telethon import TelegramClient, errors
from telethon.tl.types import DocumentAttributeVideo
from tqdm import tqdm

# --- FLASK HEARTBEAT ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running"

def run_flask():
    app.run(host="0.0.0.0", port=7860)

# --- CONFIGURATION ---
api_id = 30658177
api_hash = '8f1a693fb1d615dba6edb4a4d20b7977'
source_channel = -1004413883900
destination_channel = -1003547460293

# --- HELPER FUNCTIONS ---

def clean_text(text):
    if not text: return ""
    
    # 1. Target numbering + name prefixes like '002_Ansh_Kaushal_' or standalone variations
    patterns = [
        r'(?i)^\d+_*Ansh[-_]kaushal_*', # Matches "002_Ansh_Kaushal_" or "002Ansh_Kaushal" at start
        r'(?i)_Ansh[-_]kaushal_\s*',    # Fallback for standalone middle/end tags
        r'(?i)ansh[_-]kaushal[_-]*',
        r'(?i)ansh\s*kaushal\s*',
        r'(?i)@?itzAnandXd', 
        r'(?i)@?Anand\s*Xd', 
        r'(?i)@nikhil049', 
        r'(?i)@?HaRsHit2027'
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text)
        
    # 2. Strip standard telegram @usernames
    text = re.sub(r'@\w+', '', text)
    
    # 3. Strip Emojis, Flag Symbols, and remaining special symbols
    text = re.sub(r'[^\w\s\.\-\(\)\[\]]', '', text)
    
    # 4. Clean up formatting underscores/hyphens and change them to readable spaces
    text = text.replace("_", " ").replace("-", " ").replace("[", "").replace("]", "")
    
    return " ".join(text.split()).strip()

def compress_video(input_path, output_path):
    """Compresses video to 480p using FFmpeg with ultrafast preset for cloud servers."""
    print(f"🎬 Compressing to 480p: {os.path.basename(input_path)}...")
    try:
        command = [
            'ffmpeg', '-i', input_path,
            '-vf', 'scale=-2:480', 
            '-vcodec', 'libx264',
            '-crf', '28',          
            '-preset', 'ultrafast', 
            '-acodec', 'aac',
            '-y', output_path
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        print(f"❌ Compression Failed: {e}")
        return False

def get_video_info(file_path):
    duration, width, height = 0, 0, 0
    thumb_path = None
    cap = cv2.VideoCapture(file_path)
    if cap.isOpened():
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = int(frame_count / fps) if fps > 0 else 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        safe_name = "".join([c for c in os.path.basename(file_path) if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        temp_thumb = os.path.join(os.getcwd(), f"thumb_{safe_name}.jpg")
        
        cap.set(cv2.CAP_PROP_POS_MSEC, 2000) 
        success, image = cap.read()
        if success:
            cv2.imwrite(temp_thumb, image)
            if os.path.exists(temp_thumb):
                thumb_path = temp_thumb
        cap.release()
    return duration, width, height, thumb_path

# --- MAIN LOGIC ---

async def main(client):
    print("🚀 Script started. Connecting to Telegram...")
    await client.start()

    print("🔍 Fetching dialogs to sync private channels...")
    async for dialog in client.iter_dialogs():
        if dialog.id == source_channel or dialog.id == destination_channel:
            print(f"✅ Synced: {dialog.name}")

    start_id = 1
    end_id = 1000
    print(f"🔄 Processing IDs {start_id} to {end_id}...")

    for msg_id in range(start_id, end_id + 1):
        try:
            message = await client.get_messages(source_channel, ids=msg_id)
            if not message or not message.media or not message.file:
                continue
                
            original_ext = os.path.splitext(message.file.name)[1] if message.file.name else ""
            is_video = any(ext in original_ext.lower() for ext in ['.mp4', '.mkv', '.mov', '.avi'])
            
            base_name = os.path.splitext(message.file.name)[0] if message.file.name else f"file_{message.id}"
            cleaned_base = clean_text(base_name)
            if not cleaned_base: cleaned_base = f"File_{message.id}"
            
            final_filename = f"{cleaned_base}{original_ext}"
            final_path = os.path.join(os.getcwd(), final_filename)
            
            print(f"\n📦 Processing Lecture ID #{message.id}: {cleaned_base}")

            # DOWNLOAD WITH PROGRESS BAR
            with tqdm(total=message.file.size, unit='B', unit_scale=True, desc=f"📥 Down [#{message.id}]", leave=False) as d_bar:
                def download_progress(current, total):
                    d_bar.update(current - d_bar.n)
                
                temp_download = await message.download_media(
                    file=os.getcwd(),
                    progress_callback=download_progress
                )
            
            if not temp_download or not os.path.exists(temp_download):
                print("❌ Downloaded file not found mapping path.")
                continue

            # RENAME & COMPRESS
            if is_video:
                compressed_path = os.path.join(os.getcwd(), f"480p_{final_filename}")
                if compress_video(temp_download, compressed_path):
                    if os.path.exists(temp_download): os.remove(temp_download)
                    final_path = compressed_path
                else:
                    os.rename(temp_download, final_path)
            else:
                os.rename(temp_download, final_path)

            # METADATA & UPLOAD
            attributes = []
            thumb = None
            file_type = "Document"
            duration_str = "N/A"
            
            if is_video:
                file_type = "Video"
                duration, width, height, thumb = get_video_info(final_path)
                duration = duration or (message.file.duration if message.file.duration else 0)
                duration_str = str(datetime.timedelta(seconds=duration))
                attributes.append(DocumentAttributeVideo(
                    duration=int(duration),
                    w=int(width or 854), h=int(height or 480),
                    supports_streaming=True
                ))

            # --- CAPTION BLOCK ---
            custom_caption = (
                f"**📌 Topic:** {cleaned_base}\n"
                f"🆔 **Message ID:** `#{message.id}`\n"
                f"📂 **Type of file:** `{file_type}`\n"
                f"⏱️ **Duration:** `{duration_str}`\n"
                f"👤 **Extracted by:** @sachin_001"
            )

            # UPLOAD WITH PERCENTAGE PROGRESS BAR
            file_size = os.path.getsize(final_path)
            print(f"📤 Uploading: '{cleaned_base}' (ID: #{message.id})")
            
            with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024, desc=f"🚀 Up [#{message.id}]", leave=True) as u_bar:
                def upload_progress(current, total):
                    u_bar.update(current - u_bar.n)

                await client.send_file(
                    destination_channel,
                    final_path,
                    caption=custom_caption,
                    thumb=thumb,
                    attributes=attributes,
                    force_document=not is_video,
                    supports_streaming=is_video,
                    parse_mode='md',
                    progress_callback=upload_progress
                )
            
            # CLEANUP
            if os.path.exists(final_path): os.remove(final_path)
            if thumb and os.path.exists(thumb): os.remove(thumb)
            
            print(f"✨ Successfully uploaded Lecture #{message.id}: {cleaned_base}\n" + "-"*40)
            await asyncio.sleep(4) 

        except errors.FloodWaitError as e:
            print(f"⚠️ Sleeping for {e.seconds}s (FloodWait)")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Error on ID {msg_id}: {e}")

    print(f"\n✅ All tasks completed!")
    await client.disconnect()

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    client = TelegramClient('cloner_session', api_id, api_hash)
    with client:
        client.loop.run_until_complete(main(client))