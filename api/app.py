# api/app.py
from flask import Flask, request, jsonify
# 假设你的初始化和任务创建逻辑在 task_creation_service.py
from .task_creation_service import initialize_firebase_for_api, submit_new_task_via_sdk, get_db_client_for_api
from .models import TaskRequestModel
from pydantic import ValidationError

app = Flask(__name__)

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
    app.run(debug=True, port=5000)