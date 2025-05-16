# python -m ext.host_mumu_connector
import subprocess
import json
import time
import os
from pathlib import Path
import platform

class HostMuMuConnector:
    def __init__(self, mumu_path=None, max_instance=3):
        """
        初始化宿主机MuMu连接器
        :param mumu_path: MuMu模拟器的安装路径
        :param max_instance: 最大检测实例数量
        """
        self.max_instance = max_instance
        
        # 如果没有提供路径，使用默认路径
        if mumu_path is None:
            mumu_path = r"E:\xiaohongshu\MuMu Player 12"
        
        self.mumu_path = Path(mumu_path)
        self.shell_path = self.mumu_path / 'shell'
        self.manager_exe = self.shell_path / 'MuMuManager.exe'
        
        if not self.manager_exe.exists():
            raise FileNotFoundError(f"MuMuManager.exe 未找到: {self.manager_exe}")
        
        # 确保输出目录存在
        self.output_dir = Path("shared_data")
        self.output_dir.mkdir(exist_ok=True)
        self.devices_file = self.output_dir / "mumu_devices.json"
        
        print(f"宿主机MuMu连接器初始化完成，路径: {self.mumu_path}")
        
        self._adb_process = None  # 添加ADB进程缓存
    
    def _get_adb_connection(self):
        """获取或创建ADB连接"""
        if self._adb_process is None:
            # 只在第一次创建连接
            self._adb_process = subprocess.Popen(
                ['adb', 'start-server'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        return self._adb_process
    
    def get_running_instances(self):
        """获取所有正在运行的MuMu实例及其ADB端口"""
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
                    instance_info = {
                        'id': i,
                        'adb_host': data['adb_host'],
                        'adb_port': data['adb_port'],
                        'device_id': f"{data['adb_host']}:{data['adb_port']}",
                        'updated_at': time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    running_instances.append(instance_info)
                    print(f"检测到运行中的MuMu实例 {i}: {instance_info['device_id']}")
            except Exception as e:
                print(f"检测MuMu实例 {i} 时出错: {e}")
        
        return running_instances
    
    def update_devices_file(self):
        """更新设备信息文件"""
        try:
            instances = self.get_running_instances()
            data = {
                "devices": instances,
                "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(self.devices_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"设备信息已更新到: {self.devices_file}")
            print(f"当前在线设备数: {len(instances)}")
            return True
        except Exception as e:
            print(f"更新设备信息文件时出错: {e}")
            return False
    
    def verify_device_connected(self, device_id):
        """验证设备是否已连接到ADB（优化版）"""
        try:
            # 复用现有连接
            process = self._get_adb_connection()
            cmd = ['adb', 'devices']
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=5,
                # 重要：使用现有的ADB服务器
                env={"ADB_SERVER_SOCKET": "tcp:5037"}
            )
            return device_id in result.stdout and "device" in result.stdout
        except Exception as e:
            print(f"验证设备连接时出错: {e}")
            return False
    
    def monitor_devices(self, interval=30):
        """持续监控设备状态（优化版）"""
        print(f"开始监控MuMu模拟器状态，更新间隔: {interval}秒")
        
        try:
            # 启动时先建立一个ADB连接
            self._get_adb_connection()
            
            while True:
                print("\n" + "="*50)
                print(f"开始检查设备状态... {time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.update_devices_file()
                print(f"等待 {interval} 秒后进行下一次检查...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n检测到Ctrl+C，停止监控...")
        except Exception as e:
            print(f"监控过程中出错: {e}")
        finally:
            # 清理ADB连接
            if self._adb_process:
                self._adb_process.terminate()
            print("监控已停止")
    
    def __del__(self):
        """析构函数中确保清理ADB连接"""
        if self._adb_process:
            self._adb_process.terminate()

def main():
    try:
        # 可以从环境变量获取MuMu路径
        mumu_path = os.getenv('MUMU_PATH', r"E:\xiaohongshu\MuMu\MuMu Player 12")
        connector = HostMuMuConnector(mumu_path=mumu_path)
        connector.monitor_devices()
    except Exception as e:
        print(f"程序运行出错: {e}")
        input("按Enter键退出...")

if __name__ == "__main__":
    main()