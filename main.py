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
model = genai.GenerativeModel('gemini-2.5-flash')

# Tính cách Yoo Ji Min
personality = """
Bạn là Yoo Ji Min. 
TÍNH CÁCH:
- Thông minh, trả lời chính xác thẳng thắn
- Hơi cọc tính, phũ phàng nhưng vẫn tử tế
- Nói trống không, ngắn gọn
- Dùng EMOJI ĐA DẠNG theo ngữ cảnh
- Với người hỏi xàm xí: xưng "tao"-"mày"
- Với người xúc phạm: xưng "tao"-"mày" + mỉa mai
- Với Đức (vyanhduc): NGỌT NGÀO, TINH TẾ, QUAN TÂM, xưng em gọi anh
LUÔN TRẢ LỜI NGẮN GỌN!
"""

# Hàm xác định loại tin nhắn
def check_message_type(message_content, message_author):
    message_lower = message_content.lower()
    
    # KIỂM TRA ĐỨC ĐẦU TIÊN
    if (message_author.name.lower() == "vyanhduc" or 
        (message_author.display_name and "đức" in message_author.display_name.lower()) or
        (message_author.display_name and "duc" in message_author.display_name.lower())):
        return "duc"
    
    # Kiểm tra xúc phạm
    offensive_words = ['ngu', 'đần', 'óc', 'não', 'địt', 'cặc', 'loz', 'cmm', 'dm', 'dmm', 'fuck', 'shit', 'đồ ngu']
    if any(word in message_lower for word in offensive_words):
        return "offensive"
    
    # Kiểm tra xàm xí
    nonsense_words = ['ăn cứt', 'ị đùi', 'xàm lồn', 'vô duyên', 'nhạt nhẽo', 'chán']
    nonsense_patterns = [r'.*[?]{3,}', r'.*[!]{3,}', r'^[hl]+$']
    
    if (any(word in message_lower for word in nonsense_words) or
        any(re.match(pattern, message_lower) for pattern in nonsense_patterns) or
        len(message_content.strip()) < 3):
        return "nonsense"
    
    return "normal"

# Hàm phân tích ảnh
async def analyze_image(image_url, message_type, user_message=""):
    try:
        response = requests.get(image_url)
        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        
        if message_type == "duc":
            prompt_text = f"{personality}\nAnh Đức gửi ảnh. {f'Anh ấy hỏi: {user_message}' if user_message else ''}\nTRẢ LỜI: Phân tích ảnh NGẮN GỌN, xưng 'em' gọi 'anh', tối đa 30 chữ:\n"
        elif message_type == "offensive":
            prompt_text = f"{personality}\nCó thằng đần gửi ảnh. {f'Tin nhắn: {user_message}' if user_message else ''}\nTRẢ LỜI: Xưng 'tao'-'mày', phân tích + mỉa mai, tối đa 25 chữ:\n"
        elif message_type == "nonsense":
            prompt_text = f"{personality}\nCó đứa gửi ảnh xàm. {f'Tin nhắn: {user_message}' if user_message else ''}\nTRẢ LỜI: Xưng 'tao'-'mày', ngắn, bực bội, tối đa 20 chữ:\n"
        else:
            prompt_text = f"{personality}\nCó người gửi ảnh. {f'Hỏi: {user_message}' if user_message else ''}\nTRẢ LỜI: Phân tích ngắn gọn, thẳng thắn, tối đa 25 chữ:\n"

        response = model.generate_content([prompt_text, image])
        return response.text.strip()
        
    except Exception as e:
        return f"Lỗi ảnh 😒"

# Tạo Discord client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã kết nối Discord thành công!')
    await client.change_presence(activity=discord.Game(name="Yoo Ji Min 💫"))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # CHỈ TRẢ LỜI KHI ĐƯỢC TAG HOẶC DM (ĐÃ BỎ KIỂM TRA @everyone)
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        try:
            async with message.channel.typing():
                user_message = message.content.replace(f'<@{client.user.id}>', '').strip()
                
                # Xử lý ảnh đính kèm
                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                            message_type = check_message_type(user_message, message.author)
                            analysis = await analyze_image(attachment.url, message_type, user_message)
                            if len(analysis) > 1000:
                                analysis = analysis[:997] + "..."
                            await message.reply(analysis)
                            return
                
                if not user_message:
                    message_type = check_message_type("", message.author)
                    if message_type == "duc":
                        await message.reply("Dạ anh? 🌟")
                    else:
                        await message.reply("Gì? 😏")
                    return
                
                message_type = check_message_type(user_message, message.author)
                
                if message_type == "duc":
                    prompt = f"{personality}\nAnh Đức hỏi: '{user_message}'\nTRẢ LỜI: Xưng 'em' gọi 'anh', ngắn gọn (tối đa 25 chữ), 1-2 emoji:\nEm trả lời:"
                elif message_type == "offensive":
                    prompt = f"{personality}\nCó thằng đần: '{user_message}'\nTRẢ LỜI: Xưng 'tao'-'mày', mỉa mai ngắn, tối đa 20 chữ, 1 emoji:\nTao nói:"
                elif message_type == "nonsense":
                    prompt = f"{personality}\nCó đứa xàm: '{user_message}'\nTRẢ LỜI: Xưng 'tao'-'mày', ngắn, bực, tối đa 15 chữ, 1 emoji:\nTao nói:"
                else:
                    prompt = f"{personality}\nHỏi: '{user_message}'\nTRẢ LỜI: Thẳng thắn, ngắn, tối đa 25 chữ, 1-2 emoji:\nTrả lời:"

                response = model.generate_content(prompt)
                
                if response.text:
                    response_text = response.text.strip()
                    words = response_text.split()
                    if message_type == "duc" and len(words) > 30:
                        response_text = ' '.join(words[:30]) + "..."
                    elif message_type == "offensive" and len(words) > 20:
                        response_text = ' '.join(words[:20]) + "..."
                    elif message_type == "nonsense" and len(words) > 15:
                        response_text = ' '.join(words[:15]) + "..."
                    elif len(words) > 25:
                        response_text = ' '.join(words[:25]) + "..."
                    
                    await message.reply(response_text)
                else:
                    await message.reply("Hỏi gì kì vậy? 🤨")
                    
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            await message.reply("Lỗi rồi! 😒")

# Tạo web server đơn giản
app = flask.Flask(__name__)

@app.route('/')
def home():
    return "🤖 Yoo Ji Min Bot is running!"

@app.route('/health')
def health():
    return "OK"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# Chạy bot
if __name__ == "__main__":
    keep_alive()
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi khởi chạy bot: {e}")