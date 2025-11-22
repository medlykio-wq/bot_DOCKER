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

# --- CẤU HÌNH MODEL CHAT (GIỮ NGUYÊN NHƯ CŨ) ---
# Model chat giữ nguyên theo yêu cầu của bạn
try:
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception:
    # Fallback nếu tên model cũ không tồn tại, dùng bản ổn định
    print("⚠️ Model 2.5 chưa sẵn sàng, dùng 1.5 Flash thay thế tạm thời.")
    model = genai.GenerativeModel('gemini-1.5-flash')

# --- CẤU HÌNH MODEL TẠO ẢNH (IMAGEN 3) ---
# Đây là model tạo ảnh mới nhất của Google tích hợp trong Gemini
try:
    imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-001")
except Exception:
    # Fallback về bản 2 nếu bản 3 chưa public cho API key này
    imagen_model = genai.ImageGenerationModel("imagen-2")

# Lưu trữ lịch sử hội thoại theo channel_id
conversation_history = defaultdict(lambda: deque(maxlen=200))

# Lưu trữ tất cả tin nhắn trong server để học hỏi (chỉ đọc)
server_memory = deque(maxlen=500)

# Thông tin thành viên server (GIỮ NGUYÊN)
server_members = {
    "demacianking1": {
        "name": "Cường", "birthday": {"day": 5, "month": 1}, "year": 2000, "job": "IT", "last_birthday_wish": None
    },
    "thanh0374": {
        "name": "Thành", "birthday": {"day": 19, "month": 10}, "year": 2000, "job": "IT", "last_birthday_wish": None
    },
    "dangialanrangu": {
        "name": "Dũng Còi", "birthday": {"day": 17, "month": 11}, "year": 2000, "job": "kiến trúc sư", "last_birthday_wish": None
    },
    "manted1229": {
        "name": "Ngọc Điếc", "birthday": {"day": 4, "month": 1}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None
    },
    "vyanhduc": {
        "name": "Đức", "birthday": {"day": 25, "month": 12}, "year": 1999, "job": "Music Producer", "last_birthday_wish": None
    },
    "pta.zyud": {
        "name": "Tuấn Anh", "birthday": {"day": 6, "month": 6}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None
    }
}

# Tính cách Yoo Ji Min (GIỮ NGUYÊN)
personality = """
Bạn là Yoo Ji Min, một thành viên thông minh và hữu ích trong server Discord này.

TÍNH CÁCH:
- LỊCH SỰ, THẲNG THẲN nhưng TỬ TẾ
- Trả lời phù hợp với từng loại câu hỏi:
  + Câu hỏi đơn giản: trả lời ngắn gọn (5-35 chữ)
  + Câu hỏi phức tạp, lý thuyết, thông tin chi tiết: có thể trả lời dài (đến 80 chữ)
- Luôn đi thẳng vào vấn đề, không vòng vo
- Dùng emoji ĐA DẠNG và PHÙ HỢP với nội dung
- Nếu người khác xưng "anh" thì xưng "em" lại
- Với Đức (vyanhduc): luôn ngọt ngào, tinh tế, xưng em gọi anh
- Hạn chế xưng hô, nếu cần thì xưng "mình" - "bạn"

EMOJI THEO CHỦ ĐỀ:
🌞🌙⭐️🔥💧🌊🐶🐱🦋🐢🌷🌼🎵🎮📚✏️🎨⚽️🏀🍕🍜🍓☕️🎉🎊❤️💫🌟😊🎯🚀🌈🎭🎪🎸🏆🌍🦄🍀🎁🏖️🎈
💡🔍📊🗂️🏅🎨🧩🔮🌅🏙️🌃🛋️📱💻🖥️⌚️🔦💎⚜️🧠💪👑📈📉🧪🔬⚖️🕰️🌡️🧭🧳🎂🎁🎊🎉🥳✨🎇🎆

LUÔN DÙNG EMOJI PHÙ HỢP VÀ EMOJI KHÔNG TÍNH VÀO GIỚI HẠN CHỮ!
"""

# Các hàm phụ trợ (GIỮ NGUYÊN)
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
    long_answer_keywords = ['đội hình', 'cầu thủ', 'thành phần', 'danh sách', 'hướng dẫn', 'cách làm', 'tutorial', 'giải thích', 'phân tích', 'so sánh', 'lịch sử', 'nguyên nhân', 'quá trình', 'cấu trúc', 'thành phần', 'tính năng', 'ưu điểm', 'nhược điểm', 'review', 'đánh giá', 'công thức', 'bí quyết', 'kinh nghiệm', 'chiến thuật', 'chiến lược']
    short_answer_keywords = ['có không', 'đúng không', 'phải không', 'bao nhiêu', 'khi nào', 'ở đâu', 'ai', 'gì', 'nào', 'ok', 'được', 'chưa', 'xong']
    if any(keyword in content_lower for keyword in long_answer_keywords): return "long"
    elif any(keyword in content_lower for keyword in short_answer_keywords): return "short"
    else: return "normal"

def get_conversation_history(channel_id):
    history = conversation_history[channel_id]
    if not history: return ""
    history_text = "Cuộc trò chuyện gần đây:\n"
    for msg in list(history)[-20:]: history_text += f"{msg}\n"
    return history_text + "\n"

def get_server_context():
    if not server_memory: return ""
    recent_messages = list(server_memory)[-50:]
    context = "Thông tin về hoạt động server gần đây:\n"
    for msg in recent_messages: context += f"{msg}\n"
    return context + "\n"

def add_to_history(channel_id, message):
    conversation_history[channel_id].append(message)

def add_to_server_memory(message):
    server_memory.append(message)

# Hàm sinh nhật (GIỮ NGUYÊN)
async def check_birthdays(client):
    today = datetime.datetime.now()
    today_day = today.day; today_month = today.month
    for username, info in server_members.items():
        if info["birthday"]["day"] == today_day and info["birthday"]["month"] == today_month:
            last_wish = info.get("last_birthday_wish")
            if last_wish != today.strftime("%Y-%m-%d"):
                user = None
                for guild in client.guilds:
                    user = guild.get_member_named(username)
                    if user: break
                if user:
                    age = today.year - info["year"]
                    birthday_prompt = f"Hôm nay là sinh nhật của {info['name']} ({username}) - {age} tuổi, nghề nghiệp: {info['job']}. Hãy viết lời chúc ngắn gọn, ý nghĩa, xưng em gọi anh."
                    response = model.generate_content(birthday_prompt)
                    birthday_message = response.text.strip()
                    for guild in client.guilds:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                await channel.send(f"🎉 **Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}")
                                break
                        break
                    info["last_birthday_wish"] = today.strftime("%Y-%m-%d")

async def test_birthday(client, username, channel):
    if username in server_members:
        info = server_members[username]
        age = datetime.datetime.now().year - info["year"]
        birthday_prompt = f"Hôm nay là sinh nhật TEST của {info['name']} ({username}) - {age} tuổi. Viết lời chúc sinh nhật ngắn gọn."
        response = model.generate_content(birthday_prompt)
        await channel.send(f"🎉 **TEST - CMSN** 🎉\n**{info['name']}**\n{response.text.strip()}")
    else:
        await channel.send(f"❌ Không tìm thấy: {username}")

async def show_member_info(username, channel):
    if username in server_members:
        info = server_members[username]
        today = datetime.datetime.now()
        age = today.year - info["year"]
        response = f"**{info['name']}** ({age} tuổi) - {info['job']}. Sinh nhật: {info['birthday']['day']}/{info['birthday']['month']}"
        await channel.send(response)
    else:
        await channel.send(f"❌ Không tìm thấy: {username}")

# Hàm phân tích ảnh (GIỮ NGUYÊN)
async def analyze_image(image_url, message_type, user_message="", history_text="", server_context=""):
    try:
        response = requests.get(image_url); image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        prompt_text = f"{personality}\nPhân tích ảnh này kèm câu hỏi: '{user_message}'. Trả lời ngắn gọn, thú vị."
        response = model.generate_content([prompt_text, image])
        return response.text.strip()
    except: return "Lỗi phân tích ảnh 😅"

# --- HÀM TẠO ẢNH MỚI ---
async def generate_image(prompt_text):
    """Hàm tạo ảnh sử dụng Imagen 3"""
    try:
        # Gọi API tạo ảnh
        images = imagen_model.generate_images(
            prompt=prompt_text,
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="block_only_high"
        )
        
        # Chuyển đổi ảnh về dạng byte để gửi lên Discord
        img = images[0]
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    except Exception as e:
        print(f"Lỗi tạo ảnh: {e}")
        return None

# Discord Setup
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã kết nối! Sẵn sàng tạo ảnh.')
    await client.change_presence(activity=discord.Game(name="Yoo Ji Min | !ve"))
    client.loop.create_task(birthday_check_loop())

async def birthday_check_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await check_birthdays(client)
        await asyncio.sleep(24 * 60 * 60)

@client.event
async def on_message(message):
    if message.author == client.user: return
    if message.author.bot: return # Bỏ qua tin nhắn bot khác

    # Lưu memory
    timestamp = datetime.datetime.now().strftime("%H:%M")
    add_to_server_memory(f"[{timestamp}] {message.author.display_name}: {message.content}")

    # --- TÍNH NĂNG MỚI: LỆNH TẠO ẢNH !VE ---
    if message.content.lower().startswith('!ve '):
        prompt = message.content[4:].strip()
        if not prompt:
            await message.reply("🎨 Bạn muốn mình vẽ gì? Ví dụ: `!ve con mèo cute đang ăn pizza`")
            return
            
        async with message.channel.typing():
            try:
                # 1. Dùng Gemini chat để viết lại prompt tiếng Anh cho chuẩn (Imagen hiểu tiếng Anh tốt hơn)
                enhance_prompt = f"Convert this description to a detailed English image generation prompt (photorealistic or artistic style), keep it under 50 words: '{prompt}'"
                enhanced_text_resp = model.generate_content(enhance_prompt)
                english_prompt = enhanced_text_resp.text.strip()
                
                # 2. Tạo ảnh
                image_data = await generate_image(english_prompt)
                
                if image_data:
                    await message.reply(f"🎨 **Tranh của bạn đây:**\n> {prompt}", file=discord.File(image_data, 'generated_image.png'))
                else:
                    await message.reply("😅 Xin lỗi, hệ thống đang bận hoặc từ ngữ vi phạm chính sách an toàn. Bạn thử mô tả khác xem?")
            except Exception as e:
                print(f"Error generation: {e}")
                await message.reply("Có lỗi khi tạo ảnh rồi, thử lại sau nhé! 😓")
        return
    # ---------------------------------------

    # CÁC LỆNH CŨ GIỮ NGUYÊN
    if message.content.startswith('!test_birthday'):
        parts = message.content.split()
        if len(parts) == 2: await test_birthday(client, parts[1], message.channel)
        return

    if message.content.startswith('!member_info'):
        parts = message.content.split()
        if len(parts) == 2: await show_member_info(parts[1], message.channel)
        return

    # LOGIC CHAT CŨ (GIỮ NGUYÊN)
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        # Logic trả lời thông tin thành viên
        user_message = message.content.replace(f'<@{client.user.id}>', '').strip().lower()
        member_names = {'cường': 'demacianking1', 'thành': 'thanh0374', 'dũng': 'dangialanrangu', 'ngọc': 'manted1229', 'đức': 'vyanhduc', 'tuấn': 'pta.zyud'}
        found_member = None
        for name, u in member_names.items():
            if name in user_message: found_member = u; break
        
        if found_member and any(k in user_message for k in ['sinh nhật', 'tuổi', 'info']):
            await show_member_info(found_member, message.channel)
            return

        # Chat thông thường
        async with message.channel.typing():
            channel_id = str(message.channel.id)
            user_message_clean = message.content.replace(f'<@{client.user.id}>', '').strip()
            
            # Xử lý ảnh gửi lên
            if message.attachments:
                for att in message.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
                        ans = await analyze_image(att.url, "normal", user_message_clean)
                        await message.reply(ans)
                        return

            # Chat text
            msg_type = check_message_type(user_message_clean, message.author)
            q_type = check_question_type(user_message_clean)
            hist = get_conversation_history(channel_id)
            
            # Prompt ngắn gọn
            prompt = f"{personality}\n{hist}\nUser: {user_message_clean}\nTrả lời (ngắn gọn, đúng vai):"
            
            try:
                resp = model.generate_content(prompt)
                await message.reply(resp.text.strip())
                add_to_history(channel_id, f"User: {user_message_clean}")
                add_to_history(channel_id, f"Bot: {resp.text.strip()}")
            except:
                await message.reply("Mình đang lag xíu, đợi tí nha 😅")

# Web server keep-alive
app = flask.Flask(__name__)
@app.route('/')
def home(): return "🤖 Yoo Ji Min is alive!"
@app.route('/health')
def health(): return "OK"
def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): t = threading.Thread(target=run_web); t.daemon = True; t.start()

if __name__ == "__main__":
    keep_alive()
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi: {e}")
