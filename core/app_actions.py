# core/app_actions.py
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def is_on_homepage(driver, timeout=1):
    """
    检查当前是否在首页（通过检测底部导航栏的“首页”或其他特征元素）。
    可以根据实际情况调整定位器。
    """
    try:
        # 尝试定位底部导航栏中的“首页”文字标签，或其他能代表首页的稳定元素
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

def navigate_to_home(driver, max_back_presses=5, check_interval=0.5, home_check_timeout=1):
    """
    尝试通过按返回键并检测底部导航栏（或其他首页特征元素）来导航到应用首页。

    :param driver: Appium WebDriver 实例
    :param max_back_presses: 最多按返回键的次数
    :param check_interval: 按下返回键后等待页面稳定的时间（秒）
    :param home_check_timeout: 每次检测首页特征元素的超时时间（秒）
    :return: True 如果成功导航到首页，False 如果失败
    """
    print("尝试导航到首页...")

    # 1. 直接尝试点击底部导航栏的“首页”按钮 (如果能定位到且可靠，这是首选)
    try:
        # 根据图片和常见应用设计，底部“首页”TAB的 content-desc 通常是 “首页”
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


    # 2. 如果直接点击首页按钮不成功或不可用，则使用“按返回键 + 检测”的逻辑
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

# 你将来可能还会添加其他通用函数，例如：
# def handle_common_popup(driver):
#     pass