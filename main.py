import discord
import google.generativeai as genai
import asyncio
import io
import os
import flask
import threading
from collections import defaultdict, deque
import datetime
import time

# ================= CẤU HÌNH =================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    print("❌ Lỗi: Thiếu Token!")
    exit(1)

print("🔄 Đang khởi động Yoo Ji Min (Chế độ Nano Banana 3 - Hardcore)...")

genai.configure(api_key=GEMINI_API_KEY)
# Model chat xử lý text
TEXT_MODEL_NAME = 'gemini-1.5-flash'
text_model = genai.GenerativeModel(TEXT_MODEL_NAME)

# Lưu trữ lịch sử hội thoại
conversation_history = defaultdict(lambda: deque(maxlen=30))
server_memory = deque(maxlen=100)

# ================= DỮ LIỆU THÀNH VIÊN =================
server_members = {
    "demacianking1": {"name": "Cường", "birthday": {"day": 5, "month": 1}, "year": 2000, "job": "IT", "last_birthday_wish": None},
    "thanh0374": {"name": "Thành", "birthday": {"day": 19, "month": 10}, "year": 2000, "job": "IT", "last_birthday_wish": None},
    "dangialanrangu": {"name": "Dũng Còi", "birthday": {"day": 17, "month": 11}, "year": 2000, "job": "kiến trúc sư", "last_birthday_wish": None},
    "manted1229": {"name": "Ngọc Điếc", "birthday": {"day": 4, "month": 1}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None},
    "vyanhduc": {"name": "Đức", "birthday": {"day": 25, "month": 12}, "year": 1999, "job": "Music Producer", "last_birthday_wish": None},
    "pta.zyud": {"name": "Tuấn Anh", "birthday": {"day": 6, "month": 6}, "year": 2000, "job": "Bác sĩ", "last_birthday_wish": None}
}

personality = """
Bạn là Yoo Ji Min, một AI thông minh và tinh nghịch.
- Luôn trả lời ngắn gọn, đi thẳng vào vấn đề.
- Với Đức (vyanhduc): Ngọt ngào, xưng em gọi anh.
- Với người khác: Xưng hô linh hoạt, vui vẻ.
"""

# ================= HÀM XỬ LÝ ẢNH (CHỈ DÙNG GEMINI IMAGEN 3) =================

async def generate_image_core(prompt):
    print(f"🎨 Yêu cầu vẽ (Nano Banana 3): {prompt}")
    
    final_prompt = prompt
    
    # BƯỚC 1: Dịch prompt sang tiếng Anh bằng Gemini Flash để tối ưu hóa đầu vào cho Imagen 3
    try:
        trans_prompt = f"Translate this prompt to English for image generation, keep it detailed: {prompt}"
        trans_response = await text_model.generate_content_async(trans_prompt)
        final_prompt = trans_response.text.strip()
        print(f"✅ Đã dịch prompt: {final_prompt}")
    except Exception as e:
        print(f"⚠️ Lỗi dịch thuật: {e}")
        pass # Dùng tạm prompt tiếng Việt

    # BƯỚC 2: Gọi trực tiếp model IMAGEN 3 (Nano Banana) của Google
    try:
        # Chạy trong thread riêng vì thư viện genai có thể chặn luồng chính
        def run_imagen():
            # Thử gọi model Imagen 3 mới nhất
            # Lưu ý: Nếu Key chưa được cấp quyền Imagen 3, nó sẽ lỗi ở đây.
            imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-001")
            result = imagen_model.generate_images(
                prompt=final_prompt,
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter="block_only_high",
            )
            return result

        # Chạy hàm blocking trong executor để không lag bot Discord
        result = await asyncio.to_thread(run_imagen)
        
        # Lấy ảnh về
        if result and result.images:
            image_bytes = result.images[0].image_bytes
            return image_bytes, final_prompt
        else:
            return None, "Google không trả về ảnh nào."

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Lỗi Imagen: {error_msg}")
        
        # Kiểm tra xem có phải lỗi do chưa có quyền không
        if "404" in error_msg or "NotFound" in error_msg:
            return None, "API Key của bạn chưa được Google cấp quyền dùng 'Nano Banana 3' (Imagen 3). Hãy thử lại sau hoặc đổi Key khác."
        elif "429" in error_msg:
            return None, "Hết lượt dùng thử (Quota exceeded) của Google rồi."
        else:
            return None, f"Lỗi Google API: {error_msg}"

# Hàm tạo ảnh sinh nhật
async def generate_birthday_image(name, age, job):
    prompt = f"Happy Birthday {name}, {age} years old, working as {job}, luxury party, cake, 3d render, cinematic lighting, 8k"
    image_data, _ = await generate_image_core(prompt)
    return image_data

# ================= DISCORD CLIENT =================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ {client.user} đã Online!')
    await client.change_presence(activity=discord.Game(name="vẽ bằng Nano Banana 3 🍌"))
    client.loop.create_task(birthday_check_loop())

async def birthday_check_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await check_birthdays(client)
        await asyncio.sleep(3600 * 4)

async def check_birthdays(client):
    today = datetime.datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    for username, info in server_members.items():
        if info["birthday"]["day"] == today.day and info["birthday"]["month"] == today.month:
            if info.get("last_birthday_wish") != today_str:
                user = discord.utils.get(client.users, name=username)
                if user: # Chỉ chúc nếu tìm thấy user
                    try:
                        wish_prompt = f"Viết lời chúc sinh nhật ngắn gọn, tình cảm cho {info['name']}, {today.year - info['year']} tuổi, nghề {info['job']}."
                        wish_resp = await text_model.generate_content_async(wish_prompt)
                        wish_msg = wish_resp.text.strip()
                        
                        img_data = await generate_birthday_image(info['name'], today.year - info['year'], info['job'])
                        
                        # Gửi tin nhắn
                        # Tìm channel đầu tiên bot có thể chat
                        for guild in client.guilds:
                            if user in guild.members:
                                for channel in guild.text_channels:
                                    if channel.permissions_for(guild.me).send_messages:
                                        content = f"🎉 **CHÚC MỪNG SINH NHẬT!** 🎉\n{user.mention}\n{wish_msg}"
                                        if img_data:
                                            f = discord.File(io.BytesIO(img_data), filename="birthday_nano.png")
                                            await channel.send(content, file=f)
                                        else:
                                            await channel.send(content + "\n*(Không tạo được ảnh sinh nhật do lỗi API Nano Banana)*")
                                        break
                                break
                    except Exception as e:
                        print(f"Lỗi chúc sinh nhật: {e}")
                
                info["last_birthday_wish"] = today_str

@client.event
async def on_message(message):
    if message.author.bot: return

    # === LỆNH VẼ TRANH ===
    if message.content.lower().startswith(('!ve ', '!draw ')):
        prompt = message.content.split(' ', 1)[1].strip()
        if not prompt:
            await message.reply("Nhập nội dung cần vẽ đi nè!")
            return

        async with message.channel.typing():
            status_msg = await message.reply(f"🍌 Đang dùng **Nano Banana 3** vẽ: *{prompt}*...")
            
            image_data, result_msg = await generate_image_core(prompt)
            
            if image_data:
                f = discord.File(io.BytesIO(image_data), filename="nano_art.png")
                await status_msg.delete()
                await message.reply(f"✨ Hàng về! (Prompt: {result_msg})", file=f)
            else:
                await status_msg.edit(content=f"❌ Thất bại: {result_msg}")
        return

    # === CHAT ===
    if client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        user_msg = message.content.replace(f'<@{client.user.id}>', '').strip()
        if not user_msg and not message.attachments:
            await message.reply("Sao thế ạ? 🌟")
            return
            
        async with message.channel.typing():
            try:
                # Xử lý ảnh Vision (Đọc ảnh)
                if message.attachments:
                    img_data = await message.attachments[0].read()
                    img = Image.open(io.BytesIO(img_data))
                    prompt = f"{personality}\nUser gửi ảnh và hỏi: {user_msg}. Hãy trả lời."
                    resp = await text_model.generate_content_async([prompt, img])
                    await message.reply(resp.text.strip())
                    return

                # Chat thường
                prompt = f"{personality}\nUser: {user_msg}\nTrả lời:"
                resp = await text_model.generate_content_async(prompt)
                await message.reply(resp.text.strip())
            except Exception as e:
                print(f"Lỗi Chat: {e}")
                await message.reply("Mạng lag quá, nói lại được không ạ? 😅")

# ================= WEB SERVER =================
app = flask.Flask(__name__)
@app.route('/')
def home(): return "Yoo Ji Min (Nano Banana Mode) is OK"
def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    keep_alive()
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Lỗi Bot: {e}")
