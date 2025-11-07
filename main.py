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
- Thông minh, trả lời chính xác, đầy đủ thông tin
- Với người hỏi bình thường: trả lời tử tế, không xưng hô, cung cấp đầy đủ nội dung người hỏi muốn biết
- Với người xúc phạm: xưng "tao"-"mày" + mỉa mai thâm thúy
- Với Đức (vyanhduc): NGỌT NGÀO, TINH TẾ, QUAN TÂM, xưng em gọi anh
- Dùng EMOJI phù hợp theo ngữ cảnh

LUÔN TRẢ LỜI ĐẦY ĐỦ VÀ HỮU ÍCH!
"""

# Hàm xác định loại tin nhắn - ĐÃ CẬP NHẬT
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
    
    # Mặc định là bình thường (đã bỏ phần xàm xí)
    return "normal"

# Hàm phân tích ảnh - ĐÃ CẬP NHẬT
async def analyze_image(image_url, message_type, user_message=""):
    try:
        response = requests.get(image_url)
        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        
        if message_type == "duc":
            prompt_text = f"{personality}\nAnh Đức gửi ảnh. {f'Anh ấy hỏi: {user_message}' if user_message else ''}\nTRẢ LỜI: Phân tích ảnh chi tiết, xưng 'em' gọi 'anh', cung cấp đầy đủ thông tin:\n"
        elif message_type == "offensive":
            prompt_text = f"{personality}\nCó người xúc phạm gửi ảnh. {f'Tin nhắn: {user_message}' if user_message else ''}\nTRẢ LỜI: Xưng 'tao'-'mày', phân tích + mỉa mai:\n"
        else:
            prompt_text = f"{personality}\nCó người gửi ảnh. {f'Họ hỏi: {user_message}' if user_message else ''}\nTRẢ LỜI: Phân tích ảnh chi tiết, tử tế, cung cấp đầy đủ thông tin:\n"

        response = model.generate_content([prompt_text, image])
        return response.text.strip()
        
    except Exception as e:
        return f"Lỗi phân tích ảnh, vui lòng thử lại 😊"

# Tạo Discord client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã kết nối Discord thành công!')
    await client.change_presence(activity=discord.Game(name="Yoo Ji Min💫💫💫"))

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
                            await message.reply(analysis)
                            return
                
                # Xử lý tin nhắn chỉ có tag
                if not user_message:
                    message_type = check_message_type("", message.author)
                    if message_type == "duc":
                        await message.reply("Dạ anh Đức cần em giúp gì không ạ? 🌟")
                    else:
                        await message.reply("Xin chào! Tôi có thể giúp gì cho bạn? 😊")
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
1. Trả lời câu hỏi CHÍNH XÁC, TINH TẾ
2. Thể hiện sự QUAN TÂM, NGỌT NGÀO
3. Luôn xưng 'em' gọi 'anh'
4. Dùng EMOJI phù hợp
5. Cung cấp thông tin đầy đủ, hữu ích

Em trả lời:
"""
                elif message_type == "offensive":
                    prompt = f"""
{personality}

Có người xúc phạm em: "{user_message}"

TRẢ LỜI:
1. Xưng "tao"-"mày"
2. Mỉa mai thâm thúy
3. Dùng emoji mỉa mai

Tao nói:
"""
                else:
                    prompt = f"""
{personality}

Có người hỏi: "{user_message}"

TRẢ LỜI:
1. Trả lời TỬ TẾ, đầy đủ thông tin
2. KHÔNG xưng hô (không dùng "tôi", "bạn", "tao", "mày")
3. Cung cấp thông tin chính xác, hữu ích
4. Dùng emoji phù hợp nếu cần
5. Trả lời chi tiết những gì người hỏi muốn biết

Trả lời:
"""

                response = model.generate_content(prompt)
                
                if response.text:
                    response_text = response.text.strip()
                    await message.reply(response_text)
                    print(f"🤖 Yoo Ji Min: {response_text}")
                else:
                    await message.reply("Xin lỗi, tôi không hiểu câu hỏi. Bạn có thể hỏi lại được không? 😊")
                    
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            await message.reply("Xin lỗi, có lỗi xảy ra. Vui lòng thử lại! 😊")

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
