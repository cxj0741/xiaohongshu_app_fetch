# api/models.py
# pip install pydantic
from pydantic import BaseModel, validator, root_validator, Field
from typing import Dict, Any, Optional, Literal, Union

# 定义 Action 的字面量类型
ActionType = Literal["scrape_note", "scrape_product"]

# 为不同的 action 定义不同的 parameters 模型
class NoteScrapeParameters(BaseModel):
    keyword: str
    swipe_count: int = 10
    filters: Optional[Dict[str, Any]] = None # 例如 {"category": "美食", "sort": "popular"}

class ProductScrapeParameters(BaseModel):
    keyword: str
    swipe_count: int = 10

# 主请求模型
class TaskRequestModel(BaseModel):
    actions: ActionType
    # 根据 action 类型，parameters 会是不同的模型
    parameters: Union[NoteScrapeParameters, ProductScrapeParameters]
    # targetUrl: Optional[str] = None # 如果这类任务不需要 targetUrl，则设为可选或移除

    @root_validator(pre=True) # pre=True 表示在字段验证之前运行
    def check_parameters_type(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        action = values.get('actions')
        params_data = values.get('parameters')

        if not action or not params_data:
            # 如果 action 或 parameters 缺失，让后续的字段验证来处理
            return values

        if action == "scrape_note":
            # Pydantic 会在后续尝试将 params_data 转换为 NoteScrapeParameters
            # 这里主要是为了清晰，或者可以添加额外的预处理
            pass
        elif action == "scrape_product":
            # Pydantic 会在后续尝试将 params_data 转换为 ProductScrapeParameters
            if 'filters' in params_data:
                # Product scraping 不应该有 filters 字段，可以提前报错或移除
                # raise ValueError("Parameters for 'scrape_product' should not contain 'filters'")
                # 或者移除它以避免验证错误
                # del params_data['filters'] # 这样做比较粗暴，最好是客户端不传
                pass # 让 Pydantic 的模型验证去处理
        # 如果有其他 action 类型，可以在这里添加逻辑
        return values
