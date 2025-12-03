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
model = genai.GenerativeModel('gemini-3.0-pro-preview')

# Lưu trữ lịch sử hội thoại theo channel_id - GIẢM XUỐNG 50 TIN
conversation_history = defaultdict(lambda: deque(maxlen=50))

# Lưu trữ tất cả tin nhắn trong server để học hỏi (chỉ đọc)
server_memory = deque(maxlen=200)

# Thông tin thành viên server
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
Bạn là Yoo Ji Min, một thành viên thông minh và hữu ích trong server Discord này.

TÍNH CÁCH:
- LỊCH SỰ, THẲNG THẲN nhưng TỬ TẾ
- Trả lời phù hợp với từng loại câu hỏi:
  + Câu hỏi đơn giản: trả lời ngắn gọn (5-30 chữ)
  + Câu hỏi phức tạp, lý thuyết, thông tin chi tiết: có thể trả lời dài (đến 80 chữ)
- Luôn đi thẳng vào vấn đề, không vòng vo
- Dùng emoji ĐA DẠNG và PHÙ HỢP với nội dung
- Nếu người khác xưng "anh" thì xưng "em" lại
- Với Đức (vyanhduc): luôn ngọt ngào, tinh tế, xưng em gọi anh nhưng KHÔNG dùng câu mở đầu
- Hạn chế xưng hô, nếu cần thì xưng "mình" - "bạn"

EMOJI THEO CHỦ ĐỀ:
🌞🌙⭐️🔥💧🌊🐶🐱🦋🐢🌷🌼🎵🎮📚✏️🎨⚽️🏀🍕🍜🍓☕️🎉🎊❤️💫🌟😊🎯🚀🌈🎭🎪🎸🏆🌍🦄🍀🎁🏖️🎈
💡🔍📊🗂️🏅🎨🧩🔮🌅🏙️🌃🛋️📱💻🖥️⌚️🔦💎⚜️🧠💪👑📈📉🧪🔬⚖️🕰️🌡️🧭🧳🎂🎁🎊🎉🥳✨🎇🎆

LUÔN DÙNG EMOJI PHÙ HỢP VÀ EMOJI KHÔNG TÍNH VÀO GIỚI HẠN CHỮ!
"""

# Hàm tạo ảnh bằng Pollinations AI - CHỈ DÙNG CHO SINH NHẬT
async def generate_birthday_image(name, age, job):
    """Tạo ảnh chúc mừng sinh nhật bằng Pollinations AI"""
    try:
        # Tạo prompt cho ảnh sinh nhật dựa trên thông tin
        prompt = f"""
        Beautiful digital art celebrating birthday for {name} who is {age} years old and works as {job}.
        Birthday cake with candles, colorful balloons, festive decorations, happy birthday theme,
        vibrant colors, detailed illustration, 4K resolution, professional artwork, joyful atmosphere.
        Style: digital painting, vibrant, celebratory.
        """
        
        # Mã hóa prompt
        encoded_prompt = urllib.parse.quote(prompt)
        
        # URL Pollinations AI với Flux model, độ phân giải 1024x1024
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true"
        
        # Tải ảnh
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return image_data
                else:
                    print(f"❌ Lỗi tải ảnh: {response.status}")
                    return None
                    
    except Exception as e:
        print(f"❌ Lỗi tạo ảnh: {e}")
        return None

# Hàm xác định loại tin nhắn
def check_message_type(message_content, message_author):
    content_lower = message_content.lower()
    
    # KIỂM TRA ĐỨC ĐẦU TIÊN
    if (message_author.name.lower() == "vyanhduc" or 
        (message_author.display_name and "đức" in message_author.display_name.lower()) or
        (message_author.display_name and "duc" in message_author.display_name.lower())):
        return "duc"
    
    # Kiểm tra nếu người gửi xưng "anh"
    if " anh " in content_lower or content_lower.startswith("anh ") or content_lower.endswith(" anh"):
        return "brother"
    
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
    for msg in list(history)[-15:]:  # Chỉ hiển thị 15 tin nhắn gần nhất
        history_text += f"{msg}\n"
    return history_text + "\n"

# Hàm lấy thông tin tổng quan về server từ memory
def get_server_context():
    if not server_memory:
        return ""
    
    recent_messages = list(server_memory)[-30:]  # Giảm xuống 30 tin
    
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

# Hàm kiểm tra sinh nhật
async def check_birthdays(client):
    today = datetime.datetime.now()
    today_day = today.day
    today_month = today.month
    
    for username, info in server_members.items():
        if info["birthday"]["day"] == today_day and info["birthday"]["month"] == today_month:
            # Kiểm tra đã chúc mừng trong ngày hôm nay chưa
            last_wish = info.get("last_birthday_wish")
            if last_wish != today.strftime("%Y-%m-%d"):
                # Tìm user trong server
                user = None
                for guild in client.guilds:
                    user = guild.get_member_named(username)
                    if user:
                        break
                
                if user:
                    # Tạo lời chúc mừng sinh nhật
                    age = today.year - info["year"]
                    birthday_prompt = f"""
Hôm nay là sinh nhật của {info['name']} ({username}) - {age} tuổi, nghề nghiệp: {info['job']}.

Hãy viết một lời chúc mừng sinh nhật thật ý nghĩa và chân thành:
- Xưng 'em' gọi 'anh'
- Nhắc đến tuổi mới và nghề nghiệp của họ
- Chúc những điều tốt đẹp trong công việc và cuộc sống
- Dùng nhiều emoji sinh nhật vui vẻ
- Độ dài: khoảng 50-100 chữ
- Thật tâm và ấm áp

Lời chúc của em:
"""
                    response = model.generate_content(birthday_prompt)
                    birthday_message = response.text.strip()
                    
                    # TẠO ẢNH SINH NHẬT
                    image_data = await generate_birthday_image(info['name'], age, info['job'])
                    
                    # Gửi lời chúc đến kênh chung
                    for guild in client.guilds:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                if image_data:
                                    # Tạo file ảnh từ dữ liệu
                                    image_file = discord.File(io.BytesIO(image_data), filename=f"birthday_{info['name']}.png")
                                    await channel.send(
                                        f"🎉 **Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}",
                                        file=image_file
                                    )
                                    print(f"🎂 Đã gửi lời chúc và ảnh sinh nhật tới {info['name']}")
                                else:
                                    await channel.send(f"🎉 **Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}")
                                    print(f"🎂 Đã gửi lời chúc sinh nhật tới {info['name']} (không có ảnh)")
                                break
                        break
                    
                    # Đánh dấu đã chúc mừng trong ngày
                    info["last_birthday_wish"] = today.strftime("%Y-%m-%d")

# Hàm test sinh nhật - VẪN GIỮ ẢNH
async def test_birthday(client, username, channel):
    """Hàm test chúc mừng sinh nhật (dùng cho testing)"""
    if username in server_members:
        info = server_members[username]
        
        # Tạo lời chúc mừng sinh nhật
        age = datetime.datetime.now().year - info["year"]
        birthday_prompt = f"""
Hôm nay là sinh nhật TEST của {info['name']} ({username}) - {age} tuổi, nghề nghiệp: {info['job']}.

Hãy viết một lời chúc mừng sinh nhật thật ý nghĩa và chân thành:
- Xưng 'em' gọi 'anh'
- Nhắc đến tuổi mới và nghề nghiệp của họ
- Chúc những điều tốt đẹp trong công việc và cuộc sống
- Dùng nhiều emoji sinh nhật vui vẻ
- Độ dài: khoảng 50-100 chữ
- Thật tâm và ấm áp

Lời chúc của em:
"""
        response = model.generate_content(birthday_prompt)
        birthday_message = response.text.strip()
        
        # TẠO ẢNH SINH NHẬT
        image_data = await generate_birthday_image(info['name'], age, info['job'])
        
        # Tìm user trong server
        user = None
        for guild in client.guilds:
            user = guild.get_member_named(username)
            if user:
                break
        
        if user:
            if image_data:
                # Gửi kèm ảnh
                image_file = discord.File(io.BytesIO(image_data), filename=f"test_birthday_{info['name']}.png")
                await channel.send(
                    f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}",
                    file=image_file
                )
                print(f"✅ Đã test chúc mừng sinh nhật cho {info['name']} (có ảnh)")
            else:
                await channel.send(f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}")
                print(f"✅ Đã test chúc mừng sinh nhật cho {info['name']} (không có ảnh)")
        else:
            # Nếu không tìm thấy user, vẫn gửi thông báo
            if image_data:
                image_file = discord.File(io.BytesIO(image_data), filename=f"test_birthday_{info['name']}.png")
                await channel.send(
                    f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n**{info['name']}** ({username})\n{birthday_message}",
                    file=image_file
                )
            else:
                await channel.send(f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n**{info['name']}** ({username})\n{birthday_message}")
            print(f"⚠️ Không tìm thấy user {username}, nhưng đã gửi test sinh nhật cho {info['name']}")
    else:
        await channel.send(f"❌ Không tìm thấy thông tin cho username: {username}")

# Hàm hiển thị thông tin thành viên
async def show_member_info(username, channel):
    """Hiển thị thông tin thành viên"""
    if username in server_members:
        info = server_members[username]
        today = datetime.datetime.now()
        age = today.year - info["year"]
        next_birthday = datetime.datetime(today.year, info["birthday"]["month"], info["birthday"]["day"])
        if today > next_birthday:
            next_birthday = datetime.datetime(today.year + 1, info["birthday"]["month"], info["birthday"]["day"])
        
        days_until_birthday = (next_birthday - today).days
        
        response = f"""
**Thông tin về {info['name']}:** 🎯

🎂 **Sinh nhật:** {info['birthday']['day']}/{info['birthday']['month']}/{info['year']}
📅 **Tuổi hiện tại:** {age} tuổi
🕒 **Sinh nhật tiếp theo:** Còn {days_until_birthday} ngày nữa
💼 **Nghề nghiệp:** {info['job']}
👤 **Username:** {username}

"""
        if days_until_birthday == 0:
            response += "🎉 **Hôm nay là sinh nhật!** 🎉"
        elif days_until_birthday < 30:
            response += f"🎁 Sắp đến sinh nhật rồi, chuẩn bị quà đi nào! 🎊"
        
        await channel.send(response)
    else:
        await channel.send(f"❌ Không tìm thấy thông tin cho username: {username}")

# Hàm phân tích ảnh - ĐÃ SỬA CHO ĐỨC
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
3. KHÔNG dùng câu mở đầu như "anh Đức ơi"
4. Đi thẳng vào nội dung phân tích
5. Dùng emoji đa dạng phù hợp nội dung ảnh
6. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "20-30 chữ" }

Phân tích:
"""
        elif message_type == "brother":
            prompt_text = f"""
{personality}

{server_context}
{history_text}

Anh ấy gửi ảnh. {f"Anh ấy hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh CHI TIẾT
2. Xưng 'em' gọi 'anh'
3. Dùng emoji đa dạng phù hợp nội dung ảnh
4. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "15-25 chữ" }

Em trả lời:
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
4. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "15-25 chữ" }

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
    
    # Bắt đầu task kiểm tra sinh nhật mỗi ngày
    client.loop.create_task(birthday_check_loop())

# Vòng lặp kiểm tra sinh nhật mỗi ngày
async def birthday_check_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await check_birthdays(client)
        except Exception as e:
            print(f"❌ Lỗi khi kiểm tra sinh nhật: {e}")
        # Chờ 24 giờ
        await asyncio.sleep(24 * 60 * 60)

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

    # XỬ LÝ LỆNH TRỰC TIẾP
    if message.content.startswith('!test_birthday'):
        parts = message.content.split()
        if len(parts) == 2:
            username = parts[1]
            await test_birthday(client, username, message.channel)
        else:
            await message.channel.send("❌ Cú pháp: `!test_birthday username`")
        return

    if message.content.startswith('!member_info'):
        parts = message.content.split()
        if len(parts) == 2:
            username = parts[1]
            await show_member_info(username, message.channel)
        else:
            await message.channel.send("❌ Cú pháp: `!member_info username`")
        return

    # XỬ LÝ CÂU HỎI VỀ THÔNG TIN THÀNH VIÊN KHI ĐƯỢC TAG
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_message = message.content.replace(f'<@{client.user.id}>', '').strip().lower()
        
        # Kiểm tra các từ khóa về thông tin thành viên
        member_keywords = ['sinh nhật', 'ngày sinh', 'birthday', 'tuổi', 'thông tin', 'info', 'nghề nghiệp', 'công việc']
        member_names = {
            'cường': 'demacianking1',
            'thành': 'thanh0374', 
            'dũng': 'dangialanrangu',
            'dũng còi': 'dangialanrangu',
            'ngọc': 'manted1229',
            'ngọc điếc': 'manted1229',
            'đức': 'vyanhduc',
            'tuấn anh': 'pta.zyud',
            'tuấn': 'pta.zyud'
        }
        
        # Tìm tên thành viên được nhắc đến
        found_member = None
        for name, username in member_names.items():
            if name in user_message:
                found_member = username
                break
        
        # Nếu tìm thấy thành viên và có từ khóa về thông tin
        if found_member and any(keyword in user_message for keyword in member_keywords):
            if found_member in server_members:
                info = server_members[found_member]
                today = datetime.datetime.now()
                age = today.year - info['year']
                next_birthday = datetime.datetime(today.year, info['birthday']['month'], info['birthday']['day'])
                if today > next_birthday:
                    next_birthday = datetime.datetime(today.year + 1, info['birthday']['month'], info['birthday']['day'])
                
                days_until_birthday = (next_birthday - today).days
                
                response = f"""
**Thông tin về {info['name']}:** 🎯

🎂 **Sinh nhật:** {info['birthday']['day']}/{info['birthday']['month']}/{info['year']}
📅 **Tuổi hiện tại:** {age} tuổi
🕒 **Sinh nhật tiếp theo:** Còn {days_until_birthday} ngày nữa
💼 **Nghề nghiệp:** {info['job']}
👤 **Username:** {found_member}

"""
                if days_until_birthday == 0:
                    response += "🎉 **Hôm nay là sinh nhật!** 🎉"
                elif days_until_birthday < 30:
                    response += f"🎁 Sắp đến sinh nhật rồi, chuẩn bị quà đi nào! 🎊"
                
                await message.channel.send(response)
                return

    # Chỉ trả lời khi được tag hoặc DM (cho các tin nhắn thông thường)
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
                    elif message_type == "brother":
                        response_text = "Dạ anh cần em giúp gì không ạ? 😊"
                    else:
                        response_text = "Mình có thể giúp gì cho bạn? 😊"
                    
                    await message.reply(response_text)
                    add_to_history(channel_id, f"{message.author.display_name}: (tag)")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                    return
                
                message_type = check_message_type(user_message, message.author)
                print(f"👤 {message.author.name}: {user_message} | Loại: {message_type} | Độ dài: {question_type}")

                # Prompt cho từng loại tin nhắn - ĐÃ SỬA CHO ĐỨC
                if message_type == "duc":
                    length_guide = {
                        "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                        "short": "trả lời NGẮN GỌN (10-20 chữ)",
                        "normal": "trả lời VỪA PHẢI (20-30 chữ)"
                    }
                    
                    prompt = f"""
{personality}

{server_context}
{history_text}

Anh Đức hỏi: "{user_message}"

TRẢ LỜI:
1. {length_guide[question_type]}
2. Xưng 'em' gọi 'anh' một cách tự nhiên
3. KHÔNG dùng câu mở đầu như "anh Đức yêu quý", "thưa anh Đức",...
4. Đi thẳng vào nội dung trả lời, không đề cập đến tên trong câu trả lời
5. Thể hiện sự quan tâm một cách tinh tế
6. Dùng emoji ĐA DẠNG phù hợp chủ đề
7. Lịch sự, tinh tế, đi thẳng vào vấn đề
8. KHÔNG vòng vo, KHÔNG lan man

Em trả lời:
"""
                elif message_type == "brother":
                    length_guide = {
                        "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                        "short": "trả lời NGẮN GỌN (10-20 chữ)",
                        "normal": "trả lời VỪA PHẢI (15-25 chữ)"
                    }
                    
                    prompt = f"""
{personality}

{server_context}
{history_text}

Anh ấy hỏi: "{user_message}"

TRẢ LỜI:
1. {length_guide[question_type]}
2. Xưng 'em' gọi 'anh'
3. Dùng emoji ĐA DẠNG phù hợp chủ đề
4. Lịch sự, thẳng thắn, đi thẳng vào vấn đề
5. KHÔNG vòng vo, KHÔNG lan man

Em trả lời:
"""
                else:
                    length_guide = {
                        "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                        "short": "trả lời NGẮN GỌN (5-15 chữ)",
                        "normal": "trả lời VỪA PHẢI (15-25 chữ)"
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

Trả lời:
"""

                response = model.generate_content(prompt)
                
                if response.text:
                    response_text = response.text.strip()
                    
                    # Giới hạn chữ linh hoạt theo loại câu hỏi - ĐÃ GIẢM 5 CHỮ
                    words = response_text.split()
                    if question_type == "long" and len(words) > 80:
                        response_text = ' '.join(words[:80]) + "..."
                    elif question_type == "short" and len(words) > 15:
                        response_text = ' '.join(words[:15])
                    elif question_type == "normal" and len(words) > 25:
                        response_text = ' '.join(words[:25])
                    
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
