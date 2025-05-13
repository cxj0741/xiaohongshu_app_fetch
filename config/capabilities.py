# config/capabilities.py
from appium.options.android import UiAutomator2Options
import os

# 从环境变量中获取值，如果未设置，则使用提供的默认值
APPIUM_SERVER_URL = os.getenv('APPIUM_SERVER_URL', 'http://127.0.0.1:4723') # 默认值

# 默认设备配置 (这些可以被函数参数覆盖)
DEFAULT_DEVICE_NAME_ENV = os.getenv('DEFAULT_DEVICE_NAME', "127.0.0.1:7555") # 您可以根据需要修改默认值
DEFAULT_PLATFORM_VERSION_ENV = os.getenv('DEFAULT_PLATFORM_VERSION', "12.0")

# 小红书应用信息
XHS_APP_PACKAGE_ENV = os.getenv('XHS_APP_PACKAGE', "com.xingin.xhs")
XHS_APP_ACTIVITY_ENV = os.getenv('XHS_APP_ACTIVITY', ".index.v2.IndexActivityV2") # 请再次确认

# 其他 Appium Capabilities (从 .env 读取的是字符串, 需要转换类型)
# 对于布尔值，比较字符串
# 您强调 APPIUM_NO_RESET_ENV 需要为 True 以保持登录状态，这里的默认值 'True' 保证了这一点
APPIUM_NO_RESET_ENV = os.getenv('APPIUM_NO_RESET', 'True').lower() == 'true'
# 对于整数，进行转换
APPIUM_NEW_COMMAND_TIMEOUT_ENV = int(os.getenv('APPIUM_NEW_COMMAND_TIMEOUT', 3600))

def get_xiaohongshu_capabilities(
    device_name=None, 
    platform_version=None,
    app_package=None, 
    app_activity=None,
    no_reset=None,  # 新增参数，允许覆盖全局的 APPIUM_NO_RESET_ENV
    new_command_timeout=None, # 新增参数，允许覆盖全局的 APPIUM_NEW_COMMAND_TIMEOUT_ENV
    system_port=None, # <<<< 新增参数
    chromedriver_port=None # <<<< 新增参数
):
    """
    获取小红书应用的 Desired Capabilities。
    允许通过函数参数覆盖环境变量或此处定义的默认值。
    """

    # 处理 no_reset: 优先使用传入的参数，否则使用环境变量的默认值
    if no_reset is None:
        actual_no_reset = APPIUM_NO_RESET_ENV
    else:
        # 确保传入的 no_reset (如果不是None) 被正确转换为布尔值
        actual_no_reset = str(no_reset).lower() == 'true'
    
    # 处理 new_command_timeout: 优先使用传入的参数，否则使用环境变量的默认值
    if new_command_timeout is None:
        actual_new_command_timeout = APPIUM_NEW_COMMAND_TIMEOUT_ENV
    else:
        actual_new_command_timeout = int(new_command_timeout) # 确保传入的是整数

    caps = {
        "platformName": "Android",
        "appium:platformVersion": platform_version if platform_version else DEFAULT_PLATFORM_VERSION_ENV,
        "appium:deviceName": device_name if device_name else DEFAULT_DEVICE_NAME_ENV,
        "appium:automationName": "UiAutomator2",
        "appium:appPackage": app_package if app_package else XHS_APP_PACKAGE_ENV,
        "appium:appActivity": app_activity if app_activity else XHS_APP_ACTIVITY_ENV,
        "appium:noReset": actual_no_reset, # 使用处理后的 actual_no_reset
        "appium:ensureWebviewsHavePages": True,
        "appium:nativeWebScreenshot": True,
        "appium:newCommandTimeout": actual_new_command_timeout, # 使用处理后的 actual_new_command_timeout
        "appium:connectHardwareKeyboard": True
    }

    # 如果函数参数中提供了 system_port，则添加到 capabilities 中
    if system_port is not None:
        caps["appium:systemPort"] = int(system_port) # systemPort 应为整数

    # 如果函数参数中提供了 chromedriver_port，则添加到 capabilities 中
    if chromedriver_port is not None:
        caps["appium:chromedriverPort"] = int(chromedriver_port) # chromedriverPort 应为整数
        
    return UiAutomator2Options().load_capabilities(caps)