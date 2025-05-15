# 使用官方 Python 运行时作为父镜像 (请根据您的项目选择合适的 Python 版本，例如 3.9, 3.10 等)
FROM python:3.9-slim

# 设置环境变量，确保 Python 输出是无缓冲的，便于在 Docker 日志中实时查看
ENV PYTHONUNBUFFERED=1

# 设置容器内的工作目录
WORKDIR /app

# 复制依赖文件 (requirements.txt 应该在 XIAOHONGSHUZDH 项目的根目录下)
# 如果您的 requirements.txt 在其他位置，请相应调整路径
COPY requirements.txt .

# 安装项目依赖
# --no-cache-dir 选项可以减少镜像大小
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目中的所有文件和文件夹到容器的 /app 工作目录
# 这将包括 listeners 模块, appium_configs 文件夹, firebase-service-account-key.json, .env 文件等
COPY . .

# 容器启动时执行的命令
# 运行 listeners 包下的 firebase_task_listener 模块
CMD ["python", "-m", "listeners.firebase_task_listener"]
