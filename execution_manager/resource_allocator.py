import yaml # 用于读取 YAML 配置文件, 需要 pip install PyYAML
import os
from . import adb_helper # 从同一目录导入 adb_helper

class ResourceAllocator:
    def __init__(self, config_file_path='config/appium_instances_config.yaml'):
        """
        初始化资源分配器。
        :param config_file_path: Appium 服务器实例配置文件的相对路径 (相对于项目根目录)。
        """
        # 构建配置文件的绝对路径，假设此脚本位于 execution_manager 文件夹中
        # 项目根目录 -> config -> appium_instances_config.yaml
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        absolute_config_path = os.path.join(project_root, config_file_path)

        try:
            with open(absolute_config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                self.appium_servers_config = config_data.get('appium_servers', [])
            if not self.appium_servers_config:
                print(f"警告: 从 '{absolute_config_path}' 加载的 Appium 服务器配置为空或格式不正确。")
        except FileNotFoundError:
            print(f"错误: Appium 实例配置文件未找到于 '{absolute_config_path}'")
            self.appium_servers_config = []
        except Exception as e:
            print(f"错误: 加载或解析 Appium 实例配置文件 '{absolute_config_path}' 失败: {e}")
            self.appium_servers_config = []
        
        # 用于跟踪哪些 Appium 服务器 ID 和模拟器 ID 当前“繁忙”
        # 使用集合 (set) 可以快速添加、删除和检查成员资格
        self._busy_server_ids = set()
        self._busy_emulator_ids = set()
        print(f"ResourceAllocator 初始化完毕。已加载 {len(self.appium_servers_config)} 个 Appium 服务器配置。")

    def allocate_resource(self):
        """
        查找并分配一个空闲的 Appium 服务器和模拟器组合。
        
        返回: 
            一个包含分配信息的字典，例如：
            {
                'appium_url': 'http://127.0.0.1:4723',
                'emulator_id': '127.0.0.1:16384', // 这是从 adb_helper 获取的实际在线且匹配的模拟器ID
                'system_port': 8200, 
                'chromedriver_port': 9515,
                'appium_server_id': 'mumu_16384' // 服务器配置中的ID，用于后续释放
            }
            如果没有可用资源，则返回 None。
        """
        online_emulators = adb_helper.get_online_emulator_ids()
        if not online_emulators:
            print("ResourceAllocator: 未检测到任何在线模拟器。")
            return None

        print(f"ResourceAllocator: 检测到在线模拟器: {online_emulators}")
        print(f"ResourceAllocator: 当前繁忙的服务器ID: {self._busy_server_ids}")
        print(f"ResourceAllocator: 当前繁忙的模拟器ID: {self._busy_emulator_ids}")

        for server_conf in self.appium_servers_config:
            server_id = server_conf.get('id')
            appium_url = server_conf.get('url')
            intended_emulator_id = server_conf.get('intended_emulator_id') # 从配置中获取期望的模拟器ID

            # 1. 检查此 Appium 服务器是否空闲
            if server_id in self._busy_server_ids:
                print(f"ResourceAllocator: 服务器 '{server_id}' 当前繁忙，跳过。")
                continue

            # 2. 检查此服务器期望的模拟器是否在线且空闲
            if intended_emulator_id and intended_emulator_id in online_emulators:
                if intended_emulator_id not in self._busy_emulator_ids:
                    # 找到了一个与服务器配置中 intended_emulator_id 匹配的、在线且空闲的模拟器
                    self._busy_server_ids.add(server_id)
                    self._busy_emulator_ids.add(intended_emulator_id)
                    
                    allocation = {
                        'appium_url': appium_url,
                        'emulator_id': intended_emulator_id, # 使用配置中定义的 ID
                        'system_port': server_conf.get('system_port'),
                        'chromedriver_port': server_conf.get('chromedriver_port'),
                        'appium_server_id': server_id
                    }
                    print(f"ResourceAllocator: 已分配服务器 '{server_id}' 给模拟器 '{intended_emulator_id}'.")
                    return allocation
                else:
                    print(f"ResourceAllocator: 模拟器 '{intended_emulator_id}' (服务器 '{server_id}' 的目标) 当前繁忙。")
            elif intended_emulator_id:
                print(f"ResourceAllocator: 模拟器 '{intended_emulator_id}' (服务器 '{server_id}' 的目标) 当前不在线。")
            # 如果没有配置 intended_emulator_id，或者 intended_emulator_id 不在线/繁忙，
            # 可以选择一个当前不繁忙的任意在线模拟器 (这里为了简单，我们先强依赖 intended_emulator_id 的匹配)
            # 若要更灵活，可以取消下面的注释块，并调整逻辑：
            # else: # 服务器配置没有指定 intended_emulator_id，或指定的不满足条件
            #     for online_emu_id in online_emulators:
            #         if online_emu_id not in self._busy_emulator_ids:
            #             self._busy_server_ids.add(server_id)
            #             self._busy_emulator_ids.add(online_emu_id)
            #             allocation = { ... 'emulator_id': online_emu_id, ...}
            #             print(f"ResourceAllocator: 已分配服务器 '{server_id}' 给任意空闲模拟器 '{online_emu_id}'.")
            #             return allocation
        
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
    print("测试 ResourceAllocator (请确保 config/appium_instances_config.yaml 文件存在且配置正确，并有模拟器在运行):")
    
    # 假设您的项目结构是:
    # project_root/
    #  config/
    #    appium_instances_config.yaml
    #  execution_manager/
    #    resource_allocator.py
    #    adb_helper.py
    # 如果直接运行 resource_allocator.py，它可能无法正确找到位于父目录的 config 文件夹。
    # 在实际的测试运行器中，路径问题会更容易处理。
    # 为了直接测试，您可能需要调整 config_file_path 的默认值，或在创建实例时传入绝对路径。
    # 例如，可以这样调整测试代码：
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
            
        print("\n--- 第三次分配 ---") # 假设您配置了至少3个服务器/或期望第三次分配失败
        res3 = allocator.allocate_resource()
        if res3:
            print(f"分配结果3: {res3}")
        else:
            print("第三次分配失败。")

        print("\n--- 释放资源1 ---")
        if res1:
            allocator.release_resource(res1)
            
        print("\n--- 再次尝试分配 (释放 res1 后) ---")
        res_after_release = allocator.allocate_resource()
        if res_after_release:
            print(f"再次分配结果: {res_after_release}")
            print("\n--- 释放所有已分配资源 (res2, res3, res_after_release) ---")
            if res2: allocator.release_resource(res2)
            if res3: allocator.release_resource(res3) # 即使 res3 为 None, 也不会出错
            allocator.release_resource(res_after_release)
        else:
            print("释放 res1 后再次分配失败。")
            print("\n--- 释放剩余已分配资源 (res2, res3) ---")
            if res2: allocator.release_resource(res2)
            if res3: allocator.release_resource(res3)
            
    except Exception as main_e:
        print(f"测试过程中发生主错误: {main_e}")