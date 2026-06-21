FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装项目
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY knowledge/ ./knowledge/
COPY style/ ./style/

RUN pip install --no-cache-dir -e ".[all]"

# 默认命令
ENTRYPOINT ["qiushi"]
CMD ["--help"]
