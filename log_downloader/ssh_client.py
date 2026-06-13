"""
SSH连接管理模块：封装paramiko进行SSH连接和SFTP文件传输
"""

import paramiko
import time


class SSHClient:
    """SSH客户端类，封装了SSH连接和SFTP操作"""
    
    def __init__(self):
        self.ssh = None
        self.sftp = None
        self.hostname = ''
        self.username = ''
        self.password = ''
        self.port = 22
        self.connected = False
    
    def connect(self, hostname, username='root', password='YunXiang@2021', port=22, timeout=10):
        """
        连接到设备
        
        Args:
            hostname: 设备IP地址
            username: SSH用户名
            password: SSH密码
            port: SSH端口
            timeout: 连接超时时间（秒）
            
        Returns:
            tuple: (success, message)
        """
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=hostname,
                username=username,
                password=password,
                port=port,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout
            )
            self.hostname = hostname
            self.username = username
            self.password = password
            self.port = port
            self.connected = True
            return True, '连接成功'
        except paramiko.AuthenticationException:
            return False, '认证失败，请检查用户名和密码'
        except paramiko.SSHException as e:
            return False, f'SSH连接错误: {str(e)}'
        except TimeoutError:
            return False, '连接超时，请检查IP地址和网络'
        except Exception as e:
            return False, f'连接失败: {str(e)}'
    
    def open_sftp(self):
        """
        打开SFTP通道
        
        Returns:
            tuple: (success, message)
        """
        if not self.connected:
            return False, 'SSH未连接'
        try:
            self.sftp = self.ssh.open_sftp()
            return True, 'SFTP通道已打开'
        except Exception as e:
            return False, f'打开SFTP失败: {str(e)}'
    
    def exec_command(self, command, timeout=30):
        """
        在远程设备上执行命令
        
        Args:
            command: 要执行的命令
            timeout: 命令超时时间（秒）
            
        Returns:
            tuple: (success, stdout, stderr)
        """
        if not self.connected:
            return False, '', 'SSH未连接'
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            return True, out, err
        except Exception as e:
            return False, '', str(e)
    
    def list_dir(self, remote_path):
        """
        列出远程目录内容
        
        Args:
            remote_path: 远程目录路径
            
        Returns:
            tuple: (success, file_list, message)
                file_list: 文件名列表
        """
        if not self.connected:
            return False, [], 'SSH未连接'
        try:
            if not self.sftp:
                self.open_sftp()
            files = self.sftp.listdir(remote_path)
            return True, sorted(files), '成功'
        except Exception as e:
            return False, [], f'列出目录失败: {str(e)}'
    
    def stat_file(self, remote_path):
        """
        获取远程文件信息
        
        Args:
            remote_path: 远程文件路径
            
        Returns:
            tuple: (success, stat_obj, message)
        """
        if not self.connected:
            return False, None, 'SSH未连接'
        try:
            if not self.sftp:
                self.open_sftp()
            stat = self.sftp.stat(remote_path)
            return True, stat, '成功'
        except Exception as e:
            return False, None, str(e)
    
    def download_file(self, remote_path, local_path, callback=None):
        """
        下载单个文件
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地保存路径
            callback: 下载进度回调函数 (bytes_transferred, total_bytes)
            
        Returns:
            tuple: (success, message)
        """
        if not self.connected:
            return False, 'SSH未连接'
        try:
            if not self.sftp:
                self.open_sftp()
            self.sftp.get(remote_path, local_path, callback=callback)
            return True, '下载成功'
        except Exception as e:
            return False, f'下载失败: {str(e)}'
    
    def compress_files(self, file_paths, remote_archive_path):
        """
        在远程设备上压缩文件列表为tar.gz
        
        Args:
            file_paths: 远程文件路径列表
            remote_archive_path: 远程归档文件路径（.tar.gz）
            
        Returns:
            tuple: (success, message)
        """
        if not file_paths:
            return False, '没有文件需要压缩'
        
        # 处理文件路径，将多个文件路径拼接
        # 使用 tar -czf archive.tar.gz -C dir file1 file2 ... 的方式
        # 为了简化，我们将文件按目录分组，分别处理
        
        try:
            # 创建一个包含所有文件路径的临时文件列表
            file_list_str = ' '.join([f'"{fp}"' for fp in file_paths])
            
            # 使用 tar 命令压缩
            # -C 参数用于切换目录，保持相对路径
            # 这里采用最简单的方式：先cd到/opt/agv/log，然后tar
            cmd = f'cd /opt/agv/log && tar -czf "{remote_archive_path}" -C /opt/agv/log '
            
            # 需要重新计算相对路径
            rel_paths = []
            for fp in file_paths:
                if fp.startswith('/opt/agv/log/'):
                    rel_paths.append(fp.replace('/opt/agv/log/', '', 1))
                elif fp.startswith('/opt/agv/log'):
                    rel_paths.append(fp.replace('/opt/agv/log', '', 1).lstrip('/'))
                else:
                    rel_paths.append(fp)
            
            cmd += ' '.join([f'"{rp}"' for rp in rel_paths])
            
            success, stdout, stderr = self.exec_command(cmd, timeout=300)
            if success and not stderr.strip():
                return True, '压缩成功'
            else:
                return False, f'压缩失败: {stderr or stdout}'
        except Exception as e:
            return False, f'压缩失败: {str(e)}'
    
    def delete_file(self, remote_path):
        """
        删除远程文件
        
        Args:
            remote_path: 远程文件路径
            
        Returns:
            tuple: (success, message)
        """
        try:
            if not self.sftp:
                self.open_sftp()
            self.sftp.remove(remote_path)
            return True, '删除成功'
        except Exception as e:
            return False, f'删除失败: {str(e)}'
    
    def close(self):
        """关闭SSH连接"""
        try:
            if self.sftp:
                self.sftp.close()
            if self.ssh:
                self.ssh.close()
        except:
            pass
        finally:
            self.connected = False
            self.ssh = None
            self.sftp = None
