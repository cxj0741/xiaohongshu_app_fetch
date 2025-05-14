import time
import subprocess
from appium import webdriver
# 假设你的 capabilities 配置在 config.capabilities 模块中
# 你需要确保这个导入路径根据你的项目结构是正确的
from config.capabilities import get_xiaohongshu_capabilities, APPIUM_SERVER_URL


# todo无法使用程序启动小红书
class AppiumDriverContextManager:
    """
    一个 Appium WebDriver 上下文管理器类，用于自动创建和关闭 driver 会话。
    可以通过 with 语句使用。
    """
    def __init__(self, device_name=None, platform_version=None,
                 app_package=None, app_activity=None, no_reset=None,
                 new_command_timeout=None, server_url=None,
                  system_port=None, chromedriver_port=None, wda_local_port=None):
        """
        初始化会话管理器。
        参数可以覆盖从 .env 或 config 文件中加载的默认配置。
        """
        self.driver = None
        self.server_url = server_url if server_url else APPIUM_SERVER_URL

        # 将参数存储起来，以便在 __enter__ 中使用
        self.capabilities_args = {
            "device_name": device_name,
            "platform_version": platform_version,
            "app_package": app_package,
            "app_activity": app_activity,
            "no_reset": no_reset,
            "new_command_timeout": new_command_timeout,
            "system_port": system_port,
            "chromedriver_port": chromedriver_port,
            "wda_local_port": wda_local_port
        }
        # 移除值为 None 的参数，以便 get_xiaohongshu_capabilities 中的默认值生效
        self.capabilities_args = {k: v for k, v in self.capabilities_args.items() if v is not None}

    def _try_cleanup_uiautomator(self, device_id):
        """尝试清理可能崩溃的UiAutomator2服务"""
        try:
            print(f"尝试清理设备 {device_id} 上的UiAutomator服务...")
            subprocess.run([
                'adb', '-s', device_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server'
            ], timeout=5)
            subprocess.run([
                'adb', '-s', device_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server.test'
            ], timeout=5)
            time.sleep(2)
            print(f"UiAutomator服务清理完成")
        except Exception as e:
            print(f"清理UiAutomator服务时出错: {e}")

    def __enter__(self):
        """
        当进入 'with' 语句块时调用。
        负责创建和返回 WebDriver 实例。
        """
        print("AppiumDriverContextManager: 准备初始化 WebDriver...")
        try:
            # 预先清理UiAutomator2服务
            if self.capabilities_args.get("device_name"):
                self._try_cleanup_uiautomator(self.capabilities_args["device_name"])
            
            # 添加UiAutomator2服务重置选项，保证稳定性（注意：移除'appium:'前缀）
            stability_options = {
                "skipServerInstallation": False,  # 强制重新安装UiAutomator2服务
                "dontStopAppOnReset": True,      # 不停止应用
                "fullReset": False,              # 不完全重置应用
                "adbExecTimeout": 60000,         # 增加ADB超时时间
                "uiautomator2ServerInstallTimeout": 120000,  # 增加安装超时
                "uiautomator2ServerLaunchTimeout": 60000,    # 增加启动超时
                "relaxedSecurity": True          # 放宽安全限制
            }
            
            # 将稳定性选项合并到capabilities中
            self.capabilities_args.update(stability_options)
            
            options = get_xiaohongshu_capabilities(**self.capabilities_args)
            print(f"AppiumDriverContextManager: 使用 capabilities: {options.to_capabilities()}")
            print(f"AppiumDriverContextManager: 连接到 Appium Server URL: {self.server_url}")

            # 尝试3次初始化WebDriver，增加稳定性
            max_attempts = 3
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    self.driver = webdriver.Remote(
                        command_executor=self.server_url,
                        options=options
                    )
                    print(f"AppiumDriverContextManager: WebDriver 初始化成功 (尝试 {attempt+1}/{max_attempts})，应用已启动。")
                    # 增加App启动后的等待时间，确保UI完全加载
                    time.sleep(10)  # 从8秒增加到10秒
                    return self.driver
                except Exception as e:
                    last_error = e
                    print(f"AppiumDriverContextManager: 第{attempt+1}次初始化失败: {e}")
                    if attempt < max_attempts - 1:  # 不是最后一次尝试
                        time.sleep(5)  # 失败后等待5秒再试
            
            # 所有尝试都失败
            print(f"AppiumDriverContextManager: 所有{max_attempts}次尝试都失败: {last_error}")
            self.driver = None
            raise last_error
        except Exception as e:
            print(f"AppiumDriverContextManager: WebDriver 初始化失败: {e}")
            self.driver = None
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        当退出 'with' 语句块时调用（无论正常退出还是因异常退出）。
        负责关闭 WebDriver 会话。
        exc_type, exc_val, exc_tb 包含异常信息（如果 with 块内发生异常）。
        """
        print("AppiumDriverContextManager: 准备关闭 WebDriver...")
        if self.driver:
            try:
                # 使用初始化时提供的设备ID，这是最可靠的
                device_id = self.capabilities_args.get("device_name")
                
                # 如果没有在初始化时提供，尝试从driver.capabilities获取
                if not device_id:
                    try:
                        # 尝试多种方式获取设备ID
                        if hasattr(self.driver, 'capabilities'):
                            if 'deviceName' in self.driver.capabilities:
                                device_id = self.driver.capabilities['deviceName']
                            elif 'appium:deviceName' in self.driver.capabilities:
                                device_id = self.driver.capabilities['appium:deviceName']
                    except Exception as e:
                        print(f"AppiumDriverContextManager: 获取设备ID时出错: {e}")
                
                # 关闭driver会话
                self.driver.quit()
                print("AppiumDriverContextManager: WebDriver 会话已成功关闭。")
                
                # 会话结束后再次清理UiAutomator2服务，确保下次干净启动
                if device_id:
                    print(f"AppiumDriverContextManager: 清理设备 {device_id} 的UiAutomator2服务")
                    self._try_cleanup_uiautomator(device_id)
                else:
                    print("AppiumDriverContextManager: 无法获取设备ID，跳过UiAutomator2服务清理")
            except Exception as e:
                print(f"AppiumDriverContextManager: 关闭 WebDriver 时发生错误: {e}")
        else:
            print("AppiumDriverContextManager: WebDriver 未初始化或已关闭，无需操作。")

        # 如果返回 True，则表示异常已被处理，不会向上传播。
        # 通常在资源清理中，我们希望异常继续传播，所以返回 False 或不返回（默认为 None，等效于 False）。
        return False # 确保 with 块中的异常（如果有的话）会继续向外抛出