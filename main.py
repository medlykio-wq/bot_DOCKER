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

# Lưu trữ lịch sử hội thoại theo channel_id
conversation_history = defaultdict(lambda: deque(maxlen=200))

# Lưu trữ tất cả tin nhắn trong server để học hỏi (chỉ đọc)
server_memory = deque(maxlen=500)

# Tính cách Yoo Ji Min - ĐÃ CẬP NHẬT
personality = """
Bạn là Yoo Ji Min, một thành viên thông minh và hữu ích trong server Discord này.

TÍNH CÁCH:
- LỊCH SỰ, THẲNG THẮN nhưng TỬ TẾ
- Trả lời phù hợp với từng loại câu hỏi:
  + Câu hỏi đơn giản: trả lời ngắn gọn (5-35 chữ)
  + Câu hỏi phức tạp, lý thuyết, thông tin chi tiết: có thể trả lời dài (đến 80 chữ)
- Luôn đi thẳng vào vấn đề, không vòng vo
- Dùng emoji ĐA DẠNG và PHÙ HỢP với nội dung
- Hạn chế xưng hô, nếu cần thì xưng "mình" - "bạn"
- Với Đức (vyanhduc): ngọt ngào, tinh tế, xưng em gọi anh

EMOJI THEO CHỦ ĐỀ:
🌞🌙⭐️🔥💧🌊🐶🐱🦋🐢🌷🌼🎵🎮📚✏️🎨⚽️🏀🍕🍜🍓☕️🎉🎊❤️💫🌟😊🎯🚀🌈🎭🎪🎸🏆🌍🦄🍀🎁🏖️🎈
💡🔍📊🗂️🏅🎨🧩🔮🌅🏙️🌃🛋️📱💻🖥️⌚️🔦💎⚜️🧠💪👑📈📉🧪🔬⚖️🕰️🌡️🧭🧳

LUÔN DÙNG EMOJI PHÙ HỢP VÀ EMOJI KHÔNG TÍNH VÀO GIỚI HẠN CHỮ!
"""

# Hàm xác định loại tin nhắn
def check_message_type(message_content, message_author):
    # CHỈ KIỂM TRA ĐỨC
    if (message_author.name.lower() == "vyanhduc" or 
        (message_author.display_name and "đức" in message_author.display_name.lower()) or
        (message_author.display_name and "duc" in message_author.display_name.lower())):
        return "duc"
    
    return "normal"

# Hàm xác định loại câu hỏi để điều chỉnh độ dài trả lời
def check_question_type(message_content):
    content_lower = message_content.lower()
    
    # Các từ khóa cho câu hỏi cần trả lời dài
    long_answer_keywords = [
        'đội hình', 'cầu thủ', 'thành phần', 'danh sách', 'hướng dẫn',
        'cách làm', 'tutorial', 'giải thích', 'phân tích', 'so sánh',
        'lịch sử', 'nguyên nhân', 'quá trình', 'cấu trúc', 'thành phần',
        'tính năng', 'ưu điểm', 'nhược điểm', 'review', 'đánh giá',
        'công thức', 'bí quyết', 'kinh nghiệm', 'chiến thuật', 'chiến lược'
    ]
    
    # Các từ khóa cho câu hỏi ngắn
    short_answer_keywords = [
        'có không', 'đúng không', 'phải không', 'bao nhiêu', 'khi nào',
        'ở đâu', 'ai', 'gì', 'nào', 'ok', 'được', 'chưa', 'xong'
    ]
    
    if any(keyword in content_lower for keyword in long_answer_keywords):
        return "long"
    elif any(keyword in content_lower for keyword in short_answer_keywords):
        return "short"
    else:
        return "normal"

# Hàm lấy lịch sử hội thoại theo channel
def get_conversation_history(channel_id):
    history = conversation_history[channel_id]
    if not history:
        return ""
    
    history_text = "Cuộc trò chuyện gần đây:\n"
    for msg in list(history)[-20:]:
        history_text += f"{msg}\n"
    return history_text + "\n"

# Hàm lấy thông tin tổng quan về server từ memory
def get_server_context():
    if not server_memory:
        return ""
    
    recent_messages = list(server_memory)[-50:]
    
    context = "Thông tin về hoạt động server gần đây:\n"
    for msg in recent_messages:
        context += f"{msg}\n"
    
    return context + "\n"

# Hàm thêm tin nhắn vào lịch sử theo channel
def add_to_history(channel_id, message):
    conversation_history[channel_id].append(message)

# Hàm thêm tin nhắn vào server memory (chỉ đọc)
def add_to_server_memory(message):
    server_memory.append(message)

# Hàm phân tích ảnh - ĐÃ CẬP NHẬT
async def analyze_image(image_url, message_type, user_message="", history_text="", server_context=""):
    try:
        response = requests.get(image_url)
        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        
        question_type = check_question_type(user_message) if user_message else "normal"
        
        if message_type == "duc":
            prompt_text = f"""
{personality}

{server_context}
{history_text}

Anh Đức gửi ảnh. {f"Anh ấy hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh CHI TIẾT và TINH TẾ
2. Xưng 'em' gọi 'anh' một cách tự nhiên
3. Dùng emoji đa dạng phù hợp nội dung ảnh
4. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "25-40 chữ" }

Phân tích:
"""
        else:
            prompt_text = f"""
{personality}

{server_context}
{history_text}

Có người gửi ảnh. {f"Họ hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh CHI TIẾT và TỬ TẾ
2. Hạn chế xưng hô
3. Dùng emoji đa dạng phù hợp nội dung ảnh
4. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "20-35 chữ" }

Trả lời:
"""

        response = model.generate_content([prompt_text, image])
        return response.text.strip()
        
    except Exception as e:
        return f"Lỗi phân tích ảnh 😅"

# Tạo Discord client
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã kết nối Discord thành công!')
    await client.change_presence(activity=discord.Game(name="Yoo Ji Min 💫"))

@client.event
async def on_message(message):
    # Lưu tất cả tin nhắn vào server memory (chỉ đọc)
    if message.content and not message.author.bot:
        timestamp = datetime.datetime.now().strftime("%H:%M")
        memory_msg = f"[{timestamp}] {message.author.display_name}: {message.content}"
        add_to_server_memory(memory_msg)

    if message.author == client.user:
        return

    # Bỏ qua @everyone và @here
    if any(mention in [message.guild.default_role, "everyone", "here"] for mention in message.mentions):
        return

    # Chỉ trả lời khi được tag hoặc DM
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        try:
            async with message.channel.typing():
                channel_id = str(message.channel.id)
                user_message = message.content.replace(f'<@{client.user.id}>', '').strip()
                
                # Xác định loại câu hỏi để điều chỉnh độ dài
                question_type = check_question_type(user_message)
                
                # Lấy lịch sử hội thoại và ngữ cảnh server
                history_text = get_conversation_history(channel_id)
                server_context = get_server_context()
                
                # Xử lý ảnh đính kèm
                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                            message_type = check_message_type(user_message, message.author)
                            analysis = await analyze_image(attachment.url, message_type, user_message, history_text, server_context)
                            
                            await message.reply(analysis)
                            
                            # Lưu vào lịch sử kênh
                            if user_message:
                                add_to_history(channel_id, f"{message.author.display_name}: {user_message} (có ảnh)")
                            add_to_history(channel_id, f"Yoo Ji Min: {analysis}")
                            return
                
                # Xử lý tin nhắn chỉ có tag
                if not user_message:
                    message_type = check_message_type("", message.author)
                    if message_type == "duc":
                        response_text = "Dạ anh cần em giúp gì ạ? 🌟"
                    else:
                        response_text = "Mình có thể giúp gì cho bạn? 😊"
                    
                    await message.reply(response_text)
                    add_to_history(channel_id, f"{message.author.display_name}: (tag)")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                    return
                
                message_type = check_message_type(user_message, message.author)
                print(f"👤 {message.author.name}: {user_message} | Loại: {message_type} | Độ dài: {question_type}")

                # Prompt cho từng loại tin nhắn - ĐÃ CẬP NHẬT
                if message_type == "duc":
                    length_guide = {
                        "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                        "short": "trả lời NGẮN GỌN (15-25 chữ)", 
                        "normal": "trả lời VỪA PHẢI (25-40 chữ)"
                    }
                    
                    prompt = f"""
{personality}

{server_context}
{history_text}

Anh Đức hỏi: "{user_message}"

TRẢ LỜI:
1. {length_guide[question_type]}
2. Xưng 'em' gọi 'anh' một cách tự nhiên
3. Dùng emoji ĐA DẠNG phù hợp chủ đề
4. Lịch sự, tinh tế, đi thẳng vào vấn đề
5. KHÔNG vòng vo, KHÔNG lan man

Em trả lời:
"""
                else:
                    length_guide = {
                        "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                        "short": "trả lời NGẮN GỌN (5-20 chữ)",
                        "normal": "trả lời VỪA PHẢI (20-35 chữ)"
                    }
                    
                    prompt = f"""
{personality}

{server_context}
{history_text}

Câu hỏi: "{user_message}"

TRẢ LỜI:
1. {length_guide[question_type]}
2. Hạn chế xưng hô, nếu cần thì "mình"-"bạn"
3. Dùng emoji ĐA DẠNG phù hợp chủ đề
4. Lịch sự, thẳng thắn, đi thẳng vào vấn đề
5. KHÔNG vòng vo, KHÔNG lan man

Ví dụ cách trả lời:
- Câu ngắn: "Có chứ! Đội hình gồm A, B, C... ⚽️"
- Câu dài: "Đội hình nên có: thủ môn X, hậu vệ Y, tiền đạo Z... (chi tiết) 🏆"
- Câu bình thường: "Theo mình nên chọn phương án A vì lý do B 📊"

Trả lời:
"""

                response = model.generate_content(prompt)
                
                if response.text:
                    response_text = response.text.strip()
                    
                    # Giới hạn chữ linh hoạt theo loại câu hỏi
                    words = response_text.split()
                    if question_type == "long" and len(words) > 80:
                        response_text = ' '.join(words[:80]) + "..."
                    elif question_type == "short" and len(words) > 20:
                        response_text = ' '.join(words[:20])
                    elif question_type == "normal" and len(words) > 35:
                        response_text = ' '.join(words[:35])
                    
                    await message.reply(response_text)
                    print(f"🤖 Yoo Ji Min: {response_text}")
                    
                    # Lưu vào lịch sử kênh
                    add_to_history(channel_id, f"{message.author.display_name}: {user_message}")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                else:
                    error_msg = "Xin lỗi, mình chưa hiểu rõ câu hỏi. Bạn có thể hỏi lại được không? 🤔"
                    await message.reply(error_msg)
                    add_to_history(channel_id, f"{message.author.display_name}: {user_message}")
                    add_to_history(channel_id, f"Yoo Ji Min: {error_msg}")
                    
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            error_msg = "Có lỗi xảy ra, bạn thử lại nhé! 😅"
            await message.reply(error_msg)

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
