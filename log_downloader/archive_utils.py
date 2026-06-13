"""
压缩解压模块：处理下载后的tar.gz文件解压
"""

import os
import tarfile
import zipfile
import shutil
from datetime import datetime


def extract_tar_gz(archive_path, extract_dir=None):
    """
    解压tar.gz归档文件
    
    Args:
        archive_path: 归档文件路径
        extract_dir: 解压目录，默认为归档文件所在目录下的同名文件夹
        
    Returns:
        tuple: (success, message, extract_path)
    """
    if not os.path.exists(archive_path):
        return False, f'文件不存在: {archive_path}', ''
    
    if extract_dir is None:
        base_name = os.path.splitext(os.path.splitext(os.path.basename(archive_path))[0])[0]
        extract_dir = os.path.join(os.path.dirname(archive_path), base_name)
    
    try:
        os.makedirs(extract_dir, exist_ok=True)
        
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=extract_dir)
        
        return True, '解压成功', extract_dir
    except tarfile.TarError as e:
        return False, f'tar解压错误: {str(e)}', ''
    except Exception as e:
        return False, f'解压失败: {str(e)}', ''


def extract_zip(archive_path, extract_dir=None):
    """
    解压zip归档文件
    
    Args:
        archive_path: 归档文件路径
        extract_dir: 解压目录
        
    Returns:
        tuple: (success, message, extract_path)
    """
    if not os.path.exists(archive_path):
        return False, f'文件不存在: {archive_path}', ''
    
    if extract_dir is None:
        base_name = os.path.splitext(os.path.basename(archive_path))[0]
        extract_dir = os.path.join(os.path.dirname(archive_path), base_name)
    
    try:
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extractall(path=extract_dir)
        
        return True, '解压成功', extract_dir
    except zipfile.BadZipFile as e:
        return False, f'zip解压错误: {str(e)}', ''
    except Exception as e:
        return False, f'解压失败: {str(e)}', ''


def extract_archive(archive_path, extract_dir=None):
    """
    自动识别归档类型并解压
    
    Args:
        archive_path: 归档文件路径
        extract_dir: 解压目录
        
    Returns:
        tuple: (success, message, extract_path)
    """
    if archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
        return extract_tar_gz(archive_path, extract_dir)
    elif archive_path.endswith('.zip'):
        return extract_zip(archive_path, extract_dir)
    else:
        return False, f'不支持的归档格式: {archive_path}', ''


def get_local_download_dir(base_dir, device_id):
    """
    生成本地下载目录路径
    
    Args:
        base_dir: 基础下载目录
        device_id: 设备ID
        
    Returns:
        str: 下载目录路径
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = os.path.join(base_dir, f'{device_id}_{timestamp}')
    os.makedirs(download_dir, exist_ok=True)
    return download_dir
