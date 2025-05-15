# python -m execution_manager.adb_helper
import subprocess
import re # 正则表达式模块，可选，用于更复杂的解析
import time
import platform
import os
from pathlib import Path
import socket

# 检查是否在 Docker 容器中运行
# 这个环境变量需要在 docker-compose.yml 中为 firebase_listener 服务设置
IS_DOCKER_ENVIRONMENT = os.getenv('IS_IN_DOCKER_CONTAINER', 'false').lower() == 'true'

# 导入MuMu连接器
try:
    # 尝试相对导入 (如果 adb_helper 是 execution_manager 包的一部分)
    from .mumu_connector import MuMuConnector
except ImportError:
    try:
        # 尝试直接导入 (如果 mumu_connector 在 PYTHONPATH 中或同级目录)
        from mumu_connector import MuMuConnector
    except ImportError:
        MuMuConnector = None
        if not IS_DOCKER_ENVIRONMENT: # 本地环境才警告，Docker环境不依赖它
            print("警告: MuMuConnector 模块未能导入。")

def ensure_mumu_connected():
    """确保所有MuMu模拟器都已连接到ADB"""
    if IS_DOCKER_ENVIRONMENT:
        print("信息: 当前在 Docker 环境中运行，跳过 MuMuConnector 自动连接。")
        print("请确保模拟器已在主机端通过 ADB 连接，并且 Appium capabilities 正确配置了 adbHost 和 udid。")
        # 在 Docker 环境中，我们假设 ADB 连接由外部管理（主机ADB + Appium的adbHost能力）
        # 或者容器内的 ADB 命令会通过环境变量指向主机 ADB 服务
        return True # 返回 True，表示"已处理"或"无需处理"

    if MuMuConnector is None:
        print("警告: MuMuConnector 未导入，无法执行自动连接，跳过。")
        return False
    
    try:
        # 从环境变量获取MuMu路径 (这主要用于本地非 Docker 环境)
        mumu_path = os.getenv('MUMU_PATH')
        if not mumu_path:
            print("警告: MUMU_PATH 环境变量未设置，MuMuConnector 可能无法找到 MuMuManager.exe。")
            # 根据 MuMuConnector 的实现，它可能仍能找到默认路径的 MuMuManager.exe
            
        print(f"信息: 尝试使用 MuMuConnector (MuMu路径: {mumu_path or '未指定，将尝试默认路径'})")
        connector = MuMuConnector(mumu_path=mumu_path) # MuMuConnector 内部应能处理 mumu_path 为 None 的情况
        connected_devices = connector.connect_all_instances()
        
        if connected_devices:
            print(f"已自动连接 {len(connected_devices)} 个MuMu模拟器: {connected_devices}")
            return True
        else:
            print("MuMuConnector 未找到或未能连接任何运行中的MuMu模拟器实例。")
            return False
    except Exception as e:
        print(f"使用 MuMuConnector 自动连接MuMu模拟器时出错: {e}")
        return False

def restart_adb_server_and_connect_emulator():
    """重启ADB服务器并直接连接到模拟器"""
    try:
        print("尝试重启ADB服务器并连接模拟器...")
        
        # 1. 先杀掉ADB服务器
        subprocess.run(['adb', 'kill-server'], timeout=10)
        time.sleep(2)
        
        # 2. 设置环境变量，确保使用正确的IP地址
        os.environ['ANDROID_ADB_SERVER_ADDRESS'] = '172.17.0.1'  # 使用Docker主机IP
        
        # 3. 启动服务器
        subprocess.run(['adb', 'start-server'], timeout=10)
        time.sleep(2)
        
        # 4. 直接连接模拟器
        emulator_ports = ['16384', '16448']  # 根据您的模拟器配置
        connected_emulators = []
        
        for port in emulator_ports:
            emulator_id = f"127.0.0.1:{port}"
            print(f"尝试连接模拟器: {emulator_id}")
            try:
                result = subprocess.run(
                    ['adb', 'connect', emulator_id], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if "connected" in result.stdout:
                    print(f"成功连接到模拟器: {emulator_id}")
                    connected_emulators.append(emulator_id)
                else:
                    print(f"连接模拟器失败: {result.stdout} {result.stderr}")
            except Exception as e:
                print(f"连接模拟器 {emulator_id} 时出错: {e}")
        
        # 5. 检查连接状态
        if connected_emulators:
            print(f"成功连接的模拟器: {connected_emulators}")
            return connected_emulators
        else:
            print("未能连接到任何模拟器")
            return []
    except Exception as e:
        print(f"重启ADB服务器和连接模拟器时出错: {e}")
        return []

def get_online_emulator_ids():
    """
    获取当前所有处于 'device' 状态（即在线）的模拟器ID列表。
    增强了对IP:端口格式模拟器的识别。
    """
    # 首先尝试自动连接MuMu模拟器 (如果不在Docker环境)
    if not IS_DOCKER_ENVIRONMENT:
        print("信息: 尝试通过 MuMuConnector 确保模拟器已连接...")
        ensure_mumu_connected()
    else:
        print("信息: 在 Docker 环境中，尝试直接连接模拟器...")
        # 尝试直接重启服务器并连接
        direct_connected = restart_adb_server_and_connect_emulator()
        if direct_connected:
            return direct_connected
        else:
            print("直接连接失败，尝试标准ADB设备检测...")
    
    try:
        max_retries = 3 # 稍微增加重试次数
        adb_command = ['adb', 'devices']
        result = None

        for attempt in range(max_retries):
            try:
                print(f"尝试执行 ADB 命令: {' '.join(adb_command)} (尝试 {attempt+1}/{max_retries})")
                # 在 Docker 中，如果配置了 ANDROID_ADB_SERVER_ADDRESS 和 ANDROID_ADB_SERVER_PORT,
                # 此处的 'adb' 命令会尝试连接到主机的 ADB 服务。
                result = subprocess.run(
                    adb_command, 
                    capture_output=True, 
                    text=True,
                    check=True,
                    timeout=30 # 增加到30秒
                )
                print(f"ADB 命令成功执行。输出: \n{result.stdout}")
                break # 成功则跳出循环
            except subprocess.TimeoutExpired:
                print(f"ADB 命令执行超时 (尝试 {attempt+1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2)
            except FileNotFoundError:
                print("错误: adb 命令未找到。请确保 ADB 已安装并在系统 PATH 中，或者在 Docker 容器中已安装。")
                return []
            except Exception as e:
                print(f"ADB 命令执行失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise # 最后一次尝试失败则抛出异常
                time.sleep(2) # 等待后重试
        
        if result is None or result.returncode != 0:
            print(f"ADB 命令最终执行失败。")
            return []
            
        online_emulators = []
        output_lines = result.stdout.strip().splitlines()
        
        # print(f"ADB原始输出: {output_lines}") # 调试时可以取消注释
        
        if len(output_lines) > 1: # 第一行通常是 "List of devices attached"
            for line in output_lines[1:]:
                parts = line.strip().split('\t')
                if len(parts) == 2 and parts[1] == 'device':
                    device_id = parts[0]
                    online_emulators.append(device_id)
        
        print(f"ADB Helper - 检测到的在线模拟器 ('device'状态): {online_emulators}")
        
        # 验证部分保持不变，它依赖于 adb shell 命令
        verified_emulators = []
        emulator_info = {}
        
        for emu_id in online_emulators:
            max_verify_retries = 3
            verified = False
            
            for verify_attempt in range(max_verify_retries):
                try:
                    print(f"验证模拟器 {emu_id} (尝试 {verify_attempt+1}/{max_verify_retries})...")
                    verify_result = subprocess.run(
                        ['adb', '-s', emu_id, 'shell', 'getprop', 'ro.product.model'],
                        capture_output=True, text=True, timeout=20
                    )
                    
                    if verify_result.returncode == 0 and verify_result.stdout.strip():
                        model = verify_result.stdout.strip()
                        
                        android_id_result = subprocess.run(
                            ['adb', '-s', emu_id, 'shell', 'settings', 'get', 'secure', 'android_id'],
                            capture_output=True, text=True, timeout=20
                        )
                        android_id = android_id_result.stdout.strip() if android_id_result.returncode == 0 else "unknown"
                        
                        emulator_info[emu_id] = {
                            "model": model,
                            "android_id": android_id
                        }
                        
                        print(f"验证模拟器 {emu_id} 成功: 型号 = {model}, Android ID = {android_id}")
                        verified_emulators.append(emu_id)
                        verified = True
                        break  # 验证成功，跳出重试循环
                    else:
                        print(f"警告: 模拟器 {emu_id} 验证失败 (获取型号失败或无输出): {verify_result.stderr.strip() if verify_result.stderr else '无错误信息'}")
                except subprocess.TimeoutExpired:
                    print(f"验证模拟器 {emu_id} 时超时 (尝试 {verify_attempt+1}/{max_verify_retries})。")
                    if verify_attempt < max_verify_retries - 1:
                        print(f"将在2秒后重试...")
                        time.sleep(2)
                except Exception as e:
                    print(f"验证模拟器 {emu_id} 时出错 (尝试 {verify_attempt+1}/{max_verify_retries}): {e}")
                    if verify_attempt < max_verify_retries - 1:
                        print(f"将在2秒后重试...")
                        time.sleep(2)
            
            if not verified:
                print(f"模拟器 {emu_id} 多次验证失败，跳过此模拟器。")
        
        print(f"最终验证通过的模拟器: {verified_emulators}")
        # print(f"模拟器详细信息: {emulator_info}") # 调试时可以取消注释
        return verified_emulators
        
    except Exception as e:
        print(f"获取模拟器ID时发生严重错误: {e}")
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
        status_result = subprocess.run(status_cmd, capture_output=True, text=True, timeout=20)
        if status_result.returncode != 0 or status_result.stdout.strip() != 'device':
            print(f"模拟器 {emulator_id} 状态检查失败: {status_result.stdout.strip()} {status_result.stderr.strip()}")
            return False
        
        # 执行简单命令验证响应能力
        echo_cmd = ['adb', '-s', emulator_id, 'shell', 'echo', 'test_connection']
        echo_result = subprocess.run(echo_cmd, capture_output=True, text=True, timeout=20)
        if echo_result.returncode != 0 or 'test_connection' not in echo_result.stdout:
            print(f"模拟器 {emulator_id} 响应测试失败: {echo_result.stdout.strip()} {echo_result.stderr.strip()}")
            return False
        
        print(f"模拟器 {emulator_id} 验证为可用状态")
        return True
    except subprocess.TimeoutExpired:
        print(f"验证模拟器 {emulator_id} 可用性时超时。")
        return False
    except Exception as e:
        print(f"验证模拟器 {emulator_id} 可用性时出错: {e}")
        return False

if __name__ == '__main__':
    # 这个部分用于直接运行此文件时进行测试
    print("正在检测在线模拟器...")
    # 如果在 Docker 中，确保设置了 IS_IN_DOCKER_CONTAINER=true 环境变量
    # 并且 Dockerfile 中已安装 adb，并设置了 ANDROID_ADB_SERVER_ADDRESS 和 ANDROID_ADB_SERVER_PORT
    
    # 如果是本地运行，确保 MUMU_PATH 环境变量已设置 (如果需要 MuMuConnector 自动连接)
    # 或者手动通过 adb connect 连接模拟器

    emulators = get_online_emulator_ids()
    if emulators:
        print("\n检测到以下在线模拟器:")
        for emu_id in emulators:
            available = verify_emulator_available(emu_id)
            print(f"- {emu_id} (可用: {'是' if available else '否'})")
    else:
        print("未检测到在线模拟器，或者发生了错误。")

