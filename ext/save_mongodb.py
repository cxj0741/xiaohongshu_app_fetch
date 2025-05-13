import json
import os
import time
import pymongo
from datetime import datetime
import glob

# MongoDB 连接配置
MONGO_URI = "mongodb+srv://webcrawler:4Zqbi0qNguF2dDfL@webcrawler.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
DB_NAME = "xiaohongshu"
NOTES_COLLECTION = "notes"
PRODUCTS_COLLECTION = "products"  # 新增商品集合
# 添加检查间隔时间（秒）
CHECK_INTERVAL = 60

def connect_mongodb():
    """连接到MongoDB并返回数据库客户端和集合"""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        # 测试连接
        server_info = client.server_info()
        print(f"MongoDB连接成功! 版本: {server_info.get('version')}")
        
        db = client[DB_NAME]
        
        # 获取并配置笔记集合
        notes_collection = db[NOTES_COLLECTION]
        notes_collection.create_index("note_id", unique=True)
        
        # 获取并配置商品集合
        products_collection = db[PRODUCTS_COLLECTION]
        products_collection.create_index("product_id", unique=True)
        
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
        "crawl_time": note.get("crawl_time", ""),
        "geo_info": note.get("geo_info", {}),
        "tags": [tag.strip("#") for tag in note.get("desc", "").split("#") if tag.strip()],
    }
    
    # 添加时间处理
    if note.get("timestamp"):
        processed_note["created_at"] = datetime.fromtimestamp(note["timestamp"])
    if note.get("update_time"):
        processed_note["updated_at"] = datetime.fromtimestamp(note["update_time"] / 1000)
        
    return processed_note

def process_product(product):
    """处理商品数据，提取有用信息"""
    processed_product = {
        "product_id": product.get("product_id"),
        "title": product.get("title", ""),
        "current_price": product.get("current_price"),
        "original_price": product.get("original_price"),
        "sales_volume_text": product.get("sales_volume_text", ""),
        "vendor": {
            "vendor_name": product.get("vendor_name", ""),
            "seller_id": product.get("seller_id", "")
        },
        "images": [product.get("main_image_url", "")] if product.get("main_image_url") else [],
        "product_link": product.get("product_link", ""),
        "keyword": product.get("keyword", ""),
        "crawl_time": product.get("crawl_time", ""),
        # 如果有原始数据，可以提取更多字段
        "raw_data": product.get("raw_data", {})
    }
    
    return processed_product

def import_data():
    """导入数据到MongoDB"""
    client, db = connect_mongodb()
    notes_collection = db[NOTES_COLLECTION]
    products_collection = db[PRODUCTS_COLLECTION]
    
    try:
        # 处理笔记数据
        notes_imported = import_notes(notes_collection)
        
        # 处理商品数据
        products_imported = import_products(products_collection)
        
        return notes_imported, products_imported
    finally:
        client.close()

def import_notes(collection):
    """导入笔记数据到MongoDB"""
    # 获取所有笔记json文件
    json_files = glob.glob("xhs_data/notes_*.json")
    if not json_files:
        print("没有找到新的笔记JSON文件")
        return 0
        
    print(f"找到 {len(json_files)} 个笔记JSON文件")
    
    notes_imported = 0
    for file_path in json_files:
        print(f"\n处理笔记文件: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                notes = json.load(f)
            
            print(f"从文件读取到 {len(notes)} 条笔记")
            
            for note in notes:
                try:
                    processed_note = process_note(note)
                    
                    if not processed_note["note_id"]:
                        print(f"警告: 笔记缺少note_id字段")
                        continue
                        
                    # 使用note_id作为唯一标识
                    result = collection.update_one(
                        {"note_id": processed_note["note_id"]},
                        {"$set": processed_note},
                        upsert=True
                    )
                    
                    if result.modified_count > 0:
                        print(f"更新笔记: {processed_note['note_id']}")
                        notes_imported += 1
                    elif result.upserted_id:
                        print(f"新增笔记: {processed_note['note_id']}")
                        notes_imported += 1
                        
                except Exception as e:
                    print(f"处理笔记时出错: {e}")
                    continue
            
            # 处理完成后移动文件到已处理目录
            move_to_processed(file_path)
            
        except Exception as e:
            print(f"处理笔记文件时出错: {e}")
            continue
    
    return notes_imported

def import_products(collection):
    """导入商品数据到MongoDB"""
    # 获取所有商品json文件
    json_files = glob.glob("xhs_data/products_*.json")
    if not json_files:
        print("没有找到新的商品JSON文件")
        return 0
        
    print(f"找到 {len(json_files)} 个商品JSON文件")
    
    products_imported = 0
    for file_path in json_files:
        print(f"\n处理商品文件: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                products = json.load(f)
            
            print(f"从文件读取到 {len(products)} 条商品")
            
            for product in products:
                try:
                    processed_product = process_product(product)
                    
                    if not processed_product["product_id"]:
                        print(f"警告: 商品缺少product_id字段")
                        continue
                        
                    # 使用product_id作为唯一标识
                    result = collection.update_one(
                        {"product_id": processed_product["product_id"]},
                        {"$set": processed_product},
                        upsert=True
                    )
                    
                    if result.modified_count > 0:
                        print(f"更新商品: {processed_product['product_id']}")
                        products_imported += 1
                    elif result.upserted_id:
                        print(f"新增商品: {processed_product['product_id']}")
                        products_imported += 1
                        
                except Exception as e:
                    print(f"处理商品时出错: {e}")
                    continue
            
            # 处理完成后移动文件到已处理目录
            move_to_processed(file_path)
            
        except Exception as e:
            print(f"处理商品文件时出错: {e}")
            continue
    
    return products_imported

def move_to_processed(file_path):
    """将已处理的文件移动到processed目录"""
    processed_dir = "xhs_data/processed"
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)
    os.rename(file_path, os.path.join(processed_dir, os.path.basename(file_path)))
    print(f"文件已移动到: {processed_dir}/{os.path.basename(file_path)}")

def main():
    """主函数"""
    print("\n=== 小红书数据导入程序 ===")
    print(f"MongoDB URI: {MONGO_URI}")
    print(f"数据库名: {DB_NAME}")
    print(f"笔记集合: {NOTES_COLLECTION}")
    print(f"商品集合: {PRODUCTS_COLLECTION}")
    print(f"检查间隔: {CHECK_INTERVAL}秒")
    
    # 测试数据库连接
    try:
        client, db = connect_mongodb()
        notes_count = db[NOTES_COLLECTION].count_documents({})
        products_count = db[PRODUCTS_COLLECTION].count_documents({})
        print(f"当前数据库中笔记总数: {notes_count}")
        print(f"当前数据库中商品总数: {products_count}")
        client.close()
    except Exception as e:
        print(f"数据库连接测试失败: {e}")
        return
    
    print("\n开始监控文件变化...")
    while True:
        try:
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{current_time}] 开始检查新文件...")
            
            notes_imported, products_imported = import_data()
            
            if notes_imported > 0 or products_imported > 0:
                print(f"本次导入: {notes_imported}条笔记, {products_imported}条商品")
            else:
                print("未导入任何新数据")
            
            print(f"等待 {CHECK_INTERVAL} 秒后继续...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n程序已停止")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            print(f"等待 {CHECK_INTERVAL} 秒后重试...")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()