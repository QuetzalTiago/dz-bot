FROM python:3.11.9-bookworm

WORKDIR /app

RUN apt update && apt install -y ffmpeg

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
