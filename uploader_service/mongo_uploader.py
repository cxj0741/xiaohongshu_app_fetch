import json
import os
import time
import pymongo
from datetime import datetime
import glob
import shutil # 用于移动文件夹
import re     # 用于清理集合名称

# MongoDB 连接配置
MONGO_URI = "mongodb+srv://webcrawler:4Zqbi0qNguF2dDfL@webcrawler.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
DB_NAME = "xiaohongshu"
NOTES_COLLECTION = "notes"
# PRODUCTS_COLLECTION 不再用作全局商品集合名，因为每个任务有自己的集合
# 添加检查间隔时间（秒）
CHECK_INTERVAL = 60
# 数据主目录
DATA_DIR = "xhs_data"
PROCESSED_NOTES_DIR = os.path.join(DATA_DIR, "processed_notes") # 单独存放处理过的笔记文件
PROCESSED_TASKS_DIR = os.path.join(DATA_DIR, "processed_product_tasks") # 存放处理过的商品任务文件夹

def connect_mongodb():
    """连接到MongoDB并返回数据库客户端"""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        server_info = client.server_info()
        print(f"MongoDB连接成功! 版本: {server_info.get('version')}")
        db = client[DB_NAME]
        
        # 配置笔记集合（如果尚不存在）
        notes_collection = db[NOTES_COLLECTION]
        if NOTES_COLLECTION not in db.list_collection_names():
            print(f"创建笔记集合索引: {NOTES_COLLECTION} on note_id")
            notes_collection.create_index("note_id", unique=True)
        
        return client, db
    except Exception as e:
        print(f"MongoDB连接错误: {e}")
        raise

def process_note(note):
    """处理笔记数据，提取有用信息"""
    processed_note = {
        "note_id": note.get("note_id") or note.get("id"),
        "title": note.get("title", ""),
        "desc": note.get("desc", ""),
        "type": note.get("type", ""),
        "user": {
            "userid": note.get("user", {}).get("userid", ""),
            "nickname": note.get("user", {}).get("nickname", ""),
            "red_id": note.get("user", {}).get("red_id", "")
        },
        "stats": {
            "liked_count": note.get("liked_count", 0),
            "collected_count": note.get("collected_count", 0),
            "comments_count": note.get("comments_count", 0),
            "shared_count": note.get("shared_count", 0)
        },
        "images": [img.get("url_size_large", "") for img in note.get("images_list", []) if "url_size_large" in img],
        "video_info": {
            "duration": note.get("video_info_v2", {}).get("capa", {}).get("duration", 0),
            "thumbnail": note.get("video_info_v2", {}).get("image", {}).get("thumbnail", "")
        } if "video_info_v2" in note else None,
        "keyword": note.get("keyword", ""),
        "crawl_time": note.get("crawl_time", ""), # 来自mitmproxy脚本
        "upload_time": datetime.utcnow(), # 新增上传时间
        "geo_info": note.get("geo_info", {}),
        "tags": [tag.strip("#") for tag in note.get("desc", "").split("#") if tag.strip()],
    }
    
    if note.get("timestamp"): # 小红书笔记本身的创建时间戳
        processed_note["created_at_xhs"] = datetime.fromtimestamp(note["timestamp"])
    if note.get("update_time"): # 小红书笔记本身的更新时间戳
        processed_note["updated_at_xhs"] = datetime.fromtimestamp(note["update_time"] / 1000)
        
    return processed_note

def process_product(product):
    """处理商品数据，提取有用信息"""
    # 从你的 mitmproxy 脚本获取的字段
    processed_product = {
        "product_id": product.get("product_id"),
        "title": product.get("title", ""),
        "current_price_display": product.get("current_price_display"),
        "current_price_numeric": product.get("current_price_numeric"),
        "original_price_display": product.get("original_price_display"),
        "sales_volume_text": product.get("sales_volume_text", "未知销量"),
        "sales_volume_numeric": product.get("sales_volume_numeric"),
        "sales_revenue": product.get("sales_revenue", "未知销售额"),
        "all_tags": product.get("all_tags", []),
        "vendor": {
            "vendor_name": product.get("vendor_name", ""),
            "seller_id": product.get("seller_id", "")
        },
        "images": [product.get("main_image_url", "")] if product.get("main_image_url") else [],
        "product_link": product.get("product_link", ""),
        "keyword": product.get("keyword", ""), # 搜索该商品时使用的关键词
        "crawl_time": product.get("crawl_time", ""), # 来自mitmproxy脚本
        "upload_time": datetime.utcnow() # 新增上传时间
        # "raw_data": product.get("raw_data", {}) # 如果需要存储原始数据，可以取消注释
    }
    return processed_product

def sanitize_collection_name(name):
    """清理字符串以用作MongoDB集合名"""
    # 移除MongoDB集合名中不允许的字符，例如 '$'
    # 将其他非字母数字字符替换为下划线
    name = name.replace("$", "") 
    name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    # MongoDB集合名不能以 "system." 开头，也不能为空
    if name.startswith("system."):
        name = "sys_" + name[7:]
    if not name:
        name = "default_collection"
    # 限制长度，例如最多100个字符 (MongoDB自身有长度限制，但具体看版本)
    return name[:100]


def import_data():
    """导入数据到MongoDB"""
    client, db = connect_mongodb()
    notes_collection = db[NOTES_COLLECTION] # notes还是存到总集
    
    total_notes_imported_session = 0
    total_products_imported_session = 0
    
    try:
        # --- 处理笔记数据 (逻辑不变) ---
        notes_json_files = glob.glob(os.path.join(DATA_DIR, "notes_*.json"))
        if not notes_json_files:
            print("没有找到新的笔记JSON文件")
        else:
            print(f"找到 {len(notes_json_files)} 个笔记JSON文件待处理")
            for file_path in notes_json_files:
                print(f"\n处理笔记文件: {file_path}")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        notes = json.load(f)
                    print(f"从文件读取到 {len(notes)} 条笔记")
                    for note in notes:
                        try:
                            processed_note = process_note(note)
                            if not processed_note["note_id"]:
                                print(f"警告: 笔记缺少note_id字段，跳过。内容: {str(note)[:100]}")
                                continue
                            result = notes_collection.update_one(
                                {"note_id": processed_note["note_id"]},
                                {"$set": processed_note},
                                upsert=True
                            )
                            if result.modified_count > 0 or result.upserted_id:
                                total_notes_imported_session += 1
                        except Exception as e_item:
                            print(f"处理单条笔记时出错: {e_item}")
                    move_file_to_processed(file_path, PROCESSED_NOTES_DIR)
                except Exception as e_file:
                    print(f"处理笔记文件 {file_path} 时出错: {e_file}")
        
        # --- 处理商品数据 (新逻辑：按任务文件夹处理) ---
        # 遍历 DATA_DIR 下的所有子目录（这些被视为任务文件夹）
        print(f"\n开始扫描商品任务文件夹于: {DATA_DIR}")
        task_folders_processed_this_run = 0
        products_in_tasks_imported_this_run = 0

        for item_name in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item_name)
            if os.path.isdir(item_path) and item_name not in ["processed_notes", "processed_product_tasks"]:
                # 这应该是一个任务文件夹
                task_folder_name = item_name
                task_folder_path = item_path
                print(f"\n发现商品任务文件夹: {task_folder_name}")

                # 1. 根据任务文件夹名确定/创建 MongoDB Collection 名称
                # 你可能需要更复杂的逻辑来从文件夹名提取有意义的集合名，例如去掉时间戳部分等
                # 这里简单地使用清理后的文件夹名作为集合名，并加上 "products_" 前缀
                collection_name_raw = task_folder_name 
                collection_name = "products_" + sanitize_collection_name(collection_name_raw)
                
                task_specific_collection = db[collection_name]
                # 为新集合创建索引 (如果集合是新创建的)
                if collection_name not in db.list_collection_names() or not task_specific_collection.index_information():
                     print(f"为集合 {collection_name} 创建 product_id 唯一索引...")
                     task_specific_collection.create_index("product_id", unique=True)

                print(f"数据将导入到集合: {collection_name}")

                # 2. 查找该任务文件夹下的所有 products_*.json 文件
                product_json_files_in_task = glob.glob(os.path.join(task_folder_path, "products_*.json"))
                if not product_json_files_in_task:
                    print(f"任务文件夹 {task_folder_name} 中没有找到 products_*.json 文件。")
                    # 可以考虑是否要移动空的任务文件夹，或有其他处理逻辑
                    # 如果任务文件夹为空或者没有product json，可以选择移动或保留
                    if not os.listdir(task_folder_path): # 检查文件夹是否为空
                         print(f"任务文件夹 {task_folder_name} 为空，将其移动到已处理。")
                         move_folder_to_processed(task_folder_path, PROCESSED_TASKS_DIR, task_folder_name)
                    continue

                print(f"在任务 {task_folder_name} 中找到 {len(product_json_files_in_task)} 个商品JSON文件。")
                
                current_task_products_imported = 0
                all_files_in_task_processed = True
                for file_path in product_json_files_in_task:
                    print(f"  处理商品文件: {file_path}")
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            products = json.load(f)
                        print(f"  从文件读取到 {len(products)} 条商品")
                        for product in products:
                            try:
                                processed_product = process_product(product)
                                if not processed_product["product_id"]:
                                    print(f"  警告: 商品缺少product_id字段，跳过。内容: {str(product)[:100]}")
                                    continue
                                result = task_specific_collection.update_one(
                                    {"product_id": processed_product["product_id"]},
                                    {"$set": processed_product},
                                    upsert=True
                                )
                                if result.modified_count > 0 or result.upserted_id:
                                    current_task_products_imported += 1
                            except Exception as e_item_prod:
                                print(f"  处理单条商品时出错: {e_item_prod}")
                                all_files_in_task_processed = False # 标记此任务文件夹中有文件处理失败
                        # 单个json文件处理完后，可以不立即移动，等整个文件夹处理完再移动
                    except Exception as e_file_prod:
                        print(f"  处理商品文件 {file_path} 时出错: {e_file_prod}")
                        all_files_in_task_processed = False # 标记此任务文件夹中有文件处理失败
                
                products_in_tasks_imported_this_run += current_task_products_imported
                print(f"任务 {task_folder_name} 共导入/更新 {current_task_products_imported} 条商品到集合 {collection_name}")

                if all_files_in_task_processed and product_json_files_in_task: # 确保有文件且都处理了
                    task_folders_processed_this_run += 1
                    move_folder_to_processed(task_folder_path, PROCESSED_TASKS_DIR, task_folder_name)
                else:
                    print(f"警告: 任务文件夹 {task_folder_name} 未完全处理成功，本次不移动。")

        return total_notes_imported_session, products_in_tasks_imported_this_run, task_folders_processed_this_run

    finally:
        print("关闭MongoDB连接。")
        client.close()

def move_file_to_processed(file_path, processed_base_dir):
    """将已处理的单个文件移动到对应的processed目录"""
    if not os.path.exists(processed_base_dir):
        os.makedirs(processed_base_dir)
    try:
        destination_path = os.path.join(processed_base_dir, os.path.basename(file_path))
        shutil.move(file_path, destination_path) # shutil.move 可以覆盖同名文件
        print(f"文件已移动到: {destination_path}")
    except Exception as e:
        print(f"移动文件 {file_path} 到 {processed_base_dir} 失败: {e}")

def move_folder_to_processed(folder_path, processed_base_tasks_dir, original_folder_name):
    """将已处理的整个任务文件夹移动到processed_tasks目录"""
    if not os.path.exists(processed_base_tasks_dir):
        os.makedirs(processed_base_tasks_dir)
    
    destination_folder_path = os.path.join(processed_base_tasks_dir, original_folder_name)
    
    try:
        # 如果目标文件夹已存在，可以选择删除或备份，这里简单地先尝试删除旧的
        if os.path.exists(destination_folder_path):
            print(f"警告: 目标处理文件夹 {destination_folder_path} 已存在，将先删除旧的。")
            shutil.rmtree(destination_folder_path) # 小心使用 rmtree
        
        shutil.move(folder_path, destination_folder_path)
        print(f"任务文件夹 {original_folder_name} 已移动到: {destination_folder_path}")
    except Exception as e:
        print(f"移动任务文件夹 {original_folder_name} 到 {processed_base_tasks_dir} 失败: {e}")


def main():
    """主函数"""
    print("\n=== 小红书数据导入程序 (商品按任务文件夹分集合) ===")
    print(f"数据根目录: {DATA_DIR}")
    print(f"MongoDB URI: {MONGO_URI[:30]}...{MONGO_URI[-20:] if len(MONGO_URI) > 50 else ''}") # 避免完整打印敏感信息
    print(f"数据库名: {DB_NAME}")
    print(f"固定笔记集合: {NOTES_COLLECTION}")
    print(f"商品数据将按任务文件夹名动态创建集合 (例如: products_关键词_日期_时间戳)")
    print(f"检查间隔: {CHECK_INTERVAL}秒")
    
    # 创建已处理目录 (如果不存在)
    if not os.path.exists(PROCESSED_NOTES_DIR):
        os.makedirs(PROCESSED_NOTES_DIR)
    if not os.path.exists(PROCESSED_TASKS_DIR):
        os.makedirs(PROCESSED_TASKS_DIR)

    try:
        client, db_test = connect_mongodb()
        print(f"当前数据库中笔记总数 ({NOTES_COLLECTION}): {db_test[NOTES_COLLECTION].count_documents({})}")
        # 商品总数现在难以简单统计，因为它们分散在多个集合
        client.close()
    except Exception as e:
        print(f"数据库连接测试失败，程序退出: {e}")
        return
    
    print("\n开始监控文件和任务文件夹...")
    while True:
        try:
            current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{current_time_str}] 开始新一轮检查...")
            
            notes_imported_count, products_imported_count, tasks_processed_count = import_data()
            
            if notes_imported_count > 0 or products_imported_count > 0 or tasks_processed_count > 0:
                print(f"本轮结果: 导入笔记 {notes_imported_count} 条, "
                      f"从 {tasks_processed_count} 个任务文件夹中导入商品 {products_imported_count} 条。")
            else:
                print("本轮未发现或导入任何新数据。")
            
            print(f"等待 {CHECK_INTERVAL} 秒后继续...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n程序被用户终止。")
            break
        except Exception as e_main_loop:
            print(f"主循环发生错误: {e_main_loop}")
            print(f"等待 {CHECK_INTERVAL} 秒后重试...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()