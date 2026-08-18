FROM python:3.11-slim

# Install Linux native ADB and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    android-tools-adb \
    usbutils \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Dynamic port for Render
ENV PORT=8050
ENV PYTHONUNBUFFERED=1
ENV SMS_STUDIO_WORKER=1

EXPOSE 8050

CMD ["python", "sms_studio.py"]
