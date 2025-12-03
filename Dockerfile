# Nâng cấp lên Python 3.10-slim để tương thích với thư viện Google AI mới nhất
FROM python:3.10-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy file requirements và cài đặt
COPY requirements.txt .

# Nâng cấp pip và cài đặt thư viện (thêm --upgrade để đảm bảo không bị lỗi cache)
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (lưu ý copy tất cả các file trong thư mục để chắc chắn)
COPY . .

# Mở port 8080 cho Flask server (QUAN TRỌNG ĐỂ BOT KHÔNG BỊ TẮT TRÊN RENDER)
EXPOSE 8080

# Chạy bot
CMD ["python", "main.py"]
