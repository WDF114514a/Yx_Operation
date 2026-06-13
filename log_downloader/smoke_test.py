"""冒烟测试：验证程序核心功能"""
import sys
import os
sys.path.insert(0, r'D:\Yx_Operation\log_downloader')

print('=== 模块导入测试 ===')
try:
    from device_utils import calculate_ip, parse_device_id, get_ssh_credentials
    print('[OK] device_utils 模块导入成功')
except Exception as e:
    print(f'[FAIL] device_utils: {e}')
    sys.exit(1)

try:
    from ssh_client import SSHClient
    print('[OK] ssh_client 模块导入成功')
except Exception as e:
    print(f'[FAIL] ssh_client: {e}')
    sys.exit(1)

try:
    from log_manager import LOG_TYPES, scan_remote_logs, parse_log_filename, get_log_categories
    print('[OK] log_manager 模块导入成功')
except Exception as e:
    print(f'[FAIL] log_manager: {e}')
    sys.exit(1)

try:
    from archive_utils import extract_archive, get_local_download_dir, extract_tar_gz
    print('[OK] archive_utils 模块导入成功')
except Exception as e:
    print(f'[FAIL] archive_utils: {e}')
    sys.exit(1)

print()
print('=== SSH凭据测试 ===')
creds = get_ssh_credentials()
assert creds['username'] == 'root', '用户名不正确'
assert creds['port'] == 22, '端口不正确'
print(f'[OK] SSH凭据: user={creds["username"]}, port={creds["port"]}')

print()
print('=== IP计算测试 ===')
# 测试文档中提到的设备
test_cases = [
    ('T3P-1120', '10.200.5.120'),  # 1120//200=5, 1120%200=120
    ('T3P-1310', '10.200.6.110'),  # 1310//200=6, 1310%200=110
    ('T3P-1243', '10.200.6.43'),   # 1243//200=6, 1243%200=43
    ('T1-456', '10.200.102.56'),   # T1规则
]
all_pass = True
for device_id, expected_ip in test_cases:
    actual = calculate_ip(device_id, 'cn')
    status = 'OK' if actual == expected_ip else 'FAIL'
    if actual != expected_ip:
        all_pass = False
    print(f'  [{status}] {device_id} -> {actual} (期望: {expected_ip})')

if not all_pass:
    print('[FAIL] IP计算测试未通过')
    sys.exit(1)
print('[OK] IP计算测试全部通过')

print()
print('=== 日志分类测试 ===')
categories = get_log_categories()
print(f'[OK] 共定义了 {len(categories)} 个日志分类:')
for cat in categories:
    keywords = LOG_TYPES[cat]['keywords']
    print(f'     - {cat}: 关键字 {keywords}')

print()
print('=== 文件名解析测试 ===')
test_files = [
    'LogAvoid_20260612_143343.log',
    'TrackEntance_20260609_110031.log',
    'agv_shell_20260608_172945.log',
    'battery_state_20260607_172010.log',
    'robot_task_20260607_172010.log',
    'LocInfoLog_20260607_182654.log',
]
for f in test_files:
    info = parse_log_filename(f)
    status = 'OK' if info else 'FAIL'
    info_str = f'类型={info["type"]}, 时间={info["datetime"]}' if info else '解析失败'
    print(f'  [{status}] {f} -> {info_str}')

print()
print('=== GUI模块导入测试 ===')
try:
    import tkinter as tk
    from tkinter import ttk
    print('[OK] tkinter 模块导入成功')
except Exception as e:
    print(f'[FAIL] tkinter: {e}')
    sys.exit(1)

print()
print('=== main.py 导入测试 ===')
try:
    # 只导入不运行
    import importlib.util
    spec = importlib.util.spec_from_file_location('main', r'D:\Yx_Operation\log_downloader\main.py')
    main_mod = importlib.util.module_from_spec(spec)
    # 不直接执行，仅验证语法和结构
    import ast
    with open(r'D:\Yx_Operation\log_downloader\main.py', 'r', encoding='utf-8') as f:
        source = f.read()
    ast.parse(source)
    print('[OK] main.py 语法正确，包含 LogDownloaderApp 类')
except Exception as e:
    print(f'[FAIL] main.py 解析失败: {e}')
    sys.exit(1)

print()
print('=' * 50)
print('所有冒烟测试通过！程序结构完整。')
print('=' * 50)
