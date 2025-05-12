pip freeze > requirements.txt
pip install -r requirements.txt

# [项目名称 - 请替换]

本项目是一个基于 Python 的小红书 App 自动化工具。它通过 Flask API 接收任务指令，使用 Firebase Firestore 作为任务队列和状态管理中心，并借助 Appium 在安卓模拟器或真实设备上执行具体的小红书应用内操作。

## ✨ 主要功能

* **API 驱动的任务提交**：通过 RESTful API 接口创建自动化任务。
* **灵活的任务参数**：支持如“抓取笔记” (`scrape_note`)、“抓取商品” (`scrape_product`) 等不同类型的自动化动作，并可根据关键词、滑动次数、筛选条件等参数进行定制。
* **Firebase Firestore 任务队列**：利用 Firestore 实现强大、实时的任务创建、分发和状态追踪。
* **Appium 自动化核心**：直接与安卓版小红书 App 进行交互，模拟用户操作。
* **异步并发处理任务**：能够监听并处理多个任务，通过多线程异步执行 Appium 操作（实际并行度取决于 Appium 环境配置）。
* **Pydantic 数据校验**：确保 API 请求参数的准确性和完整性。

## 🏗️ 系统架构

系统主要由以下几个核心组件构成：

1.  **Flask API 服务 (`api/`)**：
    * 提供 HTTP POST 接口（例如 `/tasks`）用于接收新的自动化任务请求。
    * 使用 Pydantic 模型对请求数据进行严格校验。
    * 验证通过后，将任务数据写入 Firebase Firestore 的 `tasks` 集合，并设置初始状态为 `pending`。
2.  **Firebase 任务监听器 (`listeners/`)**：
    * 实时监听 Firestore 中 `tasks` 集合内状态为 `pending` 的新任务。
    * 一旦检测到新任务，立即将其状态更新为 `processing`。
    * 在新的线程中调用相应的服务模块来执行具体的 Appium 自动化脚本。
3.  **Appium 自动化服务 (`services/` 及 `core/`)**：
    * `core/driver_manager.py`: 负责管理 Appium WebDriver 的会话生命周期（连接、关闭等）。
    * `services/*.py`: 包含针对不同任务类型（如笔记抓取、商品抓取）的 Appium 自动化操作实现逻辑。
4.  **Firebase Firestore 数据库**:
    * 作为系统的中央任务队列和数据存储。
    * 存储任务的详细参数、当前状态（pending, processing, completed, failed）、执行结果或错误信息。


## 🔧 环境准备

在开始之前，请确保你的开发环境满足以下要求：

* **Python**: 建议使用 3.8 或更高版本。
* **Node.js 和 npm/yarn**: 用于安装和管理 Appium Server。
* **Appium Server**: 例如 v2.x 版本。确保已安装所需的驱动 (如 `uiautomator2`)。
* **Android SDK**: 并已将 `adb` 工具的路径配置到系统环境变量 `PATH` 中。
* **安卓模拟器或真实安卓设备**:
    * 模拟器：推荐使用 Android Studio 自带的模拟器。
    * 真实设备：需开启“开发者选项”和“USB调试”功能。
* **Java JDK**: Appium 和 Android SDK 工具可能需要。
* **Firebase 项目**:
    * 已创建一个 Firebase 项目。
    * 在项目中启用了 Firestore 数据库。
* **小红书 App**: 已在目标模拟器/设备上安装。

## ⚙️ 安装与配置

1.  **克隆代码库**:
    ```bash
    git clone <你的代码库URL>
    cd <项目目录>
    ```

2.  **创建并激活 Python 虚拟环境**:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **安装 Python 依赖**:
    (请确保 `requirements.txt` 文件包含所有必要的库)
    ```bash
    pip install -r requirements.txt
    ```
    *主要依赖可能包括:*
    ```
    Flask
    pydantic
    firebase-admin
    Appium-Python-Client
    # 其他你项目中用到的库
    ```

4.  **配置 Firebase Admin SDK**:
    * 登录 Firebase 控制台。
    * 进入你的项目，导航到“项目设置” > “服务帐号”。
    * 生成新的私钥，下载对应的 JSON 文件。
    * 将下载的 JSON 文件重命名为 `firebase-service-account-key.json` 并放置在项目的根目录下。

5.  **配置 Appium 及安卓环境**:
    * **安装 Appium Server**:
        ```bash
        npm install -g appium # 或者 yarn global add appium
        # 安装uiautomator2驱动 (用于安卓自动化)
        appium driver install uiautomator2
        ```
    * **启动并配置安卓模拟器/设备**:
        * 通过 Android Studio 启动或创建模拟器。
        * 或连接已启用USB调试的真实安卓设备。
        * 在命令行中运行 `adb devices`，确保你的设备/模拟器被正确列出且状态为 `device`。
    * **Appium Capabilities 配置**:
        打开 `core/driver_manager.py` 文件。你可能需要根据你的具体环境修改 Appium 的 Desired Capabilities，例如：
        ```python
        DESIRED_CAPABILITIES = {
            'platformName': 'Android',
            'appium:platformVersion': '12.0', # 替换为你的安卓版本
            'appium:deviceName': '127.0.0.1:7555', # 替换为你的 adb device ID (模拟器通常是 emulator-xxxx 或 IP:Port)
            'appium:automationName': 'UiAutomator2',
            'appium:appPackage': 'com.xingin.xhs', # 小红书的包名
            'appium:appActivity': '.index.v2.IndexActivityV2', # 小红书的启动Activity
            'appium:noReset': True, # True 表示不重置应用状态
            # ... 其他你需要的 capabilities
        }
        ```
        **注意**: `appPackage` 和 `appActivity` 可能因小红书版本更新而改变，请确认其准确性。

## ▶️ 运行应用

请按照以下推荐顺序启动各个组件：

1.  **启动 Appium Server**:
    打开一个新的终端窗口，输入 `appium` 命令启动 Appium Server。请留意其监听的地址和端口（默认为 `http://127.0.0.1:4723`）。

2.  **启动并准备安卓模拟器/设备**:
    确保你的安卓模拟器已启动并运行，或真实设备已通过 USB 连接并授权调试。设备需能被 `adb devices` 命令检测到。

3.  **启动 Firebase 任务监听器**:
    在项目根目录下，打开一个新的终端窗口（已激活虚拟环境），运行：
    ```bash
    python listeners/firebase_task_listener.py
    ```
    你应该会看到类似 "正在监听 Firestore..." 的日志。

4.  **启动 Flask API 服务**:
    在项目根目录下，再打开一个新的终端窗口（已激活虚拟环境），运行：
    ```bash
    python -m api.app
    ```
    API 服务默认会在 `http://127.0.0.1:5000` 上运行。

## 🚀 使用说明 (API调用示例)

你可以使用 `curl` 或 Postman 等工具向 Flask API 发送 POST 请求来创建任务。

**请求头**: `Content-Type: application/json`

**请求地址**: `http://127.0.0.1:5000/tasks`

**1. 创建 "抓取笔记" (`scrape_note`) 任务**

* **请求体 (JSON)**:
    ```json
    {
        "actions": "scrape_note",
        "parameters": {
            "keyword": "美食教程",
            "swipe_count": 5,
            "filters": {
                "category": "烹饪"
            }
        }
    }
    ```
* **curl 示例 (Windows cmd)**:
    ```cmd
    curl -X POST -H "Content-Type: application/json" -d "{\"actions\":\"scrape_note\",\"parameters\":{\"keyword\":\"美食教程\",\"swipe_count\":5,\"filters\":{\"category\":\"烹饪\"}}}" [http://127.0.0.1:5000/tasks](http://127.0.0.1:5000/tasks)
    ```
* **curl 示例 (PowerShell 或 macOS/Linux)**:
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"actions":"scrape_note","parameters":{"keyword":"美食教程","swipe_count":5,"filters":{"category":"烹饪"}}}' [http://127.0.0.1:5000/tasks](http://127.0.0.1:5000/tasks)
    ```

**2. 创建 "抓取商品" (`scrape_product`) 任务**

* **请求体 (JSON)**:
    ```json
    {
        "actions": "scrape_product",
        "parameters": {
            "keyword": "蓝牙耳机",
            "swipe_count": 3
        }
    }
    ```
* **curl 示例 (PowerShell 或 macOS/Linux)**:
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"actions":"scrape_product","parameters":{"keyword":"蓝牙耳机","swipe_count":3}}' [http://127.0.0.1:5000/tasks](http://127.0.0.1:5000/tasks)
    ```

**成功响应示例 (HTTP 201 Created)**:
```json
{
  "message": "任务创建成功",
  "taskId": "生成的任务ID"
}