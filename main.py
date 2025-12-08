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
from datetime import timedelta
import pytz
from dateutil import parser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Lấy token từ environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')  # OpenWeatherMap
WEATHERAPI_KEY = os.getenv('WEATHERAPI_KEY')    # WeatherAPI.com (dự phòng)

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

# Cấu hình múi giờ Việt Nam
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Scheduler cho các tác vụ định kỳ
scheduler = AsyncIOScheduler(timezone=VIETNAM_TZ)

# Lưu trữ lịch sử hội thoại theo channel_id
conversation_history = defaultdict(lambda: deque(maxlen=200))

# Lưu trữ tất cả tin nhắn trong server để học hỏi (chỉ đọc) - GIẢM XUỐNG 500
server_memory = deque(maxlen=500)

# Thông tin thành viên server - CẬP NHẬT: thêm trường countdown_sent
server_members = {
    "demacianking1": {
        "name": "Cường",
        "full_name": "Cường",
        "birthday": {"day": 5, "month": 1},
        "year": 2000,
        "job": "IT",
        "relationship": None,
        "last_birthday_wish": None,
        "countdown_sent": {}  # Lưu các mốc đếm ngược đã gửi: {"5": "2024-12-20", "4": "2024-12-21", ...}
    },
    "thanh0374": {
        "name": "Thành",
        "full_name": "Thành", 
        "birthday": {"day": 19, "month": 10},
        "year": 2000,
        "job": "IT",
        "relationship": None,
        "last_birthday_wish": None,
        "countdown_sent": {}
    },
    "dangialanrangu": {
        "name": "Dũng",
        "full_name": "Dũng Còi",
        "birthday": {"day": 17, "month": 11},
        "year": 2000,
        "job": "kiến trúc sư",
        "relationship": "Người yêu: Lục Ngọc Hà",
        "last_birthday_wish": None,
        "countdown_sent": {}
    },
    "manted1229": {
        "name": "Ngọc",
        "full_name": "Ngọc Điếc",
        "birthday": {"day": 4, "month": 1},
        "year": 2000,
        "job": "Bác sĩ",
        "relationship": None,
        "last_birthday_wish": None,
        "countdown_sent": {}
    },
    "vyanhduc": {
        "name": "Đức",
        "full_name": "Đức",
        "birthday": {"day": 25, "month": 12},
        "year": 1999,
        "job": "Music Producer",
        "relationship": None,
        "last_birthday_wish": None,
        "countdown_sent": {}
    },
    "pta.zyud": {
        "name": "Tuấn Anh",
        "full_name": "Tuấn Anh",
        "birthday": {"day": 6, "month": 6},
        "year": 2000,
        "job": "Bác sĩ",
        "relationship": None,
        "last_birthday_wish": None,
        "countdown_sent": {}
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
# API THỜI GIAN THỰC
# ==============================================

async def get_real_time():
    """Lấy thời gian thực từ API đáng tin cậy"""
    try:
        # Thử WorldTimeAPI trước
        async with aiohttp.ClientSession() as session:
            async with session.get('https://worldtimeapi.org/api/timezone/Asia/Ho_Chi_Minh', timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    datetime_str = data['datetime']
                    return parser.isoparse(datetime_str).astimezone(VIETNAM_TZ)
    except:
        pass
    
    try:
        # Fallback: TimeAPI
        async with aiohttp.ClientSession() as session:
            async with session.get('http://worldtimeapi.org/api/ip', timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    datetime_str = data['datetime']
                    return parser.isoparse(datetime_str).astimezone(VIETNAM_TZ)
    except:
        pass
    
    # Nếu cả hai API đều fail, dùng thời gian server với múi giờ Việt Nam
    return datetime.datetime.now(VIETNAM_TZ)

# ==============================================
# HỆ THỐNG SINH NHẬT NÂNG CAO
# ==============================================

def calculate_days_until_birthday(birthday_day, birthday_month, current_date=None):
    """Tính số ngày còn lại đến sinh nhật"""
    if current_date is None:
        current_date = datetime.datetime.now(VIETNAM_TZ).date()
    
    current_year = current_date.year
    birthday_this_year = datetime.date(current_year, birthday_month, birthday_day)
    
    if birthday_this_year < current_date:
        birthday_next_year = datetime.date(current_year + 1, birthday_month, birthday_day)
        days_left = (birthday_next_year - current_date).days
        next_birthday = birthday_next_year
    else:
        days_left = (birthday_this_year - current_date).days
        next_birthday = birthday_this_year
    
    return days_left, next_birthday

async def check_birthday_countdown():
    """Kiểm tra và gửi thông báo đếm ngược sinh nhật"""
    try:
        # Lấy thời gian thực
        current_time = await get_real_time()
        current_date = current_time.date()
        current_hour = current_time.hour
        
        print(f"🕐 Đang kiểm tra sinh nhật lúc {current_time.strftime('%H:%M %d/%m/%Y')}...")
        
        for username, info in server_members.items():
            birthday_day = info["birthday"]["day"]
            birthday_month = info["birthday"]["month"]
            
            days_left, next_birthday = calculate_days_until_birthday(birthday_day, birthday_month, current_date)
            
            # Chỉ kiểm tra vào lúc 0h sáng (12h đêm)
            if current_hour == 0:
                # Kiểm tra đếm ngược 5,4,3,2,1 ngày
                if 1 <= days_left <= 5:
                    countdown_key = str(days_left)
                    
                    # Kiểm tra xem đã gửi thông báo cho mốc này chưa
                    if info["countdown_sent"].get(countdown_key) != current_date.strftime("%Y-%m-%d"):
                        await send_countdown_notification(username, info, days_left, next_birthday)
                        info["countdown_sent"][countdown_key] = current_date.strftime("%Y-%m-%d")
                        print(f"✅ Đã gửi đếm ngược {days_left} ngày cho {info['name']}")
                
                # Kiểm tra sinh nhật chính thức (0 ngày)
                elif days_left == 0:
                    # Kiểm tra xem đã chúc mừng chưa
                    if info.get("last_birthday_wish") != current_date.strftime("%Y-%m-%d"):
                        await send_birthday_wish(username, info, current_date.year - info["year"])
                        info["last_birthday_wish"] = current_date.strftime("%Y-%m-%d")
                        
                        # Xóa tất cả countdown đã gửi để chuẩn bị cho năm sau
                        info["countdown_sent"] = {}
                        print(f"🎉 Đã gửi chúc mừng sinh nhật cho {info['name']}")
            
            # Debug: In thông tin để kiểm tra
            if days_left <= 10:
                print(f"📅 {info['name']}: Còn {days_left} ngày đến sinh nhật ({birthday_day}/{birthday_month})")
    
    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra sinh nhật: {e}")

async def send_countdown_notification(username, info, days_left, next_birthday):
    """Gửi thông báo đếm ngược sinh nhật"""
    try:
        age = next_birthday.year - info["year"]
        
        countdown_messages = {
            5: f"🎉 **ĐẾM NGƯỢC SINH NHẬT!** 🎉\nChỉ còn **5 ngày** nữa là đến sinh nhật của **{info['name']}!** 🥳\nNgày sinh nhật: **{next_birthday.strftime('%d/%m/%Y')}** ({age} tuổi)\nNghề nghiệp: {info['job']}\n\nMọi người chuẩn bị quà đi nào! 🎁✨",
            4: f"🎊 **ĐẾM NGƯỢC TIẾP TỤC!** 🎊\nChỉ còn **4 ngày** nữa là đến sinh nhật **{info['name']}!** ⏳\nSắp được ăn bánh kem rồi! 🍰",
            3: f"⏰ **SẮP ĐẾN RỒI!** ⏰\nChỉ còn **3 ngày** nữa là sinh nhật **{info['name']}!** 🎂\nTuổi mới: {age} - Hãy chuẩn bị lời chúc thật ý nghĩa! 💝",
            2: f"🚨 **CHỈ CÒN 2 NGÀY!** 🚨\nHai ngày nữa là **{info['name']}** thêm tuổi mới! 🎈\nMong chờ khoảnh khắc đặc biệt này! ✨",
            1: f"🎯 **NGÀY MAI LÀ SINH NHẬT!** 🎯\n**NGÀY MAI** - {next_birthday.strftime('%d/%m')} là sinh nhật **{info['name']}!** 🥳\nChuẩn bị tổ chức thôi nào! 🎉🎊"
        }
        
        message = countdown_messages.get(days_left, 
            f"🎉 Còn **{days_left} ngày** nữa là đến sinh nhật **{info['name']}!** 🎂")
        
        # Tìm tất cả các server mà bot đang tham gia
        for guild in client.guilds:
            # Tìm channel general hoặc channel đầu tiên có quyền gửi tin nhắn
            target_channel = None
            
            # Ưu tiên channel có tên "general", "chung", "main"
            for channel in guild.text_channels:
                if channel.name.lower() in ['general', 'chung', 'main', 'chat']:
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
            
            # Nếu không tìm thấy, lấy channel đầu tiên có quyền
            if not target_channel:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
            
            if target_channel:
                # Tìm user để tag
                user = guild.get_member_named(username)
                if user:
                    message = f"{user.mention}\n{message}"
                
                await target_channel.send(message)
                break
    
    except Exception as e:
        print(f"❌ Lỗi gửi thông báo đếm ngược: {e}")

async def send_birthday_wish(username, info, age):
    """Gửi lời chúc mừng sinh nhật"""
    try:
        birthday_prompt = f"""
Hôm nay là sinh nhật của {info['name']} ({username}) - {age} tuổi, nghề nghiệp: {info['job']}.

Hãy viết một lời chúc mừng sinh nhật thật ý nghĩa và chân thành:
- Xưng 'em' gọi 'anh' (nếu là nam)
- Nhắc đến tuổi mới và nghề nghiệp của họ
- Chúc những điều tốt đẹp trong công việc và cuộc sống
- Dùng nhiều emoji sinh nhật vui vẻ
- Độ dài: khoảng 50-100 chữ
- Thật tâm và ấm áp
- Kết thúc bằng một câu chúc đặc biệt

Lời chúc của em:
"""
        response = model.generate_content(birthday_prompt)
        birthday_message = response.text.strip()
        
        image_data = await generate_birthday_image(info['name'], age, info['job'])
        
        # Tìm tất cả các server
        for guild in client.guilds:
            target_channel = None
            
            # Ưu tiên channel chung
            for channel in guild.text_channels:
                if channel.name.lower() in ['general', 'chung', 'main', 'chat']:
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
            
            if not target_channel:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
            
            if target_channel:
                user = guild.get_member_named(username)
                mention = user.mention if user else f"**{info['name']}**"
                
                if image_data:
                    image_file = discord.File(io.BytesIO(image_data), filename=f"birthday_{info['name']}.png")
                    await target_channel.send(
                        f"🎉🎂 **CHÚC MỪNG SINH NHẬT!** 🎂🎉\n{mention}\n{birthday_message}",
                        file=image_file
                    )
                else:
                    await target_channel.send(f"🎉🎂 **CHÚC MỪNG SINH NHẬT!** 🎂🎉\n{mention}\n{birthday_message}")
                break
    
    except Exception as e:
        print(f"❌ Lỗi gửi chúc mừng sinh nhật: {e}")

async def test_countdown_system(days_offset=0):
    """Hàm test hệ thống đếm ngược (cho debug)"""
    try:
        test_date = datetime.datetime.now(VIETNAM_TZ).date() + timedelta(days=days_offset)
        print(f"🧪 TEST hệ thống với ngày: {test_date.strftime('%d/%m/%Y')}")
        
        for username, info in server_members.items():
            birthday_day = info["birthday"]["day"]
            birthday_month = info["birthday"]["month"]
            
            days_left, next_birthday = calculate_days_until_birthday(birthday_day, birthday_month, test_date)
            
            if 0 <= days_left <= 5:
                print(f"  🎯 {info['name']}: Còn {days_left} ngày (sinh nhật {birthday_day}/{birthday_month})")
                
                # Simulate notification
                if days_left == 0:
                    print(f"    🎉 HÔM NAY LÀ SINH NHẬT!")
                elif days_left <= 5:
                    print(f"    ⏰ Đếm ngược {days_left} ngày")
    
    except Exception as e:
        print(f"❌ Lỗi test hệ thống: {e}")

# ==============================================
# CÁC HÀM TIỆN ÍCH MỚI (GIỮ NGUYÊN)
# ==============================================

# Hàm lấy thời tiết từ OpenWeatherMap (hiện tại)
async def get_current_weather(location: str = "Hanoi") -> Optional[str]:
    """Lấy thông tin thời tiết hiện tại từ OpenWeatherMap API"""
    try:
        if not WEATHER_API_KEY:
            return await get_weather_backup(location, "current")
        
        encoded_location = urllib.parse.quote(location)
        url = f"https://api.openweathermap.org/data/2.5/weather?q={encoded_location}&appid={WEATHER_API_KEY}&units=metric&lang=vi"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    temp = data['main']['temp']
                    feels_like = data['main']['feels_like']
                    humidity = data['main']['humidity']
                    weather_desc = data['weather'][0]['description']
                    wind_speed = data['wind']['speed']
                    city = data['name']
                    
                    weather_emoji = {
                        'mây': '☁️', 'nắng': '☀️', 'mưa': '🌧️', 'dông': '⛈️',
                        'sương mù': '🌫️', 'tuyết': '❄️', 'gió': '💨', 'quang': '☀️',
                        'thoáng': '⛅', 'bão': '🌀'
                    }
                    
                    emoji = '🌈'
                    for key, value in weather_emoji.items():
                        if key in weather_desc.lower():
                            emoji = value
                            break
                    
                    return (f"**🌤️ Thời tiết hiện tại tại {city}:** {emoji}\n"
                           f"🌡️ **Nhiệt độ:** {temp}°C (cảm giác như {feels_like}°C)\n"
                           f"💧 **Độ ẩm:** {humidity}%\n"
                           f"🌬️ **Gió:** {wind_speed} m/s\n"
                           f"📝 **Mô tả:** {weather_desc.capitalize()}")
                    
                else:
                    return await get_weather_backup(location, "current")
    except Exception as e:
        print(f"❌ Lỗi lấy thời tiết hiện tại: {e}")
        return await get_weather_backup(location, "current")

# Hàm lấy dự báo thời tiết cho ngày cụ thể
async def get_weather_forecast(location: str = "Hanoi", day_offset: int = 0) -> Optional[str]:
    """Lấy dự báo thời tiết cho ngày hôm nay (0), ngày mai (1), ngày kia (2)"""
    try:
        # Ưu tiên WeatherAPI.com vì có dự báo 3 ngày free
        if WEATHERAPI_KEY:
            return await get_weatherapi_forecast(location, day_offset)
        
        # Fallback: OpenWeatherMap (5 day/3 hour forecast)
        if WEATHER_API_KEY:
            return await get_openweather_forecast(location, day_offset)
        
        # Final fallback: Open-Meteo (free, no API key needed)
        return await get_openmeteo_forecast(location, day_offset)
        
    except Exception as e:
        print(f"❌ Lỗi lấy dự báo thời tiết: {e}")
        return None

# Hàm dự phòng lấy thời tiết từ WeatherAPI.com
async def get_weatherapi_forecast(location: str, day_offset: int) -> Optional[str]:
    """Lấy dự báo từ WeatherAPI.com (free tier)"""
    try:
        encoded_location = urllib.parse.quote(location)
        url = f"https://api.weatherapi.com/v1/forecast.json?key={WEATHERAPI_KEY}&q={encoded_location}&days=3&lang=vi"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if day_offset >= len(data['forecast']['forecastday']):
                        day_offset = 0  # Fallback về hôm nay
                    
                    forecast_day = data['forecast']['forecastday'][day_offset]
                    date = forecast_day['date']
                    day_data = forecast_day['day']
                    
                    max_temp = day_data['maxtemp_c']
                    min_temp = day_data['mintemp_c']
                    avg_temp = day_data['avgtemp_c']
                    condition = day_data['condition']['text']
                    humidity = day_data['avghumidity']
                    wind_speed = day_data['maxwind_kph'] / 3.6  # Convert km/h to m/s
                    
                    # Map ngày offset thành tên ngày
                    day_names = {0: "HÔM NAY", 1: "NGÀY MAI", 2: "NGÀY KIA"}
                    day_name = day_names.get(day_offset, f"SAU {day_offset} NGÀY")
                    
                    # Emoji theo điều kiện
                    condition_emoji = {
                        'nắng': '☀️', 'mưa': '🌧️', 'mây': '☁️', 'quang': '☀️',
                        'dông': '⛈️', 'sương mù': '🌫️', 'tuyết': '❄️',
                        'mưa nhẹ': '🌦️', 'mưa rào': '🌧️'
                    }
                    
                    emoji = '🌈'
                    for key, value in condition_emoji.items():
                        if key in condition.lower():
                            emoji = value
                            break
                    
                    return (f"**🌤️ Dự báo {day_name} ({date}) tại {location.title()}:** {emoji}\n"
                           f"🌡️ **Nhiệt độ:** {min_temp}°C - {max_temp}°C (trung bình {avg_temp}°C)\n"
                           f"💧 **Độ ẩm:** {humidity}%\n"
                           f"🌬️ **Gió tối đa:** {wind_speed:.1f} m/s\n"
                           f"📝 **Điều kiện:** {condition}\n"
                           f"📍 **Nguồn:** WeatherAPI.com")
                    
    except Exception as e:
        print(f"❌ Lỗi WeatherAPI: {e}")
        return None

# Hàm dự phòng từ Open-Meteo (hoàn toàn miễn phí, không cần API key)
async def get_openmeteo_forecast(location: str, day_offset: int) -> Optional[str]:
    """Lấy dự báo từ Open-Meteo API (free, no API key)"""
    try:
        # Tìm tọa độ từ tên thành phố (geocoding)
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(geocode_url) as response:
                if response.status == 200:
                    geo_data = await response.json()
                    
                    if not geo_data.get('results'):
                        return None
                    
                    result = geo_data['results'][0]
                    lat = result['latitude']
                    lon = result['longitude']
                    city_name = result['name']
                    
                    # Lấy dự báo thời tiết
                    forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max&timezone=auto&forecast_days=3"
                    
                    async with session.get(forecast_url) as forecast_response:
                        if forecast_response.status == 200:
                            forecast_data = await forecast_response.json()
                            
                            if day_offset >= len(forecast_data['daily']['time']):
                                day_offset = 0
                            
                            date = forecast_data['daily']['time'][day_offset]
                            max_temp = forecast_data['daily']['temperature_2m_max'][day_offset]
                            min_temp = forecast_data['daily']['temperature_2m_min'][day_offset]
                            precipitation = forecast_data['daily']['precipitation_sum'][day_offset]
                            wind_speed = forecast_data['daily']['windspeed_10m_max'][day_offset]
                            
                            # Xác định điều kiện thời tiết dựa trên lượng mưa
                            if precipitation > 5:
                                condition = "Mưa"
                                emoji = "🌧️"
                            elif precipitation > 0.5:
                                condition = "Mưa nhẹ"
                                emoji = "🌦️"
                            else:
                                condition = "Quang đãng"
                                emoji = "☀️"
                            
                            day_names = {0: "HÔM NAY", 1: "NGÀY MAI", 2: "NGÀY KIA"}
                            day_name = day_names.get(day_offset, f"SAU {day_offset} NGÀY")
                            
                            return (f"**🌤️ Dự báo {day_name} ({date}) tại {city_name}:** {emoji}\n"
                                   f"🌡️ **Nhiệt độ:** {min_temp}°C - {max_temp}°C\n"
                                   f"💧 **Lượng mưa:** {precipitation} mm\n"
                                   f"🌬️ **Gió tối đa:** {wind_speed} km/h\n"
                                   f"📝 **Điều kiện:** {condition}\n"
                                   f"📍 **Nguồn:** Open-Meteo.com")
                            
    except Exception as e:
        print(f"❌ Lỗi Open-Meteo: {e}")
        return None

# Hàm dự phòng từ OpenWeatherMap (5 day forecast)
async def get_openweather_forecast(location: str, day_offset: int) -> Optional[str]:
    """Lấy dự báo từ OpenWeatherMap (5 day/3 hour forecast)"""
    try:
        encoded_location = urllib.parse.quote(location)
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={encoded_location}&appid={WEATHER_API_KEY}&units=metric&lang=vi"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Nhóm dự báo theo ngày
                    forecasts_by_day = {}
                    for forecast in data['list']:
                        forecast_time = datetime.datetime.fromtimestamp(forecast['dt'])
                        day_key = forecast_time.date()
                        
                        if day_key not in forecasts_by_day:
                            forecasts_by_day[day_key] = []
                        forecasts_by_day[day_key].append(forecast)
                    
                    # Sắp xếp các ngày
                    sorted_days = sorted(forecasts_by_day.keys())
                    
                    if day_offset >= len(sorted_days):
                        day_offset = 0
                    
                    target_day = sorted_days[day_offset]
                    day_forecasts = forecasts_by_day[target_day]
                    
                    # Tính toán giá trị trung bình/giá trị đại diện
                    temps = [f['main']['temp'] for f in day_forecasts]
                    feels_like = [f['main']['feels_like'] for f in day_forecasts]
                    humidity = [f['main']['humidity'] for f in day_forecasts]
                    wind_speeds = [f['wind']['speed'] for f in day_forecasts]
                    conditions = [f['weather'][0]['description'] for f in day_forecasts]
                    
                    avg_temp = sum(temps) / len(temps)
                    max_temp = max(temps)
                    min_temp = min(temps)
                    avg_humidity = sum(humidity) / len(humidity)
                    avg_wind = sum(wind_speeds) / len(wind_speeds)
                    
                    # Tìm điều kiện phổ biến nhất
                    condition_counter = {}
                    for cond in conditions:
                        condition_counter[cond] = condition_counter.get(cond, 0) + 1
                    most_common_condition = max(condition_counter, key=condition_counter.get)
                    
                    weather_emoji = {
                        'mây': '☁️', 'nắng': '☀️', 'mưa': '🌧️', 'dông': '⛈️',
                        'sương mù': '🌫️', 'tuyết': '❄️', 'gió': '💨', 'quang': '☀️'
                    }
                    
                    emoji = '🌈'
                    for key, value in weather_emoji.items():
                        if key in most_common_condition.lower():
                            emoji = value
                            break
                    
                    day_names = {0: "HÔM NAY", 1: "NGÀY MAI", 2: "NGÀY KIA", 3: "SAU 3 NGÀY", 4: "SAU 4 NGÀY"}
                    day_name = day_names.get(day_offset, f"SAU {day_offset} NGÀY")
                    
                    return (f"**🌤️ Dự báo {day_name} ({target_day}) tại {data['city']['name']}:** {emoji}\n"
                           f"🌡️ **Nhiệt độ:** {min_temp:.1f}°C - {max_temp:.1f}°C (trung bình {avg_temp:.1f}°C)\n"
                           f"💧 **Độ ẩm:** {avg_humidity:.0f}%\n"
                           f"🌬️ **Gió trung bình:** {avg_wind:.1f} m/s\n"
                           f"📝 **Điều kiện:** {most_common_condition.capitalize()}")
                    
    except Exception as e:
        print(f"❌ Lỗi OpenWeather dự báo: {e}")
        return None

# Hàm backup tổng hợp
async def get_weather_backup(location: str, forecast_type: str = "current") -> Optional[str]:
    """Hàm backup lấy thời tiết từ nhiều nguồn"""
    try:
        # Thử Open-Meteo trước (free)
        if forecast_type == "current":
            return await get_openmeteo_forecast(location, 0)
        else:
            return await get_openmeteo_forecast(location, 1 if "mai" in forecast_type else 0)
    except:
        return "❌ Hiện không thể lấy thông tin thời tiết. Vui lòng thử lại sau!"

# Hàm phân tích câu hỏi thời tiết
def parse_weather_query(query: str):
    """Phân tích câu hỏi để xác định địa điểm và ngày"""
    query_lower = query.lower()
    
    # Xác định địa điểm mặc định
    location = "Hanoi"
    
    # Danh sách thành phố phổ biến
    cities = {
        'hà nội': 'Hanoi', 'hanoi': 'Hanoi',
        'hồ chí minh': 'Ho Chi Minh City', 'hcm': 'Ho Chi Minh City', 'sài gòn': 'Ho Chi Minh City',
        'đà nẵng': 'Da Nang', 'danang': 'Da Nang',
        'hải phòng': 'Hai Phong', 'haiphong': 'Hai Phong',
        'cần thơ': 'Can Tho', 'cantho': 'Can Tho',
        'nha trang': 'Nha Trang', 'nhatrang': 'Nha Trang',
        'huế': 'Hue', 'hue': 'Hue',
        'vũng tàu': 'Vung Tau', 'vungtau': 'Vung Tau'
    }
    
    # Tìm thành phố trong câu hỏi
    for city_key, city_value in cities.items():
        if city_key in query_lower:
            location = city_value
            break
    
    # Xác định ngày
    day_offset = 0  # 0 = hôm nay
    if 'ngày mai' in query_lower or 'mai' in query_lower:
        day_offset = 1
    elif 'ngày kia' in query_lower or 'kia' in query_lower:
        day_offset = 2
    elif 'hôm nay' in query_lower or 'hôm nay' in query_lower:
        day_offset = 0
    elif 'hôm qua' in query_lower:
        day_offset = -1
    
    return location, day_offset

# Hàm tạo ảnh bài Tarot bằng Pollinations AI
async def generate_tarot_image(card_name, meaning):
    """Tạo ảnh lá bài Tarot bằng Pollinations AI"""
    try:
        prompt = f"""
        Mystical tarot card illustration: {card_name}. 
        Meaning: {meaning}.
        Art style: fantasy, mystical, magical, detailed tarot card design,
        intricate patterns, symbolic imagery, glowing effects,
        professional tarot card illustration, esoteric symbols,
        rich colors, gold accents, mystical atmosphere.
        Style: fantasy art, digital painting, tarot card.
        """
        
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    print(f"❌ Lỗi tải ảnh Tarot: {response.status}")
                    return None
                    
    except Exception as e:
        print(f"❌ Lỗi tạo ảnh Tarot: {e}")
        return None

# Hàm bói bài Tarot (CẬP NHẬT: tạo ảnh + giải thích)
async def tarot_reading() -> tuple:
    """Trải bài Tarot ngẫu nhiên và trả về (card, reading_text, image_data)"""
    try:
        card = random.choice(TAROT_CARDS)
        
        # Tạo ảnh lá bài
        image_data = await generate_tarot_image(card['name'], card['meaning'])
        
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
7. Kết thúc bằng một câu khẳng định tích cực

Giải bài:
"""
        response = model.generate_content(reading_prompt)
        reading_text = response.text.strip()
        
        return card, reading_text, image_data
        
    except Exception as e:
        print(f"❌ Lỗi khi bói bài Tarot: {str(e)}")
        return None, f"❌ Lỗi khi bói bài Tarot: {str(e)}", None

# Hàm tóm tắt drama từ chat history (ĐÃ SỬA: TÓM TẮT TOÀN BỘ 500 TIN NHẮN)
async def summarize_drama() -> str:
    """Đọc TOÀN BỘ 500 tin nhắn đã lưu và tóm tắt"""
    try:
        if not server_memory:
            return "📊 Hiện chưa có đủ dữ liệu chat để tóm tắt. Mọi người hãy trò chuyện nhiều hơn nhé! 💬"
        
        # Lấy TOÀN BỘ 500 tin nhắn đã lưu
        all_messages = list(server_memory)
        
        # Kiểm tra số lượng tin nhắn
        total_messages = len(all_messages)
        print(f"📝 Đang tóm tắt {total_messages} tin nhắn...")
        
        # Nếu có ít hơn 10 tin nhắn
        if total_messages < 10:
            return "📊 Chưa có đủ tin nhắn để tóm tắt. Hãy chat thêm để tôi có thể tóm tắt tốt hơn! 💬"
        
        # Chuẩn bị tất cả tin nhắn cho prompt
        messages_text = "\n".join(all_messages)
        
        # Ước tính độ dài của prompt
        prompt_length = len(messages_text)
        print(f"📏 Độ dài prompt: {prompt_length} ký tự")
        
        # Nếu prompt quá dài, cắt bớt nhưng vẫn giữ tối đa có thể
        if prompt_length > 20000:  # Giới hạn an toàn cho Gemini
            # Lấy 300 tin nhắn gần nhất
            messages_text = "\n".join(all_messages[-300:])
            print(f"⚠️ Prompt quá dài, chỉ lấy 300 tin nhắn gần nhất")
        
        drama_prompt = f"""
Dưới đây là TOÀN BỘ lịch sử chat trong server (tối đa 500 tin nhắn gần nhất):
{messages_text}

Hãy tóm tắt một cách CHUYÊN NGHIỆP và KHÁCH QUAN những nội dung chính trong cuộc trò chuyện:
1. Giọng văn TRUNG LẬP, CHUYÊN NGHIỆP, KHÔNG hài hước tấu hài
2. Tóm tắt các chủ đề chính đã thảo luận
3. Điểm qua các sự kiện quan trọng (nếu có)
4. Dùng emoji vừa phải, phù hợp
5. Độ dài: khoảng 150-200 chữ (tương ứng với lượng tin nhắn)
6. Tập trung vào thông tin thực tế, không bình luận cá nhân
7. Có thể nhắc đến tên thành viên nếu có trong context
8. Nếu có nhiều chủ đề, hãy phân loại rõ ràng

Bản tóm tắt CHI TIẾT:
"""
        response = model.generate_content(drama_prompt)
        summary = response.text.strip()
        
        # Thêm thông tin thống kê
        stats = f"\n\n📊 **Thống kê:** Tóm tắt từ {total_messages} tin nhắn gần nhất"
        
        return f"**📊 TÓM TẮT HOẠT ĐỘNG SERVER**\n{summary}{stats}"
    except Exception as e:
        print(f"❌ Lỗi khi tóm tắt drama: {e}")
        return "❌ Đã xảy ra lỗi khi tóm tắt. Có thể có quá nhiều tin nhắn để xử lý. Vui lòng thử lại sau!"

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
    
    # Khởi động scheduler cho hệ thống sinh nhật
    scheduler.start()
    
    # Lên lịch kiểm tra sinh nhật mỗi giờ (để đảm bảo không bỏ lỡ)
    scheduler.add_job(
        check_birthday_countdown,
        trigger=CronTrigger(hour="*", minute="0"),  # Mỗi giờ vào phút 0
        id="birthday_check",
        replace_existing=True
    )
    
    # Kiểm tra ngay khi khởi động
    await check_birthday_countdown()
    
    print(f"📅 Hệ thống sinh nhật đã được kích hoạt!")
    print(f"⏰ Kiểm tra lúc: 0h hàng ngày (GMT+7)")
    
    # Test hệ thống
    print("\n🧪 TEST HỆ THỐNG SINH NHẬT:")
    await test_countdown_system()
    await test_countdown_system(1)  # Test ngày mai

@client.event
async def on_message(message):
    # Lưu tin nhắn vào memory
    if message.content and not message.author.bot:
        timestamp = datetime.datetime.now(VIETNAM_TZ).strftime("%H:%M")
        memory_msg = f"[{timestamp}] {message.author.display_name}: {message.content}"
        add_to_server_memory(memory_msg)

    if message.author == client.user:
        return

    # Bỏ qua @everyone và @here
    if any(mention in [message.guild.default_role, "everyone", "here"] for mention in message.mentions):
        return

    # ==============================================
    # LỆNH MỚI: HỆ THỐNG SINH NHẬT
    # ==============================================
    
    # Lệnh kiểm tra sinh nhật sắp tới
    if message.content.startswith('!upcoming'):
        try:
            current_time = await get_real_time()
            current_date = current_time.date()
            
            response = "**🎉 SINH NHẬT SẮP TỚI:**\n\n"
            upcoming_list = []
            
            for username, info in server_members.items():
                birthday_day = info["birthday"]["day"]
                birthday_month = info["birthday"]["month"]
                
                days_left, next_birthday = calculate_days_until_birthday(birthday_day, birthday_month, current_date)
                age = next_birthday.year - info["year"]
                
                if days_left <= 30:  # Hiển thị trong vòng 30 ngày
                    upcoming_list.append((info['name'], username, days_left, next_birthday, age, info['job']))
            
            # Sắp xếp theo số ngày còn lại
            upcoming_list.sort(key=lambda x: x[2])
            
            if upcoming_list:
                for name, username, days_left, next_birthday, age, job in upcoming_list:
                    if days_left == 0:
                        response += f"🎂 **HÔM NAY** - {name} ({username}) tròn {age} tuổi! ({job}) 🎉\n"
                    elif days_left <= 5:
                        response += f"⏰ **Còn {days_left} ngày** ({next_birthday.strftime('%d/%m')}) - {name} ({username}) {age} tuổi ({job}) 🎁\n"
                    else:
                        response += f"📅 **Còn {days_left} ngày** ({next_birthday.strftime('%d/%m')}) - {name} ({username}) {age} tuổi\n"
                
                response += f"\n📊 **Tổng:** {len(upcoming_list)} sinh nhật trong 30 ngày tới"
            else:
                response = "📅 Không có sinh nhật nào trong 30 ngày tới."
            
            await message.channel.send(response)
            
        except Exception as e:
            await message.channel.send(f"❌ Lỗi khi kiểm tra sinh nhật: {e}")
        return
    
    # Lệnh test hệ thống sinh nhật
    if message.content.startswith('!test_birthday_system'):
        parts = message.content.split()
        days_offset = 0
        
        if len(parts) == 2:
            try:
                days_offset = int(parts[1])
            except:
                pass
        
        await message.channel.send(f"🧪 **Đang test hệ thống sinh nhật với offset {days_offset} ngày...**")
        
        # Test với ngày giả định
        test_date = datetime.datetime.now(VIETNAM_TZ).date() + timedelta(days=days_offset)
        
        response = f"**TEST HỆ THỐNG SINH NHẬT - Ngày: {test_date.strftime('%d/%m/%Y')}**\n\n"
        
        for username, info in server_members.items():
            birthday_day = info["birthday"]["day"]
            birthday_month = info["birthday"]["month"]
            
            days_left, next_birthday = calculate_days_until_birthday(birthday_day, birthday_month, test_date)
            
            if days_left <= 5:
                status = "🎉 HÔM NAY LÀ SINH NHẬT!" if days_left == 0 else f"⏰ Đếm ngược {days_left} ngày"
                response += f"• {info['name']}: {status} (sinh nhật: {birthday_day}/{birthday_month})\n"
        
        if "⏰" not in response and "🎉" not in response:
            response += "Không có sinh nhật nào trong 5 ngày tới."
        
        await message.channel.send(response)
        
        # Test thực tế
        await test_countdown_system(days_offset)
        return
    
    # Lệnh reset countdown (cho admin)
    if message.content.startswith('!reset_countdown'):
        if message.author.guild_permissions.administrator:
            for username in server_members:
                server_members[username]["countdown_sent"] = {}
                server_members[username]["last_birthday_wish"] = None
            
            await message.channel.send("✅ Đã reset tất cả countdown sinh nhật!")
        else:
            await message.channel.send("❌ Bạn không có quyền sử dụng lệnh này!")
        return
    
    # ==============================================
    # XỬ LÝ CÁC LỆNH MỚI
    # ==============================================
    
    # Lệnh Tarot (ĐÃ CẬP NHẬT: gửi ảnh + giải thích)
    if message.content.startswith('!tarot'):
        await message.channel.send("🔮 Đang rút lá bài Tarot cho bạn...")
        
        # Lấy thông tin bài Tarot
        card, reading_text, image_data = await tarot_reading()
        
        if card and reading_text:
            # Gửi ảnh lá bài trước
            if image_data:
                image_file = discord.File(io.BytesIO(image_data), filename=f"tarot_{card['name'].replace(' ', '_')}.png")
                await message.channel.send(
                    f"**🎴 Lá bài của bạn: {card['name']}**",
                    file=image_file
                )
            
            # Chờ một chút rồi gửi giải thích
            await asyncio.sleep(1)
            
            # Gửi giải thích
            await message.channel.send(
                f"**🔮 Giải thích lá bài {card['name']}:**\n{reading_text}"
            )
        else:
            await message.channel.send("❌ Đã xảy ra lỗi khi rút bài Tarot. Vui lòng thử lại!")
        return

    # Lệnh Drama (ĐÃ SỬA: TÓM TẮT TOÀN BỘ 500 TIN NHẮN)
    if message.content.startswith('!drama'):
        await message.channel.send("📊 Đang tóm tắt toàn bộ 500 tin nhắn gần nhất...")
        drama_summary = await summarize_drama()
        await message.channel.send(drama_summary)
        return

    # Lệnh thời tiết (ĐÃ NÂNG CẤP)
    if message.content.startswith('!weather') or message.content.startswith('!thoitiet'):
        parts = message.content.split()
        query = " ".join(parts[1:]) if len(parts) >= 2 else "hà nội hôm nay"
        
        await message.channel.send(f"🌤️ Đang lấy thông tin thời tiết...")
        
        # Phân tích câu hỏi
        location, day_offset = parse_weather_query(query)
        
        # Xử lý theo ngày
        if day_offset == 0:
            # Thời tiết hiện tại
            weather_info = await get_current_weather(location)
        else:
            # Dự báo cho ngày mai, ngày kia
            weather_info = await get_weather_forecast(location, day_offset)
        
        if weather_info:
            await message.channel.send(weather_info)
        else:
            await message.channel.send(f"❌ Không thể lấy thông tin thời tiết cho '{location}'. Vui lòng thử với tên thành phố khác!")
        return

    # Các lệnh cũ (giữ nguyên)
    if message.content.startswith('!test_birthday'):
        parts = message.content.split()
        if len(parts) == 2:
            username = parts[1]
            # Sử dụng hàm test cũ
            await test_birthday_old(client, username, message.channel)
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

    # Xử lý câu hỏi về thời tiết khi được tag (ĐÃ NÂNG CẤP)
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_message = message.content.replace(f'<@{client.user.id}>', '').strip().lower()
        
        # Kiểm tra câu hỏi về thời tiết
        weather_keywords = ['thời tiết', 'weather', 'nhiệt độ', 'trời', 'dự báo', 'mưa', 'nắng', 'bao nhiêu độ', 'độ ẩm']
        if any(keyword in user_message for keyword in weather_keywords):
            # Phân tích câu hỏi để xác định địa điểm và ngày
            location, day_offset = parse_weather_query(user_message)
            
            if day_offset == 0:
                # Thời tiết hiện tại
                weather_info = await get_current_weather(location)
            else:
                # Dự báo
                weather_info = await get_weather_forecast(location, day_offset)
            
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
                current_time = await get_real_time()
                current_date = current_time.date()
                
                days_left, next_birthday = calculate_days_until_birthday(
                    info["birthday"]["day"], 
                    info["birthday"]["month"], 
                    current_date
                )
                
                age = next_birthday.year - info['year']
                
                response = f"""
**Thông tin về {info['name']}:** 🎯

🎂 **Sinh nhật:** {info['birthday']['day']}/{info['birthday']['month']}/{info['year']}
📅 **Tuổi hiện tại:** {age} tuổi
🕒 **Sinh nhật tiếp theo:** {next_birthday.strftime('%d/%m/%Y')} (còn {days_left} ngày)
💼 **Nghề nghiệp:** {info['job']}
"""
                if info.get("relationship"):
                    response += f"💕 **Mối quan hệ:** {info['relationship']}\n"
                
                response += f"👤 **Username:** {found_member}\n"
                
                if days_left == 0:
                    response += "\n🎉 **Hôm nay là sinh nhật!** 🎉"
                elif days_left <= 5:
                    response += f"\n🎁 Chỉ còn **{days_left} ngày** nữa là đến sinh nhật! 🎊"
                
                await message.channel.send(response)
                return

    # Xử lý tin nhắn thông thường khi được tag (giữ nguyên)
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        try:
            async with message.channel.typing():
                channel_id = str(message.channel.id)
                user_message = message.content.replace(f'<@{client.user.id}>', '').strip()
                
                # Lấy thông tin thời gian thực
                current_time = await get_real_time()
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

# ==============================================
# HÀM CŨ (GIỮ NGUYÊN ĐỂ TƯƠNG THÍCH)
# ==============================================

async def test_birthday_old(client, username, channel):
    """Hàm test sinh nhật cũ (giữ nguyên cho tương thích)"""
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

async def show_member_info(username, channel):
    """Hiển thị thông tin thành viên"""
    if username in server_members:
        info = server_members[username]
        current_time = await get_real_time()
        current_date = current_time.date()
        
        days_left, next_birthday = calculate_days_until_birthday(
            info["birthday"]["day"], 
            info["birthday"]["month"], 
            current_date
        )
        
        age = next_birthday.year - info["year"]
        
        response = f"""
**Thông tin về {info['name']}:** 🎯

🎂 **Sinh nhật:** {info['birthday']['day']}/{info['birthday']['month']}/{info['year']}
📅 **Tuổi hiện tại:** {age} tuổi
🕒 **Sinh nhật tiếp theo:** {next_birthday.strftime('%d/%m/%Y')} (còn {days_left} ngày)
💼 **Nghề nghiệp:** {info['job']}
"""
        if info.get("relationship"):
            response += f"💕 **Mối quan hệ:** {info['relationship']}\n"
        
        response += f"👤 **Username:** {username}\n"
        
        if days_left == 0:
            response += "\n🎉 **Hôm nay là sinh nhật!** 🎉"
        elif days_left <= 5:
            response += f"\n🎁 Chỉ còn **{days_left} ngày** nữa là đến sinh nhật! 🎊"
        
        await channel.send(response)
    else:
        await channel.send(f"❌ Không tìm thấy thông tin cho username: {username}")

# Web server
app = flask.Flask(__name__)

@app.route('/')
def home():
    return "🤖 Yoo Ji Min Bot is running!"

@app.route('/health')
def health():
    return "OK"

@app.route('/birthdays')
def birthdays_status():
    """Trang web hiển thị trạng thái sinh nhật"""
    current_time = datetime.datetime.now(VIETNAM_TZ)
    html = f"""
    <html>
        <head>
            <title>Yoo Ji Min - Birthday System</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
                .status {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .member {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .countdown {{ color: #FF5722; font-weight: bold; }}
                .today {{ background: #FFF3CD; border-color: #FFC107; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #4CAF50; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎉 Yoo Ji Min - Hệ thống sinh nhật</h1>
                <div class="status">
                    🕐 Thời gian hiện tại: {current_time.strftime('%H:%M:%S %d/%m/%Y')} (GMT+7)
                </div>
                
                <h2>📊 Danh sách thành viên:</h2>
                <table>
                    <tr>
                        <th>Tên</th>
                        <th>Sinh nhật</th>
                        <th>Ngày tới</th>
                        <th>Còn lại</th>
                        <th>Trạng thái</th>
                    </tr>
    """
    
    for username, info in server_members.items():
        days_left, next_birthday = calculate_days_until_birthday(
            info["birthday"]["day"], 
            info["birthday"]["month"], 
            current_time.date()
        )
        
        age = next_birthday.year - info["year"]
        
        status = "✅ Đang chờ"
        if days_left == 0:
            status = "🎉 HÔM NAY!"
        elif days_left <= 5:
            status = f"⏰ {days_left} ngày"
        
        html += f"""
                    <tr>
                        <td><strong>{info['name']}</strong></td>
                        <td>{info['birthday']['day']}/{info['birthday']['month']}/{info['year']}</td>
                        <td>{next_birthday.strftime('%d/%m/%Y')}</td>
                        <td class="countdown">{days_left} ngày</td>
                        <td>{status}</td>
                    </tr>
        """
    
    html += """
                </table>
                
                <div style="margin-top: 20px; padding: 15px; background: #E3F2FD; border-radius: 5px;">
                    <h3>ℹ️ Thông tin hệ thống:</h3>
                    <ul>
                        <li>✅ Kiểm tra tự động lúc 0h hàng ngày</li>
                        <li>🎯 Đếm ngược 5,4,3,2,1 ngày trước sinh nhật</li>
                        <li>🎉 Tự động chúc mừng vào đúng ngày sinh nhật</li>
                        <li>🔄 Sử dụng thời gian thực từ API</li>
                        <li>⏰ Múi giờ: Việt Nam (GMT+7)</li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    """
    
    return html

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
