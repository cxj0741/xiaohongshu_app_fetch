import time
import logging # 建议使用 logging 模块来替代 print 进行日志输出
from appium.webdriver.common.appiumby import AppiumBy # extract_text_safely 用到了
from core.driver_manager import AppiumDriverContextManager # 假设这是你的驱动管理器
# python -m services.product_service

# --- 从你的项目中导入必要的模块 ---
# 确保这些函数的路径和你的项目结构一致
try:
    from core.app_actions import navigate_to_home, perform_search, human_like_scroll, click_product_tab
    from core.product_actions import ProductFilterPanel # 导入我们为商品筛选创建的类
except ImportError as e:
    print(f"导入模块失败，请检查文件路径和PYTHONPATH设置: {e}")
    print("确保 core 文件夹（包含 app_actions.py, product_actions.py）在Python的搜索路径中。")
    raise # 抛出异常，因为这些模块是必需的

# --- 配置一个简单的logger (如果你的主脚本还没有logger) ---
logger = logging.getLogger("FetchProductsScript")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s')
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


def fetch_products_by_keyword(driver, keyword, swipe_count=10,
                              # 新增筛选相关的参数，默认为None表示不应用该筛选
                              sort_by_option=None,
                              logistics_options=None, # 可以是单个服务文本或列表
                              search_scope_options=None, # 可以是单个范围文本或列表
                              min_price=None,
                              max_price=None):
    """
    根据关键词在小红书中搜索商品，应用筛选条件，并抓取信息（通过后续的mitmproxy）。

    :param driver: Appium WebDriver 实例
    :param keyword: 用户输入的搜索关键词 (字符串)
    :param swipe_count: 滑动次数，默认为10次
    :param sort_by_option: 排序选项 (例如 ProductFilterPanel.SORT_SALES_PRIORITY)
    :param logistics_options: 物流与权益选项 (单个字符串或列表)
    :param search_scope_options: 搜索范围选项 (单个字符串或列表)
    :param min_price: 最低价格
    :param max_price: 最高价格
    :return: (目前脚本设计是驱动UI，数据由mitmproxy抓取，所以这里可以返回True/False表示操作是否成功)
    """
    logger.info(f"开始搜索商品流程，关键词: {keyword}")

    # products_data = [] # 这个变量在你当前脚本中未被填充，因为数据由mitmproxy获取

    # 第一步：导航到首页
    success_nav = navigate_to_home(driver) # 假设 navigate_to_home 不需要 logger
    if not success_nav:
        logger.error("导航到首页失败，无法进行商品搜索。")
        return False

    try:
        # 第二步：定位搜索入口并输入关键词
        search_successful = perform_search(driver, keyword) # 假设 perform_search 不需要 logger
        if not search_successful:
            logger.error(f"执行搜索 '{keyword}' 操作失败。")
            return False
        logger.info(f"关键词 '{keyword}' 搜索已提交。")
        time.sleep(3) # 等待搜索结果页加载

        # 第三步：点击"商品"标签，切换到商品搜索结果
        logger.info("尝试点击'商品'标签，切换到商品搜索结果...")
        if not click_product_tab(driver): # 假设 click_product_tab 不需要 logger
            logger.error("点击'商品'标签失败，无法显示商品结果。")
            return False
        logger.info("已切换到'商品'标签页。")
        time.sleep(2) # 等待商品结果加载
        logger.info("商品搜索结果列表已初步加载。")

        # --- 第四步：应用筛选条件 ---
        # 只有当至少提供了一个筛选参数时才执行筛选操作
        if any([sort_by_option, logistics_options, search_scope_options, min_price is not None, max_price is not None]):
            logger.info(f"准备为关键词 '{keyword}' 应用筛选条件...")
            product_filter_manager = ProductFilterPanel(driver, logger) # 将logger实例传递给筛选器

            filters_applied_successfully = product_filter_manager.apply_filters(
                sort_by=sort_by_option,
                logistics_services=logistics_options,
                search_scopes=search_scope_options,
                min_price=min_price,
                max_price=max_price
            )

            if filters_applied_successfully:
                logger.info("筛选条件已成功尝试应用。等待筛选结果刷新...")
                time.sleep(3) # 等待筛选后的列表刷新
            else:
                logger.warning("应用筛选条件失败或部分失败。将继续处理当前（可能未筛选或部分筛选）的结果。")
        else:
            logger.info("未指定任何筛选条件，跳过筛选步骤。")

        # 第五步：滚动加载更多商品
        logger.info(f"开始滚动加载更多商品，预设滑动次数: {swipe_count}")
        human_like_scroll(driver, swipe_count=swipe_count) # 假设 human_like_scroll 不需要 logger
        logger.info(f"已完成 {swipe_count} 次滑动操作。")

        return True # 表示整个流程（搜索、筛选、滑动）已执行

    except Exception as e:
        logger.error(f"搜索并筛选商品过程中发生错误: {e}", exc_info=True)
        # traceback.print_exc() # logger.error 使用 exc_info=True 会自动记录堆栈
        return False

def extract_text_safely(element, xpath):
    """
    安全地从元素中提取文本，如果找不到元素则返回空字符串。
    (这个函数在你当前的 fetch_products_by_keyword 中没有直接用到，但可以保留作为工具函数)
    :param element: 父元素
    :param xpath: 相对于父元素的XPath
    :return: 文本内容或空字符串
    """
    try:
        return element.find_element(AppiumBy.XPATH, xpath).text
    except:
        return ""

# --- 示例如何调用这个增强后的函数 ---
# if __name__ == '__main__':
    # # 这个 __main__ 块是为了演示如何调用 fetch_products_by_keyword
    # # 实际的 Appium driver 初始化和管理应该在你的主测试脚本或 AppiumDriverContextManager 中完成
    
    # # 假设你有一个 AppiumDriverContextManager 和 logger 已经配置好了
    # # from core.product_actions import ProductFilterPanel # 已经在顶部导入

    # test_search_keyword = "蓝牙耳机"
    # logger.info(f"--- 开始测试 fetch_products_by_keyword (带筛选) ---")

    # # device_name 需要替换为你的实际设备ID或模拟器名称
    # with AppiumDriverContextManager(device_name="127.0.0.1:16384") as driver_instance:
    #     if not driver_instance:
    #         logger.error("获取 WebDriver 实例失败，测试中止。")
    #     else:
    #         logger.info("WebDriver 实例创建成功，准备执行带筛选的商品搜索。")
            
    #         # 为了能方便地使用 ProductFilterPanel 中定义的常量（如 SORT_SALES_PRIORITY）
    #         # 你可以在调用前获取它们，或者直接传入字符串
    #         # temp_filter_for_constants = ProductFilterPanel(driver_instance, logger) # 仅为获取常量

    #         fetch_success = fetch_products_by_keyword(
    #             driver=driver_instance,
    #             keyword=test_search_keyword,
    #             swipe_count=5, # 测试时减少滑动次数
    #             sort_by_option=ProductFilterPanel.SORT_SALES_PRIORITY, # 使用类属性作为常量
    #             logistics_options=[ProductFilterPanel.SERVICE_RETURN_SHIPPING, ProductFilterPanel.SERVICE_SHIPS_24H],
    #             min_price=50,
    #             max_price=300
    #         )
            
    #         if fetch_success:
    #             logger.info(f"带筛选的商品搜索流程执行完毕。mitmproxy应已捕获基于筛选结果的API请求。")
    #         else:
    #             logger.error(f"带筛选的商品搜索流程失败。")

    #         logger.info("测试将在10秒后结束...")
    #         time.sleep(10)
    # logger.info(f"--- fetch_products_by_keyword (带筛选) 测试结束 ---")