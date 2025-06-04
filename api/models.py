# api/models.py
from pydantic import BaseModel, root_validator, Field # 'validator' 未使用，可以移除
from typing import Dict, Any, Optional, Literal, Union, List # 增加了 List

# 定义 Action 的字面量类型
ActionType = Literal["scrape_note", "scrape_product"]

# 笔记抓取参数模型
class NoteScrapeParameters(BaseModel):
    keyword: str
    swipe_count: int = Field(10, description="Appium滑动次数，用于加载更多笔记")
    # 笔记筛选的参数，使用一个字典来传递具体的筛选键值对。
    # 例如: {"sort_by_option": "最新", "note_type_option": "图文"}
    # 具体键名需要与你的 Appium 笔记筛选函数 (apply_multiple_filters) 的参数对应。
    filters: Optional[Dict[str, Any]] = Field(None, description="笔记筛选的特定参数字典")

# 商品抓取参数模型 - 更新以包含详细的筛选条件
class ProductScrapeParameters(BaseModel):
    keyword: str
    swipe_count: int = Field(10, description="Appium滑动次数，用于加载更多商品")
    
    # 新增的商品筛选参数 (对应 ProductFilterPanel 中的 apply_filters 方法参数)
    sort_by: Optional[str] = Field(None, description="商品排序方式, 例如: '销量优先', '价格升序'")
    logistics_services: Optional[List[str]] = Field(None, description="物流与权益 (可多选), 例如: ['退货包运费', '24小时发货']")
    search_scopes: Optional[str] = Field(None, description="搜索范围 (通常为单选), 例如: '旗舰店'") # 根据UI行为，设为单选
    min_price: Optional[float] = Field(None, description="最低价格")
    max_price: Optional[float] = Field(None, description="最高价格")

# 主请求模型
class TaskRequestModel(BaseModel):
    actions: ActionType
    # 根据 action 类型，parameters 会是不同的模型
    # Pydantic 会尝试按顺序匹配 Union 中的模型。
    # ProductScrapeParameters 现在有更独特的字段，有助于区分。
    parameters: Union[ProductScrapeParameters, NoteScrapeParameters] 
    # targetUrl: Optional[str] = None # 如果不需要，可以保持注释或移除

    @root_validator(pre=True) # pre=True 表示在字段验证之前运行
    def check_parameters_type(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        action = values.get('actions')
        params_data = values.get('parameters')

        if not action or not params_data:
            # 如果 action 或 parameters 缺失，让后续的Pydantic标准字段验证来处理
            return values

        # 对于这个 root_validator，由于 Pydantic 的 Union 字段本身会尝试根据
        # params_data 的结构去匹配 ProductScrapeParameters 或 NoteScrapeParameters，
        # 此处的 validator 主要用于在 Pydantic 进行严格类型检查和转换之前，
        # 进行一些通用的预处理、日志记录或基于 action 的早期参数结构断言（如果需要）。
        # 当前的实现主要是透传，依赖后续的 Union 解析。

        if action == "scrape_note":
            # Pydantic 将会尝试把 params_data 验证/转换为 NoteScrapeParameters。
            # NoteScrapeParameters 使用一个名为 'filters' 的字典来传递其筛选条件。
            # logger.debug("Action is scrape_note, expecting NoteScrapeParameters format for 'parameters'.")
            pass # 无特殊预处理逻辑
            
        elif action == "scrape_product":
            # Pydantic 将会尝试把 params_data 验证/转换为 ProductScrapeParameters。
            # ProductScrapeParameters 现在直接定义了具体的筛选字段 (如 sort_by, min_price 等)。
            # 之前关于 'scrape_product' 的 parameters 不应包含 'filters' 字段的注释/逻辑已更新，
            # 因为我们现在期望的是独立的筛选字段，而不是一个名为 'filters' 的字典。
            # logger.debug("Action is scrape_product, expecting ProductScrapeParameters format for 'parameters'.")
            if isinstance(params_data, dict) and 'filters' in params_data:
                # 如果 action 是 scrape_product，但参数里却有一个 'filters' 字典，
                # 这可能与我们为 ProductScrapeParameters 设计的独立筛选字段（如 sort_by）冲突。
                # 不过，如果 ProductScrapeParameters 和 NoteScrapeParameters 的字段足够区分，
                # Pydantic 的 Union 解析应该能正确处理。
                # 此处可以加一个警告日志，如果需要的话。
                # logger.warning("Warning: 'scrape_product' action received 'parameters' with a 'filters' key. "
                #                "Expected individual filter fields like 'sort_by', 'min_price', etc., as defined in ProductScrapeParameters.")
                pass # 无特殊预处理逻辑
        
        # 如果有其他 action 类型，可以在这里添加逻辑
        return values