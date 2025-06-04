import json
import time
import os
import urllib.parse
import logging
import traceback

# --- 配置日志 ---
logger = logging.getLogger("mitmproxy_xhs_scraper")
logger.setLevel(logging.DEBUG)

log_dir = "xhs_data"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
    logger.debug(f"创建数据及日志所属目录: {log_dir}")

log_file_path = os.path.join(log_dir, "xhs_scraper.log")
file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("--- 脚本启动，日志记录器已初始化 ---")

total_notes_count = 0
total_products_count = 0

try:
    def response(flow):
        global total_notes_count
        global total_products_count

        request_url = flow.request.url
        keyword = "unknown"

        parsed_url = urllib.parse.urlparse(request_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        if "keyword" in query_params:
            keyword = query_params["keyword"][0]

        if "api/sns/v10/search/notes" in request_url:
            # ... (笔记处理部分代码保持不变，此处省略以减少篇幅) ...
            # --- 处理笔记API ---
            start_time_str = time.strftime("%X")
            logger.info(f"开始处理【笔记】请求 - {start_time_str} - URL: {request_url}")
            try:
                content = json.loads(flow.response.text)
            except json.JSONDecodeError as e:
                logger.error(f"【笔记】响应JSON解析失败: {e} - URL: {request_url} - 响应文本前200字符: {flow.response.text[:200]}")
                return

            notes = []
            if "data" in content and "items" in content["data"]:
                items = content["data"]["items"]
                logger.info(f"找到 {len(items)} 个笔记 items")
                for i, item in enumerate(items):
                    model_type = item.get('model_type', '')
                    note_data = None
                    if model_type == "ads" and 'ads' in item and 'note' in item['ads']:
                        note_data = item['ads']['note']
                    elif model_type == 'note' and 'note' in item:
                        note_data = item['note']

                    if note_data and 'id' in note_data:
                        if 'note_id' not in note_data:
                            note_data['note_id'] = note_data['id']
                        
                        note_data['keyword'] = keyword
                        note_data['crawl_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
                        note_data['data_type'] = 'note'
                        notes.append(note_data)
                        logger.debug(f" 成功添加笔记: {note_data.get('title', '无标题')} (ID: {note_data['id']})")
                    else:
                        logger.warning(f" 笔记 item {i+1} (类型: {model_type}) 提取失败或无ID，跳过。")
            else:
                logger.warning(f"笔记响应中未找到 'data' -> 'items' 结构。URL: {request_url} - 内容: {str(content)[:200]}")

            total_notes_count += len(notes)
            if notes:
                notes_filename = f"xhs_data/notes_{time.strftime('%Y%m%d_%H%M%S')}_{keyword}.json"
                try:
                    with open(notes_filename, "w", encoding="utf-8") as f:
                        json.dump(notes, f, ensure_ascii=False, indent=4)
                    logger.info(f"笔记数据已保存到文件: {notes_filename}")
                    logger.info(f"本次获取到 {len(notes)} 条笔记。累计 {total_notes_count} 条。")
                except IOError as e:
                    logger.error(f"保存笔记文件失败 {notes_filename}: {e}")
            else:
                logger.info("未提取到任何笔记内容！")
            logger.info(f"笔记处理完成 - {time.strftime('%X')}")


        elif "search.xiaohongshu.com/api/search/fls/products/v5" in request_url:
            start_time_str = time.strftime("%X")
            logger.info(f"开始处理【商品】请求 - {start_time_str} - URL: {request_url}")
            
            try:
                try:
                    content = json.loads(flow.response.text)
                except json.JSONDecodeError as e:
                    logger.error(f"【商品】响应JSON解析失败: {e} - URL: {request_url} - 响应文本前200字符: {flow.response.text[:200]}")
                    return

                products = []
                
                if "success" in content and content["success"] and "data" in content:
                    data_outer = content["data"] # Renamed to avoid conflict with inner 'data'
                    
                    if "module" in data_outer and "data" in data_outer["module"] and isinstance(data_outer["module"]["data"], list):
                        module_data_list = data_outer["module"]["data"]
                        logger.info(f"在 module.data 中找到 {len(module_data_list)} 个卡片项")
                        
                        for i, item_card in enumerate(module_data_list):
                            if "card_name" in item_card and "cosmos_search_goods_card" in item_card["card_name"] and "content" in item_card:
                                item_content = item_card["content"]
                                
                                if not isinstance(item_content, dict) or "id" not in item_content:
                                    logger.warning(f" 商品卡片 {item_card.get('id', '未知卡片ID')} 的 content 无效或缺少商品ID")
                                    continue
                                
                                product_id = item_content.get("id")
                                title = item_content.get("title", "")
                                price_info = item_content.get("price_info", {})
                                
                                current_price_float = None
                                if price_info.get("price") is not None:
                                    try:
                                        current_price_float = float(price_info.get("price"))
                                    except (ValueError, TypeError):
                                        logger.warning(f"商品 {product_id} 价格 '{price_info.get('price')}' 解析为数字失败。")
                                
                                current_price_str = str(price_info.get("price", ""))
                                original_price_str = str(price_info.get("origin_price", ""))
                                
                                # 初始化销量和标签相关变量
                                final_sales_text = "未知销量"
                                final_sales_numeric = None
                                temp_sold_text = None
                                temp_sold_numeric = None
                                temp_add_cart_text = None
                                temp_add_cart_numeric = None
                                all_tags_texts = []
                                
                                tag_strategy_map = item_content.get("tag_strategy_map", {})
                                if isinstance(tag_strategy_map, dict):
                                    for tag_group_key, tag_list in tag_strategy_map.items():
                                        if isinstance(tag_list, list):
                                            for tag_item in tag_list:
                                                if isinstance(tag_item, dict) and "tag_content" in tag_item:
                                                    tag_content_obj = tag_item.get("tag_content", {})
                                                    if isinstance(tag_content_obj, dict) and "content" in tag_content_obj:
                                                        tag_text = tag_content_obj.get("content", "")
                                                        if tag_text:
                                                            all_tags_texts.append(tag_text)
                                                        
                                                        tag_type = tag_item.get("type")

                                                        # 优先处理 "sold" 类型的销量标签
                                                        if tag_group_key == "after_price" and tag_type == "sold":
                                                            temp_sold_text = tag_text
                                                            try:
                                                                # 解析 "sold" 文本
                                                                _ts_text = temp_sold_text.lower()
                                                                _num_part = ""
                                                                _multiplier = 1
                                                                if '万' in _ts_text:
                                                                    _num_part = "".join(filter(lambda x: x.isdigit() or x == '.', _ts_text.split('万')[0]))
                                                                    _multiplier = 10000
                                                                elif '千' in _ts_text:
                                                                    _num_part = "".join(filter(lambda x: x.isdigit() or x == '.', _ts_text.split('千')[0]))
                                                                    _multiplier = 1000
                                                                else:
                                                                    _num_part = "".join(filter(str.isdigit, _ts_text))
                                                                
                                                                if _num_part:
                                                                    temp_sold_numeric = int(float(_num_part) * _multiplier)
                                                                else: temp_sold_numeric = None
                                                            except ValueError:
                                                                logger.warning(f"商品 {product_id} 'sold' 标签文本 '{temp_sold_text}' 解析数字失败。")
                                                                temp_sold_numeric = None
                                                        
                                                        # 处理 "add_cart_people" 类型的加购标签
                                                        elif tag_type == "add_cart_people": # 根据你的JSON示例，此类型在behavior组
                                                            temp_add_cart_text = tag_text
                                                            try:
                                                                # 解析 "add_cart_people" 文本
                                                                _num_part = "".join(filter(str.isdigit, temp_add_cart_text))
                                                                if _num_part:
                                                                    temp_add_cart_numeric = int(_num_part)
                                                                else: temp_add_cart_numeric = None
                                                            except ValueError:
                                                                logger.warning(f"商品 {product_id} 'add_cart_people' 标签 '{temp_add_cart_text}' 解析数字失败。")
                                                                temp_add_cart_numeric = None
                                else: # tag_strategy_map 不存在或格式不对
                                    logger.debug(f"商品 {product_id} 没有 tag_strategy_map 或其格式非字典。")

                                # 决定最终使用哪个销量数据
                                if temp_sold_numeric is not None:
                                    final_sales_numeric = temp_sold_numeric
                                    final_sales_text = temp_sold_text
                                    logger.debug(f"商品 {product_id}: 使用 'sold' 数据作为销量: {final_sales_numeric} (来自文本: '{final_sales_text}')")
                                elif temp_add_cart_numeric is not None:
                                    final_sales_numeric = temp_add_cart_numeric
                                    final_sales_text = temp_add_cart_text # 更新销量文本为加购文本
                                    logger.debug(f"商品 {product_id}: 未找到 'sold' 数据，使用 'add_cart_people' 数据作为销量: {final_sales_numeric} (来自文本: '{final_sales_text}')")
                                else:
                                    # 两者都未找到，final_sales_text 保持 "未知销量", final_sales_numeric 保持 None
                                    logger.debug(f"商品 {product_id}: 未找到 'sold' 或 'add_cart_people' 有效数据，销量未知。")

                                sales_revenue = "未知销售额"
                                if current_price_float is not None and final_sales_numeric is not None:
                                    sales_revenue_float = current_price_float * final_sales_numeric
                                    sales_revenue = f"{sales_revenue_float:.2f}"
                                elif current_price_float is None:
                                    logger.debug(f"商品 {product_id} 无法计算销售额：价格未知。")
                                elif final_sales_numeric is None: # 确保使用最终的数字销量判断
                                    logger.debug(f"商品 {product_id} 无法计算销售额：数字销量未知。")

                                vendor = item_content.get("vendor", {})
                                vendor_name = vendor.get("vendor_name", "")
                                seller_id = vendor.get("seller_id", "")
                                main_image_url = ""
                                image_list = item_content.get("image", [])
                                if image_list and len(image_list) > 0 and "url" in image_list[0]:
                                    main_image_url = image_list[0]["url"]
                                product_link = item_content.get("link", "")
                                
                                product = {
                                    "product_id": product_id, 
                                    "title": title, 
                                    "current_price_display": current_price_str,
                                    "current_price_numeric": current_price_float,
                                    "original_price_display": original_price_str,
                                    "sales_volume_text": final_sales_text, # 使用最终确定的销量文本
                                    "sales_volume_numeric": final_sales_numeric, # 使用最终确定的数字销量
                                    "sales_revenue": sales_revenue,
                                    "all_tags": list(set(all_tags_texts)),
                                    "vendor_name": vendor_name, 
                                    "seller_id": seller_id, 
                                    "main_image_url": main_image_url,
                                    "product_link": product_link, 
                                    "keyword": keyword,
                                    "crawl_time": time.strftime('%Y-%m-%d %H:%M:%S'), 
                                    "data_type": "product"
                                }
                                products.append(product)
                                logger.debug(f"成功添加商品: {title[:30]}... (ID: {product_id}), 价格: {current_price_float}, 最终销量文本: '{final_sales_text}', 最终数字销量: {final_sales_numeric}, 销售额: {sales_revenue}")
                        
                        if products:
                             logger.info(f"本次请求共提取 {len(products)} 个有效商品数据")
                        else:
                             logger.info("本次请求未从商品卡片中提取到有效商品数据。")
                    else:
                        logger.warning(f"商品API响应中未找到 module -> data 数组结构。URL: {request_url}")
                else:
                    logger.warning(f"商品API响应success为false或缺少data。URL: {request_url} - 内容: {str(content)[:200]}")

                total_products_count += len(products)
                if products:
                    products_filename = f"xhs_data/products_{time.strftime('%Y%m%d_%H%M%S')}_{keyword}.json"
                    try:
                        with open(products_filename, "w", encoding="utf-8") as f:
                            json.dump(products, f, ensure_ascii=False, indent=4)
                        logger.info(f"商品数据已保存到文件: {products_filename}")
                        logger.info(f"本次获取到 {len(products)} 条商品。累计 {total_products_count} 条。")
                    except IOError as e:
                        logger.error(f"保存商品文件失败 {products_filename}: {e}")
                else:
                    logger.info("最终未提取到任何可保存的商品内容！")
            
            except Exception as e:
                logger.exception(f"处理商品数据时发生未预料的错误 (URL: {request_url})")
            
            logger.info(f"商品处理完成 - {time.strftime('%X')}")

except Exception as e:
    if 'logger' in globals():
        logger.critical(f"脚本顶层发生严重错误: {e}", exc_info=True)
    else:
        print(f"发生严重错误 (logger未初始化): {e}")
        print(traceback.format_exc())