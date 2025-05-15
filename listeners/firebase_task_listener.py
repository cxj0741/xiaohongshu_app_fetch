# python -m listeners.firebase_task_listener
import firebase_admin
from firebase_admin import credentials, firestore
import time
import threading
import os
import queue
import random
import subprocess
# from threading import Semaphore # 不再需要 Semaphore(1)
from datetime import datetime, timedelta

# --- 您的模块导入 ---
# 确保这些路径根据您的项目结构是正确的
# from services import note_service, product_service # 假设这些服务已准备好
from services.note_service import fetch_notes_by_keyword
from services.product_service import fetch_products_by_keyword

# 假设 AppiumDriverContextManager 在 core.driver_manager
from core.driver_manager import AppiumDriverContextManager 
# 假设 ResourceAllocator 在 execution_manager.resource_allocator
from execution_manager.resource_allocator import ResourceAllocator 
# 添加这一行导入adb_helper
from execution_manager import adb_helper
# --- 模块导入结束 ---


# --- 配置区 ---
try:
    SERVICE_ACCOUNT_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'firebase-service-account-key.json')
    if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        raise FileNotFoundError(f"服务账户密钥文件未找到: {SERVICE_ACCOUNT_KEY_PATH}。")
    TASKS_COLLECTION_NAME = 'tasks'
    # ResourceAllocator 的配置文件路径 (相对于项目根目录)
    # 假设此脚本位于项目根目录的某个子文件夹 (例如 'firestore_processor')
    # 则 project_root 是此脚本所在文件夹的父目录
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 项目根目录
    APPIUM_INSTANCES_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config', 'appium_instances_config.yaml')
    
    # 新增配置：任务处理失败后重试的等待时间（秒）
    RETRY_DELAY_SECONDS = 30
    # 新增配置：重试前清理UiAutomator2服务
    CLEAN_UIAUTOMATOR2_ON_RETRY = True

except Exception as e:
    print(f"配置错误: {e}")
    exit(1)

# --- 全局变量 ---
db = None
task_queue = queue.Queue() # Firestore 任务将放入此队列
ALLOCATOR = None # 全局 ResourceAllocator 实例
_query_watch = None # Firestore 监听器引用
worker_threads_list = [] # 存储工作线程对象
stop_event = threading.Event() # 用于优雅地停止所有工作线程
# 新增：任务重试计数器，用于避免无限重试
task_retry_counts = {}
# 新增：服务器健康状态跟踪
server_health_status = {}

def initialize_app_services():
    global db, ALLOCATOR, server_health_status
    print("正在初始化 Firebase Admin SDK...")
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        if not firebase_admin._apps: # 避免重复初始化
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Admin SDK 初始化成功！")
    except Exception as e:
        print(f"Firebase Admin SDK 初始化失败: {e}")
        return False

    print(f"正在初始化 ResourceAllocator，配置文件: {APPIUM_INSTANCES_CONFIG_PATH}")
    try:
        ALLOCATOR = ResourceAllocator(config_file_path=APPIUM_INSTANCES_CONFIG_PATH)
        if not ALLOCATOR.appium_servers_config:
            print("警告: ResourceAllocator未能加载有效的Appium服务器配置。Appium相关任务可能无法处理。")
        else:
            print(f"ResourceAllocator 初始化成功，加载了 {len(ALLOCATOR.appium_servers_config)} 个服务器配置。")
            # 初始化服务器健康状态
            for server_conf in ALLOCATOR.appium_servers_config:
                server_id = server_conf.get('id')
                if server_id:
                    server_health_status[server_id] = {
                        'last_success': None,
                        'failures': 0,
                        'status': 'unknown'
                    }
    except Exception as e:
        print(f"ResourceAllocator 初始化失败: {e}")
        return False
        
    return True

def clean_uiautomator2_service(emulator_id):
    """清理设备上可能导致问题的UiAutomator2服务"""
    try:
        print(f"清理设备 {emulator_id} 上的UiAutomator2服务...")
        subprocess.run([
            'adb', '-s', emulator_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server'
        ], timeout=5)
        subprocess.run([
            'adb', '-s', emulator_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server.test'
        ], timeout=5)
        
        # 尝试杀死可能仍在运行的UiAutomator进程
        subprocess.run([
            'adb', '-s', emulator_id, 'shell', 'ps | grep uiautomator | awk \'{print $2}\' | xargs kill -9'
        ], shell=True, timeout=5)
        
        time.sleep(2)
        print(f"UiAutomator服务清理完成")
        return True
    except Exception as e:
        print(f"清理UiAutomator服务时出错: {e}")
        return False

def process_task(task_id, task_data, allocation_info, worker_name="DefaultWorker"):
    """
    处理单个任务的函数，现在接收 allocation_info。
    已增强错误处理和状态跟踪。
    """
    global db, server_health_status
    if not db:
        print(f"[{worker_name}][{allocation_info.get('emulator_id', 'N/A')}][{task_id}] Firestore客户端未初始化。")
        return False

    action = task_data.get('actions')
    parameters = task_data.get('parameters', {})
    emulator_id_log = allocation_info.get('emulator_id', 'N/A')
    server_id = allocation_info.get('appium_server_id')
    
    print(f"[{worker_name}][{emulator_id_log}][{task_id}] 开始处理任务: Action='{action}', Parameters='{parameters}'")

    # 更新 Firestore 状态为 'processing'
    try:
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'processing',
            'processedByWorker': worker_name,
            'processedByEmulator': emulator_id_log,
            'processingStartedAt': firestore.SERVER_TIMESTAMP,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
    except Exception as firestore_update_error:
        print(f"[{worker_name}][{emulator_id_log}][{task_id}] 更新Firestore状态为 'processing' 时失败: {firestore_update_error}")

    try:
        # 使用 AppiumDriverContextManager 和分配到的资源
        with AppiumDriverContextManager(
            server_url=allocation_info['appium_url'],
            device_name=allocation_info['emulator_id'], 
            system_port=allocation_info.get('system_port'),
            chromedriver_port=allocation_info.get('chromedriver_port'),
            wda_local_port=allocation_info.get('wda_local_port')
        ) as driver:
            if not driver:
                raise Exception("无法获取Appium驱动实例")
            
            print(f"[{worker_name}][{emulator_id_log}][{task_id}] WebDriver 会话已建立。")
            result = None
            # 根据action调用对应服务
            if action == "scrape_note":
                result = fetch_notes_by_keyword(
                    driver=driver,
                    keyword=parameters.get('keyword'),
                    swipe_count=parameters.get('swipe_count', 10),
                    filters=parameters.get('filters')
                )
            elif action == "scrape_product":
                result = fetch_products_by_keyword(
                    driver=driver,
                    keyword=parameters.get('keyword'),
                    swipe_count=parameters.get('swipe_count', 10)
                )
            else:
                raise ValueError(f"未知的 action: '{action}'")

        # 更新任务状态为完成
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'completed',
            'result': result,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        print(f"[{worker_name}][{emulator_id_log}][{task_id}] 任务处理成功！")
        
        # 更新服务器健康状态
        if server_id in server_health_status:
            server_health_status[server_id]['last_success'] = datetime.now()
            server_health_status[server_id]['failures'] = 0
            server_health_status[server_id]['status'] = 'healthy'
        
        return True

    except Exception as e:
        error_message = f"任务处理失败: {type(e).__name__} - {str(e)}"
        print(f"[{worker_name}][{emulator_id_log}][{task_id}] {error_message}")
        import traceback
        traceback.print_exc()
        
        # 更新服务器健康状态，记录失败
        if server_id in server_health_status:
            server_health_status[server_id]['failures'] += 1
            if server_health_status[server_id]['failures'] >= 3:
                server_health_status[server_id]['status'] = 'unhealthy'
            else:
                server_health_status[server_id]['status'] = 'warning'
        
        # 更新任务状态为失败
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'failed',
            'error': error_message,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        return False

def appium_task_processor_loop(worker_name):
    """
    每个工作线程运行这个循环，获取任务、分配Appium资源、处理任务、释放资源。
    增强了错误恢复和健康检查机制。
    """
    global task_queue, ALLOCATOR, stop_event, task_retry_counts, server_health_status
    print(f"[{worker_name}] 工作单元已启动，等待任务...")

    while not stop_event.is_set():
        allocation_info = None
        task_info = None # 用于在 finally 中判断是否取到了 task_id

        try:
            # 1. 从任务队列获取任务
            try:
                task_id, task_data = task_queue.get(timeout=1) # 使用超时以便能周期性检查 stop_event
                task_info = {"id": task_id, "data": task_data} # 存储任务信息用于 finally
            except queue.Empty:
                continue # 队列为空，继续循环检查 stop_event

            print(f"[{worker_name}] 从队列获取到任务: {task_id}")
            
            # 检查任务重试次数
            retry_count = task_retry_counts.get(task_id, 0)
            if retry_count >= 3:  # 最多重试3次
                print(f"[{worker_name}][{task_id}] 任务已重试{retry_count}次，放弃处理")
                db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
                    'status': 'abandoned',
                    'error': f'超过最大重试次数(3次)',
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                task_retry_counts.pop(task_id, None)  # 从重试计数器中移除
                task_queue.task_done()
                continue

            # 2. 尝试分配 Appium 资源
            print(f"[{worker_name}][{task_id}] 尝试分配 Appium 资源...")
            
            # 可以加入重试逻辑来获取资源
            retry_count = 0
            max_retries = 2 # 例如，最多重试2次 (总共3次尝试)
            retry_delay = 5 # 秒
            
            # 如果该任务已经失败过，在重试前清理UiAutomator2服务
            if CLEAN_UIAUTOMATOR2_ON_RETRY and task_id in task_retry_counts and task_retry_counts[task_id] > 0:
                # 尝试获取任何可用的设备进行清理
                print(f"[{worker_name}][{task_id}] 任务已重试{task_retry_counts[task_id]}次，尝试清理所有模拟器上的UiAutomator2服务")
                online_emulators = adb_helper.get_online_emulator_ids()
                if online_emulators:
                    for emulator_id in online_emulators:
                        if emulator_id not in ALLOCATOR._busy_emulator_ids:
                            clean_uiautomator2_service(emulator_id)
            
            while retry_count <= max_retries and not stop_event.is_set():
                # 尝试分配资源，但避免分配已知不健康的服务器
                allocation_info = ALLOCATOR.allocate_resource()
                
                # 如果成功分配，但服务器状态为不健康，可能需要额外验证或清理
                if allocation_info:
                    server_id = allocation_info.get('appium_server_id')
                    if server_id in server_health_status and server_health_status[server_id]['status'] == 'unhealthy':
                        print(f"[{worker_name}][{task_id}] 警告：分配到了标记为不健康的服务器 {server_id}，尝试额外清理")
                        clean_uiautomator2_service(allocation_info.get('emulator_id'))
                    
                    print(f"[{worker_name}][{task_id}] Appium 资源已分配: {allocation_info.get('emulator_id')}")
                    break
                
                retry_count += 1
                if retry_count <= max_retries:
                    print(f"[{worker_name}][{task_id}] 第 {retry_count} 次分配资源失败，将在 {retry_delay} 秒后重试...")
                    # 在等待期间也检查 stop_event
                    for _ in range(retry_delay):
                        if stop_event.is_set(): break
                        time.sleep(1)
                    if stop_event.is_set(): break 
            
            if stop_event.is_set(): # 如果在分配过程中收到停止信号
                print(f"[{worker_name}][{task_id}] 分配资源时收到停止信号，将任务放回队列。")
                task_queue.put((task_id, task_data)) # 将任务放回队列
                break # 跳出主 while 循环，结束线程

            if not allocation_info:
                print(f"[{worker_name}][{task_id}] 多次尝试后仍无法分配Appium资源，将任务放回队列等待后续处理。")
                # 延迟一段时间后重试
                time.sleep(5)  # 短暂延迟避免立即重新加入队列
                task_queue.put((task_id, task_data))
                time.sleep(10) # 让此 worker 稍作等待，避免立即再次抢占任务
                task_queue.task_done()
                continue # 继续下一个循环尝试获取任务

            # 3. 如果资源分配成功，则处理任务
            task_success = process_task(task_id, task_data, allocation_info, worker_name)
            
            # 任务处理失败，更新重试计数并可能重新排队
            if not task_success:
                # 更新重试计数
                current_retry_count = task_retry_counts.get(task_id, 0)
                task_retry_counts[task_id] = current_retry_count + 1
                
                if task_retry_counts[task_id] < 3:  # 如果未达到最大重试次数
                    print(f"[{worker_name}][{task_id}] 任务处理失败，这是第{task_retry_counts[task_id]}次失败，将在{RETRY_DELAY_SECONDS}秒后重试")
                    # 给系统一些时间来恢复，避免立即重试
                    time.sleep(RETRY_DELAY_SECONDS)
                    # 将任务重新放入队列
                    task_queue.put((task_id, task_data))
                else:
                    print(f"[{worker_name}][{task_id}] 任务已失败{task_retry_counts[task_id]}次，不再重试")
                    # 更新为最终失败状态
                    db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
                        'status': 'abandoned',
                        'error': f'任务失败并超过最大重试次数(3次)',
                        'updatedAt': firestore.SERVER_TIMESTAMP
                    })
                    # 从重试计数中移除
                    task_retry_counts.pop(task_id, None)

        except Exception as loop_error: # 捕获工作单元循环中的意外错误
            print(f"[{worker_name}] 工作单元主循环发生严重错误: {loop_error}")
            import traceback
            traceback.print_exc()
            # 根据错误性质，可能需要将任务放回队列或标记为特殊失败状态
            if task_info: # 如果已经取到 task_id
                 print(f"[{worker_name}] 任务 {task_info['id']} 可能因工作单元故障而中断，将重新放入队列")
                 # 将任务放回队列
                 task_queue.put((task_info['id'], task_info['data']))
        finally:
            # 4. 确保释放 Appium 资源
            if allocation_info:
                log_task_id = task_info["id"] if task_info else "未知任务"
                print(f"[{worker_name}][{log_task_id}] 准备释放Appium资源: {allocation_info.get('emulator_id')}")
                ALLOCATOR.release_resource(allocation_info)
            
            if task_info and not ('data' in task_info): # 如果任务已处理完或已重新入队
                task_queue.task_done()
    
    print(f"[{worker_name}] 工作单元检测到停止信号，正在退出...")


def start_worker_threads():
    global ALLOCATOR, worker_threads_list, stop_event
    
    if not ALLOCATOR or not ALLOCATOR.appium_servers_config:
        print("[主线程] ResourceAllocator 未初始化或无可用服务器配置，无法启动工作线程。")
        return 0

    if worker_threads_list:
        print("[主线程] 工作线程已在运行。")
        return len(worker_threads_list)

    stop_event.clear() # 重置停止事件
    num_workers = len(ALLOCATOR.appium_servers_config) # 工作线程数等于配置的服务器数
    
    if num_workers == 0:
        print("[主线程] 未配置Appium服务器，无法启动工作线程。")
        return 0
        
    print(f"[主线程] 准备启动 {num_workers} 个 Appium 任务处理工作单元...")

    for i in range(num_workers):
        worker_name = f"AppiumWorker-{i+1}"
        thread = threading.Thread(target=appium_task_processor_loop, args=(worker_name,), name=worker_name, daemon=True)
        worker_threads_list.append(thread)
        thread.start()
        print(f"[主线程] {worker_name} 已启动。")
    return num_workers

def stop_worker_threads():
    global worker_threads_list, stop_event, task_queue
    print("[主线程] 收到停止工作线程的请求...")
    stop_event.set() # 向所有工作线程发出停止信号

    # 等待队列中的任务被处理（这是一个可选的优雅停机步骤）
    # 如果希望在停止时快速结束，可以跳过或缩短此等待
    # print("[主线程] 等待任务队列处理完毕 (最多等待30秒)...")
    # try:
    #     task_queue.join(timeout=30) # 等待队列为空，或者超时
    # except AttributeError: # 老版本Python的Queue没有join(timeout=...)
    #     pass # 如果是老版本，就简单跳过

    print("[主线程] 正在停止工作线程...")
    for thread_idx, thread in enumerate(worker_threads_list):
        print(f"[主线程] 等待线程 {thread.name} 结束 (最多30秒)...")
        thread.join(timeout=30) # 给每个线程一些时间来完成当前循环并退出
        if thread.is_alive():
            print(f"[主线程] 警告: 线程 {thread.name} 未在超时内结束。")
    
    worker_threads_list = [] # 清空线程列表
    print("[主线程] 所有工作线程已尝试停止。")

def on_task_snapshot(collection_snapshot, changes, read_time):
    global db, task_queue
    if not db:
        print("Firestore客户端未初始化，无法处理快照。")
        return

    for change in changes:
        task_id = change.document.id
        task_data = change.document.to_dict()

        if change.type.name == 'ADDED' and task_data.get('status') == 'pending':
            print(f"--- 新任务出现 (ID: {task_id}) ---")
            task_ref = db.collection(TASKS_COLLECTION_NAME).document(task_id)
            try:
                # 更新任务状态为 'queued'，表示已进入Python内部队列
                task_ref.update({
                    'status': 'queued',
                    'queuedAt': firestore.SERVER_TIMESTAMP, # 记录入队时间
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f"[{task_id}] 状态更新为 'queued'，加入任务队列")
                task_queue.put((task_id, task_data)) # 将任务元组放入队列
            except Exception as firestore_error:
                print(f"[{task_id}] 更新Firestore为 'queued' 时出错: {firestore_error}")

def start_listening_and_processing():
    global db, _query_watch
    if not initialize_app_services(): # 初始化 Firebase 和 Allocator
        print("核心服务初始化失败，程序无法启动。")
        return False

    if not ALLOCATOR or not ALLOCATOR.appium_servers_config:
        print("ResourceAllocator 未正确初始化或没有服务器配置，无法启动。")
        return False

    try:
        num_started_workers = start_worker_threads() # 启动工作线程池
        if num_started_workers == 0:
            print("未能启动任何工作线程，请检查配置。")
            return False
        
        # 创建查询，只监听状态为'pending'的任务
        query = db.collection(TASKS_COLLECTION_NAME).where('status', '==', 'pending')
        _query_watch = query.on_snapshot(on_task_snapshot) # 启动 Firestore 监听
        
        print(f"[*] 正在监听 Firestore 中 '{TASKS_COLLECTION_NAME}' 集合的 'pending' 任务...")
        print(f"[*] 已启动 {num_started_workers} 个 Appium 任务处理器。主程序需要保持运行。")
        return True
    except Exception as e:
        print(f"启动监听或工作线程时发生错误: {e}")
        import traceback
        traceback.print_exc()
        if "requires an index" in str(e).lower(): # Firestore 索引提示
            print("Firestore错误提示：查询需要复合索引。请根据错误信息中的链接在Firebase控制台创建索引。")
        return False

def stop_all_services():
    global _query_watch
    
    print("[主程序] 开始关闭所有服务...")
    # 1. 停止 Firestore 监听器，避免新任务进入队列
    if _query_watch:
        print("[主程序] 正在停止监听 Firestore 任务...")
        try:
            _query_watch.unsubscribe() # 取消订阅
            _query_watch = None
            print("[主程序] Firestore 监听已停止。")
        except Exception as e_unsub:
            print(f"[主程序] 取消 Firestore 监听时出错: {e_unsub}")
    else:
        print("[主程序] Firestore 监听器未运行或已停止。")

    # 2. 停止所有工作线程
    stop_worker_threads()
    
    print("[主程序] 所有服务已尝试关闭。")


# --- 主程序入口 ---
if __name__ == '__main__':
    if start_listening_and_processing():
        try:
            print("监听器和任务处理器已启动。按Ctrl+C结束程序...")
            while True:
                # 主线程保持活动，工作线程在后台处理
                # 可以定期打印队列状态或其他监控信息
                q_size = task_queue.qsize()
                if q_size > 0:
                    print(f"当前任务队列中有 {q_size} 个任务等待处理。繁忙服务器: {len(ALLOCATOR._busy_server_ids)}/{len(ALLOCATOR.appium_servers_config)}")
                else:
                    print(f"任务队列为空。繁忙服务器: {len(ALLOCATOR._busy_server_ids)}/{len(ALLOCATOR.appium_servers_config)}。等待新任务...")
                
                # 检查工作线程是否意外退出 (简单检查)
                active_worker_count = 0
                for t in worker_threads_list:
                    if t.is_alive():
                        active_worker_count += 1
                if active_worker_count < len(ALLOCATOR.appium_servers_config) and not stop_event.is_set():
                    print(f"警告：检测到有工作线程可能已意外退出！当前活动工作线程数: {active_worker_count}")
                    # 此处可以添加逻辑尝试重启意外退出的工作线程，但会增加复杂度

                time.sleep(30) # 每30秒检查一次状态
        except KeyboardInterrupt:
            print("\n[主程序] 检测到用户终止 (Ctrl+C)...")
        finally:
            stop_all_services()
            print("[主程序] 程序已退出。")
    else:
        print("程序启动失败，请检查日志。")