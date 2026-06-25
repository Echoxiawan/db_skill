# db-inspector MCP 服务镜像
# 以 streamable-http 模式运行，供 MCP 客户端通过 HTTP 连接。
FROM python:3.12-slim

# 不写 .pyc、日志实时刷出
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先单独拷依赖清单，利用 Docker 层缓存（依赖不变时不重装）
COPY scripts/requirements.txt /app/scripts/requirements.txt
RUN pip install --no-cache-dir -r /app/scripts/requirements.txt

# 再拷脚本
COPY scripts/ /app/scripts/

# 容器内默认配置：
# - 绑 0.0.0.0 才能让宿主机/外部访问到端口
# - 连接信息 + 自签证书存到 /data（挂卷持久化），而非容器内 home
# - 传输默认 streamable-http
# - 默认开启 TLS：未给证书时自动生成自签证书到 /data/certs（重启复用）
ENV DB_MCP_HOST=0.0.0.0 \
    DB_MCP_PORT=8765 \
    DB_MCP_TRANSPORT=streamable-http \
    DB_MCP_TLS=true \
    DB_SKILL_HOME=/data

# 持久化连接信息的目录
VOLUME ["/data"]
RUN mkdir -p /data

EXPOSE 8765

# streamable-http (HTTPS) 端点：https://<host>:8765/mcp
CMD ["python3", "scripts/mcp_server.py"]
