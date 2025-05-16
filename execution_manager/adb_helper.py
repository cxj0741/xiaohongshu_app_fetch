# python -m execution_manager.adb_helper
import subprocess
import re # 正则表达式模块，可选，用于更复杂的解析
import time
import platform
import os
from pathlib import Path
from config.environment import EnvironmentConfig

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

def get_online_emulator_ids():
    """
    获取当前所有处于 'device' 状态（即在线）的模拟器ID列表。
    增强了对IP:端口格式模拟器的识别。
    """
    # 首先尝试自动连接MuMu模拟器
    ensure_mumu_connected()
    
    try:
        # 尝试多次执行ADB命令，因为有时候可能会不稳定
        max_retries = 2
        for attempt in range(max_retries):
            try:
                result = subprocess.run(
                    ['adb', 'devices'], 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                break
            except Exception as e:
                print(f"ADB命令执行失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise
        
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
                # 尝试获取模拟器的一些基本信息，验证连接
                verify_result = subprocess.run(
                    ['adb', '-s', emu_id, 'shell', 'getprop', 'ro.product.model'],
                    capture_output=True, text=True, timeout=3
                )
                
                if verify_result.returncode == 0:
                    model = verify_result.stdout.strip()
                    
                    # 获取更多信息来区分模拟器
                    android_id_result = subprocess.run(
                        ['adb', '-s', emu_id, 'shell', 'settings', 'get', 'secure', 'android_id'],
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
    
    :param emulator_id: 模拟器ID
    :return: 可用返回True，否则返回False
    """
    try:
        # 检查连接状态
        status_cmd = ['adb', '-s', emulator_id, 'get-state']
        status_result = subprocess.run(status_cmd, capture_output=True, text=True, timeout=3)
        if status_result.returncode != 0 or status_result.stdout.strip() != 'device':
            print(f"模拟器 {emulator_id} 状态检查失败: {status_result.stderr}")
            return False
        
        # 执行简单命令验证响应能力
        echo_cmd = ['adb', '-s', emulator_id, 'shell', 'echo', 'test_connection']
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