from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from core.app_actions import navigate_to_home, perform_search, human_like_scroll, click_product_tab

def fetch_products_by_keyword(driver, keyword, swipe_count=10):
    """
    根据关键词在小红书中搜索商品并抓取信息。

    :param driver: Appium WebDriver 实例
    :param keyword: 用户输入的搜索关键词 (字符串)
    :param swipe_count: 滑动次数，默认为10次
    :return: 商品数据列表
    """
    print(f"开始搜索商品，关键词: {keyword}")

    products_data = []

    # 第一步：导航到首页
    success = navigate_to_home(driver)
    if not success:
        print("导航到首页失败，无法进行商品搜索。")
        return products_data

    try:
        # 第二步：定位搜索入口并输入关键词
        search_successful = perform_search(driver, keyword)
        if not search_successful:
            print("搜索操作失败。")
            return products_data

        # 等待搜索结果加载
        time.sleep(2)

        # 第三步：点击"商品"标签，切换到商品搜索结果
        print("点击'商品'标签，切换到商品搜索结果...")
        if not click_product_tab(driver):
            print("点击'商品'标签失败，无法显示商品结果。")
            return products_data
            
        # 等待商品结果加载
        time.sleep(2)
        print("商品搜索结果已加载")

        # 第四步：滚动加载更多商品
        print(f"开始滚动加载更多商品，滑动次数: {swipe_count}")
        human_like_scroll(driver, swipe_count=swipe_count)

        return products_data

    except Exception as e:
        print(f"搜索商品过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return products_data

def extract_text_safely(element, xpath):
    """
    安全地从元素中提取文本，如果找不到元素则返回空字符串。
    
    :param element: 父元素
    :param xpath: 相对于父元素的XPath
    :return: 文本内容或空字符串
    """
    try:
        return element.find_element(AppiumBy.XPATH, xpath).text
    except:
        return "" 