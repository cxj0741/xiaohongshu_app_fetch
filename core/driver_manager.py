import time
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
                  system_port=None, chromedriver_port=None):
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
            "system_port": system_port,               # <<<< 将参数存起来
            "chromedriver_port": chromedriver_port    # <<<< 将参数存起来
        }
        # 移除值为 None 的参数，以便 get_xiaohongshu_capabilities 中的默认值生效
        self.capabilities_args = {k: v for k, v in self.capabilities_args.items() if v is not None}


    def __enter__(self):
        """
        当进入 'with' 语句块时调用。
        负责创建和返回 WebDriver 实例。
        """
        print("AppiumDriverContextManager: 准备初始化 WebDriver...")
        try:
            options = get_xiaohongshu_capabilities(**self.capabilities_args)
            print(f"AppiumDriverContextManager: 使用 capabilities: {options.to_capabilities()}")
            print(f"AppiumDriverContextManager: 连接到 Appium Server URL: {self.server_url}")

            self.driver = webdriver.Remote(
                command_executor=self.server_url,
                options=options
            )
            print("AppiumDriverContextManager: WebDriver 初始化成功，应用已启动。")
            # 你可以在这里添加一个短暂的等待，以确保应用完全加载
            # 对于实际操作，更推荐使用显式等待 (WebDriverWait)
            time.sleep(8) # 例如，等待8秒让应用稳定
            return self.driver # 将 driver 实例返回给 'with ... as driver:' 中的 'driver'
        except Exception as e:
            print(f"AppiumDriverContextManager: WebDriver 初始化失败: {e}")
            # 如果初始化失败，确保 driver 保持为 None，并在 __exit__ 中不会尝试 quit
            self.driver = None # 确保 driver 是 None
            raise # 重新抛出异常，以便 with 块外部可以捕获到

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        当退出 'with' 语句块时调用（无论正常退出还是因异常退出）。
        负责关闭 WebDriver 会话。
        exc_type, exc_val, exc_tb 包含异常信息（如果 with 块内发生异常）。
        """
        print("AppiumDriverContextManager: 准备关闭 WebDriver...")
        if self.driver:
            try:
                self.driver.quit()
                print("AppiumDriverContextManager: WebDriver 会话已成功关闭。")
            except Exception as e:
                print(f"AppiumDriverContextManager: 关闭 WebDriver 时发生错误: {e}")
        else:
            print("AppiumDriverContextManager: WebDriver 未初始化或已关闭，无需操作。")

        # 如果返回 True，则表示异常已被处理，不会向上传播。
        # 通常在资源清理中，我们希望异常继续传播，所以返回 False 或不返回（默认为 None，等效于 False）。
        return False # 确保 with 块中的异常（如果有的话）会继续向外抛出