import subprocess
import re # 正则表达式模块，可选，用于更复杂的解析

def get_online_emulator_ids():
    """
    获取当前所有处于 'device' 状态（即在线）的模拟器ID列表。
    只返回以 'emulator-' 开头的设备ID。
    """
    try:
        # 执行 'adb devices' 命令
        # 'capture_output=True' 捕获命令的输出
        # 'text=True' (或 Python 3.7+ 的 'encoding="utf-8"') 将输出解码为文本
        # 'check=True' 如果命令返回非零退出码则抛出 CalledProcessError
        result = subprocess.run(
            ['adb', 'devices'], 
            capture_output=True, 
            text=True, # 或者 encoding='utf-8'
            check=True
        )
        
        online_emulators = []
        output_lines = result.stdout.strip().splitlines()
        
        # 解析输出：
        # 示例输出:
        # List of devices attached
        # emulator-5554	device
        # emulator-5556	device
        # FA77P0300198	device  (这可能是一个真实设备)
        
        if len(output_lines) > 1: # 确保至少有一行设备信息
            for line in output_lines[1:]: # 跳过第一行 "List of devices attached"
                parts = line.strip().split('\t') # 按制表符分割
                if len(parts) == 2 and parts[1] == 'device':
                    device_id = parts[0]
                    if device_id.startswith('emulator-') or ':' in device_id: # 只选择模拟器
                        online_emulators.append(device_id)
                        
        return online_emulators
        
    except FileNotFoundError:
        print("错误: ADB 命令未找到。请确保 ADB 已安装并配置在系统 PATH 中。")
        return []
    except subprocess.CalledProcessError as e:
        print(f"执行 'adb devices' 命令失败: {e}")
        print(f"ADB stderr: {e.stderr}")
        return []
    except Exception as e:
        print(f"解析 ADB 输出时发生未知错误: {e}")
        return []

if __name__ == '__main__':
    # 这个部分用于直接运行此文件时进行测试
    print("正在检测在线模拟器...")
    emulators = get_online_emulator_ids()
    if emulators:
        print("检测到的在线模拟器ID:")
        for emu_id in emulators:
            print(f"- {emu_id}")
    else:
        print("未检测到在线模拟器，或者发生了错误。")