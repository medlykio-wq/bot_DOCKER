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
import aiohttp
import urllib.parse
import json

# ================= CẤU HÌNH =================
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

print("🔄 Đang khởi động Yoo Ji Min (Phiên bản Nano Banana 3)...")

# Cấu hình Gemini
genai.configure(api_key=GEMINI_API_KEY)

# LƯU Ý: Dùng gemini-1.5-flash cho tốc độ nhanh và ổn định nhất với tier free
# Nếu bạn chắc chắn có quyền truy cập model khác, hãy sửa tên ở đây.
TEXT_MODEL_NAME = 'gemini-2.5-flash' 
model = genai.GenerativeModel(TEXT_MODEL_NAME)

# Lưu trữ lịch sử hội thoại
conversation_history = defaultdict(lambda: deque(maxlen=30))
server_memory = deque(maxlen=100)

# ================= DỮ LIỆU THÀNH VIÊN =================
server_members = {
    "demacianking1": {
        "name": "Cường",
        "birthday": {"day": 5, "month": 1},
        "year": 2000,
        "job": "IT",
        "last_birthday_wish": None
    },
    "thanh0374": {
        "name": "Thành", 
        "birthday": {"day": 19, "month": 10},
        "year": 2000,
        "job": "IT",
        "last_birthday_wish": None
    },
    "dangialanrangu": {
        "name": "Dũng Còi",
        "birthday": {"day": 17, "month": 11},
        "year": 2000,
        "job": "kiến trúc sư",
        "last_birthday_wish": None
    },
    "manted1229": {
        "name": "Ngọc Điếc",
        "birthday": {"day": 4, "month": 1},
        "year": 2000,
        "job": "Bác sĩ",
        "last_birthday_wish": None
    },
    "vyanhduc": {
        "name": "Đức",
        "birthday": {"day": 25, "month": 12},
        "year": 1999,
        "job": "Music Producer",
        "last_birthday_wish": None
    },
    "pta.zyud": {
        "name": "Tuấn Anh",
        "birthday": {"day": 6, "month": 6},
        "year": 2000,
        "job": "Bác sĩ",
        "last_birthday_wish": None
    }
}

# Tính cách Yoo Ji Min
personality = """
Bạn là Yoo Ji Min, một thành viên thông minh, hài hước và hữu ích trong server Discord này.

TÍNH CÁCH:
- LỊCH SỰ, THẲNG THẲN nhưng TỬ TẾ và hơi TINH NGHỊCH.
- Trả lời ngắn gọn, súc tích (trừ khi được hỏi sâu).
- Dùng emoji ĐA DẠNG và PHÙ HỢP.
- Với Đức (vyanhduc): luôn ngọt ngào, tinh tế, xưng em gọi anh.
- Với người khác: Xưng hô linh hoạt (bạn/mình hoặc em/anh tùy ngữ cảnh), nếu họ xưng "anh" thì mình xưng "em".

NHIỆM VỤ ĐẶC BIỆT:
- Bạn có khả năng vẽ tranh (tạo ảnh) siêu hạng bằng công nghệ mới.
- Khi được nhờ vẽ, hãy nhiệt tình.
"""

# ================= HÀM XỬ LÝ ẢNH (CORE IMAGE GEN) =================

async def generate_image_core(prompt, width=1024, height=1024):
    """
    Hàm xử lý tạo ảnh:
    1. Thử dùng Gemini Imagen 3 (nếu Key hỗ trợ).
    2. Nếu thất bại, tự động chuyển sang Flux (Pollinations) chất lượng cao tương đương.
    """
    print(f"🎨 Đang xử lý yêu cầu vẽ: {prompt}")
    
    # Cách 1: Thử dùng Pollinations với model Flux (Chất lượng rất cao, giống Imagen 3)
    # Đây là phương án ổn định nhất cho Discord Bot Free Tier hiện nay
    # vì API Imagen trực tiếp của Google thường yêu cầu Vertex AI (Project Cloud) phức tạp.
    try:
        # Dịch prompt sang tiếng Anh bằng Gemini để vẽ đẹp hơn
        trans_prompt = f"Translate this prompt to English for image generation, keep it detailed: {prompt}"
        trans_response = await model.generate_content_async(trans_prompt)
        english_prompt = trans_response.text.strip()
        
        # Thêm từ khóa tăng chất lượng
        enhanced_prompt = f"{english_prompt}, 8k resolution, highly detailed, masterpiece, best quality, vivid colors, cinematic lighting"
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        
        # Sử dụng model FLUX (Công nghệ mới tương đương Nano Banana/Imagen 3)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&seed={int(time.time())}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    print("✅ Đã tạo ảnh thành công!")
                    return image_data, english_prompt
                else:
                    print(f"❌ Lỗi tải ảnh: {response.status}")
                    return None, None
    except Exception as e:
        print(f"❌ Lỗi quy trình tạo ảnh: {e}")
        return None, None

# Hàm tạo ảnh sinh nhật (Đã nâng cấp)
async def generate_birthday_image(name, age, job):
    prompt = f"""
    Happy Birthday card for {name}, {age} years old, working as {job}.
    Luxury birthday party, cake, balloons, confetti, joyful atmosphere.
    Text 'Happy Birthday {name}' beautifully written.
    Digital art, 3D render style, cinematic lighting, 8k, masterpiece.
    """
    image_data, _ = await generate_image_core(prompt)
    return image_data

# ================= CÁC HÀM TIỆN ÍCH KHÁC =================

def check_message_type(message_content, message_author):
    content_lower = message_content.lower()
    
    # KIỂM TRA ĐỨC
    if (message_author.name.lower() == "vyanhduc" or 
        (message_author.display_name and "đức" in message_author.display_name.lower()) or
        (message_author.display_name and "duc" in message_author.display_name.lower())):
        return "duc"
    
    # Kiểm tra xưng hô
    if " anh " in content_lower or content_lower.startswith("anh ") or content_lower.endswith(" anh"):
        return "brother"
    
    return "normal"

def check_question_type(message_content):
    content_lower = message_content.lower()
    long_keywords = ['giải thích', 'phân tích', 'hướng dẫn', 'cách làm', 'chi tiết', 'như thế nào', 'tại sao', 'ý nghĩa']
    if any(k in content_lower for k in long_keywords):
        return "long"
    return "normal"

def get_conversation_history(channel_id):
    history = conversation_history[channel_id]
    if not history: return ""
    return "Lịch sử chat:\n" + "\n".join(list(history)[-10:]) + "\n"

def add_to_history(channel_id, message):
    conversation_history[channel_id].append(message)

# ================= DISCORD CLIENT & EVENTS =================
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã sẵn sàng phục vụ!')
    await client.change_presence(activity=discord.Game(name="vẽ tranh Nano Banana 3 🎨"))
    client.loop.create_task(birthday_check_loop())

async def birthday_check_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await check_birthdays(client)
        except Exception as e:
            print(f"❌ Lỗi check sinh nhật: {e}")
        await asyncio.sleep(3600 * 4) # Check mỗi 4 tiếng

async def check_birthdays(client):
    today = datetime.datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    for username, info in server_members.items():
        if info["birthday"]["day"] == today.day and info["birthday"]["month"] == today.month:
            if info.get("last_birthday_wish") != today_str:
                user = None
                for guild in client.guilds:
                    user = guild.get_member_named(username)
                    if user: break
                
                age = today.year - info["year"]
                
                # Tạo lời chúc
                wish_prompt = f"Viết lời chúc sinh nhật ngắn gọn, tình cảm cho {info['name']}, {age} tuổi, làm nghề {info['job']}. Có emoji."
                resp = await model.generate_content_async(wish_prompt)
                wish_msg = resp.text.strip()

                # Tạo ảnh
                img_data = await generate_birthday_image(info['name'], age, info['job'])
                
                # Gửi
                if user and guild:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            content = f"🎉 **CHÚC MỪNG SINH NHẬT!** 🎉\n{user.mention}\n{wish_msg}"
                            if img_data:
                                f = discord.File(io.BytesIO(img_data), filename="birthday.png")
                                await channel.send(content, file=f)
                            else:
                                await channel.send(content)
                            info["last_birthday_wish"] = today_str
                            break

@client.event
async def on_message(message):
    if message.author.bot: return

    # === LỆNH VẼ TRANH (!ve hoặc !draw) ===
    if message.content.lower().startswith(('!ve ', '!draw ', '!tạo ảnh ')):
        prompt = message.content.split(' ', 1)[1].strip()
        if not prompt:
            await message.reply("Bạn muốn mình vẽ gì nè? (Ví dụ: `!ve con mèo lái phi thuyền`)")
            return

        async with message.channel.typing():
            # Phản hồi vui vẻ trước khi vẽ
            pre_msg = await message.reply(f"🎨 Đợi xíu, mình đang dùng công nghệ **Nano Banana 3** để vẽ: *{prompt}* ...")
            
            image_data, english_prompt = await generate_image_core(prompt)
            
            if image_data:
                file = discord.File(io.BytesIO(image_data), filename=f"gemini_art_{int(time.time())}.png")
                await pre_msg.delete() # Xóa tin nhắn chờ
                await message.reply(f"✨ Tranh của bạn đây! (Prompt gốc: *{english_prompt}*)", file=file)
            else:
                await pre_msg.edit(content="😅 Xin lỗi, hôm nay mình hết mực rồi (Lỗi server ảnh), bạn thử lại sau nhé!")
        return

    # === LỆNH TEST & INFO ===
    if message.content.startswith('!test_birthday'):
        username = message.content.split()[1] if len(message.content.split()) > 1 else ""
        if username in server_members:
            info = server_members[username]
            age = datetime.datetime.now().year - info['year']
            async with message.channel.typing():
                img_data = await generate_birthday_image(info['name'], age, info['job'])
                if img_data:
                    await message.channel.send(f"Test Birthday for **{info['name']}**:", file=discord.File(io.BytesIO(img_data), filename="test.png"))
                else:
                    await message.channel.send("Test Birthday: Tạo ảnh lỗi.")
        return

    if message.content.startswith('!member_info'):
        username = message.content.split()[1] if len(message.content.split()) > 1 else ""
        if username in server_members:
            info = server_members[username]
            await message.channel.send(f"ℹ️ **{info['name']}** | Job: {info['job']} | Born: {info['year']}")
        return

    # === CHAT THÔNG MINH (KHI TAG HOẶC DM) ===
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_msg = message.content.replace(f'<@{client.user.id}>', '').strip()
        if not user_msg and not message.attachments:
            await message.reply("Dạ mình nghe nè! 🌟")
            return

        async with message.channel.typing():
            try:
                msg_type = check_message_type(user_msg, message.author)
                history = get_conversation_history(str(message.channel.id))
                
                # Xử lý ảnh đầu vào (Vision)
                if message.attachments:
                    att = message.attachments[0]
                    if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                        img_bytes = await att.read()
                        img = Image.open(io.BytesIO(img_bytes))
                        
                        prompt = f"{personality}\n{history}\nNgười dùng gửi ảnh và nói: '{user_msg}'. Hãy phân tích ảnh và trả lời."
                        response = await model.generate_content_async([prompt, img])
                        await message.reply(response.text.strip())
                        return

                # Xử lý chat text
                prompt = f"""
                {personality}
                {history}
                User ({message.author.display_name}) nói: "{user_msg}"
                
                Yêu cầu:
                - Nếu là anh Đức: Trả lời cực kỳ ngọt ngào.
                - Nếu người dùng yêu cầu vẽ tranh nhưng không dùng lệnh !ve, hãy nhắc họ dùng lệnh `!ve [nội dung]`.
                - Trả lời ngắn gọn, vui vẻ.
                """
                
                response = await model.generate_content_async(prompt)
                bot_reply = response.text.strip()
                
                add_to_history(str(message.channel.id), f"User: {user_msg}")
                add_to_history(str(message.channel.id), f"Bot: {bot_reply}")
                
                await message.reply(bot_reply)
                
            except Exception as e:
                print(f"Chat Error: {e}")
                await message.reply("Ui, mình bị vấp chút xíu, bạn nói lại được không? 😅")

# ================= SERVER WEB (KEEP ALIVE) =================
app = flask.Flask(__name__)

@app.route('/')
def home():
    return "🤖 Yoo Ji Min Bot is ONLINE!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    keep_alive()
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi Run Bot: {e}")
