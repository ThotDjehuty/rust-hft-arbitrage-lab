FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl git pkg-config libffi-dev && rm -rf /var/lib/apt/lists/*
COPY docker/requirements.txt /app/docker/requirements.txt
RUN pip install --no-cache-dir -r /app/docker/requirements.txt
COPY . /app
EXPOSE 8888
CMD ["bash", "scripts/start_jupyter.sh"]
