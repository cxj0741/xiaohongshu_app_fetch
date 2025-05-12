import firebase_admin
from firebase_admin import credentials, firestore
import time
import threading
import os # 用于拼接路径
import queue
from threading import Semaphore, Thread

# 假设你的 services 模块可以这样导入，并且里面有相应的处理函数
# 你可能需要根据你的实际 services 结构调整导入路径
# 例如: from ..services import note_service, product_service
# 或者: import sys; sys.path.append(os.path.join(os.path.dirname(__file__), '..')); from services import your_service_module
from services import note_service, product_service  # 替换为你的实际服务模块
from services.note_service import fetch_notes_by_keyword
from services.product_service import fetch_products_by_keyword
from core.driver_manager import AppiumDriverContextManager

# --- 配置区 ---
# 建议将密钥文件路径和集合名称也放入配置文件或环境变量中
# 为了简单起见，先直接写在这里，但后续可以移到 config 文件夹或 .env
try:
    # 假设 firebase-service-account-key.json 在项目根目录
    SERVICE_ACCOUNT_KEY_PATH = os.path.join(os.path.dirname(__file__), '..', 'firebase-service-account-key.json')
    if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        raise FileNotFoundError(f"服务账户密钥文件未找到: {SERVICE_ACCOUNT_KEY_PATH}。请确保它在项目根目录下，并且路径正确。")
    TASKS_COLLECTION_NAME = 'tasks' # Firestore中的集合名称
except Exception as e:
    print(f"配置错误: {e}")
    exit()


# 全局 Firestore 客户端变量
db = None

# 任务队列和信号量，用于控制任务并发
task_queue = queue.Queue()
execution_semaphore = Semaphore(1)  # 限制同时只有1个任务执行
is_worker_running = False  # 标记工作线程是否运行

def initialize_firebase():
    global db
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Admin SDK 初始化成功！")
        return True
    except Exception as e:
        print(f"Firebase Admin SDK 初始化失败: {e}")
        return False

def process_task(task_id, task_data):
    """
    处理单个任务的函数
    """
    global db
    if not db:
        print(f"[{task_id}] Firestore客户端未初始化，无法更新任务。")
        return

    action = task_data.get('actions')
    parameters = task_data.get('parameters', {})
    
    print(f"[{task_id}] 开始处理任务: Action='{action}', Parameters='{parameters}'")

    try:
        # 使用上下文管理器获取驱动
        with AppiumDriverContextManager() as driver:
            if not driver:
                raise Exception("无法获取Appium驱动实例")
            
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

        # 任务成功，更新Firestore
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'completed',
            'result': result,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        print(f"[{task_id}] 任务处理成功！")

    except Exception as e:
        error_message = f"任务处理失败: {type(e).__name__} - {e}"
        print(f"[{task_id}] {error_message}")
        import traceback
        traceback.print_exc()
        
        # 任务失败，更新Firestore
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'failed',
            'error': error_message,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })

def task_worker():
    """
    工作线程函数，不断从队列获取任务并执行
    """
    global is_worker_running
    
    print("[工作线程] 启动，等待处理任务...")
    
    try:
        while is_worker_running:
            try:
                # 从队列获取任务，最多等待5秒
                task_id, task_data = task_queue.get(timeout=5)
                
                print(f"[工作线程] 从队列获取任务: {task_id}")
                
                # 获取信号量，限制并发
                execution_semaphore.acquire()
                try:
                    # 处理任务
                    process_task(task_id, task_data)
                finally:
                    # 释放信号量
                    execution_semaphore.release()
                    # 标记任务完成
                    task_queue.task_done()
                    
            except queue.Empty:
                # 队列为空，继续等待
                continue
                
    except Exception as e:
        print(f"[工作线程] 发生错误: {e}")
    finally:
        print("[工作线程] 退出")

def start_worker_thread():
    """
    启动工作线程
    """
    global is_worker_running
    
    if is_worker_running:
        return  # 已经运行
        
    is_worker_running = True
    worker = Thread(target=task_worker, daemon=True)
    worker.start()
    print("[主线程] 工作线程已启动")

def stop_worker_thread():
    """
    停止工作线程
    """
    global is_worker_running
    
    if not is_worker_running:
        return  # 已经停止
        
    is_worker_running = False
    # 等待队列清空
    if not task_queue.empty():
        print("[主线程] 等待队列中的任务完成...")
        task_queue.join()
    print("[主线程] 工作线程已停止")

def on_task_snapshot(collection_snapshot, changes, read_time):
    """
    Firestore快照变化回调函数
    """
    global db
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
                # 更新任务状态为等待中
                task_ref.update({
                    'status': 'processing',
                    'processingStartedAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f"[{task_id}] 状态更新为 'processing'，加入任务队列")
                
                # 将任务添加到队列
                task_queue.put((task_id, task_data))
                
            except Exception as firestore_error:
                print(f"[{task_id}] 更新Firestore为 'processing' 时出错: {firestore_error}")

def start_listening():
    """
    开始监听Firestore任务
    """
    global db, _query_watch
    if not db:
        if not initialize_firebase():
            print("无法启动监听，因为Firebase初始化失败。")
            return False

    try:
        # 启动工作线程
        start_worker_thread()
        
        # 创建查询，只监听状态为'pending'的任务
        query = db.collection(TASKS_COLLECTION_NAME).where('status', '==', 'pending')
        
        # 启动监听
        _query_watch = query.on_snapshot(on_task_snapshot)
        
        print(f"[*] 正在监听 Firestore 中 '{TASKS_COLLECTION_NAME}' 集合的 'pending' 任务...")
        print("[*] 监听器已启动。主程序需要保持运行。")
        return True
        
    except Exception as e:
        print(f"启动监听时发生错误: {e}")
        if "requires an index" in str(e):
            print("需要创建索引。请访问错误信息中的链接创建索引，或暂时移除order_by子句。")
        return False

def stop_listening():
    """
    停止监听
    """
    global _query_watch
    
    # 停止工作线程
    stop_worker_thread()
    
    # 取消Firestore监听
    if _query_watch:
        print("[*] 正在停止监听 Firestore 任务...")
        _query_watch.unsubscribe()
        _query_watch = None
        print("[*] 监听已停止。")
    else:
        print("[*] 监听器未运行或已停止。")

# 如果直接运行此文件进行测试，可以添加以下代码
if __name__ == '__main__':
    if initialize_firebase():
        if start_listening():
            try:
                print("监听器和任务处理器已启动。按Ctrl+C结束程序...")
                while True:
                    time.sleep(1)
                    # 显示队列状态
                    if task_queue.qsize() > 0:
                        print(f"当前队列中有 {task_queue.qsize()} 个任务等待处理")
                    time.sleep(59)  # 每分钟显示一次队列状态
            except KeyboardInterrupt:
                print("\n程序被用户终止 (Ctrl+C)...")
            finally:
                stop_listening()
                print("程序退出。")
        else:
            print("启动监听失败，程序退出。")
    else:
        print("无法初始化Firebase，程序退出。")