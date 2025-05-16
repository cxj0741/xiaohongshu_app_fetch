# python -m execution_manager.adb_helper
import subprocess
import re # 正则表达式模块，可选，用于更复杂的解析
import time
import platform
import os
from pathlib import Path
from config.environment import EnvironmentConfig
import json

# 导入MuMu连接器
try:
    from .mumu_connector import MuMuConnector
except ImportError:
    try:
        from mumu_connector import MuMuConnector
    except ImportError:
        MuMuConnector = None

def ensure_mumu_connected():
    """确保所有MuMu模拟器都已连接到ADB"""
    if MuMuConnector is None:
        print("警告: MuMuConnector未导入，跳过自动连接")
        return False
    
    try:
        # 使用环境配置获取MuMu路径
        mumu_path = EnvironmentConfig.get_mumu_path()
        connector = MuMuConnector(mumu_path=mumu_path)
        connected_devices = connector.connect_all_instances()
        
        if connected_devices:
            print(f"已自动连接 {len(connected_devices)} 个MuMu模拟器")
            return True
        else:
            print("未找到运行中的MuMu模拟器实例")
            return False
    except Exception as e:
        print(f"自动连接MuMu模拟器时出错: {e}")
        return False

def get_adb_command_prefix():
    """获取ADB命令前缀，根据运行模式返回不同的配置"""
    running_mode = os.getenv('RUNNING_MODE', 'local')
    
    if running_mode == 'docker':
        # Docker模式：使用配置的ADB服务器
        host = EnvironmentConfig.get_adb_server_host()
        port = EnvironmentConfig.get_adb_server_port()
        return ['adb', '-H', host, '-P', port]
    else:
        # 本地模式：使用默认的ADB配置
        return ['adb']

def get_online_emulator_ids():
    """获取当前所有处于 'device' 状态的模拟器ID列表"""
    try:
        # 在Docker环境中设置ADB服务器
        if os.getenv('RUNNING_MODE') == 'docker':
            os.environ['ANDROID_ADB_SERVER_HOST'] = 'host.docker.internal'
            os.environ['ANDROID_ADB_SERVER_PORT'] = '5037'
            
        # 获取正确的ADB命令前缀
        adb_cmd = get_adb_command_prefix()
        
        # 获取设备列表
        result = subprocess.run(
            adb_cmd + ['devices'],
            capture_output=True,
            text=True,
            check=True
        )
        
        online_emulators = []
        output_lines = result.stdout.strip().splitlines()
        
        print(f"ADB原始输出: {output_lines}")  # 添加调试输出
        
        if len(output_lines) > 1:
            for line in output_lines[1:]:
                parts = line.strip().split('\t')
                if len(parts) == 2 and parts[1] == 'device':
                    device_id = parts[0]
                    # 无论是IP:端口还是emulator-格式，都直接添加到列表中
                    online_emulators.append(device_id)
        
        # 添加详细日志
        print(f"ADB Helper - 实际检测到的在线模拟器: {online_emulators}")
        
        # 验证每个模拟器是否真正可用，并获取更多信息
        verified_emulators = []
        emulator_info = {}  # 存储更详细的模拟器信息，用于区分
        
        for emu_id in online_emulators:
            try:
                # 使用正确的ADB命令前缀
                verify_result = subprocess.run(
                    adb_cmd + ['-s', emu_id, 'shell', 'getprop', 'ro.product.model'],
                    capture_output=True, text=True, timeout=3
                )
                
                if verify_result.returncode == 0:
                    model = verify_result.stdout.strip()
                    
                    # 使用正确的ADB命令前缀
                    android_id_result = subprocess.run(
                        adb_cmd + ['-s', emu_id, 'shell', 'settings', 'get', 'secure', 'android_id'],
                        capture_output=True, text=True, timeout=3
                    )
                    android_id = android_id_result.stdout.strip() if android_id_result.returncode == 0 else "unknown"
                    
                    # 存储信息
                    emulator_info[emu_id] = {
                        "model": model,
                        "android_id": android_id
                    }
                    
                    print(f"验证模拟器 {emu_id} 成功: 型号 = {model}, Android ID = {android_id}")
                    verified_emulators.append(emu_id)
                else:
                    print(f"警告: 模拟器 {emu_id} 验证失败: {verify_result.stderr}")
            except Exception as e:
                print(f"验证模拟器 {emu_id} 时出错: {e}")
        
        print(f"最终验证通过的模拟器: {verified_emulators}")
        print(f"模拟器详细信息: {emulator_info}")
        return verified_emulators
        
    except Exception as e:
        print(f"获取模拟器ID时出错: {e}")
        import traceback
        traceback.print_exc()
        return []

def verify_emulator_available(emulator_id):
    """
    验证模拟器是否可用，更详细的测试
    """
    try:
        # 获取正确的ADB命令前缀
        adb_cmd = get_adb_command_prefix()
        
        # 检查连接状态
        status_cmd = adb_cmd + ['-s', emulator_id, 'get-state']
        status_result = subprocess.run(status_cmd, capture_output=True, text=True, timeout=3)
        if status_result.returncode != 0 or status_result.stdout.strip() != 'device':
            print(f"模拟器 {emulator_id} 状态检查失败: {status_result.stderr}")
            return False
        
        # 执行简单命令验证响应能力
        echo_cmd = adb_cmd + ['-s', emulator_id, 'shell', 'echo', 'test_connection']
        echo_result = subprocess.run(echo_cmd, capture_output=True, text=True, timeout=3)
        if echo_result.returncode != 0 or 'test_connection' not in echo_result.stdout:
            print(f"模拟器 {emulator_id} 响应测试失败")
            return False
        
        print(f"模拟器 {emulator_id} 验证为可用状态")
        return True
    except Exception as e:
        print(f"验证模拟器 {emulator_id} 可用性时出错: {e}")
        return False

if __name__ == '__main__':
    # 这个部分用于直接运行此文件时进行测试
    print("正在检测在线模拟器...")
    emulators = get_online_emulator_ids()
    if emulators:
        print("\n检测到以下在线模拟器:")
        for emu_id in emulators:
            available = verify_emulator_available(emu_id)
            print(f"- {emu_id} (可用: {'是' if available else '否'})")
    else:
        print("未检测到在线模拟器，或者发生了错误。")

def _try_cleanup_uiautomator(self, device_id):
    """尝试清理可能崩溃的UiAutomator2服务"""
    try:
        print(f"尝试清理设备 {device_id} 上的UiAutomator服务...")
        # 检测操作系统
        is_windows = platform.system() == "Windows"
        
        # 获取正确的ADB命令前缀
        adb_cmd = get_adb_command_prefix()
        
        # 停止服务
        subprocess.run(
            adb_cmd + ['-s', device_id, 'shell', 'am', 'force-stop', 'io.appium.uiautomator2.server'],
            shell=is_windows, timeout=5
        )
        
        # 清理服务
        subprocess.run(
            adb_cmd + ['-s', device_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server'],
            shell=is_windows, timeout=5
        )
        
        subprocess.run(
            adb_cmd + ['-s', device_id, 'shell', 'pm', 'clear', 'io.appium.uiautomator2.server.test'],
            shell=is_windows, timeout=5
        )
        
        time.sleep(2)
        print(f"UiAutomator服务清理完成")
    except Exception as e:
        print(f"清理UiAutomator服务时出错: {e}")