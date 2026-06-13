"""最小化测试 - 检查GUI是否能正常渲染"""
import sys
import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

# 先测试基础 tkinter 是否工作
print("测试1: 基础 tkinter 窗口...")
try:
    root = tk.Tk()
    root.title("Test Window")
    root.geometry("400x200")
    tk.Label(root, text="Hello World! This is basic tkinter.").pack(pady=30)
    ttk.Button(root, text="Close", command=root.destroy).pack()
    root.after(1500, root.destroy)
    root.mainloop()
    print("  [OK] 基础 tkinter 窗口正常")
except Exception as e:
    print(f"  [FAIL] {e}")

# 测试带颜色和自定义Frame的tkinter
print("\n测试2: 带颜色的 Frame...")
try:
    root = tk.Tk()
    root.title("Colored Test")
    root.configure(bg="#1e1e2e")
    root.geometry("400x200")
    
    frame = tk.Frame(root, bg="#252538", highlightthickness=1, highlightbackground="#3f3f52")
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    tk.Label(frame, text="Colored Label", bg="#252538", fg="#7c7cff", font=("Microsoft YaHei", 12)).pack(pady=20)
    ttk.Button(frame, text="Test Button", command=root.destroy).pack()
    
    root.after(1500, root.destroy)
    root.mainloop()
    print("  [OK] 带颜色的 Frame 正常")
except Exception as e:
    print(f"  [FAIL] {e}")

# 测试自定义 ttk 样式
print("\n测试3: 自定义ttk样式...")
try:
    root = tk.Tk()
    root.title("Style Test")
    root.configure(bg="#1e1e2e")
    root.geometry("400x300")
    
    style = ttk.Style()
    try:
        style.theme_use('clam')
        print("  clam theme loaded")
    except:
        print("  使用默认主题")
    
    style.configure('Test.TButton', background='#7c7cff', foreground='#ffffff',
                    font=('Microsoft YaHei', 9, 'bold'), padding=10, borderwidth=0)
    style.map('Test.TButton', background=[('active', '#9a9aff')])
    
    style.configure('Test.TCombobox', fieldbackground='#252538', 
                    background='#252538', foreground='#e4e4e7', padding=6)
    
    tk.Label(root, text="Custom Style Test", bg="#1e1e2e", fg="#7c7cff").pack(pady=10)
    
    ttk.Button(root, text="Styled Button", style='Test.TButton', command=root.destroy).pack(pady=5)
    
    cb = ttk.Combobox(root, values=['T3P', 'T3', 'T1'], style='Test.TCombobox')
    cb.set('T3P')
    cb.pack(pady=10)
    
    # 测试entry
    style.configure('Test.TEntry', fieldbackground='#252538', foreground='#e4e4e7', padding=6)
    entry = ttk.Entry(root, style='Test.TEntry', width=20)
    entry.insert(0, "Test Entry")
    entry.pack(pady=10)
    
    root.after(2000, root.destroy)
    root.mainloop()
    print("  [OK] 自定义 ttk 样式正常")
except Exception as e:
    print(f"  [FAIL] {e}")

print("\n=== 所有GUI测试完成 ===")
