# 文件名: product_actions.py
# 注意：请确保此文件与 app_actions.py 在同一目录，或 app_actions.py 路径在 PYTHONPATH 中
# 以便下面的导入能够成功。如果目录结构不同，请调整导入语句。
# from app_actions import click_filter_option
# 如果 app_actions 在上一级目录的 core 子目录中，可以尝试:
# from ..core.app_actions import click_filter_option

import time
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 尝试导入你自定义的 click_filter_option 函数
# 你需要确保 app_actions.py 文件和这个文件在同一个Python查找路径下
# 如果你的 app_actions.py 在一个名为 core 的文件夹下，并且这个文件也在 core 里，可能是 from .app_actions import click_filter_option
# 如果这个文件在 core 外面，而 app_actions.py 在 core 里面，可能是 from core.app_actions import click_filter_option
# 这里假设它们在同一目录或 app_actions 已在可导入路径
try:
    from app_actions import click_filter_option
except ImportError:
    print("错误：无法从 app_actions.py 导入 click_filter_option。请确保文件路径正确。")
    print("将使用一个简化的内部点击方法作为替代，但这可能不如你原来的方法健壮。")
    # 如果导入失败，提供一个非常基础的替代方案（不推荐长期使用）
    def click_filter_option(driver, option_text_or_desc, timeout=5):
        print(f"  [备用点击方法] 尝试点击: '{option_text_or_desc}'")
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, f"//*[@text='{option_text_or_desc}']"))
            )
            el.click()
            time.sleep(1.5)
            return True
        except Exception as e_fallback:
            print(f"  [备用点击方法] 点击 '{option_text_or_desc}' 失败: {e_fallback}")
            return False

class ProductFilterPanel:

    # --- 把选项常量定义为类属性 ---
    SORT_COMPREHENSIVE = "综合"
    SORT_SALES_PRIORITY = "销量优先"
    SORT_PRICE_ASC = "价格升序"
    SORT_PRICE_DESC = "价格降序"
    
    SERVICE_RETURN_SHIPPING = "退货包运费"
    SERVICE_SHIPS_24H = "24小时发货"
    SERVICE_PRICE_GUARANTEE = "买贵必赔"
    # ... 其他物流权益选项的文本 ...

    SCOPE_LIVE_STREAMING = "直播中"
    SCOPE_BOUGHT_STORES = "买过的店"
    SCOPE_FOLLOWED_STORES = "关注的店"
    SCOPE_FLAGSHIP_STORE = "旗舰店"
    # ... 其他搜索范围选项的文本 ...
    def __init__(self, driver, logger):
        self.driver = driver
        self.logger = logger # 使用传入的logger实例

        # --- 定位器 ---
        # 打开筛选面板的按钮（漏斗图标） - 你之前确认的XPath
        self.FILTER_ICON_XPATH = '//android.widget.RelativeLayout[@resource-id="com.xingin.xhs:id/0_resource_name_obfuscated"]'
        
        # 面板打开后的特征元素 (用于确认面板已打开)
        self.PANEL_INDICATOR_XPATH = "//*[@text='排序依据']" # 筛选面板的稳定文本元素
       

        # 价格区间输入框 (这些XPath是占位符，你需要用Appium Inspector找到准确的定位器!)
        self.MIN_PRICE_INPUT_XPATH = "//android.widget.EditText[contains(@text,'最低价') or preceding-sibling::android.widget.TextView[@text='最低价'] or count(preceding-sibling::android.widget.EditText)=0 and ancestor::*[android.widget.TextView[@text='价格区间']]]" # 极度依赖UI结构，需替换
        self.MAX_PRICE_INPUT_XPATH = "//android.widget.EditText[contains(@text,'最高价') or preceding-sibling::android.widget.TextView[@text='最高价'] or count(preceding-sibling::android.widget.EditText)=1 and ancestor::*[android.widget.TextView[@text='价格区间']]]" # 极度依赖UI结构，需替换
        
        # 底部按钮 (这些XPath是占位符，你需要用Appium Inspector找到准确的定位器!)
        self.RESET_BUTTON_XPATH = "//*[@text='重置']" 
        self.CONFIRM_BUTTON_XPATH = "//*[@text='完成']" # 商品筛选通常是“完成”

    def open_panel(self, timeout=10):
        self.logger.info("尝试打开商品筛选面板...")
        try:
            filter_button_element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, self.FILTER_ICON_XPATH))
            )
            filter_button_element.click()
            # 确认面板已打开
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((AppiumBy.XPATH, self.PANEL_INDICATOR_XPATH))
            )
            self.logger.info("商品筛选面板已成功打开。")
            return True
        except TimeoutException:
            self.logger.error(f"打开商品筛选面板超时或指示元素 '{self.PANEL_INDICATOR_XPATH}' 未找到。使用的筛选图标XPath: {self.FILTER_ICON_XPATH}")
            return False
        except Exception as e:
            self.logger.error(f"打开商品筛选面板时发生错误: {e}", exc_info=True)
            return False

    def _click_filter_option_wrapper(self, option_text_or_desc, timeout=5):
        """封装对外部 click_filter_option 的调用，并使用自身的logger"""
        self.logger.info(f"准备点击筛选选项: '{option_text_or_desc}' (通过复用的 click_filter_option)")
        try:
            # 这里调用的是从 app_actions.py 导入的 click_filter_option 函数
            # 注意：如果 click_filter_option 内部使用了 print，那些输出不会通过这里的 logger
            success = click_filter_option(self.driver, option_text_or_desc, timeout)
            if success:
                self.logger.info(f"click_filter_option 报告成功点击: '{option_text_or_desc}'")
            else:
                self.logger.warning(f"click_filter_option 报告未能点击: '{option_text_or_desc}'")
            return success
        except Exception as e:
            self.logger.error(f"调用 click_filter_option 点击 '{option_text_or_desc}' 时发生异常: {e}", exc_info=True)
            return False

    def set_sort_by(self, sort_option_text, timeout=5):
        self.logger.info(f"设置商品排序方式为: '{sort_option_text}'")
        return self._click_filter_option_wrapper(sort_option_text, timeout)

    def select_logistics_service(self, service_option_text, timeout=5):
        self.logger.info(f"选择物流与权益: '{service_option_text}'")
        return self._click_filter_option_wrapper(service_option_text, timeout)
        
    def select_search_scope(self, scope_option_text, timeout=5):
        self.logger.info(f"选择搜索范围: '{scope_option_text}'")
        return self._click_filter_option_wrapper(scope_option_text, timeout)

    def set_price_range(self, min_price=None, max_price=None, timeout=5):
        self.logger.info(f"设置价格区间: 最低价='{min_price}', 最高价='{max_price}'")
        try:
            if min_price is not None:
                self.logger.debug(f"尝试定位最低价输入框: {self.MIN_PRICE_INPUT_XPATH}")
                min_input = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((AppiumBy.XPATH, self.MIN_PRICE_INPUT_XPATH))
                )
                min_input.click() # 点击以聚焦，某些情况下可能需要
                min_input.clear()
                min_input.send_keys(str(min_price))
                self.logger.info(f"已输入最低价: {min_price}")
                # self.driver.hide_keyboard() # 如果键盘弹出，可能需要隐藏
                time.sleep(0.5)

            if max_price is not None:
                self.logger.debug(f"尝试定位最高价输入框: {self.MAX_PRICE_INPUT_XPATH}")
                max_input = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((AppiumBy.XPATH, self.MAX_PRICE_INPUT_XPATH))
                )
                max_input.click() # 点击以聚焦
                max_input.clear()
                max_input.send_keys(str(max_price))
                self.logger.info(f"已输入最高价: {max_price}")
                # self.driver.hide_keyboard() # 如果键盘弹出，可能需要隐藏
                time.sleep(0.5)
            return True
        except Exception as e:
            self.logger.error(f"设置价格区间时发生错误: {e}", exc_info=True)
            return False

    def reset(self, timeout=5):
        self.logger.info("尝试重置商品筛选条件...")
        try:
            reset_button = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, self.RESET_BUTTON_XPATH))
            )
            reset_button.click()
            self.logger.info("已点击商品筛选重置按钮。")
            time.sleep(1.5) # 等待UI响应
            return True
        except Exception as e:
            self.logger.error(f"点击商品筛选重置按钮时发生错误: {e}", exc_info=True)
            return False

    def confirm(self, timeout=5):
        self.logger.info("尝试确认商品筛选条件并关闭面板...")
        try:
            confirm_button = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, self.CONFIRM_BUTTON_XPATH))
            )
            confirm_button.click()
            self.logger.info("已点击商品筛选完成按钮。")
            time.sleep(2.5) # 等待筛选应用和列表刷新
            return True
        except TimeoutException:
            self.logger.warning(f"商品筛选“完成”按钮在 {timeout} 秒内未找到或不可点击。可能筛选已即时应用或面板自动关闭。")
            return True # 在这种情况下也可能视为成功，因为面板可能已不存在
        except Exception as e:
            self.logger.error(f"点击商品筛选完成按钮时发生错误: {e}", exc_info=True)
            return False

    def apply_filters(self, 
                      sort_by=None, 
                      logistics_services=None, # 可以是单个字符串或字符串列表
                      search_scopes=None,    # 可以是单个字符串或字符串列表
                      min_price=None, 
                      max_price=None):
        """
        打开商品筛选面板并应用指定的筛选条件。
        """
        self.logger.info("开始应用商品聚合筛选...")
        if not self.open_panel():
            self.logger.error("未能打开商品筛选面板，筛选操作中止。")
            return False
        
        all_steps_successful = True

        if sort_by:
            if not self.set_sort_by(sort_by):
                all_steps_successful = False
                self.logger.warning(f"应用排序方式 '{sort_by}' 失败。")
        
        if logistics_services:
            services_to_apply = logistics_services if isinstance(logistics_services, list) else [logistics_services]
            for service in services_to_apply:
                if not self.select_logistics_service(service):
                    all_steps_successful = False
                    self.logger.warning(f"选择物流与权益 '{service}' 失败。")
        
        if search_scopes:
            scopes_to_apply = search_scopes if isinstance(search_scopes, list) else [search_scopes]
            for scope in scopes_to_apply:
                if not self.select_search_scope(scope):
                    all_steps_successful = False
                    self.logger.warning(f"选择搜索范围 '{scope}' 失败。")

        if min_price is not None or max_price is not None:
            if not self.set_price_range(min_price, max_price):
                all_steps_successful = False
                self.logger.warning("设置价格区间失败。")
            
        if not self.confirm():
            # 即使“完成”按钮点击失败（可能面板已自动关闭），也可能之前的操作已生效
            self.logger.warning("未能点击“完成”按钮，但之前的筛选可能已部分应用。")
            # all_steps_successful = False # 根据你的严格程度决定是否将此视为整体失败

        if all_steps_successful:
            self.logger.info("商品聚合筛选流程执行完毕。请检查实际筛选效果。")
        else:
            self.logger.warning("商品聚合筛选流程中部分步骤失败。请检查日志。")
            
        return all_steps_successful


# --- 示例：如何在你的主控制脚本中使用 (假设此文件名为 product_actions.py) ---
if __name__ == '__main__':
    # 这部分仅为演示如何使用，实际不会在mitmproxy脚本中这样运行
    # 你需要在你的 Appium 主控制脚本中实例化和调用
    
    # 假设你已经有了 driver 和 logger 对象
    # from appium import webdriver # 示例导入
    # import logging # 示例导入

    # capabilities = { ... } #你的 capabilities
    # driver = webdriver.Remote("http://localhost:4723/wd/hub", capabilities)
    
    # logger = logging.getLogger("MyTestLogger")
    # logger.setLevel(logging.DEBUG)
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.DEBUG)
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # console_handler.setFormatter(formatter)
    # logger.addHandler(console_handler)

    # class MockDriver: # 模拟 driver
    #     def find_element(self, by, value): print(f"模拟 find_element: {by} {value}"); return self
    #     def find_elements(self, by, value): print(f"模拟 find_elements: {by} {value}"); return [self]
    #     def click(self): print("模拟 click")
    #     def clear(self): print("模拟 clear")
    #     def send_keys(self, val): print(f"模拟 send_keys: {val}")
    #     def get_window_size(self): return {"width": 1080, "height": 1920}
    #     @property
    #     def location(self): return {'x': 100, 'y': 100}
    #     @property
    #     def size(self): return {'width': 50, 'height': 50}
    #     def get_attribute(self, attr): return "mock_attr"


    # print("\n--- 开始演示 ProductFilterPanel ---")
    # mock_driver = MockDriver()
    # test_logger = logger # 使用上面配置的 logger

    # product_filters = ProductFilterPanel(mock_driver, test_logger)

    # print("\n1. 演示打开面板 (假设筛选图标XPath能找到)")
    # # 模拟 open_panel 会用到真实的 WebDriverWait, 所以这里只演示后续步骤
    # # product_filters.open_panel() 

    # print("\n2. 演示设置排序方式")
    # product_filters.set_sort_by(product_filters.SORT_SALES_PRIORITY)

    # print("\n3. 演示选择物流服务")
    # product_filters.select_logistics_service(product_filters.SERVICE_RETURN_SHIPPING)
    
    # print("\n4. 演示选择搜索范围")
    # product_filters.select_search_scope(product_filters.SCOPE_FLAGSHIP_STORE)

    # print("\n5. 演示设置价格区间 (需要真实定位器)")
    # product_filters.set_price_range(min_price=50, max_price=200)

    # print("\n6. 演示点击重置 (需要真实定位器)")
    # product_filters.reset()

    # print("\n7. 演示点击完成 (需要真实定位器)")
    # product_filters.confirm()
    
    # print("\n8. 演示聚合应用筛选 (需要真实定位器和 open_panel 成功)")
    # product_filters.apply_filters(
    #     sort_by=product_filters.SORT_PRICE_ASC,
    #     logistics_services=[product_filters.SERVICE_RETURN_SHIPPING, product_filters.SERVICE_SHIPS_24H],
    #     search_scopes=product_filters.SCOPE_FLAGSHIP_STORE,
    #     min_price=10,
    #     max_price=100
    # )
    pass # 移除非mitmproxy环境下的演示代码执行