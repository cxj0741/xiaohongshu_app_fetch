# 使用官方 Python 运行时作为父镜像
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    # 下面这两个环境变量会让容器内的 adb 客户端尝试连接到主机的 ADB 服务
    ANDROID_ADB_SERVER_ADDRESS=172.17.0.1 \
    ANDROID_ADB_SERVER_PORT=5037 \
    # 这个环境变量用于在 Python 脚本中判断是否在 Docker 环境运行
    IS_IN_DOCKER_CONTAINER=true

# 设置容器内的工作目录
WORKDIR /app

# 安装 ADB 工具和其他可能需要的系统依赖
# 对于 debian/ubuntu-based 镜像 (如 python:3.11-slim)
# apt-get update && apt-get install -y --no-install-recommends <packages> && rm -rf /var/lib/apt/lists/*
# 是一个标准的安装模式，可以减少镜像大小
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        adb \
        # 如果您的脚本还需要其他系统工具，可以在这里添加，例如 procps (用于ps命令等)
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件 (requirements.txt 应该在 XIAOHONGSHUZDH 项目的根目录下)
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
