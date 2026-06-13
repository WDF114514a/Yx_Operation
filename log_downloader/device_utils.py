"""
设备工具模块：处理设备ID到IP的转换
"""

import re
import ipaddress


def parse_device_id(device_id):
    """
    解析设备ID，返回设备类型和编号
    
    Args:
        device_id: 设备ID，如 T3P-1234, T3-123, T1-456
        
    Returns:
        tuple: (device_type, number, region)
            device_type: 'T3P', 'T3', 'T1', 'UNKNOWN'
            number: 设备编号（整数）
            region: 'cn'（国内），'ru'（俄罗斯），'other'（其他国外）
    """
    device_id = device_id.strip().upper()
    
    # 匹配 T3P-XXXX 或 T3P-XXX
    match = re.match(r'^(T3P|T3|T1)-(\d{3,4})$', device_id)
    if not match:
        return 'UNKNOWN', 0, 'cn'
    
    device_type = match.group(1)
    number = int(match.group(2))
    
    return device_type, number, 'cn'


def calculate_ip_by_model(model, number, region='cn'):
    """
    根据型号和编号计算IP地址
    
    Args:
        model: 设备型号 ('T3P', 'T3', 'T1')
        number: 设备编号 (整数)
        region: 地区 ('cn', 'ru', 'other')
        
    Returns:
        str: IP地址，解析失败返回空字符串
    """
    model = model.strip().upper()
    if model not in ('T3P', 'T3', 'T1'):
        return ''
    if not isinstance(number, int) or number <= 0:
        return ''
    
    a = number // 200
    b = number % 200
    
    if region == 'ru':
        prefix = '10.203'
    elif region == 'other':
        prefix = '10.202'
    else:
        prefix = '10.200'
    
    if model in ('T3P', 'T3'):
        ip = f'{prefix}.{a}.{b}'
    elif model == 'T1':
        ip = f'{prefix}.10{a}.{b}'
    else:
        return ''
    
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return ''


def calculate_ip(device_id, region='cn'):
    """
    根据设备ID计算IP地址（兼容旧接口）
    
    IP规则：
    - T3P-XXXX / T3-XXXX: 10.200.A.BBB
      A = XXXX // 200, BBB = XXXX % 200
    - T1-XXX: 10.200.10C.DDD
      C = XXX // 200, DDD = XXX % 200
    - 俄罗斯: 前缀改为 10.203
    - 其他国外: 前缀改为 10.202
    
    Args:
        device_id: 设备ID
        region: 地区 ('cn', 'ru', 'other')
        
    Returns:
        str: IP地址，解析失败返回空字符串
    """
    device_type, number, _ = parse_device_id(device_id)
    return calculate_ip_by_model(device_type, number, region)


def get_ssh_credentials():
    """
    返回SSH连接的默认凭据
    
    Returns:
        dict: {'username': 'root', 'password': 'YunXiang@2021', 'port': 22}
    """
    return {
        'username': 'root',
        'password': 'YunXiang@2021',
        'port': 22
    }
