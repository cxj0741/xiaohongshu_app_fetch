#  python -m execution_manager.mumu_connector
import subprocess
import os
import json
import time
from pathlib import Path
import platform
from config.environment import EnvironmentConfig

class MuMuConnector:
    def __init__(self, mumu_path=None, max_instance=3):
        """
        初始化MuMu连接器
        :param mumu_path: MuMu模拟器的安装路径
        :param max_instance: 最大检测实例数量
        """
        self.max_instance = max_instance
        
        if EnvironmentConfig.is_docker():
            # Docker环境下，直接读取共享文件
            self.devices_file = Path("/xiaohongshuZDH/shared_data/mumu_devices.json")
            # Docker环境下不需要manager_exe
            self.manager_exe = None
        else:
            # 本地环境使用完整路径
            if mumu_path is None:
                mumu_path = EnvironmentConfig.get_mumu_path()
            self.mumu_path = Path(mumu_path)
            self.shell_path = self.mumu_path / 'shell'
            self.manager_exe = self.shell_path / 'MuMuManager.exe'
        
        if not Path(self.manager_exe).exists():
            raise FileNotFoundError(f"MuMuManager.exe 未找到: {self.manager_exe}")
        
        print(f"MuMu连接器初始化完成，路径: {self.mumu_path}")
    
    def get_running_instances(self):
        """获取所有正在运行的MuMu实例及其ADB端口"""
        if EnvironmentConfig.is_docker():
            try:
                with open(self.devices_file, 'r') as f:
                    data = json.load(f)
                
                running_instances = []
                for device in data.get('devices', []):
                    # 替换localhost和127.0.0.1为host.docker.internal
                    adb_host = EnvironmentConfig.get_mumu_host() if device['adb_host'] in ['localhost', '127.0.0.1'] else device['adb_host']
                    
                    instance_info = {
                        'id': device['id'],
                        'adb_host': adb_host,
                        'adb_port': device['adb_port'],
                        'device_id': f"{adb_host}:{device['adb_port']}"
                    }
                    running_instances.append(instance_info)
                    print(f"从文件检测到运行中的MuMu实例 {instance_info['id']}: {instance_info['device_id']}")
                
                return running_instances
            except Exception as e:
                print(f"从文件读取MuMu实例信息时出错: {e}")
                return []
        else:
            # 原有的exe调用逻辑
            return self._get_instances_from_exe()
    
    def _get_instances_from_exe(self):
        """从exe获取实例信息（原有的get_running_instances方法的内容）"""
        running_instances = []
        
        # 检查从0到max_instance-1的实例
        for i in range(self.max_instance):
            try:
                cmd = [str(self.manager_exe), 'adb', '-v', str(i)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                data = json.loads(result.stdout)
                
                if 'errcode' in data and data['errcode'] == -201:
                    print(f"MuMu实例 {i} 未运行")
                    continue
                
                if 'adb_host' in data and 'adb_port' in data:
                    # 在Docker环境下替换localhost为host.docker.internal
                    adb_host = EnvironmentConfig.get_mumu_host() if data['adb_host'] == 'localhost' else data['adb_host']
                    
                    instance_info = {
                        'id': i,
                        'adb_host': adb_host,
                        'adb_port': data['adb_port'],
                        'device_id': f"{adb_host}:{data['adb_port']}"
                    }
                    running_instances.append(instance_info)
                    print(f"检测到运行中的MuMu实例 {i}: {instance_info['device_id']}")
            except Exception as e:
                print(f"检测MuMu实例 {i} 时出错: {e}")
        
        return running_instances
    
    def connect_all_instances(self):
        """连接所有运行中的MuMu实例到ADB"""
        instances = self.get_running_instances()
        connected_devices = []
        
        if not instances:
            print("未检测到任何运行中的MuMu实例")
            return []
        
        for instance in instances:
            try:
                device_id = instance['device_id']
                # 尝试连接ADB
                cmd = ['adb', 'connect', device_id]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                print(f"连接结果 ({device_id}): {result.stdout.strip()}")
                
                # 检查连接状态
                connected = self.verify_device_connected(device_id)
                if connected:
                    connected_devices.append(instance)
                    print(f"成功连接MuMu模拟器 {instance['id']}: {device_id}")
                else:
                    print(f"无法连接MuMu模拟器 {instance['id']}: {device_id}")
            except Exception as e:
                print(f"连接MuMu实例 {instance['id']} 时出错: {e}")
        
        return connected_devices
    
    def verify_device_connected(self, device_id):
        """验证设备是否已连接到ADB"""
        try:
            cmd = ['adb', 'devices']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return device_id in result.stdout and "device" in result.stdout
        except Exception as e:
            print(f"验证设备连接时出错: {e}")
            return False
    
    def restart_adb_server(self):
        """重启ADB服务器"""
        try:
            subprocess.run(['adb', 'kill-server'], timeout=5)
            time.sleep(1)
            subprocess.run(['adb', 'start-server'], timeout=5)
            print("ADB服务器已重启")
            return True
        except Exception as e:
            print(f"重启ADB服务器时出错: {e}")
            return False

def main():
    # 从环境变量或默认路径创建连接器
    mumu_path = os.getenv('MUMU_PATH')
    connector = MuMuConnector(mumu_path=mumu_path)
    
    print("正在重启ADB服务器...")
    connector.restart_adb_server()
    
    print("正在连接所有MuMu模拟器实例...")
    connected_devices = connector.connect_all_instances()
    
    print("\n=== 连接摘要 ===")
    if connected_devices:
        print(f"成功连接 {len(connected_devices)} 个MuMu模拟器:")
        for device in connected_devices:
            print(f"- 实例 {device['id']}: {device['device_id']}")
    else:
        print("未连接任何MuMu模拟器。")

if __name__ == "__main__":
    main()