import firebase_admin
from firebase_admin import credentials, firestore
import time
import threading
import os # 用于拼接路径

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

def dispatch_task_to_service(task_id, task_data):
    """
    根据 task_data 中的 'actions' 调用相应的 service 函数。
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
            # --- 根据 action 调用对应的服务，使用正确的函数名 ---
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

        # 任务成功，更新 Firestore
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'completed',
            'result': result,  # 确保 result 是 Firestore 兼容的类型
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        print(f"[{task_id}] 任务处理成功！")

    except Exception as e:
        error_message = f"任务处理失败: {type(e).__name__} - {e}"
        print(f"[{task_id}] {error_message}")
        import traceback
        traceback.print_exc()  # 打印详细错误信息
        
        # 任务失败，更新 Firestore
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'failed',
            'error': error_message,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })

# --- Firestore 任务监听与处理回调 ---
_query_watch = None # 用于保存快照监听器，以便后续可以取消订阅

def on_task_snapshot(collection_snapshot, changes, read_time):
    global db # 确保可以使用全局db变量
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
                # 更新任务状态为处理中
                task_ref.update({
                    'status': 'processing',
                    'processingStartedAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f"[{task_id}] 状态更新为 'processing'")

                # 使用线程处理任务，避免阻塞 Firestore 的快照监听器
                thread = threading.Thread(target=dispatch_task_to_service, args=(task_id, task_data))
                thread.daemon = True # 设置为守护线程，主程序退出时它们也会退出
                thread.start()

            except Exception as firestore_error:
                print(f"[{task_id}] 更新Firestore为 'processing' 时出错: {firestore_error}")
        # 可以添加对处理中但超时的任务进行监控
        elif change.type.name == 'MODIFIED' and task_data.get('status') == 'processing':
            # 这里可以添加超时检测逻辑
            pass

def start_listening():
    global db, _query_watch
    if not db:
        if not initialize_firebase():
            print("无法启动监听，因为Firebase初始化失败。")
            return

    try:
        # 创建一个查询，只监听状态为 'pending' 的任务
        # 先不使用order_by，以避免索引问题
        query = db.collection(TASKS_COLLECTION_NAME).where('status', '==', 'pending')
        
        # 启动监听
        _query_watch = query.on_snapshot(on_task_snapshot)
        
        print(f"[*] 正在监听 Firestore 中 '{TASKS_COLLECTION_NAME}' 集合的 'pending' 任务...")
        print("[*] 监听器已启动。主程序需要保持运行。")
        
    except Exception as e:
        print(f"启动监听时发生错误: {e}")
        if "requires an index" in str(e):
            print("需要创建索引。请访问错误信息中的链接创建索引，或暂时移除order_by子句。")
        return False
    
    return True

def stop_listening():
    global _query_watch
    if _query_watch:
        print("[*] 正在停止监听 Firestore 任务...")
        _query_watch.unsubscribe() # 取消订阅快照
        _query_watch = None
        print("[*] 监听已停止。")
    else:
        print("[*] 监听器未运行或已停止。")

# 如果直接运行此文件进行测试，可以添加以下代码
if __name__ == '__main__':
    if initialize_firebase():
        start_listening()
        try:
            print("监听器已启动。按Ctrl+C结束程序...")
            while True:
                time.sleep(60) # 主线程保持存活，让后台线程工作
        except KeyboardInterrupt:
            print("\n程序被用户终止 (Ctrl+C)...")
        finally:
            stop_listening()
            print("程序退出。")
    else:
        print("无法初始化Firebase，程序退出。")