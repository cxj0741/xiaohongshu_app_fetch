import json
import time
import os
import urllib.parse

# 创建数据保存目录
if not os.path.exists("xhs_data"):
    os.makedirs("xhs_data")

# 添加全局统计变量
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

        # --- 处理笔记API ---
        if "api/sns/v10/search/notes" in request_url:
            start_time = time.strftime("%X")
            print(f"开始处理【笔记】请求 - {start_time} - URL: {request_url}")
            content = json.loads(flow.response.text)
            notes = []
            if "data" in content and "items" in content["data"]:
                items = content["data"]["items"]
                print(f"找到 {len(items)} 个笔记 items")
                for i, item in enumerate(items):
                    model_type = item.get('model_type', '')
                    note_data = None
                    if model_type == "ads" and 'ads' in item and 'note' in item['ads']:
                        note_data = item['ads']['note']
                    elif model_type == 'note' and 'note' in item:
                        note_data = item['note']

                    if note_data and 'id' in note_data:
                        # 确保使用统一的ID字段名
                        if 'note_id' not in note_data:
                            note_data['note_id'] = note_data['id']
                            
                        note_data['keyword'] = keyword
                        note_data['crawl_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
                        note_data['data_type'] = 'note'  # 添加数据类型标记
                        notes.append(note_data)
                        print(f"  成功添加笔记: {note_data.get('title', '无标题')} (ID: {note_data['id']})")
                    else:
                        print(f"  笔记 item {i+1} (类型: {model_type}) 提取失败或无ID，跳过。")
            else:
                print(f"笔记响应中未找到 'data' -> 'items' 结构。内容: {str(content)[:200]}")

            total_notes_count += len(notes)
            if notes:
                notes_filename = f"xhs_data/notes_{time.strftime('%Y%m%d_%H%M%S')}_{keyword}.json"
                with open(notes_filename, "w", encoding="utf-8") as f:
                    json.dump(notes, f, ensure_ascii=False, indent=2)
                print(f"笔记数据已保存到文件: {notes_filename}")
                print(f"本次获取到 {len(notes)} 条笔记。累计 {total_notes_count} 条。")
            else:
                print("未提取到任何笔记内容！")
            print(f"笔记处理完成 - {time.strftime('%X')}")

        # --- 处理商品API ---
        elif "search.xiaohongshu.com/api/search/fls/products/v5" in request_url:
            start_time = time.strftime("%X")
            print(f"开始处理【商品】请求 - {start_time} - URL: {request_url}")
            
            try:
                content = json.loads(flow.response.text)
                products = []
                
                # 根据你提供的JSON结构进行解析
                if "success" in content and content["success"] and "data" in content:
                    data = content["data"]
                    
                    # 检查module是否存在且包含data列表
                    if "module" in data and "data" in data["module"] and isinstance(data["module"]["data"], list):
                        module_data_list = data["module"]["data"]
                        print(f"找到 {len(module_data_list)} 个商品卡片")
                        
                        # 处理每个商品卡片
                        for i, item in enumerate(module_data_list):
                            if "card_name" in item and "cosmos_search_goods_card" in item["card_name"] and "content" in item:
                                item_content = item["content"]
                                
                                if not isinstance(item_content, dict) or "id" not in item_content:
                                    print(f"  商品卡片 {item['id']} 的内容无效或缺少ID")
                                    continue
                                
                                # 提取商品ID和标题
                                product_id = item_content.get("id")
                                title = item_content.get("title", "")
                                
                                # 提取价格信息
                                price_info = item_content.get("price_info", {})
                                current_price = price_info.get("price")
                                original_price = price_info.get("origin_price")
                                
                                # 提取销量信息
                                sales_volume_text = "未知销量"
                                tag_strategy_map = item_content.get("tag_strategy_map", {})
                                if "after_price" in tag_strategy_map and isinstance(tag_strategy_map["after_price"], list):
                                    for tag in tag_strategy_map["after_price"]:
                                        if tag.get("type") == "sold" and "tag_content" in tag:
                                            sales_volume_text = tag["tag_content"].get("content", "未知销量")
                                            break
                                
                                # 提取店铺信息
                                vendor = item_content.get("vendor", {})
                                vendor_name = vendor.get("vendor_name", "")
                                seller_id = vendor.get("seller_id", "")
                                
                                # 提取图片信息
                                main_image_url = ""
                                image_list = item_content.get("image", [])
                                if image_list and len(image_list) > 0 and "url" in image_list[0]:
                                    main_image_url = image_list[0]["url"]
                                
                                # 提取商品链接
                                product_link = item_content.get("link", "")
                                
                                # 创建商品数据对象
                                product = {
                                    "product_id": product_id,
                                    "title": title,
                                    "current_price": current_price,
                                    "original_price": original_price,
                                    "sales_volume_text": sales_volume_text,
                                    "vendor_name": vendor_name,
                                    "seller_id": seller_id,
                                    "main_image_url": main_image_url,
                                    "product_link": product_link,
                                    "keyword": keyword,
                                    "crawl_time": time.strftime('%Y-%m-%d %H:%M:%S'),
                                    "data_type": "product"
                                }
                                
                                products.append(product)
                                print(f"  成功添加商品: {title[:30]}... (ID: {product_id})")
                        
                        print(f"共提取 {len(products)} 个商品")
                    else:
                        print("API响应中未找到module.data数组")
                else:
                    print("API响应success为false或缺少必要的数据结构")

                # 保存商品数据
                total_products_count += len(products)
                if products:
                    products_filename = f"xhs_data/products_{time.strftime('%Y%m%d_%H%M%S')}_{keyword}.json"
                    with open(products_filename, "w", encoding="utf-8") as f:
                        json.dump(products, f, ensure_ascii=False, indent=2)
                    print(f"商品数据已保存到文件: {products_filename}")
                    print(f"本次获取到 {len(products)} 条商品。累计 {total_products_count} 条。")
                else:
                    print("未提取到任何商品内容！")
            except Exception as e:
                print(f"处理商品数据时发生错误: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"商品处理完成 - {time.strftime('%X')}")

except Exception as e:
    import traceback
    print(f"发生严重错误: {e}")
    print(traceback.format_exc()) # 打印完整的错误堆栈信息

# 如何运行此脚本:
# mitmproxy -s http_handle.py
# 或者 (无交互界面，仅日志):
# mitmdump -s http_handle.py