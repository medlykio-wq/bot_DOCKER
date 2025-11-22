import discord
import google.generativeai as genai
import asyncio
import re
import requests
import io
from PIL import Image
import os
import flask
import threading
from collections import defaultdict, deque
import datetime
import time

# Lấy token từ environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Kiểm tra environment variables
if not DISCORD_TOKEN:
    print("❌ Lỗi: Thiếu DISCORD_TOKEN!")
    exit(1)
if not GEMINI_API_KEY:
    print("❌ Lỗi: Thiếu GEMINI_API_KEY!")
    exit(1)

print("🔄 Đang khởi động Yoo Ji Min...")

# Cấu hình Gemini
genai.configure(api_key=GEMINI_API_KEY)

# --- CẤU HÌNH MODEL CHAT ---
try:
    # Thử dùng model Pro mới nhất
    model = genai.GenerativeModel('gemini-3.0-pro')
    print("✅ Chat Model: Gemini 3.0 Pro")
except Exception:
    # Fallback về bản Flash nếu lỗi
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("⚠️ Chat Model: Gemini 2.5 Flash (Fallback)")

# --- CẤU HÌNH MODEL TẠO ẢNH (ĐÃ SỬA LỖI) ---
imagen_model = None
try:
    # Cú pháp đúng: Phải dùng .from_pretrained
    imagen_model = genai.ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
    print("✅ Image Model: Imagen 3 (Nano Banana)")
except Exception as e:
    print(f"⚠️ Chưa tải được Imagen 3: {e}")
    try:
        imagen_model = genai.ImageGenerationModel.from_pretrained("imagen-2")
        print("✅ Image Model: Imagen 2 (Fallback)")
    except Exception as e2:
        print(f"❌ Không tải được model tạo ảnh nào: {e2}")

# Lưu trữ lịch sử hội thoại
conversation_history = defaultdict(lambda: deque(maxlen=200))
server_memory = deque(maxlen=500)

# Thông tin thành viên server
server_members = {
    "demacianking1": {"name": "Cường", "birthday": {"day": 5, "month": 1}, "year": 2000, "job": "IT", "last_birthday_wish": None},
    "thanh0374": {"name": "Thành", "birthday": {"day": 19, "month": 10}, "year": 2000, "job": "IT", "last_birthday_wish": None},
    "dangialanrangu": {"name": "Dũng Còi", "birthday": {"day": 17, "month": 11}, "year": 2000, "job": "kiến trúc sư", "last_birthday_wish": None},
    "manted1229": {"name": "Ngọc Điếc", "birthday": {"day": 4, "month": 1}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None},
    "vyanhduc": {"name": "Đức", "birthday": {"day": 25, "month": 12}, "year": 1999, "job": "Music Producer", "last_birthday_wish": None},
    "pta.zyud": {"name": "Tuấn Anh", "birthday": {"day": 6, "month": 6}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None}
}

# Tính cách Yoo Ji Min
personality = """
Bạn là Yoo Ji Min, một thành viên thông minh và hữu ích trong server Discord này.
TÍNH CÁCH:
- LỊCH SỰ, THẲNG THẲN nhưng TỬ TẾ
- Trả lời phù hợp: Câu đơn giản (5-35 chữ), câu phức tạp (đến 80 chữ)
- Luôn đi thẳng vào vấn đề
- Dùng emoji ĐA DẠNG và PHÙ HỢP
- Nếu người khác xưng "anh" thì xưng "em" lại
- Với Đức (vyanhduc): luôn ngọt ngào, tinh tế, xưng em gọi anh
- Hạn chế xưng hô, nếu cần thì xưng "mình" - "bạn"
EMOJI: 🌞🌙⭐️🔥💧🌊🐶🐱🦋🌷🎵🎮📚🎨⚽️🍕☕️🎉❤️💫😊🎯🚀🌈🎪🎸🏆🌍🦄🎁🎈
"""

# Các hàm phụ trợ
def check_message_type(message_content, message_author):
    content_lower = message_content.lower()
    if (message_author.name.lower() == "vyanhduc" or 
        (message_author.display_name and "đức" in message_author.display_name.lower()) or
        (message_author.display_name and "duc" in message_author.display_name.lower())):
        return "duc"
    if " anh " in content_lower or content_lower.startswith("anh ") or content_lower.endswith(" anh"):
        return "brother"
    return "normal"

def check_question_type(message_content):
    content_lower = message_content.lower()
    long_kw = ['hướng dẫn', 'giải thích', 'phân tích', 'so sánh', 'nguyên nhân', 'chi tiết', 'như thế nào', 'tại sao', 'review']
    short_kw = ['có không', 'đúng không', 'mấy giờ', 'khi nào', 'ở đâu', 'ai', 'gì', 'ok', 'được']
    if any(k in content_lower for k in long_kw): return "long"
    elif any(k in content_lower for k in short_kw): return "short"
    return "normal"

def get_conversation_history(channel_id):
    history = conversation_history[channel_id]
    if not history: return ""
    return "Lịch sử chat:\n" + "\n".join(list(history)[-20:]) + "\n"

def add_to_history(channel_id, message):
    conversation_history[channel_id].append(message)

def add_to_server_memory(message):
    server_memory.append(message)

# Sinh nhật
async def check_birthdays(client):
    today = datetime.datetime.now()
    for username, info in server_members.items():
        if info["birthday"]["day"] == today.day and info["birthday"]["month"] == today.month:
            if info.get("last_birthday_wish") != today.strftime("%Y-%m-%d"):
                user = discord.utils.get(client.get_all_members(), name=username)
                if user:
                    age = today.year - info["year"]
                    prompt = f"Chúc mừng sinh nhật {info['name']} ({age} tuổi, {info['job']}). Viết lời chúc ngắn gọn, ý nghĩa, xưng em."
                    try:
                        resp = model.generate_content(prompt)
                        msg = resp.text.strip()
                        for guild in client.guilds:
                            if guild.system_channel: await guild.system_channel.send(f"🎉 {user.mention} {msg}"); break
                    except: pass
                    info["last_birthday_wish"] = today.strftime("%Y-%m-%d")

async def test_birthday(client, username, channel):
    if username in server_members:
        info = server_members[username]
        prompt = f"Viết lời chúc sinh nhật test cho {info['name']}."
        resp = model.generate_content(prompt)
        await channel.send(f"🎉 **TEST:** {resp.text}")

async def show_member_info(username, channel):
    if username in server_members:
        info = server_members[username]
        today = datetime.datetime.now()
        age = today.year - info["year"]
        await channel.send(f"ℹ️ **{info['name']}** ({age} tuổi) - {info['job']}. SN: {info['birthday']['day']}/{info['birthday']['month']}")

# Phân tích ảnh
async def analyze_image(image_url, user_message):
    try:
        resp = requests.get(image_url)
        img = Image.open(io.BytesIO(resp.content))
        prompt = f"{personality}\nNgười dùng gửi ảnh và hỏi: '{user_message}'. Hãy phân tích và trả lời."
        response = model.generate_content([prompt, img])
        return response.text.strip()
    except: return "Lỗi khi xem ảnh 😅"

# --- HÀM TẠO ẢNH (FIXED) ---
async def generate_image(prompt_text):
    if not imagen_model:
        return None
    try:
        # Gọi API tạo ảnh
        result = imagen_model.generate_images(
            prompt=prompt_text,
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="block_only_high"
        )
        if result and result.images:
            img = result.images[0]
            # Convert to byte array
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            return img_byte_arr
    except Exception as e:
        print(f"Lỗi tạo ảnh: {e}")
    return None

# Setup Discord
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True 
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ Bot Online: {client.user}')
    await client.change_presence(activity=discord.Game(name="!ve [mô tả]"))
    client.loop.create_task(birthday_check_loop())

async def birthday_check_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await check_birthdays(client)
        await asyncio.sleep(3600) # Check mỗi tiếng

@client.event
async def on_message(message):
    if message.author.bot: return

    # Save log
    t = datetime.datetime.now().strftime("%H:%M")
    add_to_server_memory(f"[{t}] {message.author.name}: {message.content}")

    # Lệnh !ve
    if message.content.lower().startswith('!ve '):
        if not imagen_model:
            await message.reply("⚠️ Tính năng vẽ tranh chưa khởi động được do lỗi server.")
            return

        prompt = message.content[4:].strip()
        if not prompt:
            await message.reply("🎨 Nhập mô tả đi ạ. Ví dụ: `!ve con mèo`")
            return

        async with message.channel.typing():
            try:
                # Dịch prompt sang tiếng Anh
                trans_prompt = f"Translate this to detailed English prompt for image generation (under 40 words): '{prompt}'"
                eng_prompt_resp = model.generate_content(trans_prompt)
                eng_prompt = eng_prompt_resp.text.strip()
                
                # Tạo ảnh
                img_data = await generate_image(eng_prompt)
                if img_data:
                    await message.reply(f"🎨 **{prompt}**", file=discord.File(img_data, 'art.png'))
                else:
                    await message.reply("😅 Không vẽ được, thử mô tả khác xem sao?")
            except Exception as e:
                await message.reply("Lỗi rồi: " + str(e))
        return

    # Lệnh khác
    if message.content.startswith('!test_birthday'):
        parts = message.content.split()
        if len(parts) == 2: await test_birthday(client, parts[1], message.channel)
        return
    if message.content.startswith('!member_info'):
        parts = message.content.split()
        if len(parts) == 2: await show_member_info(parts[1], message.channel)
        return

    # Chat
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_msg = message.content.replace(f'<@{client.user.id}>', '').strip()
        
        # Check hỏi thông tin user
        for name, u_id in server_members.items():
            if server_members[u_id]['name'].lower() in user_msg.lower() and ('sinh nhật' in user_msg or 'tuổi' in user_msg):
                await show_member_info(u_id, message.channel)
                return

        async with message.channel.typing():
            # Xử lý ảnh gửi kèm
            if message.attachments:
                for att in message.attachments:
                    if any(att.filename.lower().endswith(x) for x in ['.png','.jpg','.jpeg']):
                        ans = await analyze_image(att.url, user_msg)
                        await message.reply(ans)
                        return
            
            # Chat text
            hist = get_conversation_history(str(message.channel.id))
            m_type = check_message_type(user_msg, message.author)
            
            prompt = f"{personality}\n{hist}\nUser ({m_type}): {user_msg}\nTrả lời:"
            try:
                resp = model.generate_content(prompt)
                await message.reply(resp.text.strip())
                add_to_history(str(message.channel.id), f"User: {user_msg}")
                add_to_history(str(message.channel.id), f"Bot: {resp.text.strip()}")
            except:
                await message.reply("Đang suy nghĩ... thử lại sau nhé 🤯")

# Web Server Keep-alive
app = flask.Flask(__name__)
@app.route('/')
def home(): return "Yoo Ji Min is Alive!"
def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): t = threading.Thread(target=run_web); t.daemon = True; t.start()

if __name__ == "__main__":
    keep_alive()
    client.run(DISCORD_TOKEN)
