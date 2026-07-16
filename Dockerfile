# STAGE 1: Build Dependencies and C++ Engine.
FROM python:3.12-slim AS builder

# Install system compilation dependencies.
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    unzip \
    libopencv-dev \
    libportaudio2 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a virtual environment for isolating dependencies.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies inside the virtual environment.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Download Vosk voice model (cached as it is quite heavy).
RUN mkdir -p /app/src/voice/models && \
    cd /app/src/voice/models && \
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip && \
    unzip -q vosk-model-small-ru-0.22.zip && \
    rm vosk-model-small-ru-0.22.zip

# Copy C++ extension source code and build script.
COPY setup.py .
COPY src/core/video_engine.cpp src/core/

# Compile C++ extension inside the virtual environment.
RUN python setup.py build_ext --inplace


# STAGE 2: Lightweight Runtime Image.
FROM python:3.12-slim

# Install system runtime libraries (no compilers or dev headers).
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libportaudio2 \
    libopencv-core4.6 \
    libopencv-imgproc4.6 \
    libopencv-videoio4.6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copy virtual environment with Python packages from builder stage.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 2. Copy the offline Vosk voice model from builder stage.
COPY --from=builder /app/src/voice/models/ /app/src/voice/models/

# 3. Copy application source code.
COPY src/ src/
COPY main.py .

# 4. Copy the compiled C++ shared library over to the src/core directory.
# This ensures the compiled binary isn't overwritten by stage steps.
COPY --from=builder /app/src/core/video_engine*.so /app/src/core/

# Create a non-privileged user for security purposes.
RUN useradd -m -u 1000 guardian && chown -R guardian:guardian /app
USER guardian

ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:0

EXPOSE 5000

CMD ["python", "main.py", "--web", "--host", "0.0.0.0", "--port", "5000"]
