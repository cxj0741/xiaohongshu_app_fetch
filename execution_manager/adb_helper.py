import subprocess
import re # 正则表达式模块，可选，用于更复杂的解析

def get_online_emulator_ids():
    """
    获取当前所有处于 'device' 状态（即在线）的模拟器ID列表。
    增强了对IP:端口格式模拟器的识别。
    """
    try:
        result = subprocess.run(
            ['adb', 'devices'], 
            capture_output=True, 
            text=True,
            check=True
        )
        
        online_emulators = []
        seen_ips = set()  # 用于跟踪已经看到的IP地址
        output_lines = result.stdout.strip().splitlines()
        
        print(f"ADB原始输出: {output_lines}")  # 添加调试输出
        
        if len(output_lines) > 1:
            for line in output_lines[1:]:
                parts = line.strip().split('\t')
                if len(parts) == 2 and parts[1] == 'device':
                    device_id = parts[0]
                    
                    # 对于IP:端口形式的设备ID，提取IP部分
                    if ':' in device_id:
                        ip_part = device_id.split(':')[0]
                        # 确保同一IP的不同端口被视为不同设备
                        if device_id not in seen_ips:
                            online_emulators.append(device_id)
                            seen_ips.add(device_id)
                    elif device_id.startswith('emulator-'):
                        online_emulators.append(device_id)
        
        # 添加详细日志
        print(f"ADB Helper - 实际检测到的在线模拟器: {online_emulators}")
        
        # 验证每个模拟器是否真正可用
        verified_emulators = []
        for emu_id in online_emulators:
            try:
                # 尝试获取模拟器的一些基本信息，验证连接
                verify_result = subprocess.run(
                    ['adb', '-s', emu_id, 'shell', 'getprop', 'ro.product.model'],
                    capture_output=True, text=True, timeout=3
                )
                if verify_result.returncode == 0:
                    model = verify_result.stdout.strip()
                    print(f"验证模拟器 {emu_id} 成功: 型号 = {model}")
                    verified_emulators.append(emu_id)
                else:
                    print(f"警告: 模拟器 {emu_id} 验证失败: {verify_result.stderr}")
            except Exception as e:
                print(f"验证模拟器 {emu_id} 时出错: {e}")
        
        print(f"最终验证通过的模拟器: {verified_emulators}")
        return verified_emulators
        
    except Exception as e:
        print(f"获取模拟器ID时出错: {e}")
        import traceback
        traceback.print_exc()
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