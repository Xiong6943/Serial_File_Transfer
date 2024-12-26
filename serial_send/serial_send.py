#pip install pyserial
#pip install tqdm
import serial
import time
import os
from serial.tools import list_ports
from tqdm import tqdm
import sys

#关闭快速编辑模式，以防命令行窗口有鼠标点击触发暂停的bug
def disable_quick_edit():
    if sys.platform == "win32":
        from ctypes import windll, byref, wintypes
        from ctypes.wintypes import DWORD

        # 获取控制台句柄
        kernel32 = windll.kernel32
        hStdin = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = DWORD(0)
        
        # 获取当前控制台模式
        kernel32.GetConsoleMode(hStdin, byref(mode))
        
        # 禁用快速编辑模式 (ENABLE_QUICK_EDIT_MODE = 0x40)
        mode.value &= ~0x40
        
        # 设置新的控制台模式
        kernel32.SetConsoleMode(hStdin, mode)

def list_available_ports():
    """列出所有可用的串口"""
    ports = list_ports.comports()
    if not ports:
        print("没有找到可用的串口。")
        return None
    
    print("可用的串口列表：")
    for i, port in enumerate(ports, start=1):
        # 获取厂商和序列号，如果为空则显示为 "未知"
        manufacturer = port.manufacturer or "未知"
        serial_number = port.serial_number or "未知"
        
        print(f"{i}: {port.device} - {port.description}")
        print(f"  {manufacturer}:{serial_number}")
        print()  # 空行分隔不同串口的信息

    return ports

def get_user_input(ports):
    """获取用户输入的选择"""
    if not ports:
        return None, None, None

    # 选择串口
    while True:
        try:
            choice = int(input("请选择一个串口 (输入数字): "))
            if 1 <= choice <= len(ports):
                selected_port = ports[choice - 1].device
                break
            else:
                print("无效的选择，请重新输入。")
        except ValueError:
            print("无效的输入，请输入一个数字。")

    # 选择波特率
    baud_rate = input("请输入波特率 (默认2000000): ").strip() or '2000000'
    try:
        baud_rate = int(baud_rate)
    except ValueError:
        print("无效的波特率，使用默认值2000000。")
        baud_rate = 2000000

    # 输入文件路径
    file_path = input("请输入待发送文件的路径: ").strip()
    if not file_path:
        print("文件路径不能为空。")
        return None, None, None

    return selected_port, baud_rate, file_path

def send_file_to_serial_with_rts_cts(port, baudrate, file_path):
    try:
        # 打开串口并启用RTS/CTS硬件流控
        with serial.Serial(port, baudrate, timeout=1, rtscts=True, dsrdtr=True) as ser:
            print(f"成功打开串口: {ser.name}，波特率：{baudrate}，已启用硬件流控")

            # 打开文件并读取内容，确保以二进制模式读取
            with open(file_path, 'rb') as file:
                # 获取文件大小
                file_size = os.path.getsize(file_path)
                print(f"文件大小: {file_size / 1024:.2f} KB")

                # 创建进度条
                with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024, desc="发送进度") as pbar:
                    chunk_size = 1024  # 每次发送1024字节
                    start_time = time.time()

                    while True:
                        chunk = file.read(chunk_size)
                        if not chunk:
                            break  # 如果没有更多数据可读，则退出循环

                        # 发送数据块
                        ser.write(chunk)
                        pbar.update(len(chunk))  # 更新进度条

                        # 计算并显示发送速率
                        elapsed_time = time.time() - start_time
                        if elapsed_time > 0:
                            send_rate = (pbar.n / elapsed_time) / 1024  # KB/s
                            pbar.set_postfix({"发送平均速率": f"{send_rate:.2f} KB/s"})

            print("文件传输完成。")
    except serial.SerialException as e:
        print(f"发生错误: {e}")
    except IOError as e:
        print(f"文件操作失败: {e}")

# 使用函数
if __name__ == "__main__":
    #关闭命令行窗口快速编辑
    disable_quick_edit()

    # 定义串口参数和文件路径，可以使用输入选择也可以使用这个
    SERIAL_PORT = 'COM8'  # Windows示例；如果是Linux或Mac，请使用类似'/dev/ttyUSB0'
    BAUD_RATE = 2000000      # 根据实际需求调整波特率
    FILE_PATH = r'C:\Users\xxx\Downloads\xxx.exe'  # 替换为你的文件路径

    # 列出所有可用的串口
    available_ports = list_available_ports()
    
    # 获取用户输入的选择
    selected_port, baud_rate, file_path = get_user_input(available_ports)
    
    if selected_port and baud_rate and file_path:
        send_file_to_serial_with_rts_cts(selected_port, baud_rate, file_path)
    else:
        print("配置不完整，无法继续。")
