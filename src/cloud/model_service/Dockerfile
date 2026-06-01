FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    YOLOV5_CONFIG_DIR=/tmp/yolov5 \
    MPLCONFIGDIR=/tmp/matplotlib \
    YOLOv5_AUTOINSTALL=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --no-deps onnx==1.16.1 onnx2torch==1.5.15

COPY app.py .

CMD exec gunicorn --bind :${PORT:-8080} --timeout 900 --workers 1 --threads 1 app:app
