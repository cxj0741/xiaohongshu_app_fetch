# core/app_actions.py
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def is_on_homepage(driver, timeout=1):
    """
    检查当前是否在首页（通过检测底部导航栏的"首页"或其他特征元素）。
    可以根据实际情况调整定位器。
    """
    try:
        # 尝试定位底部导航栏中的"首页"文字标签，或其他能代表首页的稳定元素
        # XPath 示例: 查找 content-desc 为 "首页" 的元素，或者 text 为 "首页" 的特定类型元素
        # 你需要用 Appium Inspector 确认最稳定可靠的定位器
        home_tab_locator_by_accessibility_id = (AppiumBy.ACCESSIBILITY_ID, "首页")
        home_tab_locator_by_text = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("首页").className("android.widget.TextView")') # 更精确的文本匹配
        
        # 或者，如果底部导航栏本身有一个固定的ID，也可以检测它是否存在
        bottom_nav_bar_locator = (AppiumBy.ID, "com.xingin.xhs:id/bottom_navigation_bar") # 假设ID，请用Inspector确认

        # 尝试其中一种或几种组合判断
        WebDriverWait(driver, timeout).until(
            EC.any_of(
                EC.presence_of_element_located(home_tab_locator_by_accessibility_id),
                EC.presence_of_element_located(home_tab_locator_by_text),
                EC.presence_of_element_located(bottom_nav_bar_locator) # 如果导航栏本身可见即可
            )
        )
        # print("调试：检测到首页特征元素。") # 调试时可以打开
        return True
    except TimeoutException:
        # print("调试：未检测到首页特征元素。") # 调试时可以打开
        return False
    except Exception as e:
        # print(f"调试：检测首页元素时发生错误: {e}") # 调试时可以打开
        return False

def navigate_to_home(driver, max_back_presses=10, check_interval=0.5, home_check_timeout=1):
    """
    尝试通过按返回键并检测底部导航栏（或其他首页特征元素）来导航到应用首页。

    :param driver: Appium WebDriver 实例
    :param max_back_presses: 最多按返回键的次数
    :param check_interval: 按下返回键后等待页面稳定的时间（秒）
    :param home_check_timeout: 每次检测首页特征元素的超时时间（秒）
    :return: True 如果成功导航到首页，False 如果失败
    """
    print("尝试导航到首页...")

    # 1. 直接尝试点击底部导航栏的"首页"按钮 (如果能定位到且可靠，这是首选)
    try:
        # 根据图片和常见应用设计，底部"首页"TAB的 content-desc 通常是 "首页"
        # 你需要用 Appium Inspector 确认！
        home_button_locator = (AppiumBy.ACCESSIBILITY_ID, "首页") # 这是一个常见的Accessibility ID
        # 或者 XPath: (AppiumBy.XPATH, "//android.widget.FrameLayout[@content-desc='首页']")
        # 或者其他稳定的定位器
        
        # 尝试直接点击首页TAB，如果它存在的话
        home_button = WebDriverWait(driver, 2).until( # 用较短的超时尝试直接点击
            EC.element_to_be_clickable(home_button_locator)
        )
        home_button.click()
        print("通过点击底部导航栏'首页'按钮尝试返回主页。")
        time.sleep(check_interval) # 等待页面稳定
        if is_on_homepage(driver, home_check_timeout):
            print("已成功导航到首页。")
            return True
        else:
            print("点击底部导航栏'首页'后未能确认在首页，继续尝试返回键。")

    except (TimeoutException, NoSuchElementException):
        print("未直接找到或点击底部导航栏'首页'按钮，将尝试使用返回键。")
    except Exception as e:
        print(f"尝试直接点击首页按钮时发生错误: {e}，将尝试使用返回键。")


    # 2. 如果直接点击首页按钮不成功或不可用，则使用"按返回键 + 检测"的逻辑
    for attempt in range(max_back_presses):
        if is_on_homepage(driver, home_check_timeout):
            print(f"已在首页 (尝试 {attempt+1}/{max_back_presses} 次返回后检测成功)。")
            return True

        print(f"当前不在首页，尝试按返回键 (第 {attempt + 1} 次)...")
        try:
            driver.back()
        except Exception as e:
            print(f"执行 driver.back() 时出错: {e}")
            # 即使driver.back()出错，也可能需要检查是否意外回到了首页
            if is_on_homepage(driver, home_check_timeout):
                 print("driver.back() 出错后，检测到已在首页。")
                 return True
            return False # driver.back() 失败，且不在首页，则认为导航失败

        time.sleep(check_interval) # 等待页面可能发生的转换

    # 在所有返回尝试结束后，最后再检查一次
    if is_on_homepage(driver, home_check_timeout):
        print(f"已在首页 (在所有 {max_back_presses} 次返回尝试结束后检测成功)。")
        return True
    else:
        print(f"尝试 {max_back_presses} 次返回后，仍未能导航到首页。")
        return False

def perform_search(driver, keyword, timeout=10):
    """
    Performs a search in the Xiaohongshu app.
    1. Clicks the search icon on the current page (assumed to be homepage or similar).
    2. Enters the keyword (as the input field is expected to be auto-focused).
    3. Presses the Enter key to submit the search.

    :param driver: Appium WebDriver instance
    :param keyword: The search term (string)
    :param timeout: Timeout for locating the initial search icon
    :return: True if search initiated successfully, False otherwise.
    """
    try:
        # 1. 点击搜索图标（代码保持不变）
        print("执行搜索操作：点击搜索入口...")
        search_icon_locator = (AppiumBy.ACCESSIBILITY_ID, "搜索") 
        
        search_icon = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(search_icon_locator)
        )
        search_icon.click()
        print("已点击搜索入口。等待搜索页面加载并输入框聚焦...")

        time.sleep(1.5)
        
        # 2. 输入关键词（使用替代方法）
        print(f"输入关键词 '{keyword}' (因输入框已自动聚焦)...")
        # 替代方法1: 使用driver的send_keys方法
        # 尝试找到搜索输入框
        try:
            search_box = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((AppiumBy.CLASS_NAME, "android.widget.EditText"))
            )
            search_box.send_keys(keyword)
        except:
            # 如果找不到输入框，尝试使用driver的keyboard方法
            # 这依赖于输入框已被聚焦
            driver.keyboard.send_keys(keyword)
            
        print("关键词输入完毕。")

        # 3. 按回车键提交（保持不变）
        print("按回车键提交搜索...")
        driver.press_keycode(66)  # 66是Android中的ENTER键码
        print("已按回车键，搜索已提交。")
        
        return True
        
    except Exception as e:
        print(f"执行搜索操作时发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def open_filter_panel(driver, timeout=10):
    """
    在搜索结果页面，确保详细的筛选面板是展开的。
    它会尝试点击顶部的TAB来触发筛选面板的显示。

    :param driver: Appium WebDriver 实例
    :param timeout: 等待元素出现的超时时间
    :return: True 如果成功打开或已打开，False 如果失败
    """
    # 特征元素：用于判断详细筛选面板是否已经可见，例如"排序依据"这个文本标签
    # 你需要用 Appium Inspector 确认这个标签的可靠定位器
    detailed_filter_indicator_locator = (AppiumBy.XPATH, "//*[@text='排序依据']") # 示例，请用Inspector确认

    try:
        # 1. 首先检查详细筛选面板是否已经可见
        print("检查筛选面板是否已可见...")
        WebDriverWait(driver, 2).until( # 用较短的超时尝试检查
            EC.presence_of_element_located(detailed_filter_indicator_locator)
        )
        print("筛选面板已可见。")
        return True
    except TimeoutException:
        # 如果筛选面板不可见，则尝试点击"全部"TAB来展开它
        print("筛选面板当前不可见或未完全加载，尝试点击'全部'TAB...")
        try:
            # 定位"全部"TAB
            # 根据你的截图 image_0b737d.png，它的 text 是 "全部"
            # 优先使用 Accessibility ID (如果 content-desc 是 "全部") 或精确的 XPath
            
            # 尝试1: 如果 "全部" TAB 有唯一的 content-desc="全部"
            # all_tab_locator = (AppiumBy.ACCESSIBILITY_ID, "全部")
            
            # 尝试2: 使用 text 属性定位 (更通用，但要确保它是正确的那个 "全部")
            # 注意：如果页面上有多个元素的 text 都是 "全部"，这个XPath需要更精确
            all_tab_locator_by_text = (AppiumBy.XPATH, "//android.widget.TextView[@text='全部']") # 示例，请用Inspector确认
                                                                                            # 并确保它是顶部TAB的那个
            
            # 你需要用Inspector确定最可靠的定位器来点击那个顶部的"全部"TAB
            # 假设它的父容器或它自己是可点击的

            all_tab_button = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(all_tab_locator_by_text) # 或者你找到的更可靠的定位器
            )
            all_tab_button.click()
            print("已点击'全部'TAB。")

            # 等待详细筛选面板的特征元素出现
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(detailed_filter_indicator_locator)
            )
            print("已成功打开/显示详细筛选面板。")
            return True
        except TimeoutException:
            print(f"错误：点击'全部'TAB后，在{timeout}秒内未找到详细筛选面板的特征元素。")
            return False
        except Exception as e:
            print(f"点击'全部'TAB或等待筛选面板展开时发生错误: {e}")
            return False
    except Exception as e_outer:
        print(f"检查或打开筛选面板时发生未知错误: {e_outer}")
        return False

# todo  点击最新的时候点击不到   
def click_filter_option(driver, option_text_or_desc, timeout=5):
    """
    尝试点击指定的筛选选项。
    这个函数假设筛选面板已经可见。
    它会尝试多种策略来定位和点击元素，优先考虑可点击的容器。

    :param driver: Appium WebDriver 实例
    :param option_text_or_desc: 筛选选项的文本或 content-desc (Accessibility ID)
    :param timeout: 等待元素出现的超时时间
    :return: True 如果点击成功，False 如果失败
    """
    print(f"尝试点击筛选选项: '{option_text_or_desc}'...")
    element_clicked = False

    # 策略1: 尝试使用 Accessibility ID (content-desc) 直接定位可点击元素
    # 这种策略假设 option_text_or_desc 本身就是某个可点击元素 (如 FrameLayout) 的 content-desc
    try:
        print(f"  策略1: 尝试通过 Accessibility ID '{option_text_or_desc}' 定位可点击元素...")
        locator_by_desc = (AppiumBy.ACCESSIBILITY_ID, option_text_or_desc)
        option_element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator_by_desc)
        )
        option_element.click()
        element_clicked = True
        print(f"  已通过 Accessibility ID 点击: '{option_text_or_desc}'。")
    except TimeoutException:
        print(f"  策略1: 通过 Accessibility ID 未找到或不可点击 '{option_text_or_desc}'。")
    except Exception as e:
        print(f"  策略1: 通过 Accessibility ID 点击时发生错误: {e}。")

    if element_clicked:
        time.sleep(1.5) # 给UI一些响应时间
        return True

    # 策略2: 尝试通过 XPath 查找包含指定文本的、可点击的父容器或自身
    # (主要针对 TextView 本身 clickable=false，但其父容器 clickable=true 的情况)
    if not element_clicked:
        try:
            # 这个XPath会查找一个clickable='true'的任何类型(*)的元素，
            # 该元素内部包含一个文本为 option_text_or_desc 的 TextView。
            # 或者，如果TextView本身是可点击的（虽然之前看到是false，但作为备选）。
            # [1] 表示选择满足条件的第一个祖先或自身，可以根据需要调整。
            # 你需要根据 Inspector 中 TextView 和其可点击父容器的实际层级和类名来优化此 XPath。
            # 一个更具体的例子可能是：
            # xpath_query = f"//android.widget.FrameLayout[@clickable='true' and .//android.widget.TextView[@text='{option_text_or_desc}']]"
            # 或者，如果TextView的直接父级是可点击的：
            # xpath_query = f"//android.widget.TextView[@text='{option_text_or_desc}']/parent::*[@clickable='true']"
            
            # 通用尝试：找到文本，然后找它最近的可点击祖先；或者文本元素本身可点击
            xpath_query_ancestor = f"//android.widget.TextView[@text='{option_text_or_desc}']/ancestor-or-self::*[@clickable='true'][1]"
            # 备选：直接定位文本为 option_text_or_desc 且 class 为 TextView 的元素（作为最后手段）
            xpath_query_text_direct = f"//android.widget.TextView[@text='{option_text_or_desc}']"

            print(f"  策略2: 尝试通过 XPath '{xpath_query_ancestor}' 定位可点击容器...")
            
            # 优先尝试定位可点击的祖先或自身
            option_element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, xpath_query_ancestor))
            )
            option_element.click()
            element_clicked = True
            print(f"  已通过 XPath (可点击祖先/自身) 点击: '{option_text_or_desc}'。")

        except TimeoutException:
            print(f"  策略2: 通过 XPath (可点击祖先/自身) 未找到或不可点击 '{option_text_or_desc}'。尝试直接点击文本...")
            # 回退：尝试直接点击文本元素 (即使 clickable=false，有时也可能有效)
            try:
                option_element = WebDriverWait(driver, 1).until( # 用较短的超时
                    EC.presence_of_element_located((AppiumBy.XPATH, xpath_query_text_direct))
                )
                option_element.click()
                element_clicked = True
                print(f"  策略2回退: 已直接点击文本元素 '{option_text_or_desc}'。")
            except Exception as e_direct:
                print(f"  策略2回退: 直接点击文本元素 '{option_text_or_desc}' 失败: {e_direct}")
        except Exception as e:
            print(f"  策略2: 通过 XPath 点击时发生错误: {e}")

    if element_clicked:
        time.sleep(1.5) # 给UI一些响应时间，可以根据应用实际响应速度调整
        return True
    else:
        print(f"错误：所有策略均未能成功点击筛选选项 '{option_text_or_desc}'。")
        return False
    
def apply_sort_by_filter(driver, option_text, timeout=5):
    """
    应用"排序依据"筛选。
    :param driver: Appium WebDriver 实例
    :param option_text: 例如 "综合", "最新", "最多点赞", "最多评论", "最多收藏"
    :param timeout: 等待元素出现的超时时间
    :return: True 如果点击成功，False 如果失败
    """
    print(f"尝试应用排序依据: '{option_text}'...")
    # 假设在调用此函数前，筛选面板已经通过 open_filter_panel(driver) 打开
    # 如果筛选面板可能收起，可以在这里再次调用 open_filter_panel 或检查
    # if not open_filter_panel(driver): # 确保面板已打开
    #     print(f"错误: 打开筛选面板失败，无法应用排序选项 '{option_text}'。")
    #     return False
    return click_filter_option(driver, option_text, timeout)

def apply_note_type_filter(driver, option_text, timeout=5):
    """
    应用"笔记类型"筛选。
    :param driver: Appium WebDriver 实例
    :param option_text: 例如 "不限", "视频", "图文", "直播"
    :param timeout: 等待元素出现的超时时间
    :return: True 如果点击成功，False 如果失败
    """
    print(f"尝试应用笔记类型: '{option_text}'...")
    return click_filter_option(driver, option_text, timeout)

def apply_publish_time_filter(driver, option_text, timeout=5):
    """
    应用"发布时间"筛选。
    :param driver: Appium WebDriver 实例
    :param option_text: 例如 "不限", "一天内", "一周内", "半年内"
    :param timeout: 等待元素出现的超时时间
    :return: True 如果点击成功，False 如果失败
    """
    print(f"尝试应用发布时间: '{option_text}'...")
    return click_filter_option(driver, option_text, timeout)

def apply_search_scope_filter(driver, option_text, timeout=5):
    """
    应用"搜索范围"筛选。
    :param driver: Appium WebDriver 实例
    :param option_text: 例如 "不限", "已看过", "未看过", "已关注"
    :param timeout: 等待元素出现的超时时间
    :return: True 如果点击成功，False 如果失败
    """
    print(f"尝试应用搜索范围: '{option_text}'...")
    return click_filter_option(driver, option_text, timeout)

def apply_location_distance_filter(driver, option_text, timeout=5):
    """
    应用"位置距离"筛选。
    :param driver: Appium WebDriver 实例
    :param option_text: 例如 "不限", "同城", "附近"
    :param timeout: 等待元素出现的超时时间
    :return: True 如果点击成功，False 如果失败
    """
    print(f"尝试应用位置距离: '{option_text}'...")
    return click_filter_option(driver, option_text, timeout)

def reset_filters(driver, timeout=5):
    """
    点击筛选面板底部的"重置"按钮。
    假设筛选面板已打开。
    """
    print("尝试重置筛选条件...")
    try:
        # 定位"重置"按钮，根据图片它的文字就是"重置"
        # 你需要用 Appium Inspector 确认"重置"按钮最可靠的定位器
        reset_button_locator = (AppiumBy.XPATH, f"//android.widget.TextView[@text='重置']") # 示例
        
        reset_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(reset_button_locator)
        )
        reset_button.click()
        print("已点击重置按钮。")
        time.sleep(1) # 等待生效
        return True
    except TimeoutException:
        print(f"错误：重置按钮在{timeout}秒内未找到或不可点击。")
        return False
    except Exception as e:
        print(f"点击重置按钮时发生错误: {e}")
        return False

def confirm_or_collapse_filters(driver, timeout=5):
    """
    尝试点击筛选面板底部的"收起"或可能的"完成"按钮。
    如果这些按钮存在的话。如果筛选是即时应用的，则此步骤可能不需要。
    假设筛选面板已打开。
    """
    print("尝试确认或收起筛选面板...")
    try:
        # 定位"收起"按钮，根据图片它的文字就是"收起"
        # 你需要用 Appium Inspector 确认"收起"按钮最可靠的定位器
        collapse_button_locator = (AppiumBy.XPATH, f"//android.widget.TextView[@text='收起']") # 示例
        
        collapse_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(collapse_button_locator)
        )
        collapse_button.click()
        print("已点击收起/完成按钮。")
        time.sleep(1) # 等待面板收起或列表刷新
        return True
    except TimeoutException:
        print(f"提示：收起或完成按钮在{timeout}秒内未找到，可能筛选已即时应用或不需要此操作。")
        return True # 认为操作也算完成，因为可能不需要这个按钮
    except Exception as e:
        print(f"点击收起/完成按钮时发生错误: {e}")
        return False
    
def apply_multiple_filters(driver,
                           sort_by_option=None,
                           note_type_option=None,
                           publish_time_option=None,
                           search_scope_option=None,
                           location_distance_option=None,
                           timeout_per_option=5):
    """
    应用一组指定的筛选条件。
    如果某个筛选类别的参数为 None，则跳过该类别的筛选。

    :param driver: Appium WebDriver 实例
    :param sort_by_option: 排序选项文本，例如 "最新"
    :param note_type_option: 笔记类型文本，例如 "视频"
    :param publish_time_option: 发布时间文本，例如 "一天内"
    :param search_scope_option: 搜索范围文本，例如 "未看过"
    :param location_distance_option: 位置距离文本，例如 "附近"
    :param timeout_per_option: 单个筛选选项点击的超时时间
    :return: True 如果所有指定的筛选都成功尝试应用（不保证每个都成功点击，但会尝试），
             False 如果打开筛选面板失败。
    """
    print("开始应用聚合筛选条件...")

    # 1. 确保筛选面板已打开
    if not open_filter_panel(driver): # 假设 open_filter_panel 存在且能打开筛选面板
        print("错误：未能打开筛选面板，无法应用任何筛选条件。")
        return False
    
    print("筛选面板已打开或已确认可见。")
    any_filter_applied_or_attempted = False

    # 2. 依次应用各个筛选条件
    if sort_by_option:
        any_filter_applied_or_attempted = True
        print(f"  - 应用排序依据: {sort_by_option}")
        if not apply_sort_by_filter(driver, sort_by_option, timeout=timeout_per_option):
            print(f"  -- 应用排序依据 '{sort_by_option}' 失败。")
            # 根据需求，你可以选择在这里直接 return False，或者记录失败并继续
    
    if note_type_option:
        any_filter_applied_or_attempted = True
        print(f"  - 应用笔记类型: {note_type_option}")
        if not apply_note_type_filter(driver, note_type_option, timeout=timeout_per_option):
            print(f"  -- 应用笔记类型 '{note_type_option}' 失败。")

    if publish_time_option:
        any_filter_applied_or_attempted = True
        print(f"  - 应用发布时间: {publish_time_option}")
        if not apply_publish_time_filter(driver, publish_time_option, timeout=timeout_per_option):
            print(f"  -- 应用发布时间 '{publish_time_option}' 失败。")

    if search_scope_option:
        any_filter_applied_or_attempted = True
        print(f"  - 应用搜索范围: {search_scope_option}")
        if not apply_search_scope_filter(driver, search_scope_option, timeout=timeout_per_option):
            print(f"  -- 应用搜索范围 '{search_scope_option}' 失败。")

    if location_distance_option:
        any_filter_applied_or_attempted = True
        print(f"  - 应用位置距离: {location_distance_option}")
        if not apply_location_distance_filter(driver, location_distance_option, timeout=timeout_per_option):
            print(f"  -- 应用位置距离 '{location_distance_option}' 失败。")
            
    if not any_filter_applied_or_attempted:
        print("未指定任何有效的筛选条件进行应用。")
        # 即使没有应用筛选，也尝试收起面板（如果它之前被打开了）
        confirm_or_collapse_filters(driver)
        return True # 没有筛选被要求，也算成功

    # 3. 应用完所有筛选后，尝试点击"收起"或让面板自动消失
    print("所有指定筛选已尝试应用，尝试确认/收起筛选面板...")
    if not confirm_or_collapse_filters(driver): # 假设 confirm_or_collapse_filters 存在
        print("警告：未能成功点击'收起'或'完成'按钮，但筛选可能已部分或全部应用。")
        # 即使收起失败，也可能筛选已经生效，所以这里不直接返回 False

    print("聚合筛选条件应用流程结束。")
    # 这个函数主要负责尝试应用，是否每个都成功取决于底层的点击函数
    # 返回 True 表示流程执行完毕。具体是否每个选项都成功选中，需要看日志。
    # 如果需要更严格的成功判断，可以在每个 apply_..._filter 失败时让整个函数返回 False。
    return True
import random
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions import interaction

def human_like_scroll(driver, direction="down", swipe_count=30,
                      base_duration_ms=700, duration_variance_ms=400,
                      pre_delay_s_min=0.2, pre_delay_s_max=0.5,
                      post_delay_s_min=0.3, post_delay_s_max=0.8,
                      between_swipes_delay_min=0.5, between_swipes_delay_max=1.2):
    """
    执行一个带有类人延迟和可变时长的滑动/滚动操作。
    使用 W3C Actions 和单个触摸指针。

    :param driver: Appium WebDriver 实例。
    :param direction: 滑动方向，可选 "down", "up", "left", "right"。
    :param swipe_count: 连续滑动的次数。
    :param base_duration_ms: 滑动的基础持续时间（毫秒）。
    :param duration_variance_ms: 持续时间的最大随机变化量（毫秒，可正可负）。
    :param pre_delay_s_min: 首次滑动前最小延迟（秒）。
    :param pre_delay_s_max: 首次滑动前最大延迟（秒）。
    :param post_delay_s_min: 最后一次滑动后最小延迟（秒）。
    :param post_delay_s_max: 最后一次滑动后最大延迟（秒）。
    :param between_swipes_delay_min: 多次滑动之间的最小延迟（秒）。
    :param between_swipes_delay_max: 多次滑动之间的最大延迟（秒）。
    :return: True 如果所有滑动成功执行，False 如果发生错误。
    """
    print(f"执行类人滑动: 方向 '{direction}', 次数 {swipe_count}")

    # 1. 滑动前随机延迟
    pre_delay = random.uniform(pre_delay_s_min, pre_delay_s_max)
    print(f"  滑动前延迟: {pre_delay:.2f} 秒")
    time.sleep(pre_delay)

    # 2. 获取屏幕尺寸
    try:
        window_size = driver.get_window_size()
        width = window_size['width']
        height = window_size['height']
    except Exception as e:
        print(f"  错误: 获取屏幕尺寸失败 - {e}")
        return False

    successful_swipes = 0
    
    # 执行指定次数的滑动
    for swipe_index in range(swipe_count):
        print(f"  执行第 {swipe_index + 1}/{swipe_count} 次滑动...")
        
        # 3. 根据方向计算滑动的起始点和结束点
        # 每次滑动可以有轻微的随机偏移，使滑动看起来更自然
        scroll_magnitude_ratio = random.uniform(0.55, 0.75) 
        x_offset = random.randint(-20, 20)  # 水平方向的随机偏移

        if direction == "down": 
            start_x, end_x = width // 2 + x_offset, width // 2 + x_offset
            start_y = int(height * random.uniform(0.75, 0.85))
            end_y = int(start_y - height * scroll_magnitude_ratio)
            end_y = max(int(height * 0.15), end_y) 
        elif direction == "up": 
            start_x, end_x = width // 2 + x_offset, width // 2 + x_offset
            start_y = int(height * random.uniform(0.15, 0.25))
            end_y = int(start_y + height * scroll_magnitude_ratio)
            end_y = min(int(height * 0.85), end_y) 
        elif direction == "left": 
            start_y, end_y = height // 2 + x_offset, height // 2 + x_offset
            start_x = int(width * random.uniform(0.75, 0.85))
            end_x = int(start_x - width * scroll_magnitude_ratio)
            end_x = max(int(width * 0.15), end_x)
        elif direction == "right": 
            start_y, end_y = height // 2 + x_offset, height // 2 + x_offset
            start_x = int(width * random.uniform(0.15, 0.25))
            end_x = int(start_x + width * scroll_magnitude_ratio)
            end_x = min(int(width * 0.85), end_x)
        else:
            print(f"  错误: 未知的滑动方向 '{direction}'。支持 'up', 'down', 'left', 'right'。")
            return False

        # 4. 计算随机的滑动持续时间
        variance = random.uniform(-abs(duration_variance_ms), abs(duration_variance_ms))
        actual_duration_ms = int(max(150, base_duration_ms + variance)) 

        print(f"  起始点: ({start_x}, {start_y}), 结束点: ({end_x}, {end_y}), 预计持续时间: {actual_duration_ms} ms")

        # 5. 执行W3C Actions滑动
        try:
            # 创建一个触摸指针输入源
            finger = PointerInput(interaction.POINTER_TOUCH, "finger1")
            
            # 按顺序调用方法来构建动作序列到 finger 对象中
            finger.create_pointer_move(duration=0, x=start_x, y=start_y, origin='viewport')
            finger.create_pointer_down(button=0)
            finger.create_pause(random.uniform(0.02, 0.08)) 
            finger.create_pointer_move(duration=actual_duration_ms, x=end_x, y=end_y, origin='viewport')
            finger.create_pointer_up(button=0)
            
            # 使用 ActionChains 来执行滑动操作
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver, devices=[finger])
            actions.perform()

            print(f"  滑动操作 '{direction}' 第 {swipe_index + 1} 次完成。")
            successful_swipes += 1
            
            # 如果不是最后一次滑动，则添加滑动间的延迟
            if swipe_index < swipe_count - 1:
                between_delay = random.uniform(between_swipes_delay_min, between_swipes_delay_max)
                print(f"  滑动间延迟: {between_delay:.2f} 秒")
                time.sleep(between_delay)

        except Exception as e:
            print(f"  执行第 {swipe_index + 1} 次滑动操作时发生错误: {e}")
            import traceback
            traceback.print_exc()
            
            # 即使一次滑动失败，也尝试继续执行后续滑动
            continue

    # 6. 最后一次滑动后的随机延迟
    post_delay = random.uniform(post_delay_s_min, post_delay_s_max)
    print(f"  滑动后延迟: {post_delay:.2f} 秒")
    time.sleep(post_delay)
    
    print(f"滑动操作完成，成功执行 {successful_swipes}/{swipe_count} 次滑动。")
    # 如果至少有一次滑动成功，则返回 True
    return successful_swipes > 0

def click_product_tab(driver, timeout=10):
    """
    在搜索结果页面点击"商品"标签，切换到商品搜索结果。
    
    :param driver: Appium WebDriver 实例
    :param timeout: 等待元素出现的超时时间（秒）
    :return: True 如果点击成功，False 如果失败
    """
    print("尝试点击'商品'标签...")
    
    try:
        # 根据截图，尝试使用多种方式定位"商品"标签
        
        # 使用UiSelector定位文本为"商品"的元素
        product_tab_locator = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("商品")')
        
        # 备选：使用XPath定位
        product_tab_xpath = (AppiumBy.XPATH, "//android.widget.TextView[@text='商品']")
        
        # 等待元素可点击
        WebDriverWait(driver, timeout).until(
            EC.any_of(
                EC.element_to_be_clickable(product_tab_locator),
                EC.element_to_be_clickable(product_tab_xpath)
            )
        )
        
        # 尝试点击
        try:
            # 首先尝试使用UiSelector定位方式
            product_element = driver.find_element(*product_tab_locator)
            product_element.click()
            print("已点击'商品'标签 (使用UiSelector方式)")
        except Exception as e1:
            print(f"使用UiSelector点击'商品'标签失败: {e1}，尝试使用XPath...")
            # 如果第一种方式失败，尝试使用XPath
            product_element = driver.find_element(*product_tab_xpath)
            product_element.click()
            print("已点击'商品'标签 (使用XPath方式)")
        
        # 等待页面响应
        time.sleep(2)
        print("商品列表应已加载")
        return True
        
    except Exception as e:
        print(f"点击'商品'标签失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 增强版：尝试点击指定的内容类型标签(商品、笔记、用户等)
def click_content_type_tab(driver, tab_name, timeout=10):
    """
    在搜索结果页面点击指定的内容类型标签，如"商品"、"笔记"、"用户"等。
    
    :param driver: Appium WebDriver 实例
    :param tab_name: 要点击的标签名称，如"商品"、"笔记"、"用户"等
    :param timeout: 等待元素出现的超时时间（秒）
    :return: True 如果点击成功，False 如果失败
    """
    print(f"尝试点击'{tab_name}'标签...")
    
    try:
        # 使用UiSelector定位文本匹配的元素
        tab_locator = (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{tab_name}")')
        
        # 备选：使用XPath定位
        tab_xpath = (AppiumBy.XPATH, f"//android.widget.TextView[@text='{tab_name}']")
        
        # 等待元素可点击
        tab_element = WebDriverWait(driver, timeout).until(
            EC.any_of(
                EC.element_to_be_clickable(tab_locator),
                EC.element_to_be_clickable(tab_xpath)
            )
        )
        
        # 尝试点击找到的元素
        if isinstance(tab_element, WebDriverWait):
            # 如果返回的是WebDriverWait对象，需要找到实际元素
            for locator in [tab_locator, tab_xpath]:
                try:
                    element = driver.find_element(*locator)
                    element.click()
                    print(f"已点击'{tab_name}'标签")
                    break
                except:
                    continue
        else:
            # 如果已经是元素，直接点击
            tab_element.click()
            print(f"已点击'{tab_name}'标签")
        
        # 等待页面响应
        time.sleep(2)
        print(f"'{tab_name}'内容列表应已加载")
        return True
        
    except Exception as e:
        print(f"点击'{tab_name}'标签失败: {e}")
        import traceback
        traceback.print_exc()
        return False