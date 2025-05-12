# api/task_creation_service.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

SERVICE_ACCOUNT_KEY_PATH = os.path.join(os.path.dirname(__file__), '..', 'firebase-service-account-key.json')
_db_api_client = None

def initialize_firebase_for_api():
    global _db_api_client
    if _db_api_client: # 如果已经初始化过，直接返回
        return True
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
            firebase_admin.initialize_app(cred)
            print("API Service: Firebase Admin SDK (default app) 初始化成功！")
        else:
            print("API Service: Default Firebase app already initialized by another module in this process (unexpected for separate API process) or this is a re-init attempt.")
        
        _db_api_client = firestore.client()
        return True
    except Exception as e:
        print(f"API Service: Firebase Admin SDK 初始化失败: {e}")
        return False

def get_db_client_for_api():
    return _db_api_client

def submit_new_task_via_sdk(db_client, actions, parameters):
    """
    提交新任务到Firestore数据库
    
    参数:
        db_client: Firestore客户端
        actions: 任务类型
        parameters: 任务参数
        
    返回:
        成功时返回任务ID，失败时返回None
    """
    if not db_client:
        print("Firestore 客户端未提供给 submit_new_task_via_sdk")
        return None
    
    try:
        # 创建任务数据
        new_task_data = {
            "status": "pending",  # 确保初始状态为pending
            "actions": actions,
            "parameters": parameters,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "processingStartedAt": firestore.SERVER_TIMESTAMP
        }
        
        # 添加到Firestore
        _, task_ref = db_client.collection('tasks').add(new_task_data)
        print(f"成功创建任务: {task_ref.id}")
        return task_ref.id
    except Exception as e:
        print(f"创建任务时出错: {e}")
        return None