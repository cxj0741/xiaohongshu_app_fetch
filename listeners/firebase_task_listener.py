import firebase_admin
from firebase_admin import credentials, firestore
import time
import threading
import os # 用于拼接路径

# 假设你的 services 模块可以这样导入，并且里面有相应的处理函数
# 你可能需要根据你的实际 services 结构调整导入路径
# 例如: from ..services import note_service, product_service
# 或者: import sys; sys.path.append(os.path.join(os.path.dirname(__file__), '..')); from services import your_service_module
from services import your_data_scraping_service # 替换为你的实际服务模块名

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
    global db # 确保可以使用全局db变量
    if not db:
        print(f"[{task_id}] Firestore客户端未初始化，无法更新任务。")
        return

    action = task_data.get('actions')
    parameters = task_data.get('parameters', {})
    target_url = task_data.get('targetUrl') # 确保任务中有这个字段

    print(f"[{task_id}] 开始处理任务: Action='{action}', Target='{target_url}'")

    try:
        result = None
        # --- 在这里根据 action 调用你的 services ---
        if action == "scrape_note_details":
            # 假设你的服务中有这个函数
            result = your_data_scraping_service.scrape_note_details(target_url, parameters)
        elif action == "scrape_product_info":
            result = your_data_scraping_service.scrape_product_info(target_url, parameters)
        # ... 添加其他 action 的判断和调用 ...
        else:
            raise ValueError(f"未知的 action: '{action}'")

        # 任务成功，更新 Firestore
        db.collection(TASKS_COLLECTION_NAME).document(task_id).update({
            'status': 'completed',
            'result': result, # 确保 result 是 Firestore 兼容的类型
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        print(f"[{task_id}] 任务处理成功！")

    except Exception as e:
        error_message = f"任务处理失败: {type(e).__name__} - {e}"
        print(f"[{task_id}] {error_message}")
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
                task_ref.update({
                    'status': 'processing',
                    'processingStartedAt': firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f"[{task_id}] 状态更新为 'processing'")

                # 使用线程处理任务，避免阻塞 Firestore 的快照监听器
                # 这对于耗时的 Appium 操作尤为重要
                thread = threading.Thread(target=dispatch_task_to_service, args=(task_id, task_data))
                thread.daemon = True # 设置为守护线程，主程序退出时它们也会退出
                thread.start()

            except Exception as firestore_error:
                print(f"[{task_id}] 更新Firestore为 'processing' 时出错: {firestore_error}")
        # 你也可以在这里处理 MODIFIED 或 REMOVED 的情况，如果需要的话
        # elif change.type.name == 'MODIFIED':
        #     print(f"任务 {task_id} 被修改: {task_data}")


def start_listening():
    global db, _query_watch # 确保可以使用和修改全局变量
    if not db:
        if not initialize_firebase(): # 如果db未初始化，则尝试初始化
            print("无法启动监听，因为Firebase初始化失败。")
            return

    # 创建一个查询，只监听状态为 'pending' 的任务，并按创建时间升序排列
    query = db.collection(TASKS_COLLECTION_NAME).where('status', '==', 'pending').order_by('createdAt')

    # on_snapshot 会在后台线程中持续监听变化
    _query_watch = query.on_snapshot(on_task_snapshot)

    print(f"[*] 正在监听 Firestore 中 '{TASKS_COLLECTION_NAME}' 集合的 'pending' 任务...")
    print("[*] 监听器已启动。主程序需要保持运行。")

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
            while True:
                time.sleep(60) # 主线程保持存活，让后台线程工作
        except KeyboardInterrupt:
            print("\n程序被用户终止 (Ctrl+C)...")
        finally:
            stop_listening()
            print("程序退出。")
    else:
        print("无法初始化Firebase，程序退出。")