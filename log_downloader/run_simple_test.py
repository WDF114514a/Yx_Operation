"""简单测试脚本 - 检查主程序是否能正常启动"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import tkinter as tk
    from tkinter import ttk
    print("[OK] tkinter 导入成功")
    
    # 测试核心模块
    from device_utils import calculate_ip_by_model
    from ssh_client import SSHClient
    from log_manager import LOG_TYPES
    from archive_utils import extract_archive
    print("[OK] 所有业务模块导入成功")
    
    # 测试IP计算
    ip = calculate_ip_by_model('T3P', 1234, 'cn')
    print(f"[OK] IP计算测试: T3P-1234 -> {ip}")
    
    # 简单测试UI构建（不显示太久）
    import main as main_module
    print("[OK] main.py 导入成功")
    
    # 创建一个极简测试窗口
    root = tk.Tk()
    root.title("Test")
    root.geometry("800x500")
    
    # 测试自定义样式
    style = ttk.Style()
    try:
        style.theme_use('clam')
        print("[OK] clam 主题启用成功")
    except Exception as e:
        print(f"[WARN] clam 主题失败: {e}")
    
    # 测试几个控件
    tk.Label(root, text="基础 Label 测试").pack(pady=5)
    ttk.Button(root, text="基础 Button 测试").pack(pady=5)
    ttk.Combobox(root, values=['A', 'B', 'C']).pack(pady=5)
    ttk.Entry(root).pack(pady=5)
    
    # 测试带自定义样式的按钮
    style.configure('Test1.TButton', background='#6a6aff', foreground='white',
                    font=('Microsoft YaHei', 9, 'bold'), padding=10, borderwidth=0)
    ttk.Button(root, text="自定义样式 Button", style='Test1.TButton').pack(pady=5)
    
    # 测试带颜色的 Frame
    f1 = tk.Frame(root, bg='#383850', highlightthickness=1, highlightbackground='#4a4a66')
    f1.pack(fill=tk.X, pady=10, padx=10)
    tk.Label(f1, text="带颜色的 Frame 测试", bg='#383850', fg='#e4e4e7',
             font=('Microsoft YaHei', 9)).pack(pady=10)
    
    # 测试 scrolledtext
    from tkinter import scrolledtext
    st = scrolledtext.ScrolledText(root, height=5, bg='#202030', fg='#e4e4e7')
    st.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)
    st.insert(tk.END, "ScrolledText 测试\n如果能看到这行说明没问题\n")
    
    print("[OK] 所有控件创建成功")
    
    # 3秒后自动关闭
    root.after(3000, root.destroy)
    root.mainloop()
    print("\n[SUCCESS] 测试完成，GUI正常显示！")
    
except Exception as e:
    import traceback
    print(f"\n[ERROR] 测试失败: {e}")
    traceback.print_exc()
    sys.exit(1)
