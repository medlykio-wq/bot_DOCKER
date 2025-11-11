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
server_memory = deque(maxlen=500)

# Tính cách Yoo Ji Min - ĐÃ CẬP NHẬT
personality = """
Bạn là Yoo Ji Min, một thành viên trong server Discord này.

TÍNH CÁCH:
- TRỰC TIẾP, THẲNG THẮN, KHÔNG VÒNG VO
- Trả lời ngắn gọn, đi thẳng vào vấn đề
- Có thể trả lời CÓ/KHÔNG rõ ràng
- Tự nhiên như bạn bè, không cần quá lịch sự
- Dùng từ đơn giản, dễ hiểu
- Hạn chế xưng hô, nếu cần thì xưng "mình" - "bạn"
- Dùng emoji tự nhiên, phù hợp với sự vật sự việc

CHỈ XỬ LÝ ĐẶC BIỆT:
- Với Đức (vyanhduc): vẫn ngọt ngào, tinh tế, xưng em gọi anh

CÁCH TRẢ LỜI:
- Câu hỏi thông thường: trả lời 5-25 chữ
- Câu hỏi lý thuyết, thông tin chi tiết, giải thích: có thể trả lời dài đến 60 từ
- Trả lời trực tiếp câu hỏi, không giải thích dài dòng nếu không cần
- Có thể dùng tiếng lóng, từ ngữ thông dụng
- Tự nhiên như đang nói chuyện với bạn
- Nếu không biết thì nói không biết

EMOJI THEO CHỦ ĐỀ:
- Thể thao: ⚽️🏀🎾🏐🏈⚾️🎯🏆🥇
- Âm nhạc: 🎵🎶🎸🎹🥁🎧🎤🎷
- Du lịch: 🏖️🗺️✈️🚗🏞️🏕️🌅
- Học tập: 📚📖✏️📝🎓💡🧠
- Ẩm thực: 🍜🍕🍣🍔🌮🍲☕️🍰
- Thiên nhiên: 🌞🌙⭐️🌧️❄️🌈🌺🐶🐱
-Công nghệ: 💻📱🖥️🎮🔧⚙️🚀
- Cảm xúc: 😊😂😍😎🤔😢🔥💫

VÍ DỤ:
- "Có chứ, đẳng cấp lắm! 😎"
- "Không, chưa đủ level đâu 💀"
- "Đội hình gồm: Ronaldo, Messi, Neymar, Mbappé... ⚽️"
- "JavaScript là ngôn ngữ lập trình cho web, chạy trên browser 💻"
"""

# Hàm xác định loại tin nhắn
def check_message_type(message_content, message_author):
    # CHỈ KIỂM TRA ĐỨC
    if (message_author.name.lower() == "vyanhduc" or 
        (message_author.display_name and "đức" in message_author.display_name.lower()) or
        (message_author.display_name and "duc" in message_author.display_name.lower())):
        return "duc"
    
    return "normal"

# Hàm kiểm tra câu hỏi có cần trả lời dài không
def need_long_answer(message_content):
    message_lower = message_content.lower()
    long_answer_keywords = [
        'là gì', 'là ai', 'tại sao', 'như thế nào', 'hướng dẫn', 'cách',
        'giải thích', 'định nghĩa', 'khái niệm', 'liệt kê', 'danh sách',
        'đội hình', 'thành phần', 'cấu trúc', 'nguyên lý', 'cơ chế',
        'so sánh', 'phân tích', 'đánh giá', 'quy trình', 'bước'
    ]
    
    return any(keyword in message_lower for keyword in long_answer_keywords)

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
        
        # Xác định độ dài câu trả lời dựa trên câu hỏi
        is_long_answer = need_long_answer(user_message) if user_message else False
        
        if message_type == "duc":
            prompt_text = f"""
{personality}

{server_context}
{history_text}

Anh Đức gửi ảnh. {f"Anh ấy hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh NGẮN GỌN, TRỰC TIẾP
2. Xưng 'em' gọi 'anh' một cách tự nhiên
3. Dùng emoji phù hợp nội dung ảnh
4. {'Có thể trả lời dài đến 60 từ nếu cần giải thích chi tiết' if is_long_answer else 'Ngắn gọn 5-25 chữ'}

Phân tích:
"""
        else:  # normal
            prompt_text = f"""
{personality}

{server_context}
{history_text}

Có người gửi ảnh. {f"Họ hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh TRỰC TIẾP, KHÔNG VÒNG VO
2. Hạn chế xưng hô
3. Dùng emoji phù hợp
4. {'Có thể trả lời dài đến 60 từ nếu cần giải thích chi tiết' if is_long_answer else 'Ngắn gọn 5-25 chữ'}

Trả lời:
"""

        response = model.generate_content([prompt_text, image])
        return response.text.strip()
        
    except Exception as e:
        return f"Lỗi ảnh rồi"

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
                
                # Lấy lịch sử hội thoại của kênh và ngữ cảnh server
                history_text = get_conversation_history(channel_id)
                server_context = get_server_context()
                
                # Kiểm tra xem có cần trả lời dài không
                is_long_answer = need_long_answer(user_message)
                
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
                        response_text = "Dạ anh? 🌟"
                    else:
                        response_text = "Gì? 😏"
                    
                    await message.reply(response_text)
                    add_to_history(channel_id, f"{message.author.display_name}: (tag)")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                    return
                
                message_type = check_message_type(user_message, message.author)
                print(f"👤 {message.author.name}: {user_message} | Loại: {message_type} | Dài: {is_long_answer}")

                # Prompt cho từng loại tin nhắn - ĐÃ CẬP NHẬT
                if message_type == "duc":
                    prompt = f"""
{personality}

{server_context}
{history_text}

Anh Đức hỏi: "{user_message}"

TRẢ LỜI:
1. Trả lời TRỰC TIẾP, TINH TẾ
2. Xưng 'em' gọi 'anh' tự nhiên
3. Có thể kết thúc bằng "anh ạ", "nha anh"
4. Dùng emoji phù hợp
5. {'Có thể trả lời dài đến 60 từ để giải thích chi tiết' if is_long_answer else 'Ngắn gọn 5-25 chữ'}
6. KHÔNG vòng vo

Em trả lời:
"""
                else:  # normal - TRỰC TIẾP
                    prompt = f"""
{personality}

{server_context}
{history_text}

Câu hỏi: "{user_message}"

TRẢ LỜI:
1. TRẢ LỜI THẲNG VÀO VẤN ĐỀ
2. Có thể trả lời CÓ/KHÔNG trực tiếp
3. Hạn chế xưng hô, nếu cần thì "mình"-"bạn"
4. Tự nhiên, không khách sáo
5. Dùng emoji phù hợp với nội dung
6. {'Có thể trả lời dài đến 60 từ để cung cấp thông tin đầy đủ' if is_long_answer else 'Ngắn gọn 5-25 chữ'}
7. KHÔNG giải thích dài nếu không cần

Ví dụ:
- "Có! 🔥"
- "Không đâu 💀"  
- "Đội hình: Ronaldo, Messi, Neymar... ⚽️"
- "JavaScript là ngôn ngữ lập trình web 💻"

Trả lời:
"""

                response = model.generate_content(prompt)
                
                if response.text:
                    response_text = response.text.strip()
                    
                    # Giới hạn chữ linh hoạt
                    words = response_text.split()
                    if is_long_answer and len(words) > 60:
                        response_text = ' '.join(words[:60]) + "..."
                    elif not is_long_answer and len(words) > 25:
                        response_text = ' '.join(words[:25])
                    
                    await message.reply(response_text)
                    print(f"🤖 Yoo Ji Min: {response_text}")
                    
                    # Lưu vào lịch sử kênh
                    add_to_history(channel_id, f"{message.author.display_name}: {user_message}")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                else:
                    error_msg = "Hỏi gì? 🤨"
                    await message.reply(error_msg)
                    add_to_history(channel_id, f"{message.author.display_name}: {user_message}")
                    add_to_history(channel_id, f"Yoo Ji Min: {error_msg}")
                    
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            error_msg = "Lỗi rồi!"
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
