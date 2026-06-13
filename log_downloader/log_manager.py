"""
日志管理模块：定义日志类型、扫描远程设备日志（并行+服务端预过滤优化版）
"""

import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from config_manager import get_log_types_config, DEFAULT_LOG_TYPES


LOG_ROOT_DIR = '/opt/agv/log'


def get_log_types():
    """获取当前日志类型配置（来自用户配置或默认值）"""
    return get_log_types_config()


def parse_log_filename(filename):
    """解析日志文件名，提取日志类型和时间戳"""
    pattern = r'^([A-Za-z_]+?)_(\d{8})_(\d{6})\.log$'
    match = re.match(pattern, filename)
    if match:
        try:
            log_type = match.group(1).rstrip('_')
            date_str = match.group(2)
            time_str = match.group(3)
            dt = datetime.strptime(date_str + time_str, '%Y%m%d%H%M%S')
            return {'type': log_type, 'datetime': dt, 'filename': filename}
        except ValueError:
            return None
    pattern2 = r'^([A-Za-z_]+?)(?:_(\d{8})_(\d{6}))?\.log$'
    match2 = re.match(pattern2, filename)
    if match2 and match2.group(2):
        try:
            log_type = match2.group(1).rstrip('_')
            date_str = match2.group(2)
            time_str = match2.group(3)
            dt = datetime.strptime(date_str + time_str, '%Y%m%d%H%M%S')
            return {'type': log_type, 'datetime': dt, 'filename': filename}
        except ValueError:
            return None
    return None


def get_log_category(filename, log_types=None):
    """根据文件名判断日志分类"""
    if log_types is None:
        log_types = get_log_types()
    for category, info in log_types.items():
        for keyword in info['keywords']:
            if filename.startswith(keyword):
                return category
    return '其他日志'


def _scan_single_category(ssh_client, category, info, start_time=None, end_time=None):
    """
    扫描单个日志分类。
    - 基础版：一条 ls 命令拿到目录，再在本地过滤
    - 如指定时间范围：在服务端先用 grep 按关键字+日期预过滤，大幅减少返回量
    """
    log_path = info['path']
    keywords = info['keywords']

    if start_time and end_time:
        # 构造日期集
        s_ymd = set()
        tmp = datetime(start_time.year, start_time.month, start_time.day)
        end_day = datetime(end_time.year, end_time.month, end_time.day)
        while tmp <= end_day:
            s_ymd.add(tmp.strftime('%Y%m%d'))
            tmp += timedelta(days=1)
        date_grep = '|'.join(s_ymd)
        kw_grep = '|'.join(keywords)
        # 服务端先用 grep 按关键字 + 日期预过滤，大幅减少回传数据
        cmd = (
            f"ls -la --time-style=long-iso '{log_path}' 2>/dev/null "
            f"| grep -E '{kw_grep}' "
            f"| grep -E '{date_grep}'"
        )
        success, out, err = ssh_client.exec_command(cmd)
        if success and out.strip():
            return category, _parse_ls_output(out, log_path, keywords, start_time, end_time)
        # 如果服务端 grep 返回空，说明此范围内无匹配，直接返回空
        if success and not out.strip():
            return category, []

    # 默认路径（无时间过滤 或 服务端预过滤失败）
    cmd = f"ls -la --time-style=long-iso '{log_path}' 2>/dev/null"
    success, out, err = ssh_client.exec_command(cmd)
    if not success or not out.strip():
        return category, []
    return category, _parse_ls_output(out, log_path, keywords, start_time, end_time)


def _parse_ls_output(out, log_path, keywords, start_time=None, end_time=None):
    """解析 ls -la 输出"""
    results = []
    lines = out.strip().split('\n')
    key_prefixes = tuple(keywords)

    for line in lines:
        try:
            if line.startswith('total') or not line.strip():
                continue
            parts = line.split()
            if len(parts) < 7:
                continue
            try:
                size = int(parts[4])
            except (ValueError, IndexError):
                continue
            date_part = parts[5]
            time_part = parts[6]
            filename = ' '.join(parts[7:]) if len(parts) > 7 else ''
            if not filename or not filename.endswith('.log'):
                continue
            if not filename.startswith(key_prefixes):
                continue
            file_info = parse_log_filename(filename)
            if file_info is None:
                file_info = {
                    'type': filename.split('_')[0] if '_' in filename else filename,
                    'datetime': None,
                    'filename': filename
                }
            mod_time = None
            try:
                dt_str = f'{date_part} {time_part}'
                if '.' in time_part:
                    dt_str = dt_str.split('.')[0]
                if len(time_part.split(':')) == 2:
                    mod_time = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                else:
                    mod_time = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except (ValueError, IndexError):
                mod_time = None
            size_kb = size / 1024 if size else 0

            # 时间过滤（严格过滤：按文件名时间或修改时间）
            if start_time and end_time:
                dt = file_info.get('datetime') or mod_time
                if dt is None:
                    continue
                if not (start_time <= dt <= end_time):
                    continue

            results.append({
                'filename': filename,
                'full_path': f'{log_path}/{filename}',
                'type': file_info['type'],
                'datetime': file_info['datetime'],
                'mod_time': mod_time,
                'size_kb': size_kb,
            })
        except Exception:
            continue
    return results


def scan_remote_logs(ssh_client, log_types=None, max_workers=4):
    """并行扫描远程日志（全量）"""
    if log_types is None:
        log_types = get_log_types()
    result = {category: [] for category in log_types.keys()}

    success, root_out, _ = ssh_client.exec_command(f"ls -d '{LOG_ROOT_DIR}' 2>/dev/null")
    if not success or not root_out.strip():
        return {'error': f'日志根目录不存在: {LOG_ROOT_DIR}'}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for category, info in log_types.items():
            future = executor.submit(_scan_single_category, ssh_client, category, info)
            futures[future] = category
        for future in as_completed(futures):
            try:
                category, logs = future.result(timeout=30)
                result[category] = logs
            except Exception:
                result[futures[future]] = []

    for category in result:
        if isinstance(result[category], list):
            result[category].sort(
                key=lambda x: x.get('datetime') or x.get('mod_time') or datetime.min,
                reverse=True
            )
    return result


def scan_remote_logs_with_time_filter(ssh_client, start_time, end_time, log_types=None, max_workers=4):
    """按时间范围扫描 - 服务端预过滤，减少返回数据量"""
    if log_types is None:
        log_types = get_log_types()
    result = {category: [] for category in log_types.keys()}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for category, info in log_types.items():
            future = executor.submit(_scan_single_category,
                                  ssh_client, category, info,
                                  start_time, end_time)
            futures[future] = category
        for future in as_completed(futures):
            try:
                category, logs = future.result(timeout=60)
                result[category] = logs
            except Exception:
                result[futures[future]] = []

    for category in result:
        if isinstance(result[category], list):
            result[category].sort(
                key=lambda x: x.get('datetime') or x.get('mod_time') or datetime.min,
                reverse=True
            )
    return result


def get_log_categories(log_types=None):
    """返回日志分类名称列表"""
    if log_types is None:
        log_types = get_log_types()
    return list(log_types.keys())
