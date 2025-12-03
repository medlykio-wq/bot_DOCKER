import discord
import google.generativeai as genai
import asyncio
import requests
import io
from PIL import Image
import os
import flask
import threading
from collections import defaultdict, deque
import datetime
import time
import aiohttp
import urllib.parse
import random

# ================= CẤU HÌNH =================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    print("❌ Lỗi: Thiếu Token!")
    exit(1)

print("🔄 Đang khởi động Yoo Ji Min (Phiên bản Nano Banana 3 - Robust Mode)...")

genai.configure(api_key=GEMINI_API_KEY)
# Sử dụng gemini-1.5-flash cho tốc độ và ổn định
TEXT_MODEL_NAME = 'gemini-1.5-flash' 
model = genai.GenerativeModel(TEXT_MODEL_NAME)

conversation_history = defaultdict(lambda: deque(maxlen=30))
server_memory = deque(maxlen=100)

# ================= DỮ LIỆU THÀNH VIÊN =================
server_members = {
    "demacianking1": {"name": "Cường", "birthday": {"day": 5, "month": 1}, "year": 2000, "job": "IT", "last_birthday_wish": None},
    "thanh0374": {"name": "Thành", "birthday": {"day": 19, "month": 10}, "year": 2000, "job": "IT", "last_birthday_wish": None},
    "dangialanrangu": {"name": "Dũng Còi", "birthday": {"day": 17, "month": 11}, "year": 2000, "job": "kiến trúc sư", "last_birthday_wish": None},
    "manted1229": {"name": "Ngọc Điếc", "birthday": {"day": 4, "month": 1}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None},
    "vyanhduc": {"name": "Đức", "birthday": {"day": 25, "month": 12}, "year": 1999, "job": "Music Producer", "last_birthday_wish": None},
    "pta.zyud": {"name": "Tuấn Anh", "birthday": {"day": 6, "month": 6}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None}
}

personality = """
Bạn là Yoo Ji Min, một AI thông minh và tinh nghịch.
- Luôn trả lời ngắn gọn, đi thẳng vào vấn đề.
- Với Đức (vyanhduc): Ngọt ngào, xưng em gọi anh.
- Với người khác: Xưng hô linh hoạt, vui vẻ.
"""

# ================= HÀM XỬ LÝ ẢNH (CORE IMAGE GEN - FIX LỖI) =================

async def generate_image_core(prompt, width=1024, height=1024):
    print(f"🎨 Yêu cầu vẽ: {prompt}")
    
    final_prompt = prompt
    
    # BƯỚC 1: Cố gắng dịch sang tiếng Anh để ảnh đẹp hơn
    # Nếu lỗi bước này, bỏ qua và dùng luôn tiếng Việt (Fallback)
    try:
        trans_prompt = f"Translate this prompt to English for image generation, keep it detailed, direct translation only: {prompt}"
        # Thêm timeout để không bị treo nếu Gemini lag
        trans_response = await asyncio.wait_for(model.generate_content_async(trans_prompt), timeout=5.0)
        final_prompt = trans_response.text.strip()
        final_prompt += ", 8k resolution, highly detailed, masterpiece, cinematic lighting"
        print(f"✅ Đã dịch prompt: {final_prompt}")
    except Exception as e:
        print(f"⚠️ Không dịch được prompt (dùng gốc): {e}")
        # Không return None, mà vẫn tiếp tục vẽ bằng prompt gốc
        pass

    # BƯỚC 2: Vẽ bằng Pollinations (Flux Model)
    try:
        encoded_prompt = urllib.parse.quote(final_prompt)
        # Thêm seed ngẫu nhiên để ảnh không bị trùng
        seed = random.randint(1, 100000)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"
        
        timeout = aiohttp.ClientTimeout(total=30) # 30 giây timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return image_data, final_prompt
                else:
                    return None, f"Lỗi Server Ảnh: {response.status}"
    except Exception as e:
        return None, f"Lỗi kết nối: {str(e)}"

# Hàm tạo ảnh sinh nhật
async def generate_birthday_image(name, age, job):
    prompt = f"Happy Birthday {name}, {age} years old, {job}, luxury party, cake, 3d render, cinematic"
    image_data, _ = await generate_image_core(prompt)
    return image_data

# ================= DISCORD CLIENT =================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã Online!')
    await client.change_presence(activity=discord.Game(name="!ve để tạo ảnh 🎨"))
    client.loop.create_task(birthday_check_loop())

async def birthday_check_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await check_birthdays(client)
        await asyncio.sleep(3600 * 4)

async def check_birthdays(client):
    today = datetime.datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    for username, info in server_members.items():
        if info["birthday"]["day"] == today.day and info["birthday"]["month"] == today.month:
            if info.get("last_birthday_wish") != today_str:
                user = discord.utils.get(client.users, name=username) # Cách tìm user an toàn hơn
                # Logic gửi lời chúc và ảnh...
                info["last_birthday_wish"] = today_str

@client.event
async def on_message(message):
    if message.author.bot: return

    # === LỆNH VẼ TRANH ===
    if message.content.lower().startswith(('!ve ', '!draw ')):
        prompt = message.content.split(' ', 1)[1].strip()
        if not prompt:
            await message.reply("Nhập nội dung cần vẽ đi nè!")
            return

        async with message.channel.typing():
            # Báo cho người dùng biết đang làm gì
            status_msg = await message.reply(f"🖌️ Đang vẽ: *{prompt}*...")
            
            image_data, result_msg = await generate_image_core(prompt)
            
            if image_data:
                f = discord.File(io.BytesIO(image_data), filename="art.png")
                await status_msg.delete()
                await message.reply(f"✨ Xong rồi nè! (Prompt: {result_msg})", file=f)
            else:
                # In lỗi cụ thể ra để debug
                await status_msg.edit(content=f"❌ Không vẽ được rồi: {result_msg}")
        return

    # === CHAT ===
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_msg = message.content.replace(f'<@{client.user.id}>', '').strip()
        if not user_msg and not message.attachments:
            await message.reply("Sao thế ạ? 🌟")
            return
            
        async with message.channel.typing():
            try:
                # Xử lý ảnh Vision
                if message.attachments:
                    img_data = await message.attachments[0].read()
                    img = Image.open(io.BytesIO(img_data))
                    prompt = f"{personality}\nUser gửi ảnh và hỏi: {user_msg}. Hãy trả lời."
                    resp = await model.generate_content_async([prompt, img])
                    await message.reply(resp.text.strip())
                    return

                # Chat thường
                prompt = f"{personality}\nUser: {user_msg}\nTrả lời:"
                resp = await model.generate_content_async(prompt)
                await message.reply(resp.text.strip())
            except Exception as e:
                print(f"Lỗi Chat: {e}")
                await message.reply("Mạng lag quá, nói lại được không ạ? 😅")

# ================= WEB SERVER =================
app = flask.Flask(__name__)
@app.route('/')
def home(): return "Yoo Ji Min is OK"
def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    keep_alive()
    client.run(DISCORD_TOKEN)
