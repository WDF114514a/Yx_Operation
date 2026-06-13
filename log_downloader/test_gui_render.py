"""GUI测试 - 启动程序 3 秒后自动关闭，用于验证界面渲染"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import main as app_module

# 创建主窗口
root = tk.Tk()

# 启动应用
app = app_module.LogDownloaderApp(root)

# 3 秒后自动关闭
root.after(3000, root.destroy)

print("GUI已启动，3秒后自动关闭...")
root.mainloop()
print("GUI测试完成，程序正常退出")
