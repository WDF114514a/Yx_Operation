"""快速功能测试"""
import sys
sys.path.insert(0, r'D:\Yx_Operation\log_downloader')

from device_utils import calculate_ip, parse_device_id
from log_manager import parse_log_filename
from datetime import datetime

print('=== 设备ID到IP的测试 ===')
test_ids = ['T3P-1120', 'T3P-1310', 'T3-123', 'T1-456', 'T3P-9999']
for did in test_ids:
    dev_type, num, _ = parse_device_id(did)
    ip_cn = calculate_ip(did, 'cn')
    ip_ru = calculate_ip(did, 'ru')
    ip_other = calculate_ip(did, 'other')
    print(f'{did}: 类型={dev_type}, 编号={num}')
    print(f'  国内:   {ip_cn}')
    print(f'  俄罗斯: {ip_ru}')
    print(f'  其他:   {ip_other}')
    print()

print('=== 日志文件名解析测试 ===')
test_files = [
    'LogAvoid_20260612_143343.log',
    'TrackEntance_20260609_110031.log',
    'agv_shell_20260608_172945.log',
    'battery_state_20260607_172010.log',
]
for f in test_files:
    info = parse_log_filename(f)
    if info:
        print(f'{f} -> 类型={info["type"]}, 时间={info["datetime"]}')
    else:
        print(f'{f} -> 解析失败')

print()
print('所有测试完成！')
