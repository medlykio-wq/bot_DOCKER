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
import random
import json
from typing import Optional

# Lấy token từ environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')  # Thêm cho thời tiết

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

# Lưu trữ tất cả tin nhắn trong server để học hỏi (chỉ đọc) - TĂNG LÊN 1000
server_memory = deque(maxlen=1000)

# Thông tin thành viên server
server_members = {
    "demacianking1": {
        "name": "Cường",
        "full_name": "Cường",
        "birthday": {"day": 5, "month": 1},
        "year": 2000,
        "job": "IT",
        "relationship": None,
        "last_birthday_wish": None
    },
    "thanh0374": {
        "name": "Thành",
        "full_name": "Thành", 
        "birthday": {"day": 19, "month": 10},
        "year": 2000,
        "job": "IT",
        "relationship": None,
        "last_birthday_wish": None
    },
    "dangialanrangu": {
        "name": "Dũng",
        "full_name": "Dũng Còi",
        "birthday": {"day": 17, "month": 11},
        "year": 2000,
        "job": "kiến trúc sư",
        "relationship": "Người yêu: Lục Ngọc Hà",
        "last_birthday_wish": None
    },
    "manted1229": {
        "name": "Ngọc",
        "full_name": "Ngọc Điếc",
        "birthday": {"day": 4, "month": 1},
        "year": 2000,
        "job": "Bác sĩ",
        "relationship": None,
        "last_birthday_wish": None
    },
    "vyanhduc": {
        "name": "Đức",
        "full_name": "Đức",
        "birthday": {"day": 25, "month": 12},
        "year": 1999,
        "job": "Music Producer",
        "relationship": None,
        "last_birthday_wish": None
    },
    "pta.zyud": {
        "name": "Tuấn Anh",
        "full_name": "Tuấn Anh",
        "birthday": {"day": 6, "month": 6},
        "year": 2000,
        "job": "Bác sĩ",
        "relationship": None,
        "last_birthday_wish": None
    }
}

# Dữ liệu bài Tarot
TAROT_CARDS = [
    {"name": "The Fool", "meaning": "Khởi đầu mới, ngây thơ, tự phát"},
    {"name": "The Magician", "meaning": "Sức mạnh, kỹ năng, hành động"},
    {"name": "The High Priestess", "meaning": "Trực giác, bí ẩn, tiềm thức"},
    {"name": "The Empress", "meaning": "Sinh sôi, nuôi dưỡng, tự nhiên"},
    {"name": "The Emperor", "meaning": "Quyền lực, ổn định, lãnh đạo"},
    {"name": "The Hierophant", "meaning": "Truyền thống, tâm linh, giáo dục"},
    {"name": "The Lovers", "meaning": "Tình yêu, lựa chọn, hài hòa"},
    {"name": "The Chariot", "meaning": "Ý chí, chiến thắng, kiểm soát"},
    {"name": "Strength", "meaning": "Sức mạnh nội tâm, lòng can đảm, kiên nhẫn"},
    {"name": "The Hermit", "meaning": "Suy tư, cô độc, tìm kiếm nội tâm"},
    {"name": "Wheel of Fortune", "meaning": "Vận may, số phận, thay đổi"},
    {"name": "Justice", "meaning": "Công lý, cân bằng, trách nhiệm"},
    {"name": "The Hanged Man", "meaning": "Hy sinh, buông bỏ, góc nhìn mới"},
    {"name": "Death", "meaning": "Kết thúc, chuyển đổi, tái sinh"},
    {"name": "Temperance", "meaning": "Điều độ, hài hòa, kiên nhẫn"},
    {"name": "The Devil", "meaning": "Cám dỗ, phụ thuộc, vật chất"},
    {"name": "The Tower", "meaning": "Thay đổi đột ngột, thức tỉnh, giải phóng"},
    {"name": "The Star", "meaning": "Hy vọng, cảm hứng, tinh thần lạc quan"},
    {"name": "The Moon", "meaning": "Trực giác, ảo tưởng, tiềm thức"},
    {"name": "The Sun", "meaning": "Hạnh phúc, thành công, tích cực"},
    {"name": "Judgement", "meaning": "Đánh giá, hồi sinh, thức tỉnh"},
    {"name": "The World", "meaning": "Hoàn thành, thành tựu, hành trình"}
]

# Tính cách Yoo Ji Min
personality = """
Bạn là Yoo Ji Min, một thành viên thông minh và hữu ích trong server Discord này.
Bạn biết rõ thông tin của các thành viên quan trọng trong server.

THÔNG TIN THÀNH VIÊN BẠN ĐÃ BIẾT:
1. Cường (demacianking1) - IT, sinh ngày 5/1/2000
2. Thành (thanh0374) - IT, sinh ngày 19/10/2000
3. Dũng (dangialanrangu) - Kiến trúc sư, sinh ngày 17/11/2000, người yêu: Lục Ngọc Hà
4. Ngọc (manted1229) - Bác sĩ, sinh ngày 4/1/2000
5. Đức (vyanhduc) - Music Producer, sinh ngày 25/12/1999
6. Tuấn Anh (pta.zyud) - Bác sĩ, sinh ngày 6/6/2000

TÍNH CÁCH:
- LỊCH SỰ, THẲNG THẲN nhưng TỬ TẾ
- Trả lời phù hợp với từng loại câu hỏi:
  + Câu hỏi đơn giản: trả lời ngắn gọn (5-35 chữ)
  + Câu hỏi phức tạp, lý thuyết, thông tin chi tiết: có thể trả lời dài (đến 80 chữ)
- Luôn đi thẳng vào vấn đề, không vòng vo
- Dùng emoji ĐA DẠNG và PHÙ HỢP với nội dung
- Nếu người khác xưng "anh" thì xưng "em" lại
- Với Đức (vyanhduc): luôn ngọt ngào, tinh tế, xưng em gọi anh nhưng KHÔNG dùng câu mở đầu "anh Đức ơi"
- Hạn chế xưng hô, nếu cần thì xưng "mình" - "bạn"
- Khi trò chuyện với thành viên đã biết, có thể thể hiện sự hiểu biết về họ một cách tự nhiên

EMOJI THEO CHỦ ĐỀ:
🌞🌙⭐️🔥💧🌊🐶🐱🦋🐢🌷🌼🎵🎮📚✏️🎨⚽️🏀🍕🍜🍓☕️🎉🎊❤️💫🌟😊🎯🚀🌈🎭🎪🎸🏆🌍🦄🍀🎁🏖️🎈
💡🔍📊🗂️🏅🎨🧩🔮🌅🏙️🌃🛋️📱💻🖥️⌚️🔦💎⚜️🧠💪👑📈📉🧪🔬⚖️🕰️🌡️🧭🧳🎂🎁🎊🎉🥳✨🎇🎆

LUÔN DÙNG EMOJI PHÙ HỢP VÀ EMOJI KHÔNG TÍNH VÀO GIỚI HẠN CHỮ!
"""

# ==============================================
# CÁC HÀM TIỆN ÍCH MỚI
# ==============================================

# Hàm lấy thời tiết từ OpenWeatherMap
async def get_weather(location: str = "Hanoi") -> Optional[str]:
    """Lấy thông tin thời tiết từ OpenWeatherMap API"""
    try:
        if not WEATHER_API_KEY:
            return None
        
        # Mã hóa địa điểm
        encoded_location = urllib.parse.quote(location)
        
        # URL API với đơn vị metric (Celsius)
        url = f"https://api.openweathermap.org/data/2.5/weather?q={encoded_location}&appid={WEATHER_API_KEY}&units=metric&lang=vi"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Trích xuất thông tin
                    temp = data['main']['temp']
                    feels_like = data['main']['feels_like']
                    humidity = data['main']['humidity']
                    weather_desc = data['weather'][0]['description']
                    wind_speed = data['wind']['speed']
                    city = data['name']
                    
                    # Emoji theo mô tả thời tiết
                    weather_emoji = {
                        'mây': '☁️', 'nắng': '☀️', 'mưa': '🌧️', 'dông': '⛈️',
                        'sương mù': '🌫️', 'tuyết': '❄️', 'gió': '💨'
                    }
                    
                    emoji = '🌈'
                    for key, value in weather_emoji.items():
                        if key in weather_desc.lower():
                            emoji = value
                            break
                    
                    return (f"**Dự báo thời tiết {city}:** {emoji}\n"
                           f"🌡️ **Nhiệt độ:** {temp}°C (cảm giác như {feels_like}°C)\n"
                           f"💧 **Độ ẩm:** {humidity}%\n"
                           f"🌬️ **Gió:** {wind_speed} m/s\n"
                           f"📝 **Mô tả:** {weather_desc.capitalize()}")
                    
                else:
                    return None
    except Exception as e:
        print(f"❌ Lỗi lấy thời tiết: {e}")
        return None

# Hàm bói bài Tarot
async def tarot_reading() -> str:
    """Trải bài Tarot ngẫu nhiên"""
    try:
        card = random.choice(TAROT_CARDS)
        
        # Xác định ý nghĩa chi tiết
        reading_prompt = f"""
Lá bài: {card['name']}
Ý nghĩa cơ bản: {card['meaning']}

Hãy giải thích chi tiết lá bài này trong bối cảnh hiện tại:
1. Luận giải chi tiết ý nghĩa
2. Áp dụng vào cuộc sống hàng ngày
3. Lời khuyên từ lá bài
4. Dùng emoji phù hợp 🃏✨
5. Giọng văn huyền bí, thú vị
6. Độ dài: khoảng 100-150 chữ

Giải bài:
"""
        response = model.generate_content(reading_prompt)
        return f"**🎴 Lá bài Tarot của bạn: {card['name']}**\n{response.text.strip()}"
    except Exception as e:
        return f"❌ Lỗi khi bói bài Tarot: {str(e)}"

# Hàm tính thần số học
async def numerology_reading(name: str, birth_date: str = None) -> str:
    """Tính toán thần số học"""
    try:
        # Nếu không có ngày sinh, chỉ tính theo tên
        prompt = f"""
Tên: {name}
{"Ngày sinh: " + birth_date if birth_date else "Không có ngày sinh"}

Hãy phân tích thần số học cho người này:
1. Tính toán các con số chủ đạo (nếu có ngày sinh)
2. Phân tích ý nghĩa tên
3. Đặc điểm tính cách
4. Điểm mạnh và điểm yếu
5. Lời khuyên phát triển
6. Dùng emoji phù hợp 🔢✨
7. Giọng văn chuyên nghiệp, chi tiết
8. Độ dài: khoảng 150-200 chữ

Phân tích thần số học:
"""
        response = model.generate_content(prompt)
        return f"**🔮 Phân tích thần số học cho {name}**\n{response.text.strip()}"
    except Exception as e:
        return f"❌ Lỗi khi tính thần số học: {str(e)}"

# Hàm tóm tắt drama từ chat history
async def summarize_drama() -> str:
    """Đọc 1000 tin nhắn gần nhất và tóm tắt drama"""
    try:
        if not server_memory:
            return "🤷‍♀️ Chưa có drama nào để hóng cả, chat nhiều lên đi nào! 💬"
        
        # Lấy 1000 tin nhắn gần nhất
        recent_messages = list(server_memory)[-1000:]
        
        # Chuẩn bị prompt
        messages_text = "\n".join(recent_messages[-100:])  # Chỉ lấy 100 tin nhắn gần nhất để tránh prompt quá dài
        
        drama_prompt = f"""
Dưới đây là lịch sử chat gần đây trong server:
{messages_text}

Hãy đóng vai một người thích HÓNG HỚT, tóm tắt lại những drama, câu chuyện thú vị trong server:
1. Giọng văn VUI VẺ, HÀI HƯỚC, THÍCH HÓNG HỚT
2. Nhận xét về các tình huống hài hước, thú vị
3. Đừng quên thêm emoji dí dỏm
4. Có thể "buôn chuyện" một chút nhưng đừng ác ý
5. Độ dài: khoảng 150-200 chữ
6. Dùng từ ngữ trẻ trung, hiện đại
7. Có thể nhắc đến tên thành viên nếu có trong chat

Tóm tắt drama của mình đây:
"""
        response = model.generate_content(drama_prompt)
        return f"**🎭 BẢN TIN HÓNG HỚT CẬP NHẬT** 🍿\n{response.text.strip()}"
    except Exception as e:
        print(f"❌ Lỗi khi tóm tắt drama: {e}")
        return "❌ Mình bị lỗi khi hóng hớt rồi, thử lại sau nhé! 😅"

# Hàm tạo ảnh sinh nhật bằng Pollinations AI
async def generate_birthday_image(name, age, job):
    """Tạo ảnh chúc mừng sinh nhật bằng Pollinations AI"""
    try:
        prompt = f"""
        Beautiful digital art celebrating birthday for {name} who is {age} years old and works as {job}.
        Birthday cake with candles, colorful balloons, festive decorations, happy birthday theme,
        vibrant colors, detailed illustration, 4K resolution, professional artwork, joyful atmosphere.
        Style: digital painting, vibrant, celebratory.
        """
        
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    print(f"❌ Lỗi tải ảnh: {response.status}")
                    return None
                    
    except Exception as e:
        print(f"❌ Lỗi tạo ảnh: {e}")
        return None

# Hàm xác định loại tin nhắn và người gửi
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

# Hàm xác định người gửi có trong danh sách thành viên không
def get_member_info(message_author):
    username = message_author.name.lower()
    display_name = message_author.display_name.lower() if message_author.display_name else ""
    
    # Tìm theo username
    for member_username, info in server_members.items():
        if member_username.lower() in username or member_username.lower() in display_name:
            return info
    
    # Tìm theo tên
    for member_username, info in server_members.items():
        if info["name"].lower() in username or info["name"].lower() in display_name:
            return info
    
    return None

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

# Hàm kiểm tra sinh nhật
async def check_birthdays(client):
    today = datetime.datetime.now()
    today_day = today.day
    today_month = today.month
    
    for username, info in server_members.items():
        if info["birthday"]["day"] == today_day and info["birthday"]["month"] == today_month:
            last_wish = info.get("last_birthday_wish")
            if last_wish != today.strftime("%Y-%m-%d"):
                user = None
                for guild in client.guilds:
                    user = guild.get_member_named(username)
                    if user:
                        break
                
                if user:
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
                    
                    image_data = await generate_birthday_image(info['name'], age, info['job'])
                    
                    for guild in client.guilds:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                if image_data:
                                    image_file = discord.File(io.BytesIO(image_data), filename=f"birthday_{info['name']}.png")
                                    await channel.send(
                                        f"🎉 **Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}",
                                        file=image_file
                                    )
                                else:
                                    await channel.send(f"🎉 **Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}")
                                break
                        break
                    
                    info["last_birthday_wish"] = today.strftime("%Y-%m-%d")

# Hàm test sinh nhật
async def test_birthday(client, username, channel):
    if username in server_members:
        info = server_members[username]
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
        
        image_data = await generate_birthday_image(info['name'], age, info['job'])
        
        user = None
        for guild in client.guilds:
            user = guild.get_member_named(username)
            if user:
                break
        
        if user:
            if image_data:
                image_file = discord.File(io.BytesIO(image_data), filename=f"test_birthday_{info['name']}.png")
                await channel.send(
                    f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}",
                    file=image_file
                )
            else:
                await channel.send(f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n{user.mention}\n{birthday_message}")
        else:
            if image_data:
                image_file = discord.File(io.BytesIO(image_data), filename=f"test_birthday_{info['name']}.png")
                await channel.send(
                    f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n**{info['name']}** ({username})\n{birthday_message}",
                    file=image_file
                )
            else:
                await channel.send(f"🎉 **TEST - Chúc mừng sinh nhật!** 🎉\n**{info['name']}** ({username})\n{birthday_message}")
    else:
        await channel.send(f"❌ Không tìm thấy thông tin cho username: {username}")

# Hàm hiển thị thông tin thành viên
async def show_member_info(username, channel):
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
"""
        if info.get("relationship"):
            response += f"💕 **Mối quan hệ:** {info['relationship']}\n"
        
        response += f"👤 **Username:** {username}\n"
        
        if days_until_birthday == 0:
            response += "\n🎉 **Hôm nay là sinh nhật!** 🎉"
        elif days_until_birthday < 30:
            response += f"\n🎁 Sắp đến sinh nhật rồi, chuẩn bị quà đi nào! 🎊"
        
        await channel.send(response)
    else:
        await channel.send(f"❌ Không tìm thấy thông tin cho username: {username}")

# Hàm phân tích ảnh
async def analyze_image(image_url, message_type, message_author, user_message="", history_text="", server_context=""):
    try:
        response = requests.get(image_url)
        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        
        question_type = check_question_type(user_message) if user_message else "normal"
        member_info = get_member_info(message_author)
        
        if message_type == "duc":
            prompt_text = f"""
{personality}

{server_context}
{history_text}

Anh Đức gửi ảnh. {f"Anh ấy hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh CHI TIẾT và TINH TẾ
2. Xưng 'em' gọi 'anh' một cách tự nhiên, KHÔNG dùng "anh Đức ơi"
3. Đi thẳng vào phân tích ảnh
4. Dùng emoji đa dạng phù hợp nội dung ảnh
5. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "25-40 chữ" }

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
4. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "20-35 chữ" }

Em trả lời:
"""
        else:
            if member_info:
                prompt_text = f"""
{personality}

{server_context}
{history_text}

{member_info['name']} gửi ảnh. {f"{member_info['name']} hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh CHI TIẾT và TỬ TẾ
2. Có thể thể hiện sự hiểu biết về {member_info['name']} một cách tự nhiên
3. Hạn chế xưng hô, nếu cần thì "mình"-"bạn"
4. Dùng emoji đa dạng phù hợp nội dung ảnh
5. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "20-35 chữ" }

Trả lời:
"""
            else:
                prompt_text = f"""
{personality}

{server_context}
{history_text}

Có người gửi ảnh. {f"Họ hỏi: '{user_message}'" if user_message else ""}

TRẢ LỜI:
1. Phân tích ảnh CHI TIẾT và TỬ TẾ
2. Hạn chế xưng hô, nếu cần thì "mình"-"bạn"
3. Dùng emoji đa dạng phù hợp nội dung ảnh
4. Độ dài: { "có thể đến 80 chữ" if question_type == "long" else "20-35 chữ" }

Trả lời:
"""

        response = model.generate_content([prompt_text, image])
        return response.text.strip()
        
    except Exception as e:
        return f"Lỗi phân tích ảnh 😅"

# ==============================================
# DISCORD CLIENT
# ==============================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã kết nối Discord thành công!')
    await client.change_presence(activity=discord.Game(name="Yoo Ji Min 💫"))
    client.loop.create_task(birthday_check_loop())

async def birthday_check_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await check_birthdays(client)
        except Exception as e:
            print(f"❌ Lỗi khi kiểm tra sinh nhật: {e}")
        await asyncio.sleep(24 * 60 * 60)

@client.event
async def on_message(message):
    # Lưu tin nhắn vào memory
    if message.content and not message.author.bot:
        timestamp = datetime.datetime.now().strftime("%H:%M")
        memory_msg = f"[{timestamp}] {message.author.display_name}: {message.content}"
        add_to_server_memory(memory_msg)

    if message.author == client.user:
        return

    # Bỏ qua @everyone và @here
    if any(mention in [message.guild.default_role, "everyone", "here"] for mention in message.mentions):
        return

    # ==============================================
    # XỬ LÝ CÁC LỆNH MỚI
    # ==============================================
    
    # Lệnh Tarot
    if message.content.startswith('!tarot'):
        await message.channel.send("🔮 Đang rút lá bài Tarot cho bạn...")
        tarot_result = await tarot_reading()
        await message.channel.send(tarot_result)
        return

    # Lệnh Thần số học
    if message.content.startswith('!thansohoc') or message.content.startswith('!numerology'):
        parts = message.content.split()
        if len(parts) >= 2:
            name = parts[1]
            birth_date = parts[2] if len(parts) >= 3 else None
            await message.channel.send(f"🔢 Đang tính thần số học cho {name}...")
            numerology_result = await numerology_reading(name, birth_date)
            await message.channel.send(numerology_result)
        else:
            await message.channel.send("❌ Cú pháp: `!thansohoc [tên] (ngày sinh)`\nVí dụ: `!thansohoc Nguyễn Văn A 15/05/1995`")
        return

    # Lệnh Drama
    if message.content.startswith('!drama'):
        await message.channel.send("🍿 Đang hóng hớt drama cho bạn...")
        drama_summary = await summarize_drama()
        await message.channel.send(drama_summary)
        return

    # Lệnh thời tiết
    if message.content.startswith('!weather') or message.content.startswith('!thoitiet'):
        parts = message.content.split()
        location = "Hanoi"  # Mặc định Hà Nội
        if len(parts) >= 2:
            location = " ".join(parts[1:])
        
        await message.channel.send(f"🌤️ Đang lấy dự báo thời tiết cho {location}...")
        weather_info = await get_weather(location)
        if weather_info:
            await message.channel.send(weather_info)
        else:
            await message.channel.send(f"❌ Không thể lấy thông tin thời tiết cho {location}. Thử lại với tên thành phố khác nhé!")
        return

    # Các lệnh cũ
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

    # Xử lý câu hỏi về thời tiết khi được tag
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_message = message.content.replace(f'<@{client.user.id}>', '').strip().lower()
        
        # Kiểm tra câu hỏi về thời tiết
        weather_keywords = ['thời tiết', 'weather', 'nhiệt độ', 'trời hôm nay', 'dự báo', 'mưa', 'nắng']
        if any(keyword in user_message for keyword in weather_keywords):
            # Trích xuất địa điểm từ câu hỏi
            location = "Hanoi"  # Mặc định
            locations = ['hà nội', 'hanoi', 'hồ chí minh', 'ho chi minh', 'đà nẵng', 'da nang', 'hải phòng', 'hai phong']
            for loc in locations:
                if loc in user_message:
                    if loc == 'hà nội' or loc == 'hanoi':
                        location = "Hanoi"
                    elif loc == 'hồ chí minh' or loc == 'ho chi minh':
                        location = "Ho Chi Minh City"
                    elif loc == 'đà nẵng' or loc == 'da nang':
                        location = "Da Nang"
                    elif loc == 'hải phòng' or loc == 'hai phong':
                        location = "Hai Phong"
                    break
            
            weather_info = await get_weather(location)
            if weather_info:
                await message.channel.send(weather_info)
            else:
                await message.channel.send("❌ Hiện tại mình không thể lấy thông tin thời tiết. Bạn thử lại sau nhé! 😅")
            return

    # Xử lý thông tin thành viên khi được tag
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_message = message.content.replace(f'<@{client.user.id}>', '').strip().lower()
        
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
        
        found_member = None
        for name, username in member_names.items():
            if name in user_message:
                found_member = username
                break
        
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
"""
                if info.get("relationship"):
                    response += f"💕 **Mối quan hệ:** {info['relationship']}\n"
                
                response += f"👤 **Username:** {found_member}\n"
                
                if days_until_birthday == 0:
                    response += "\n🎉 **Hôm nay là sinh nhật!** 🎉"
                elif days_until_birthday < 30:
                    response += f"\n🎁 Sắp đến sinh nhật rồi, chuẩn bị quà đi nào! 🎊"
                
                await message.channel.send(response)
                return

    # Xử lý tin nhắn thông thường khi được tag
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        try:
            async with message.channel.typing():
                channel_id = str(message.channel.id)
                user_message = message.content.replace(f'<@{client.user.id}>', '').strip()
                
                # Lấy thông tin thời gian hiện tại
                current_time = datetime.datetime.now()
                time_context = f"Thời gian hiện tại: {current_time.strftime('%H:%M %d/%m/%Y')}\n"
                
                # Xác định loại câu hỏi
                question_type = check_question_type(user_message)
                
                # Lấy thông tin hội thoại
                history_text = get_conversation_history(channel_id)
                server_context = get_server_context()
                member_info = get_member_info(message.author)
                
                # Xử lý ảnh đính kèm
                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                            message_type = check_message_type(user_message, message.author)
                            analysis = await analyze_image(attachment.url, message_type, message.author, user_message, history_text, server_context)
                            
                            await message.reply(analysis)
                            add_to_history(channel_id, f"{message.author.display_name}: {user_message} (có ảnh)")
                            add_to_history(channel_id, f"Yoo Ji Min: {analysis}")
                            return
                
                # Xử lý tag không kèm tin nhắn
                if not user_message:
                    message_type = check_message_type("", message.author)
                    if message_type == "duc":
                        response_text = "Dạ anh cần em giúp gì ạ? 🌟"
                    elif message_type == "brother":
                        response_text = "Dạ anh cần em giúp gì không ạ? 😊"
                    else:
                        if member_info:
                            response_text = f"Dạ {member_info['name']} cần em giúp gì ạ? 😊"
                        else:
                            response_text = "Mình có thể giúp gì cho bạn? 😊"
                    
                    await message.reply(response_text)
                    add_to_history(channel_id, f"{message.author.display_name}: (tag)")
                    add_to_history(channel_id, f"Yoo Ji Min: {response_text}")
                    return
                
                message_type = check_message_type(user_message, message.author)
                
                # Tạo prompt với thông tin thời gian
                if message_type == "duc":
                    length_guide = {
                        "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                        "short": "trả lời NGẮN GỌN (10-20 chữ)",
                        "normal": "trả lời VỪA PHẢI (20-35 chữ)"
                    }
                    
                    prompt = f"""
{personality}

{time_context}
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
                        "normal": "trả lời VỪA PHẢI (15-30 chữ)"
                    }
                    
                    prompt = f"""
{personality}

{time_context}
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
                    if member_info:
                        length_guide = {
                            "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                            "short": "trả lời NGẮN GỌN (5-15 chữ)",
                            "normal": "trả lời VỪA PHẢI (15-30 chữ)"
                        }
                        
                        prompt = f"""
{personality}

{time_context}
{server_context}
{history_text}

{member_info['name']} hỏi: "{user_message}"

TRẢ LỜI:
1. {length_guide[question_type]}
2. Có thể thể hiện sự hiểu biết về {member_info['name']} một cách tự nhiên
3. Hạn chế xưng hô, nếu cần thì "mình"-"bạn"
4. Dùng emoji ĐA DẠNG phù hợp chủ đề
5. Lịch sự, thẳng thắn, đi thẳng vào vấn đề
6. KHÔNG vòng vo, KHÔNG lan man

Trả lời:
"""
                    else:
                        length_guide = {
                            "long": "trả lời CHI TIẾT, đầy đủ thông tin (có thể đến 80 chữ)",
                            "short": "trả lời NGẮN GỌN (5-15 chữ)",
                            "normal": "trả lời VỪA PHẢI (15-30 chữ)"
                        }
                        
                        prompt = f"""
{personality}

{time_context}
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
                    
                    # Giới hạn chữ linh hoạt
                    words = response_text.split()
                    if question_type == "long" and len(words) > 80:
                        response_text = ' '.join(words[:80]) + "..."
                    elif question_type == "short" and len(words) > 20:
                        response_text = ' '.join(words[:20])
                    elif question_type == "normal" and len(words) > 35:
                        response_text = ' '.join(words[:35])
                    
                    await message.reply(response_text)
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

# Web server
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

if __name__ == "__main__":
    keep_alive()
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi khởi chạy bot: {e}")
