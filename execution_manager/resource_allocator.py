import yaml # 用于读取 YAML 配置文件, 需要 pip install PyYAML
import os
import time
import random
import platform
import subprocess
from . import adb_helper # 从同一目录导入 adb_helper
import requests

class ResourceAllocator:
    def __init__(self, config_file_path='config/appium_instances_config.yaml'):
        """
        初始化资源分配器。
        :param config_file_path: Appium 服务器实例配置文件的相对路径 (相对于项目根目录)。
        """
        # 构建配置文件的绝对路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Docker环境使用特定的配置文件
        if os.getenv('RUNNING_MODE') == 'docker':
            config_file_path = 'config/appium_instances_config.docker.yaml'
            print(f"Docker环境检测到，使用配置文件: {config_file_path}")
        
        absolute_config_path = os.path.join(project_root, config_file_path)
        print(f"配置文件绝对路径: {absolute_config_path}")

        try:
            with open(absolute_config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                self.appium_servers_config = config_data.get('appium_servers', [])
                
                # Docker环境下修改URL
                if os.getenv('RUNNING_MODE') == 'docker':
                    for server in self.appium_servers_config:
                        if '127.0.0.1' in server['url']:
                            server['url'] = server['url'].replace('127.0.0.1', 'host.docker.internal')
                        
                # 打印加载的配置
                print("加载的Appium服务器配置:")
                for server in self.appium_servers_config:
                    print(f"  - ID: {server.get('id')}")
                    print(f"    URL: {server.get('url')}")
                    print(f"    模拟器: {server.get('intended_emulator_id')}")
            if not self.appium_servers_config:
                print(f"警告: 从 '{absolute_config_path}' 加载的 Appium 服务器配置为空或格式不正确。")
        except FileNotFoundError:
            print(f"错误: Appium 实例配置文件未找到于 '{absolute_config_path}'")
            self.appium_servers_config = []
        except Exception as e:
            print(f"错误: 加载或解析 Appium 实例配置文件 '{absolute_config_path}' 失败: {e}")
            self.appium_servers_config = []
        
        # 用于跟踪哪些 Appium 服务器 ID 和模拟器 ID 当前"繁忙"
        # 使用集合 (set) 可以快速添加、删除和检查成员资格
        self._busy_server_ids = set()
        self._busy_emulator_ids = set()
        
        # 记录每个服务器上次分配的模拟器ID，用于调试
        self._server_emulator_mapping = {}
        
        print(f"ResourceAllocator 初始化完毕。已加载 {len(self.appium_servers_config)} 个 Appium 服务器配置。")

    def verify_emulator_available(self, emulator_id):
        """
        验证模拟器是否真正可用
        """
        return adb_helper.verify_emulator_available(emulator_id)

    def _try_cleanup_uiautomator(self, device_id):
        """尝试清理可能崩溃的UiAutomator2服务"""
        try:
            print(f"尝试清理设备 {device_id} 上的UiAutomator服务...")
            # 检测操作系统
            is_windows = platform.system() == "Windows"
            
            # 停止服务
            subprocess.run([
                'adb', '-s', device_id, 'shell', 'am', 'force-stop', 'io.appium.uiautomator2.server'
            ], shell=is_windows, timeout=5)
            
            # 清理服务
            subprocess.run([
                'adb', '-s', device_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server'
            ], shell=is_windows, timeout=5)
            
            subprocess.run([
                'adb', '-s', device_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server.test'
            ], shell=is_windows, timeout=5)
            
            time.sleep(2)
            print(f"UiAutomator服务清理完成")
        except Exception as e:
            print(f"清理UiAutomator服务时出错: {e}")

    def verify_appium_server_running(self, server_url):
        """
        验证Appium服务器是否正常运行
        """
        try:
            print(f"正在验证Appium服务器URL: {server_url}")
            status_url = f"{server_url}/status"
            response = requests.get(status_url, timeout=5)
            
            if response.status_code == 200:
                print(f"Appium服务器 {server_url} 状态正常")
                return True
            else:
                print(f"Appium服务器 {server_url} 返回错误状态码: {response.status_code}")
                return False
        except Exception as e:
            print(f"连接Appium服务器 {server_url} 失败: {e}")
            return False

    def allocate_resource(self):
        """
        查找并分配一个空闲的 Appium 服务器和模拟器组合。
        
        返回: 
            一个包含分配信息的字典，例如：
            {
                'appium_url': 'http://127.0.0.1:4723',
                'emulator_id': '127.0.0.1:16384', 
                'system_port': 8200, 
                'chromedriver_port': 9515,
                'wda_local_port': 8100,
                'appium_server_id': 'server_1'
            }
            如果没有可用资源，则返回 None。
        """
        # 获取在线模拟器列表
        online_emulators = adb_helper.get_online_emulator_ids()
        if not online_emulators:
            print("ResourceAllocator: 未检测到任何在线模拟器。")
            return None

        print(f"ResourceAllocator: 检测到在线模拟器: {online_emulators}")
        print(f"ResourceAllocator: 当前繁忙的服务器ID: {self._busy_server_ids}")
        print(f"ResourceAllocator: 当前繁忙的模拟器ID: {self._busy_emulator_ids}")
        print(f"ResourceAllocator: 服务器-模拟器映射: {self._server_emulator_mapping}")

        # 随机打乱服务器配置顺序，避免总是分配同一个服务器
        shuffled_servers = list(self.appium_servers_config)
        random.shuffle(shuffled_servers)

        # 创建一个映射，记录每个模拟器被哪些服务器指定
        emulator_to_servers = {}
        for emu_id in online_emulators:
            emulator_to_servers[emu_id] = []
            
        # 找出每个在线模拟器被哪些服务器指定
        for server_conf in self.appium_servers_config:
            server_id = server_conf.get('id')
            intended_emu_id = server_conf.get('intended_emulator_id')
            
            if intended_emu_id in online_emulators:
                emulator_to_servers[intended_emu_id].append(server_id)
        
        print(f"ResourceAllocator: 模拟器与服务器对应关系: {emulator_to_servers}")

        # 遍历服务器配置进行分配
        for server_conf in shuffled_servers:
            server_id = server_conf.get('id')
            appium_url = server_conf.get('url')
            
            # 打印当前处理的服务器配置
            print(f"正在处理服务器配置:")
            print(f"  ID: {server_id}")
            print(f"  URL: {appium_url}")
            
            intended_emulator_id = server_conf.get('intended_emulator_id')

            # 1. 跳过已繁忙的服务器
            if server_id in self._busy_server_ids:
                print(f"ResourceAllocator: 服务器 '{server_id}' 当前繁忙，跳过。")
                continue
            
            # 新增：检查Appium服务器是否运行
            if not self.verify_appium_server_running(appium_url):
                print(f"ResourceAllocator: 服务器 '{server_id}' 的Appium实例 ({appium_url}) 未运行或无响应，跳过。")
                continue

            # 2. 尝试分配指定的模拟器
            target_emulator = None
            
            # 先尝试服务器的预期模拟器
            if intended_emulator_id and intended_emulator_id in online_emulators:
                if intended_emulator_id not in self._busy_emulator_ids:
                    # 验证模拟器是否真正可用
                    if self.verify_emulator_available(intended_emulator_id):
                        target_emulator = intended_emulator_id
                        print(f"ResourceAllocator: 服务器 '{server_id}' 使用其指定的模拟器 '{target_emulator}'。")
                    else:
                        print(f"ResourceAllocator: 服务器 '{server_id}' 的指定模拟器 '{intended_emulator_id}' 验证失败，尝试其他可用模拟器.")
                else:
                    print(f"ResourceAllocator: 模拟器 '{intended_emulator_id}' (服务器 '{server_id}' 的目标) 当前繁忙。")
            elif intended_emulator_id:
                print(f"ResourceAllocator: 模拟器 '{intended_emulator_id}' (服务器 '{server_id}' 的目标) 当前不在线。")
                
                # 如果指定的模拟器不在线，尝试分配任意空闲模拟器
                for emu_id in online_emulators:
                    if emu_id not in self._busy_emulator_ids and self.verify_emulator_available(emu_id):
                        target_emulator = emu_id
                        print(f"ResourceAllocator: 服务器 '{server_id}' 的指定模拟器不在线，使用替代模拟器 '{target_emulator}'。")
                        break
            else:
                # 服务器没有指定模拟器，尝试分配任意空闲模拟器
                for emu_id in online_emulators:
                    if emu_id not in self._busy_emulator_ids and self.verify_emulator_available(emu_id):
                        target_emulator = emu_id
                        print(f"ResourceAllocator: 服务器 '{server_id}' 没有指定模拟器，使用可用模拟器 '{target_emulator}'。")
                        break
                
            # 如果找到了可用模拟器，完成分配
            if target_emulator:
                # 清理UiAutomator2服务
                self._try_cleanup_uiautomator(target_emulator)
                
                # 标记资源为繁忙
                self._busy_server_ids.add(server_id)
                self._busy_emulator_ids.add(target_emulator)
                
                # 记录服务器-模拟器映射
                self._server_emulator_mapping[server_id] = target_emulator
                
                allocation = {
                    'appium_url': appium_url,
                    'emulator_id': target_emulator,
                    'system_port': server_conf.get('system_port'),
                    'chromedriver_port': server_conf.get('chromedriver_port'),
                    'wda_local_port': server_conf.get('wda_local_port'),
                    'appium_server_id': server_id
                }
                print(f"ResourceAllocator: 已分配服务器 '{server_id}' 给模拟器 '{target_emulator}'.")
                return allocation
        
        print("ResourceAllocator: 未找到可用的 Appium 服务器和模拟器组合。")
        return None

    def release_resource(self, allocation_info):
        """
        释放之前通过 allocate_resource() 分配的资源。
        :param allocation_info: allocate_resource() 返回的字典。
        """
        if not allocation_info or not isinstance(allocation_info, dict):
            print("ResourceAllocator: 释放资源失败，allocation_info 无效。")
            return

        server_id_to_release = allocation_info.get('appium_server_id')
        emulator_id_to_release = allocation_info.get('emulator_id')

        if server_id_to_release in self._busy_server_ids:
            self._busy_server_ids.remove(server_id_to_release)
            # 清理服务器-模拟器映射
            if server_id_to_release in self._server_emulator_mapping:
                del self._server_emulator_mapping[server_id_to_release]
            print(f"ResourceAllocator: Appium 服务器 '{server_id_to_release}' 已释放。")
        else:
            print(f"ResourceAllocator: 警告 - 尝试释放一个未标记为繁忙的服务器 '{server_id_to_release}'。")

        if emulator_id_to_release in self._busy_emulator_ids:
            self._busy_emulator_ids.remove(emulator_id_to_release)
            print(f"ResourceAllocator: 模拟器 '{emulator_id_to_release}' 已释放。")
        else:
            print(f"ResourceAllocator: 警告 - 尝试释放一个未标记为繁忙的模拟器 '{emulator_id_to_release}'。")

# --- 用于直接运行此文件进行测试 ---
if __name__ == '__main__':
    print("测试 ResourceAllocator:")
    
    try:
        # 获取当前脚本的父目录 (execution_manager)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 获取项目根目录 (execution_manager 的父目录)
        project_root_for_test = os.path.dirname(current_dir)
        # 构建配置文件的测试路径
        test_config_path = os.path.join(project_root_for_test, 'config', 'appium_instances_config.yaml')
        
        allocator = ResourceAllocator(config_file_path=test_config_path)
        
        print("\n--- 第一次分配 ---")
        res1 = allocator.allocate_resource()
        if res1:
            print(f"分配结果1: {res1}")
        else:
            print("第一次分配失败。")

        print("\n--- 第二次分配 ---")
        res2 = allocator.allocate_resource()
        if res2:
            print(f"分配结果2: {res2}")
        else:
            print("第二次分配失败。")
            
        if res1:
            print("\n--- 释放第一个资源 ---")
            allocator.release_resource(res1)
            
            print("\n--- 重新分配一次 ---")
            res3 = allocator.allocate_resource()
            if res3:
                print(f"重新分配结果: {res3}")
                allocator.release_resource(res3)
            else:
                print("重新分配失败。")
        
        if res2:
            print("\n--- 释放第二个资源 ---")
            allocator.release_resource(res2)
            
    except Exception as main_e:
        print(f"测试过程中发生错误: {main_e}")
        import traceback
        traceback.print_exc()

def initialize_app_services():
    global db, ALLOCATOR, server_health_status
    # 已有的初始化代码...
    
    # 在ResourceAllocator初始化成功后，检查所有服务器的状态
    if ALLOCATOR and ALLOCATOR.appium_servers_config:
        print("检查所有Appium服务器状态...")
        available_servers = 0
        
        for server_conf in ALLOCATOR.appium_servers_config:
            server_id = server_conf.get('id')
            server_url = server_conf.get('url')
            intended_emulator = server_conf.get('intended_emulator_id')
            
            if server_id and server_url:
                # 首先检查该服务器对应的模拟器是否在线
                emulator_online = False
                if intended_emulator:
                    online_emulators = get_online_emulator_ids()
                    if intended_emulator in online_emulators:
                        emulator_online = True
                        print(f"服务器 {server_id} 的指定模拟器 {intended_emulator} 在线。")
                    else:
                        print(f"警告: 服务器 {server_id} 的指定模拟器 {intended_emulator} 不在线。")
                
                # 再检查Appium服务是否正常运行
                server_running = ALLOCATOR.verify_appium_server_running(server_url)
                
                # 更新服务器健康状态
                if emulator_online and server_running:
                    available_servers += 1
                    server_health_status[server_id]['status'] = 'available'
                    print(f"服务器 {server_id} ({server_url}) 及其模拟器正常。")
                else:
                    server_health_status[server_id]['status'] = 'unavailable'
                    if not emulator_online:
                        print(f"警告: 服务器 {server_id} 的模拟器不在线。")
                    if not server_running:
                        print(f"警告: 服务器 {server_id} 的Appium服务 ({server_url}) 不可用。")
        
        if available_servers == 0:
            print("错误: 没有可用的Appium服务器和模拟器组合，程序无法正常工作。")
            return False
        else:
            print(f"共有 {available_servers}/{len(ALLOCATOR.appium_servers_config)} 个Appium服务器及模拟器可用。")
    
    return True