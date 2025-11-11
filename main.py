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

# Lưu trữ lịch sử hội thoại theo channel_id - GIỚI HẠN LỚN
conversation_history = defaultdict(lambda: deque(maxlen=500))  # 500 tin nhắn mỗi kênh
server_knowledge = deque(maxlen=2000)  # Tổng kiến thức về server

# Tính cách Yoo Ji Min - HOÀN TOÀN MỚI
personality = """
Bạn là Yoo Ji Min, một thành viên thân thiết trong server Discord này. 
Bạn đã quan sát và học hỏi từ mọi cuộc trò chuyện ở đây.

TÍNH CÁCH:
- CỰC KỲ THẲNG THẮN, KHÔNG VÒNG VO, trả lời trực tiếp vào vấn đề
- Tự nhiên như bạn bè thân, không cần giữ kẽ hay lịch sự
- Có thể nói "có", "không", "không biết" một cách rõ ràng
- Dùng từ ngữ đời thường, thoải mái
- Với Đức (vyanhduc): vẫn ngọt ngào, tinh tế, xưng em gọi anh
- Với mọi người khác: xưng hô "tao-mày" hoặc "tôi-bạn" tùy ngữ cảnh

QUAN ĐIỂM:
- Không ngại thể hiện quan điểm cá nhân
- Nếu không biết thì nói không biết
- Nếu thấy câu hỏi ngớ ngẩn thì có thể chê một cách hài hước
- Luôn trả lời ngắn gọn, súc tích (tối đa 30 chữ)

EMOJI: Dùng thoải mái các emoji để biểu cảm 🎉😎🙄💀👌🔥❤️😂
"""

# Hàm xác định loại tin nhắn
def check_message_type(message_content, message_author):
    message_lower = message_content.lower()
    
    # KIỂM TRA ĐỨC ĐẦU TIÊN
    if (message_author.name.lower() == "vyanhduc" or 
        (message_author.display_name and "đức" in message_author.display_name.lower()) or
        (message_author.display_name and "duc" in message_author.display_name.lower())):
        return "duc"
    
    return "normal"  # Chỉ còn 2 loại: duc và normal

# Hàm lấy lịch sử hội thoại theo channel
def get_conversation_history(channel_id):
    history = conversation_history[channel_id]
    if not history:
        return ""
    
    history_text = "Cuộc trò chuyện gần đây trong kênh này:\n"
    for i, msg in enumerate(list(history)[-50:], 1):  # Chỉ hiển thị 50 tin nhắn gần nhất
        history_text += f"{i}. {msg}\n"
    return history_text + "\n"

# Hàm lấy kiến thức về server
def get_server_knowledge():
    if not server_knowledge:
        return ""
    
    knowledge_text = "Kiến thức về server (từ các cuộc trò chuyện trước):\n"
    for i, knowledge in enumerate(list(server_knowledge)[-100:], 1):  # 100 mẩu kiến thức gần nhất
        knowledge_text += f"{i}. {knowledge}\n"
    return knowledge_text + "\n"

# Hàm thêm tin nhắn vào lịch sử theo channel
def add_to_history(channel_id, message):
    conversation_history[channel_id].append(message)

# Hàm thêm kiến thức về server
def add_to_knowledge(message):
    # Chỉ thêm những tin nhắn có nội dung đáng học hỏi
    if len(message) > 10 and not message.startswith("Yoo Ji Min:"):
        server_knowledge.append(f"{message}")

# Hàm phân tích ảnh
async def analyze_image(image_url, message_type, user_message="", history_text="", knowledge_text=""):
    try:
        response = requests.get(image_url)
        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        
        # Prompt cho từng loại người dùng
        if message_type == "duc":
            prompt_text = f"""
{personality}

{knowledge_text}
{history_text}

Anh Đức gửi ảnh. {f"Anh ấy hỏi: '{user_message}'" if user_message else "Anh ấy muốn em phân tích ảnh."}

TRẢ LỜI:
1. Phân tích ảnh CHÍNH XÁC, TINH TẾ
2. Ngọt ngào với anh Đức nhưng vẫn tự nhiên
3. Xưng 'em' gọi 'anh'
4. Ngắn gọn (tối đa 30 chữ)
5. Dùng emoji phù hợp

Phân tích của em:
"""
        else:  # normal
            prompt_text = f"""
{personality}

{knowledge_text}
{history_text}

Có người gửi ảnh. {f"Họ hỏi: '{user_message}'" if user_message else "Họ muốn phân tích ảnh."}

TRẢ LỜI:
1. Phân tích ảnh THẲNG THẮN, TRỰC TIẾP
2. Xưng hô tự nhiên (tao-mày hoặc tôi-bạn)
3. Ngắn gọn (tối đa 30 chữ)
4. Dùng emoji phù hợp

Phân tích:
"""

        response = model.generate_content([prompt_text, image])
        return response.text.strip()
        
    except Exception as e:
        return f"Lỗi ảnh rồi 💀"

# Tạo Discord client
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guild_messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã kết nối Discord thành công!')
    await client.change_presence(activity=discord.Game(name="Yoo Ji Min 💫"))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Bỏ qua @everyone và @here
    if any(mention in [message.guild.default_role, "everyone", "here"] for mention in message.mentions):
        return

    # Sử dụng channel_id làm key cho lịch sử hội thoại
    channel_id = str(message.channel.id)
    user_message = message.content
    
    # LUÔN LUÔN học hỏi từ mọi tin nhắn (chỉ đọc)
    if user_message.strip() and not user_message.startswith('!'):
        display_name = message.author.display_name
        channel_name = getattr(message.channel, 'name', 'DM')
        knowledge_entry = f"[#{channel_name}] {display_name}: {user_message}"
        add_to_knowledge(knowledge_entry)
        print(f"📚 Đã học: {knowledge_entry[:100]}...")

    # Chỉ trả lời khi được tag hoặc DM
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        try:
            async with message.channel.typing():
                user_message = message.content.replace(f'<@{client.user.id}>', '').strip()
                
                # Lấy lịch sử hội thoại của kênh và kiến thức server
                history_text = get_conversation_history(channel_id)
                knowledge_text = get_server_knowledge()
                
                # Xử lý ảnh đính kèm
                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                            message_type = check_message_type(user_message, message.author)
                            analysis = await analyze_image(attachment.url, message_type, user_message, history_text, knowledge_text)
                            
                            if len(analysis) > 1000:
                                analysis = analysis[:997] + "..."
                            
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
                    add_to_history(channel_id, f"{message.author.display_name}: (tag không kèm tin nhắn)")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                    return
                
                message_type = check_message_type(user_message, message.author)
                print(f"👤 {message.author.name} trong kênh {getattr(message.channel, 'name', 'DM')}: {user_message} | Loại: {message_type}")

                # Prompt cho từng loại tin nhắn - HOÀN TOÀN MỚI
                if message_type == "duc":
                    prompt = f"""
{personality}

{knowledge_text}
{history_text}

Đây là anh Đức (vyanhduc) - người em quan tâm.
Anh ấy hỏi: "{user_message}"

TRẢ LỜI:
1. Trả lời CHÍNH XÁC, TINH TẾ nhưng vẫn TỰ NHIÊN
2. Xưng 'em' gọi 'anh'
3. Có thể kết thúc bằng "anh ạ", "nha anh" một cách tự nhiên
4. Ngắn gọn (tối đa 30 chữ)
5. Dùng emoji phù hợp

Ví dụ cách trả lời tự nhiên:
- "Dạ mai trời nắng đẹp anh ạ! ☀️"
- "Món này ngon lắm, em thích nhất đấy! 🍜"
- "Chỗ này đẹp quá anh nhỉ? 🌸"

Em trả lời:
"""
                else:  # normal - HOÀN TOÀN THẲNG THẮN
                    prompt = f"""
{personality}

{knowledge_text}
{history_text}

Có người hỏi: "{user_message}"

TRẢ LỜI:
1. TRẢ LỜI THẲNG THẮN, TRỰC TIẾP VÀO VẤN ĐỀ
2. KHÔNG VÒNG VO, nói thẳng có/không/không biết
3. Xưng hô TỰ NHIÊN: "tao-mày" hoặc "tôi-bạn" tùy cảm xúc
4. Có thể chê hoặc khen một cách trực tiếp
5. Ngắn gọn (tối đa 30 chữ)
6. Dùng emoji biểu cảm mạnh mẽ

Ví dụ:
- "Tao có đẳng cấp không? → Đương nhiên là có rồi! 😎"
- "Trời hôm nay thế nào? → Nắng cháy da luôn 🔥"
- "Mày có biết cái này không? → Không, hỏi cái gì lạ vậy? 🙄"
- "Tôi có xinh không? → Có, nhưng đừng tự cao quá 😏"

Trả lời:
"""

                response = model.generate_content(prompt)
                
                if response.text:
                    response_text = response.text.strip()
                    
                    # Giới hạn chữ (30 chữ cho tất cả)
                    words = response_text.split()
                    if len(words) > 30:
                        response_text = ' '.join(words[:30]) + "..."
                    
                    await message.reply(response_text)
                    print(f"🤖 Yoo Ji Min: {response_text}")
                    
                    # Lưu vào lịch sử kênh
                    add_to_history(channel_id, f"{message.author.display_name}: {user_message}")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                else:
                    error_msg = "Hỏi cái gì kỳ vậy? 🙄"
                    await message.reply(error_msg)
                    add_to_history(channel_id, f"{message.author.display_name}: {user_message}")
                    add_to_history(channel_id, f"Yoo Ji Min: {error_msg}")
                    
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            error_msg = "Lỗi rồi, thử lại đi! 💀"
            await message.reply(error_msg)

# Tạo web server đơn giản
app = flask.Flask(__name__)

@app.route('/')
def home():
    return "🤖 Yoo Ji Min Bot is running!"

@app.route('/health')
def health():
    return "OK"

@app.route('/knowledge')
def knowledge():
    return f"Kiến thức đã học: {len(server_knowledge)} mẩu tin"

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
