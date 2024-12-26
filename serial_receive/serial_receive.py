#pip install pyserial
#pip install tqdm
#pip install keyboard
import serial
import time
import io
from serial.tools import list_ports
from tqdm import tqdm
import os
from datetime import datetime
import threading
import keyboard  # 用于监听键盘输入
import sys
import select
import platform
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

# 在程序开始时调用此函数
disable_quick_edit()
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
    file_path = input("请输入保存文件的路径 (留空自动生成文件名): ").strip()

    # 如果用户没有提供文件路径，则生成基于当前日期和时间的文件名
    if not file_path:
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"received_{current_time}.dat"
        file_path = os.path.join(os.getcwd(), file_name)  # 保存到当前工作目录
        print(f"文件将保存为: {file_path}")

    return selected_port, baud_rate, file_path

def listen_for_keyboard_stop(stop_event):
    """监听键盘输入，按下 Enter 键时设置 stop_event"""
    print("按 Enter 键结束接收...")
    if platform.system() == "Windows":
        import msvcrt
        while True:
            if msvcrt.kbhit():  # 检查是否有按键被按下
                key = msvcrt.getch()
                if key == b'\r':  # 检查是否是 Enter 键 (ASCII 13)
                    stop_event.set()  # 设置事件，通知主接收线程停止接收
                    print("\n检测到 Enter 键，停止接收数据。")
                    break
                else:
                    # 清空输入缓冲区，忽略其他按键
                    while msvcrt.kbhit():
                        msvcrt.getch()
            time.sleep(0.1)  # 短暂休眠以避免CPU占用过高
    else:
        # 使用 select 和 sys.stdin 实现跨平台的键盘输入监听
        while True:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                input()  # 读取输入并忽略
                stop_event.set()  # 设置事件，通知主接收线程停止接收
                print("\n检测到 Enter 键，停止接收数据。")
                break
            time.sleep(0.1)  # 短暂休眠以避免CPU占用过高

def receive_file_from_serial(port, baudrate, file_path):
    try:
        # 打开串口，禁用RTS/CTS硬件流控，提高波特率
        with serial.Serial(port, baudrate, timeout=2, rtscts=True, dsrdtr=True) as ser:
            print(f"成功打开串口: {ser.name}，波特率: {baudrate}，已启用硬件流控")

            # 创建一个内存缓冲区来存储接收到的数据
            buffer = io.BytesIO()

            chunk_size = 1024  # 每次读取1024字节
            start_time = time.time()
            total_received = 0  # 记录已接收的总字节数
            first_byte_received = False  # 标记是否接收到第一个字节

            #启动接收前串口缓冲区遗留的数据
            data_pre_read=ser.read(2048)
            if data_pre_read:
                user_choice = input("是否接收并保存当前串口缓冲区数据？(y/n): ").strip().lower()
                if user_choice != 'y':
                    print("用户选择不接收。")
                else:
                    print("用户选择接收。")
                    total_received+=len(data_pre_read)
                    buffer.write(data_pre_read)

            # 创建一个事件对象，用于控制接收线程的停止
            stop_event = threading.Event()

            # 启动一个线程监听键盘输入
            keyboard_thread = threading.Thread(target=listen_for_keyboard_stop, args=(stop_event,))
            keyboard_thread.daemon = True  # 设置为守护线程，程序退出时自动终止
            keyboard_thread.start()

            print("开始接收数据... (等待第一个字符)")
            
            while not stop_event.is_set():  # 只要 stop_event 未被设置，继续接收数据
                # 等待接收到第一个字符
                if not first_byte_received:
                    byte = ser.read(1)
                    if byte:
                        first_byte_received = True
                        buffer.write(byte)
                        total_received += len(byte)
                        start_time = time.time()  # 重置计时器
                        print("接收到第一个字符，开始接收数据...")
                    continue

                # 正常接收数据
                chunk = ser.read(chunk_size)
                if not chunk:
                    continue  # 如果没有数据可读，继续等待

                buffer.write(chunk)
                total_received += len(chunk)

                # 计算并显示接收速率
                elapsed_time = time.time() - start_time
                if elapsed_time > 0:
                    receive_rate = (total_received / elapsed_time) / 1024  # KB/s
                    print(f"\r平均接收速率: {receive_rate:.2f} KB/s", end='')

            print("\n用户已结束接收。")

            # 将内存缓冲区中的数据保存到硬盘
            with open(file_path, 'wb') as file:
                buffer.seek(0)  # 移动指针到缓冲区的开头
                file.write(buffer.getbuffer())

            print(f"文件已保存到: {file_path}")

    except serial.SerialException as e:
        print(f"发生错误: {e}")
    except IOError as e:
        print(f"文件操作失败: {e}")

# 使用函数
if __name__ == "__main__":
    #关闭命令行窗口快速编辑
    disable_quick_edit()

    # 列出所有可用的串口
    available_ports = list_available_ports()
    
    # 获取用户输入的选择
    
    selected_port, baud_rate, file_path = get_user_input(available_ports)
    
    if selected_port and baud_rate and file_path:
        receive_file_from_serial(selected_port, baud_rate, file_path)
    else:
        print("配置不完整，无法继续。")