"""
配置管理模块：持久化保存下载路径、设备历史、日志关键字
"""

import os
import json


def _get_config_dir():
    """返回配置文件目录（用户目录下 .agv_log_tool）"""
    base = os.path.expanduser('~')
    cfg_dir = os.path.join(base, '.agv_log_tool')
    try:
        os.makedirs(cfg_dir, exist_ok=True)
    except Exception:
        pass
    return cfg_dir


def _config_path(filename):
    return os.path.join(_get_config_dir(), filename)


def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ================== 下载路径 ==================

DOWNLOAD_PATH_FILE = 'download_path.json'


def get_last_download_dir():
    """获取上次使用的下载目录"""
    data = _load_json(_config_path(DOWNLOAD_PATH_FILE), {})
    return data.get('path', '') or os.path.join(os.path.expanduser('~'), 'Downloads', 'AGV_Logs')


def save_last_download_dir(path):
    """保存当前下载目录"""
    _save_json(_config_path(DOWNLOAD_PATH_FILE), {'path': path})


# ================== 设备历史 ==================

DEVICES_FILE = 'devices.json'

# 默认日志分类结构
DEFAULT_LOG_TYPES = {
    '绕障日志 (MotionPlugin)': {
        'path': '/opt/agv/log/MotionPlugin',
        'keywords': ['LogAvoid_', 'TrackEntance_', 'PathPlanner_', 'grace_interface_'],
    },
    '调度日志 (TaskSever)': {
        'path': '/opt/agv/log/TaskSever',
        'keywords': ['robot_task_', 'water_level', 'battery_state', 'charge_', 'water_', 'water_task_'],
    },
    '电气日志 (agv_shell)': {
        'path': '/opt/agv/log/agv_shell',
        'keywords': ['mcmesg_', 'agv_shell_'],
    },
    '定位日志 (StarLoc3D)': {
        'path': '/opt/agv/log',
        'keywords': ['LocInfoLog_', 'LocManager_', 'LocOutput_', 'SynSensorData_', 'StarLoc3D_'],
    },
}


def get_devices():
    """获取设备历史列表
    Returns:
        list: [{'model': 'T3P', 'number': 1234, 'region': 'cn', 'category': '默认', 'last_used': '2026-...'}, ...]
    """
    data = _load_json(_config_path(DEVICES_FILE), [])
    if not isinstance(data, list):
        return []
    return data


def save_device(device_info):
    """保存/更新设备信息（按 model+number+region 去重）"""
    devices = get_devices()
    key = f"{device_info['model']}-{device_info['number']}-{device_info.get('region', 'cn')}"
    found = False
    for d in devices:
        d_key = f"{d['model']}-{d['number']}-{d.get('region', 'cn')}"
        if d_key == key:
            d.update(device_info)
            found = True
            break
    if not found:
        devices.append(device_info)
    _save_json(_config_path(DEVICES_FILE), devices)


def delete_device(device_info):
    """删除设备"""
    devices = get_devices()
    key = f"{device_info['model']}-{device_info['number']}-{device_info.get('region', 'cn')}"
    devices = [d for d in devices
               if f"{d['model']}-{d['number']}-{d.get('region', 'cn')}" != key]
    _save_json(_config_path(DEVICES_FILE), devices)


def get_device_categories():
    """获取所有设备分类名"""
    devices = get_devices()
    cats = set()
    for d in devices:
        cats.add(d.get('category', '默认'))
    return sorted(cats)


def update_device_category(device_info, new_category):
    """更新设备分类"""
    devices = get_devices()
    key = f"{device_info['model']}-{device_info['number']}-{device_info.get('region', 'cn')}"
    for d in devices:
        d_key = f"{d['model']}-{d['number']}-{d.get('region', 'cn')}"
        if d_key == key:
            d['category'] = new_category
            break
    _save_json(_config_path(DEVICES_FILE), devices)


# ================== 日志关键字配置 ==================

LOG_TYPES_FILE = 'log_types.json'


def get_log_types_config():
    """获取日志类型配置
    Returns:
        dict: {分类名: {'path': str, 'keywords': [str, ...]}, ...}
    """
    data = _load_json(_config_path(LOG_TYPES_FILE), None)
    if isinstance(data, dict) and data:
        return data
    return dict(DEFAULT_LOG_TYPES)


def save_log_types_config(config):
    """保存日志类型配置"""
    _save_json(_config_path(LOG_TYPES_FILE), config)


def reset_log_types_config():
    """重置为默认配置"""
    _save_json(_config_path(LOG_TYPES_FILE), dict(DEFAULT_LOG_TYPES))
