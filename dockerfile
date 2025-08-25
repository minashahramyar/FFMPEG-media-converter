FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Create logs dir
RUN mkdir -p /app/logs

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]