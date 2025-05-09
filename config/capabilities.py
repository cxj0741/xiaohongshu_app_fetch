# config/capabilities.py
from appium.options.android import UiAutomator2Options
import os

# 从环境变量中获取值，如果未设置，则使用提供的默认值
APPIUM_SERVER_URL = os.getenv('APPIUM_SERVER_URL', 'http://127.0.0.1:4723') # 默认值

# 默认设备配置 (这些可以被函数参数覆盖)
DEFAULT_DEVICE_NAME_ENV = os.getenv('DEFAULT_DEVICE_NAME', "127.0.0.1:7555")
DEFAULT_PLATFORM_VERSION_ENV = os.getenv('DEFAULT_PLATFORM_VERSION', "12.0")

# 小红书应用信息
XHS_APP_PACKAGE_ENV = os.getenv('XHS_APP_PACKAGE', "com.xingin.xhs")
XHS_APP_ACTIVITY_ENV = os.getenv('XHS_APP_ACTIVITY', ".index.v2.IndexActivityV2") # 请再次确认

# 其他 Appium Capabilities (从 .env 读取的是字符串, 需要转换类型)
# 对于布尔值，比较字符串
APPIUM_NO_RESET_ENV = os.getenv('APPIUM_NO_RESET', 'True').lower() == 'true'
# 对于整数，进行转换
APPIUM_NEW_COMMAND_TIMEOUT_ENV = int(os.getenv('APPIUM_NEW_COMMAND_TIMEOUT', 3600))

def get_xiaohongshu_capabilities(device_name=None, platform_version=None,
                                app_package=None, app_activity=None):
    """
    获取小红书应用的 Desired Capabilities。
    允许通过函数参数覆盖 .env 文件中或此处定义的默认值。
    """
    caps = {
        "platformName": "Android",
        "appium:platformVersion": platform_version if platform_version else DEFAULT_PLATFORM_VERSION_ENV,
        "appium:deviceName": device_name if device_name else DEFAULT_DEVICE_NAME_ENV,
        "appium:automationName": "UiAutomator2",
        "appium:appPackage": app_package if app_package else XHS_APP_PACKAGE_ENV,
        "appium:appActivity": app_activity if app_activity else XHS_APP_ACTIVITY_ENV,
        "appium:noReset": APPIUM_NO_RESET_ENV, # 使用从 .env 加载并转换后的值
        "appium:ensureWebviewsHavePages": True,
        "appium:nativeWebScreenshot": True,
        "appium:newCommandTimeout": APPIUM_NEW_COMMAND_TIMEOUT_ENV, # 使用从 .env 加载并转换后的值
        "appium:connectHardwareKeyboard": True
    }
    return UiAutomator2Options().load_capabilities(caps)