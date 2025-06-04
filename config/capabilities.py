# config/capabilities.py
from appium.options.android import UiAutomator2Options
import os

# 从环境变量中获取值，如果未设置，则使用提供的默认值
APPIUM_SERVER_URL = os.getenv('APPIUM_SERVER_URL', 'http://192.168.0.102:4723') # 默认值

# 默认设备配置 (这些可以被函数参数覆盖)
# 将默认设备ID设置为空字符串，强制要求显式指定
DEFAULT_DEVICE_NAME_ENV = os.getenv('DEFAULT_DEVICE_NAME', "")  # 修改为空字符串
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
    no_reset=None,
    new_command_timeout=None,
    system_port=None,
    chromedriver_port=None,
    wda_local_port=None,
    **extra_caps  # 添加这个参数来接收任何额外的capabilities
):
    """
    获取小红书应用的 Desired Capabilities。
    允许通过函数参数覆盖环境变量或此处定义的默认值。
    
    :param extra_caps: 接收任何额外的capability参数，会直接添加到capabilities中
    """
    # 确保device_name参数是必须的
    if not device_name:
        raise ValueError("必须指定device_name参数")

    # 处理 no_reset
    if no_reset is None:
        actual_no_reset = APPIUM_NO_RESET_ENV
    else:
        actual_no_reset = str(no_reset).lower() == 'true'
    
    # 处理 new_command_timeout
    if new_command_timeout is None:
        actual_new_command_timeout = APPIUM_NEW_COMMAND_TIMEOUT_ENV
    else:
        actual_new_command_timeout = int(new_command_timeout)

    caps = {
        "platformName": "Android",
        "appium:platformVersion": platform_version if platform_version else DEFAULT_PLATFORM_VERSION_ENV,
        "appium:deviceName": device_name,  # 直接使用传入的device_name，不再使用默认值
        "appium:automationName": "UiAutomator2",
        "appium:appPackage": app_package if app_package else XHS_APP_PACKAGE_ENV,
        "appium:appActivity": app_activity if app_activity else XHS_APP_ACTIVITY_ENV,
        "appium:noReset": actual_no_reset,
        "appium:ensureWebviewsHavePages": True,
        "appium:nativeWebScreenshot": True,
        "appium:newCommandTimeout": actual_new_command_timeout,
        "appium:connectHardwareKeyboard": True,
        # 添加明确指定设备的附加参数
        "appium:udid": device_name  # 添加udid参数，显式指定要连接的设备
    }

    # 添加特定端口配置
    if system_port is not None:
        caps["appium:systemPort"] = int(system_port)
    if chromedriver_port is not None:
        caps["appium:chromedriverPort"] = int(chromedriver_port)
    if wda_local_port is not None:
        caps["appium:wdaLocalPort"] = int(wda_local_port)
        
    # 处理额外的capabilities参数
    for key, value in extra_caps.items():
        # 添加appium:前缀（如果需要）
        caps_key = f"appium:{key}" if not key.startswith("appium:") else key
        caps[caps_key] = value
        
    print(f"最终capabilities配置: {caps}")
    return UiAutomator2Options().load_capabilities(caps)