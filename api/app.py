# api/app.py
import json
import os

from bson import json_util
from flask import Flask, request, jsonify
# 假设你的初始化和任务创建逻辑在 task_creation_service.py
from .task_creation_service import initialize_firebase_for_api, submit_new_task_via_sdk, get_db_client_for_api
from .models import TaskRequestModel
from pydantic import ValidationError
from pymongo import MongoClient

# --- 配置 (Configuration) ---
app = Flask(__name__)

# 使用您的 MongoDB 连接信息
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://webcrawler:4Zqbi0qNguF2dDfL@webcrawler.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
)
MONGO_DB_NAME = "xiaohongshu"

# --- 数据库连接 (Database Connection) ---
try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(f"Could not connect to MongoDB: {e}")
    client = None


def get_db():
    """获取数据库实例的辅助函数"""
    if client:
        return client[MONGO_DB_NAME]
    return None


# --- JSON 序列化辅助函数 (JSON Serialization Helper) ---
def parse_json(data):
    """一个用于正确处理MongoDB ObjectId 的辅助函数"""
    return json.loads(json_util.dumps(data))


# --- API 端点 (API Endpoints) ---

@app.route('/products', methods=['GET'])
def get_products():
    """
    获取商品列表，支持分页和关键字搜索。
    """
    db = get_db()
    if db is None:
        return jsonify({"error": "数据库服务不可用 (Database service unavailable)"}), 503

    try:
        keyword = request.args.get('keyword', None)
        # --- 关键修改：清理关键字前后的空格 ---
        if keyword:
            keyword = keyword.strip()

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        skip = (page - 1) * limit

        query = {}
        if keyword:
            regex_query = {"$regex": keyword, "$options": "i"}
            query["keyword"] = regex_query

        products_cursor = db.products.find(query).skip(skip).limit(limit)
        products_list = list(products_cursor)
        total_products = db.products.count_documents(query)

        return jsonify({
            "message": "商品数据获取成功 (Products fetched successfully)",
            "data": parse_json(products_list),
            "pagination": {
                "total": total_products,
                "page": page,
                "limit": limit,
                "totalPages": (total_products + limit - 1) // limit if limit > 0 else 0
            }
        }), 200

    except Exception as e:
        return jsonify({"error": f"处理请求时发生错误 (An error occurred): {str(e)}"}), 500


@app.route('/notes', methods=['GET'])
def get_notes():
    """
    获取笔记列表，支持分页和关键字搜索。
    """
    db = get_db()
    if db is None:
        return jsonify({"error": "数据库服务不可用 (Database service unavailable)"}), 503

    try:
        keyword = request.args.get('keyword', None)
        # --- 关键修改：清理关键字前后的空格 ---
        if keyword:
            keyword = keyword.strip()

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        skip = (page - 1) * limit

        query = {}
        if keyword:
            regex_query = {"$regex": keyword, "$options": "i"}
            query["keyword"] = regex_query

        notes_cursor = db.notes.find(query).skip(skip).limit(limit)
        notes_list = list(notes_cursor)
        total_notes = db.notes.count_documents(query)

        return jsonify({
            "message": "笔记数据获取成功 (Notes fetched successfully)",
            "data": parse_json(notes_list),
            "pagination": {
                "total": total_notes,
                "page": page,
                "limit": limit,
                "totalPages": (total_notes + limit - 1) // limit if limit > 0 else 0
            }
        }), 200

    except Exception as e:
        return jsonify({"error": f"处理请求时发生错误 (An error occurred): {str(e)}"}), 500

# 应用启动时初始化 Firebase (只执行一次)
if not initialize_firebase_for_api():
    # 可以选择记录错误并优雅退出，或者让应用在没有数据库连接的情况下继续运行（如果部分功能可用）
    print("严重错误: API 服务无法初始化 Firebase。API 可能无法正常工作。")

@app.route('/tasks', methods=['POST'])
def create_task_endpoint():
    db_client = get_db_client_for_api()
    if not db_client:
        return jsonify({"error": "数据库服务不可用"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "无效的JSON数据或缺少Content-Type头"}), 400

    try:
        # 使用Pydantic模型进行数据验证
        task_request = TaskRequestModel(**data)
        
        # 验证通过后，可以安全地使用验证后的数据
        task_id = submit_new_task_via_sdk(
            db_client,
            task_request.actions,
            task_request.parameters.model_dump()  # 使用model_dump()替代dict()
        )

        if task_id:
            return jsonify({
                "message": "任务创建成功",
                "taskId": task_id
            }), 201
        else:
            return jsonify({
                "error": "在数据库中创建任务失败"
            }), 500
            
    except ValidationError as e:
        # 捕获Pydantic验证错误并返回详细信息
        error_messages = []
        for error in e.errors():
            location = ".".join(str(loc) for loc in error["loc"])
            error_messages.append(f"{location}: {error['msg']}")
        
        return jsonify({
            "error": "参数验证失败",
            "details": error_messages
        }), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5050)