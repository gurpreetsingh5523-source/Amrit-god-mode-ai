FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git curl ffmpeg libsm6 libxext6 tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p workspace datasets experiments logs
CMD ["python", "main.py", "--mode", "interactive"]
