FROM python:3.12-slim
WORKDIR /usr/src/zendure
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p utils
COPY collector.py .
USER 65534:65534
CMD ["python", "-u", "collector.py"]
