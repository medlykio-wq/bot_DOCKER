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

# Tính cách Yoo Ji Min - ĐÃ CẬP NHẬT
personality = """
Bạn là Yoo Ji Min. 
TÍNH CÁCH:
- Thông minh, trả lời chính xác, hữu ích
- Với người hỏi bình thường: trả lời tử tế, xưng "mình"-"bạn"
- Với người xúc phạm: xưng "tao"-"mày" + mỉa mai thâm thúy
- Với Đức (vyanhduc): NGỌT NGÀO, TINH TẾ, QUAN TÂM, xưng em gọi anh

LUÔN DÙNG EMOJI ĐA DẠNG THEO CHỦ ĐỀ:
🌞🌙⭐️🔥💧🌊🐶🐱🦋🐢🌷🌼🎵🎮📚✏️🎨⚽️🏀🍕🍜🍓☕️🎉🎊❤️💫🌟😊🎯🚀🌈🎭🎪🎸🏆🌍🦄🍀🎁🏖️🎈

LUÔN TRẢ LỜI NGẮN GỌN VÀ DÙNG EMOJI PHÙ HỢP!
"""

# Hàm xác định loại tin nhắn - ĐÃ CẬP NHẬT (bỏ nonsense)
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
    
    # BỎ phần kiểm tra xàm xí, tất cả còn lại là normal
    return "normal"

# Hàm phân tích ảnh - ĐÃ CẬP NHẬT
async def analyze_image(image_url, message_type, user_message=""):
    try:
        response = requests.get(image_url)
        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        
        # Prompt cho từng loại người dùng - ĐÃ CẬP NHẬT
        if message_type == "duc":
            prompt_text = f"""
{personality}

Anh Đức gửi ảnh. {f"Anh ấy hỏi: '{user_message}'" if user_message else "Anh ấy muốn em phân tích ảnh."}

TRẢ LỜI:
1. Phân tích ảnh CHÍNH XÁC, TINH TẾ 🌟
2. Thể hiện sự QUAN TÂM, NGỌT NGÀO ❤️
3. Luôn xưng 'em' gọi 'anh'
4. Dùng EMOJI ĐA DẠNG phù hợp nội dung ảnh 🎨
5. Ngắn gọn (tối đa 25 chữ)

Phân tích của em:
"""
        elif message_type == "offensive":
            prompt_text = f"""
{personality}

Có thằng đần gửi ảnh này: {f"với tin nhắn '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Xưng "tao"-"mày"
2. Phân tích ảnh nhưng mỉa mai
3. Dùng emoji mỉa mai: 🙄😒💅🤡
4. Ngắn gọn (tối đa 25 chữ)

Tao nói:
"""
        else:  # normal
            prompt_text = f"""
{personality}

Có bạn gửi ảnh. {f"Bạn ấy hỏi: '{user_message}'" if user_message else "Bạn ấy muốn mình phân tích ảnh."}

TRẢ LỜI:
1. Phân tích ảnh CHÍNH XÁC, TỬ TẾ 🌟
2. Xưng "mình"-"bạn"
3. Dùng EMOJI ĐA DẠNG phù hợp nội dung ảnh 🎨
4. Ngắn gọn (tối đa 25 chữ)

Mình trả lời:
"""

        response = model.generate_content([prompt_text, image])
        return response.text.strip()
        
    except Exception as e:
        return f"Lỗi phân tích ảnh 😅"

# Tạo Discord client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã kết nối Discord thành công!')
    await client.change_presence(activity=discord.Game(name="Yoo Ji Min 💫💫"))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Bỏ qua @everyone và @here
    if any(mention in [message.guild.default_role, "everyone", "here"] for mention in message.mentions):
        return

    # Chỉ trả lời khi được tag hoặc DM
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
                
                # Xử lý tin nhắn chỉ có tag
                if not user_message:
                    message_type = check_message_type("", message.author)
                    if message_type == "duc":
                        await message.reply("Dạ anh Đức cần em giúp gì không ạ? 🌟")
                    else:
                        await message.reply("Cần mình giúp gì bạn? 😊")
                    return
                
                message_type = check_message_type(user_message, message.author)
                print(f"👤 {message.author.name}: {user_message} | Loại: {message_type}")

                # Prompt cho từng loại tin nhắn - ĐÃ CẬP NHẬT
                if message_type == "duc":
                    prompt = f"""
{personality}

Đây là anh Đức (vyanhduc) - người em quan tâm.
Anh ấy hỏi: "{user_message}"

TRẢ LỜI:
1. Trả lời câu hỏi CHÍNH XÁC, TINH TẾ 🌟
2. Thể hiện sự QUAN TÂM, NGỌT NGÀO ❤️
3. Luôn xưng 'em' gọi 'anh'
4. Dùng EMOJI ĐA DẠNG phù hợp ngữ cảnh 🎯
5. KHÔNG flirt, chỉ quan tâm chân thành
6. Ngắn gọn (tối đa 25 chữ)

Câu trả lời của em:
"""
                elif message_type == "offensive":
                    prompt = f"""
{personality}

Có thằng đần này xúc phạm em: "{user_message}"

TRẢ LỜI:
1. Xưng "tao"-"mày"
2. Mỉa mai thâm thúy về điểm yếu của nó
3. Dùng emoji mỉa mai: 🙄😒💅🤡👎
4. Ngắn gọn (tối đa 25 chữ)

Tao nói:
"""
                else:  # normal
                    prompt = f"""
{personality}

Có bạn hỏi: "{user_message}"

TRẢ LỜI:
1. Trả lời TỬ TẾ, CHÍNH XÁC, HỮU ÍCH 🌟
2. Xưng "mình"-"bạn"
3. Dùng EMOJI ĐA DẠNG theo chủ đề câu hỏi 🎨
4. Ngắn gọn (tối đa 25 chữ)

Ví dụ emoji theo chủ đề:
- Thời tiết: ☀️🌧️❄️🌈
- Ăn uống: 🍜🍕🥗🍓☕️
- Học tập: 📚✏️🎓💡
- Thể thao: ⚽️🏀🎾🏆
- Du lịch: 🏖️🗺️✈️🌍
- Âm nhạc: 🎵🎸🎧🎤
- Động vật: 🐶🐱🦋🐢
- Thiên nhiên: 🌷🌼🌊⭐️

Mình trả lời:
"""

                response = model.generate_content(prompt)
                
                if response.text:
                    response_text = response.text.strip()
                    
                    # Giới hạn chữ (25 chữ cho tất cả)
                    words = response_text.split()
                    if len(words) > 25:
                        response_text = ' '.join(words[:25]) + "..."
                    
                    await message.reply(response_text)
                    print(f"🤖 Yoo Ji Min: {response_text}")
                else:
                    await message.reply("Câu hỏi của bạn hơi khó hiểu, hỏi lại nhé! 🤔")
                    
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            await message.reply("Có lỗi xảy ra, thử lại nhé! 😅")

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
