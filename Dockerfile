# Hugging Face Spaces (Docker SDK) 部署用镜像
FROM python:3.12-slim

# scipy / numpy 运行期需要的系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目（含本地 alphalens 源码与数据素材）
COPY . .

# HF Spaces 默认暴露 7860
ENV PORT=7860
EXPOSE 7860

# 启动 FastAPI
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
