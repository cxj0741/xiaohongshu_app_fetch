# services/note_service.py
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from core.app_actions import navigate_to_home, perform_search, human_like_scroll, open_filter_panel, apply_multiple_filters

def fetch_notes_by_keyword(driver, keyword, swipe_count=10, filters=None):
    """
    根据关键词在小红书中搜索笔记并抓取信息。

    :param driver: Appium WebDriver 实例
    :param keyword: 用户输入的搜索关键词 (字符串)
    :param swipe_count: 滑动次数，默认为10次
    :param filters: 筛选条件，字典形式，例如：
                    {
                        'sort_by_option': '最新',
                        'note_type_option': '图文',
                        'publish_time_option': '一天内',
                        'search_scope_option': '不限',
                        'location_distance_option': '不限'
                    }
    :return: 笔记数据列表
    """
    print(f"开始搜索关键词: {keyword}")

    notes_data = []

    # 第一步：导航到首页
    success = navigate_to_home(driver)
    if not success:
        print("导航到首页失败，无法进行搜索。")
        return notes_data

    try:
        # 第二步：定位搜索入口并输入关键词
        search_successful = perform_search(driver, keyword)
        if not search_successful:
            print("搜索操作失败。")
            return notes_data

        # 等待搜索结果加载
        time.sleep(2)

        # 第三步：应用筛选条件（如果有）
        if filters:
            try:
                print("开始应用筛选条件...")
                # 打开筛选面板
                open_filter_panel(driver)
                
                # 应用多个筛选条件
                apply_multiple_filters(
                    driver,
                    sort_by_option=filters.get('sort_by_option', '综合'),
                    note_type_option=filters.get('note_type_option', '不限'),
                    publish_time_option=filters.get('publish_time_option', '不限'),
                    search_scope_option=filters.get('search_scope_option', '不限'),
                    location_distance_option=filters.get('location_distance_option', '不限')
                )
                
                print("筛选条件应用完成")
                # 等待筛选结果加载
                time.sleep(2)
            except Exception as e:
                print(f"应用筛选条件时出错: {e}")

        # 第四步：滚动加载更多笔记
        print(f"开始滚动加载更多笔记，滑动次数: {swipe_count}")
        human_like_scroll(driver, swipe_count=swipe_count)

        # 此处不处理收缩结果，按照要求

        print(f"关键词 '{keyword}' 的笔记搜索过程完成。")
        return notes_data

    except Exception as e:
        print(f"抓取笔记过程中发生错误: {e}")
        return notes_data