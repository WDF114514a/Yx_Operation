"""
设备日志下载工具 v3.0
"""
import os
import threading
import queue
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime, timedelta

from device_utils import calculate_ip_by_model, get_ssh_credentials
from ssh_client import SSHClient
from log_manager import get_log_types, scan_remote_logs_with_time_filter
from archive_utils import extract_archive, get_local_download_dir
from config_manager import (
    get_last_download_dir, save_last_download_dir,
    get_devices, save_device,
    get_log_types_config, save_log_types_config,
)


BG_MAIN = '#1e1e2e'
BG_CARD = '#2a2a3e'
BG_CARD_LIGHT = '#33334d'
BG_INPUT = '#3a3a55'
ACCENT = '#7c82ff'
ACCENT_HOVER = '#9399ff'
SUCCESS = '#5cd6a0'
WARNING = '#ffc980'
ERROR = '#ff8080'
TEXT = '#e4e4f0'
TEXT_MUTED = '#8a8aa8'
BORDER = '#43435e'

FONT_MAIN = ('Microsoft YaHei UI', 9)
FONT_TITLE = ('Microsoft YaHei UI', 14, 'bold')
FONT_CARD = ('Microsoft YaHei UI', 10, 'bold')
FONT_BTN = ('Microsoft YaHei UI', 9)
FONT_SMALL = ('Microsoft YaHei UI', 8)
FONT_MONO = ('Consolas', 9)

DEVICES_FILE = os.path.join(os.path.expanduser('~'), '.agv_log_tool', 'devices.json')


def get_beijing_time():
    return datetime.now()


def _devices_load():
    try:
        if os.path.exists(DEVICES_FILE):
            with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _devices_save(data):
    try:
        os.makedirs(os.path.dirname(DEVICES_FILE), exist_ok=True)
        with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _get_device_categories():
    cats = set()
    for d in _devices_load():
        cats.add(d.get('category', '默认'))
    return sorted(cats)


def _guess_default_category(model, number, region):
    # 按地区做一个简单默认分类
    if region == 'ru':
        return '俄罗斯设备'
    elif region == 'other':
        return '海外设备'
    return f'{model}设备'


# ============ CollapsibleCategory ============
class CollapsibleCategory(tk.Frame):
    BATCH_SIZE = 50

    def __init__(self, master, category_name, log_list, on_selection_change=None):
        super().__init__(master, bg=BG_CARD, highlightthickness=1,
                         highlightbackground=BORDER)
        self.category_name = category_name
        self.log_list = log_list
        self.is_collapsed = True
        self._checkbox_vars = []
        self._category_var = tk.BooleanVar(value=False)
        self._on_selection_change = on_selection_change
        self._pending_batch_idx = 0
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG_CARD)
        header.pack(fill=tk.X, padx=10, pady=(8, 6))
        self.toggle_btn = tk.Label(header, text='[+]', bg=BG_CARD, fg=ACCENT,
                                   font=FONT_MAIN, cursor='hand2')
        self.toggle_btn.pack(side=tk.LEFT)
        self.toggle_btn.bind('<Button-1>', lambda e: self.toggle())
        tk.Checkbutton(header, variable=self._category_var, bg=BG_CARD,
                       activebackground=BG_CARD, selectcolor=BG_CARD,
                       fg=TEXT, activeforeground=TEXT, command=self._on_category_check,
                       cursor='hand2', highlightthickness=0, bd=0
                       ).pack(side=tk.LEFT, padx=(6, 4))
        tk.Label(header, text=self.category_name, bg=BG_CARD, fg=ACCENT,
                 font=FONT_CARD).pack(side=tk.LEFT)
        tk.Label(header, text=f'  ({len(self.log_list)} 个文件)',
                 bg=BG_CARD, fg=TEXT_MUTED, font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, padx=10)
        self.items_frame = tk.Frame(self, bg=BG_CARD)

    def _render_next_batch(self):
        if not self.log_list or self._pending_batch_idx >= len(self.log_list):
            return
        start = self._pending_batch_idx
        end = min(start + self.BATCH_SIZE, len(self.log_list))
        for i in range(start, end):
            info = self.log_list[i]
            row = tk.Frame(self.items_frame, bg=BG_CARD)
            row.pack(fill=tk.X, pady=1)
            var = tk.BooleanVar(value=False)
            self._checkbox_vars.append((var, info))
            info['_var'] = var
            tk.Checkbutton(row, variable=var, bg=BG_CARD, activebackground=BG_CARD,
                          selectcolor=BG_CARD, fg=TEXT, command=self._on_item_check,
                          cursor='hand2', highlightthickness=0, bd=0
                          ).pack(side=tk.LEFT, padx=(30, 8))
            dt = info.get('datetime') or info.get('mod_time')
            dt_str = dt.strftime('%Y-%m-%d %H:%M:%S') if isinstance(dt, datetime) else '未知时间'
            size_kb = info.get('size_kb', 0)
            size_str = f'{size_kb / 1024:.2f} MB' if size_kb >= 1024 else f'{size_kb:.1f} KB'
            tk.Label(row, text=info['filename'], bg=BG_CARD, fg=TEXT,
                    font=FONT_MAIN).pack(side=tk.LEFT, padx=(0, 12))
            tk.Label(row, text=f'{dt_str} | {size_str}', bg=BG_CARD, fg=TEXT_MUTED,
                    font=FONT_SMALL).pack(side=tk.RIGHT)
        self._pending_batch_idx = end
        if end < len(self.log_list):
            self.after(10, self._render_next_batch)

    def _force_render_all(self, select_val=None):
        # 清理已有内容并全量渲染（用于勾选/取消全选时）
        for w in self.items_frame.winfo_children():
            w.destroy()
        self._checkbox_vars = []
        self._pending_batch_idx = 0
        for info in self.log_list:
            row = tk.Frame(self.items_frame, bg=BG_CARD)
            row.pack(fill=tk.X, pady=1)
            val = self._category_var.get() if select_val is None else select_val
            var = tk.BooleanVar(value=val)
            self._checkbox_vars.append((var, info))
            info['_var'] = var
            tk.Checkbutton(row, variable=var, bg=BG_CARD, activebackground=BG_CARD,
                          selectcolor=BG_CARD, fg=TEXT, command=self._on_item_check,
                          cursor='hand2', highlightthickness=0, bd=0
                          ).pack(side=tk.LEFT, padx=(30, 8))
            dt = info.get('datetime') or info.get('mod_time')
            dt_str = dt.strftime('%Y-%m-%d %H:%M:%S') if isinstance(dt, datetime) else '未知时间'
            size_kb = info.get('size_kb', 0)
            size_str = f'{size_kb / 1024:.2f} MB' if size_kb >= 1024 else f'{size_kb:.1f} KB'
            tk.Label(row, text=info['filename'], bg=BG_CARD, fg=TEXT,
                    font=FONT_MAIN).pack(side=tk.LEFT, padx=(0, 12))
            tk.Label(row, text=f'{dt_str} | {size_str}', bg=BG_CARD, fg=TEXT_MUTED,
                    font=FONT_SMALL).pack(side=tk.RIGHT)
        self._pending_batch_idx = len(self.log_list)

    def toggle(self):
        if self.is_collapsed:
            self.items_frame.pack(fill=tk.X, padx=8, pady=4)
            if self._pending_batch_idx == 0 and self.log_list:
                self._render_next_batch()
            self.toggle_btn.configure(text='[-]')
            self.is_collapsed = False
        else:
            self.items_frame.pack_forget()
            self.toggle_btn.configure(text='[+]')
            self.is_collapsed = True

    def _on_category_check(self):
        val = self._category_var.get()
        if self._pending_batch_idx < len(self.log_list):
            self._force_render_all(val)
        else:
            for var, _ in self._checkbox_vars:
                var.set(val)
        if self._on_selection_change:
            self._on_selection_change()

    def _on_item_check(self):
        if self._checkbox_vars:
            all_sel = all(v.get() for v, _ in self._checkbox_vars)
            self._category_var.set(all_sel)
        if self._on_selection_change:
            self._on_selection_change()

    def select_all(self):
        self._category_var.set(True)
        self._on_category_check()

    def deselect_all(self):
        self._category_var.set(False)
        self._on_category_check()

    def get_selected(self):
        return [info for var, info in self._checkbox_vars if var.get()]

    def expand(self):
        if self.is_collapsed:
            self.toggle()

    def collapse(self):
        if not self.is_collapsed:
            self.toggle()


# ============ Settings Dialog ============
class LogTypesSettingsDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title('高级设置 - 日志类型与关键字管理')
        self.geometry('760x600')
        self.configure(bg=BG_MAIN)
        self.transient(master)
        self.grab_set()
        self._result = None
        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text='  日志类型与关键字管理', bg=BG_MAIN, fg=ACCENT,
                 font=FONT_TITLE).pack(fill=tk.X, pady=(12, 8))
        tk.Label(self,
                text='  JSON 格式：{"分类名": {"path": "远程目录路径", "keywords": ["关键字1", "关键字2"]}}',
                bg=BG_MAIN, fg=TEXT_MUTED, font=FONT_SMALL).pack(fill=tk.X, padx=12, pady=(0, 8))
        container = tk.Frame(self, bg=BG_CARD, highlightthickness=1,
                            highlightbackground=BORDER)
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        hint = tk.Frame(container, bg=BG_CARD)
        hint.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(hint, text='编辑配置:', bg=BG_CARD, fg=TEXT,
                 font=FONT_CARD).pack(side=tk.LEFT)
        self.editor = scrolledtext.ScrolledText(
            container, height=22, wrap=tk.NONE,
            bg=BG_INPUT, fg=TEXT, insertbackground=TEXT,
            selectbackground=ACCENT, selectforeground='white',
            font=FONT_MONO, relief=tk.FLAT, borderwidth=2,
            highlightthickness=1, highlightbackground=BORDER
        )
        self.editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        current = get_log_types_config()
        self.editor.insert(tk.END, json.dumps(current, ensure_ascii=False, indent=2))
        btn_frame = tk.Frame(self, bg=BG_MAIN)
        btn_frame.pack(fill=tk.X, padx=12, pady=(8, 12))
        ttk.Button(btn_frame, text='重置为默认', style='Secondary.TButton',
                   command=self._reset_default).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='取消', style='Secondary.TButton',
                   command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text='保存', style='Primary.TButton',
                   command=self._on_save).pack(side=tk.RIGHT, padx=4)

    def _reset_default(self):
        if messagebox.askyesno('确认', '确定要重置为默认日志类型配置吗？', parent=self):
            from config_manager import DEFAULT_LOG_TYPES
            self.editor.delete('1.0', tk.END)
            self.editor.insert(tk.END, json.dumps(DEFAULT_LOG_TYPES, ensure_ascii=False, indent=2))

    def _on_save(self):
        content = self.editor.get('1.0', tk.END).strip()
        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError('顶层必须是对象')
            for k, v in data.items():
                if not isinstance(v, dict) or 'path' not in v or 'keywords' not in v:
                    raise ValueError(f'分类 "{k}" 缺少 path 或 keywords')
            save_log_types_config(data)
            self._result = data
            self.destroy()
        except Exception as e:
            messagebox.showerror('保存失败', f'配置错误：\n{str(e)}', parent=self)

    def get_result(self):
        return self._result


# ============ Main App ============
class LogDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title('设备日志下载工具 v3.0')
        self.root.geometry('1400x800')
        self.root.minsize(1100, 720)
        self.root.configure(bg=BG_MAIN)
        self.ssh_client = SSHClient()
        self.log_data = {}
        self.category_widgets = []
        self.msg_queue = queue.Queue()
        self.current_log_types_config = get_log_types_config()
        self.download_dir = get_last_download_dir()
        try:
            os.makedirs(self.download_dir, exist_ok=True)
        except Exception:
            pass
        self.selected_log_types = {}
        self._setup_styles()
        self._build_ui()
        self._check_queue()
        self._log('程序启动完成。请连接设备，设置时间范围后点击 [按时间范围筛选]。')

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Primary.TButton', background=ACCENT, foreground='white',
                       font=FONT_BTN, padding=(16, 7), borderwidth=0)
        style.map('Primary.TButton',
                 background=[('active', ACCENT_HOVER), ('disabled', '#555570')],
                 foreground=[('disabled', '#8a8aa8')])
        style.configure('Secondary.TButton', background=BG_CARD_LIGHT, foreground=TEXT,
                       font=FONT_BTN, padding=(12, 6), borderwidth=0)
        style.map('Secondary.TButton',
                 background=[('active', '#44446a'), ('disabled', '#333348')],
                 foreground=[('disabled', '#7a7a94')])
        style.configure('Quick.TButton', background=BG_CARD_LIGHT, foreground=ACCENT,
                       font=FONT_BTN, padding=(8, 4), borderwidth=0)
        style.map('Quick.TButton', background=[('active', '#44446a')])
        style.configure('Modern.TCombobox', fieldbackground=BG_INPUT,
                       background=BG_CARD_LIGHT, foreground=TEXT, arrowcolor=ACCENT, padding=4)
        style.map('Modern.TCombobox', fieldbackground=[('readonly', BG_INPUT)])
        style.configure('Modern.TEntry', fieldbackground=BG_INPUT, foreground=TEXT,
                       insertcolor=TEXT, padding=4)
        style.configure('TNotebook', background=BG_MAIN, borderwidth=0)
        style.configure('TNotebook.Tab', background=BG_CARD, foreground=TEXT,
                       padding=(16, 8), font=FONT_BTN)
        style.map('TNotebook.Tab',
                 background=[('selected', ACCENT), ('active', BG_CARD_LIGHT)],
                 foreground=[('selected', 'white')])
        style.configure('Treeview', background=BG_CARD, fieldbackground=BG_CARD,
                       foreground=TEXT, borderwidth=0, font=FONT_MAIN, rowheight=26)
        style.configure('Treeview.Heading', background=BG_CARD_LIGHT, foreground=ACCENT,
                       font=FONT_CARD, borderwidth=0)
        style.map('Treeview', background=[('selected', ACCENT)],
                 foreground=[('selected', 'white')])
        style.configure('Modern.Horizontal.TProgressbar',
                       troughcolor=BG_INPUT, background=ACCENT,
                       bordercolor=BG_INPUT, lightcolor=ACCENT,
                       darkcolor=ACCENT, thickness=12)
        self.root.option_add('*TCombobox*Listbox.background', BG_INPUT)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
        self.root.option_add('*TCombobox*Listbox.selectForeground', 'white')

    def _build_ui(self):
        title_bar = tk.Frame(self.root, bg=BG_MAIN, height=50)
        title_bar.grid(row=0, column=0, sticky='ew')
        title_bar.grid_propagate(False)
        title_bar.grid_columnconfigure(1, weight=1)
        tk.Label(title_bar, text='  云象-设备日志下载工具', bg=BG_MAIN, fg=ACCENT,
                 font=FONT_TITLE).grid(row=0, column=0, sticky='w', padx=16, pady=14)
        tk.Label(title_bar, text='v3.0 By-胡陈浩',
                 bg=BG_MAIN, fg=TEXT_MUTED, font=FONT_SMALL
                 ).grid(row=0, column=1, sticky='w', pady=14)
        self.status_var = tk.StringVar(value='[ 未连接 ]')
        tk.Label(title_bar, textvariable=self.status_var, bg=BG_MAIN, fg=TEXT,
                 font=FONT_CARD).grid(row=0, column=2, sticky='e', padx=16, pady=14)

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky='nsew', padx=12, pady=6)
        self._build_main_tab()
        self._build_device_tab()

    def _make_card(self, parent, title, expand=False):
        card = tk.Frame(parent, bg=BG_CARD, highlightthickness=1,
                       highlightbackground=BORDER)
        sticky = 'nsew' if expand else 'ew'
        card.grid(sticky=sticky, padx=6, pady=6)
        card.grid_columnconfigure(0, weight=1)
        if expand:
            card.grid_rowconfigure(2, weight=1)
        header = tk.Frame(card, bg=BG_CARD)
        header.grid(row=0, column=0, sticky='ew', padx=14, pady=(12, 6))
        tk.Label(header, text=title, bg=BG_CARD, fg=ACCENT, font=FONT_CARD).pack(side=tk.LEFT)
        tk.Frame(card, bg=BORDER, height=1).grid(row=1, column=0, sticky='ew', padx=14)
        content = tk.Frame(card, bg=BG_CARD)
        content_sticky = 'nsew' if expand else 'ew'
        content.grid(row=2, column=0, sticky=content_sticky, padx=14, pady=12)
        return content

    # -------- Main Tab --------
    def _build_main_tab(self):
        main_frame = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(main_frame, text='  日志下载  ')
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=2)
        main_frame.grid_rowconfigure(0, weight=1)

        # Left panel
        left_panel = tk.Frame(main_frame, bg=BG_MAIN)
        left_panel.grid(row=0, column=0, sticky='nsew', padx=(6, 3), pady=6)
        left_panel.grid_rowconfigure(2, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        conn_card = self._make_card(left_panel, '设备连接配置')
        self._build_conn_panel(conn_card)
        type_card = self._make_card(left_panel, '要扫描的日志类型（勾选）')
        self._build_log_type_panel(type_card)
        log_card = self._make_card(left_panel, '设备日志列表（按时间范围筛选后显示）', expand=True)
        self._build_log_panel(log_card)

        # Right panel
        right_panel = tk.Frame(main_frame, bg=BG_MAIN)
        right_panel.grid(row=0, column=1, sticky='nsew', padx=(3, 6), pady=6)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        time_card = self._make_card(right_panel, '时间范围筛选（精确到秒）')
        self._build_time_panel(time_card)
        dl_card = self._make_card(right_panel, '下载设置')
        self._build_download_panel(dl_card)
        log_out_card = self._make_card(right_panel, '运行日志', expand=True)
        self._build_log_output(log_out_card)

        # Progress
        bottom = tk.Frame(main_frame, bg=BG_MAIN)
        bottom.grid(row=1, column=0, columnspan=2, sticky='ew', padx=12, pady=(4, 10))
        bottom.grid_columnconfigure(1, weight=1)
        tk.Label(bottom, text='进度:', bg=BG_MAIN, fg=TEXT_MUTED,
                 font=FONT_BTN).grid(row=0, column=0, sticky='e', padx=(0, 8))
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(bottom, variable=self.progress_var, maximum=100,
                       style='Modern.Horizontal.TProgressbar').grid(row=0, column=1, sticky='ew')

    # -------- Device Tab --------
    def _build_device_tab(self):
        dev_frame = tk.Frame(self.notebook, bg=BG_MAIN)
        self.notebook.add(dev_frame, text='  设备列表  ')
        dev_frame.grid_columnconfigure(0, weight=1)
        dev_frame.grid_rowconfigure(0, weight=1)
        card = self._make_card(dev_frame, '已连接过的设备（双击快速连接，支持分类）', expand=True)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        toolbar = tk.Frame(card, bg=BG_CARD)
        toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Button(toolbar, text='刷新', style='Quick.TButton',
                   command=self._refresh_device_list).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text='设置分类', style='Quick.TButton',
                   command=self._set_device_category).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text='删除', style='Quick.TButton',
                   command=self._delete_selected_device).pack(side=tk.LEFT, padx=4)

        tk.Label(toolbar, text='筛选:', bg=BG_CARD, fg=TEXT,
                 font=FONT_BTN).pack(side=tk.LEFT, padx=(20, 6))
        self.device_filter_var = tk.StringVar(value='全部')
        self.filter_combo = ttk.Combobox(toolbar, textvariable=self.device_filter_var,
                                        values=['全部'], state='readonly', width=14,
                                        style='Modern.TCombobox')
        self.filter_combo.pack(side=tk.LEFT, padx=2)
        self.filter_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_device_list())

        cols = ('model', 'number', 'region', 'category', 'ip', 'last_used')
        self.device_tree = ttk.Treeview(card, columns=cols, show='headings', selectmode='browse')
        for c, w, text in [('model', 80, '型号'), ('number', 90, '编号'),
                           ('region', 80, '地区'), ('category', 120, '分类'),
                           ('ip', 150, 'IP'), ('last_used', 160, '最近使用')]:
            self.device_tree.heading(c, text=text)
            self.device_tree.column(c, width=w, anchor='center')
        self.device_tree.grid(row=1, column=0, sticky='nsew')
        self.device_tree.bind('<Double-1>', lambda e: self._quick_connect())
        self.device_tree.bind('<Return>', lambda e: self._quick_connect())
        sb = ttk.Scrollbar(card, orient='vertical', command=self.device_tree.yview)
        sb.grid(row=1, column=1, sticky='ns')
        self.device_tree.configure(yscrollcommand=sb.set)
        tk.Label(card, text='提示: 双击任意设备项即可快速连接',
                bg=BG_CARD, fg=TEXT_MUTED, font=FONT_SMALL
                ).grid(row=2, column=0, sticky='w', pady=(8, 0))
        self._refresh_device_list()

    # -------- Panels --------
    def _build_conn_panel(self, parent):
        parent.grid_columnconfigure(7, weight=1)
        tk.Label(parent, text='型号:', bg=BG_CARD, fg=TEXT,
                 font=FONT_BTN).grid(row=0, column=0, sticky='w', pady=4)
        self.model_var = tk.StringVar(value='T3P')
        ttk.Combobox(parent, textvariable=self.model_var,
                     values=['T3P', 'T3', 'T1'], state='readonly',
                     width=8, style='Modern.TCombobox'
                     ).grid(row=0, column=1, sticky='w', padx=(4, 20), pady=4)
        tk.Label(parent, text='设备编号:', bg=BG_CARD, fg=TEXT,
                 font=FONT_BTN).grid(row=0, column=2, sticky='w', pady=4)
        self.device_num_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.device_num_var, width=14,
                  style='Modern.TEntry').grid(row=0, column=3, sticky='w', padx=(4, 20), pady=4)
        self.device_num_var.trace_add('write', lambda *a: self._update_ip())
        tk.Label(parent, text='地区:', bg=BG_CARD, fg=TEXT,
                 font=FONT_BTN).grid(row=0, column=4, sticky='w', pady=4)
        self.region_var = tk.StringVar(value='国内')
        rc = ttk.Combobox(parent, textvariable=self.region_var,
                         values=['国内', '俄罗斯', '其他国外'], state='readonly',
                         width=10, style='Modern.TCombobox')
        rc.grid(row=0, column=5, sticky='w', padx=(4, 20), pady=4)
        rc.bind('<<ComboboxSelected>>', lambda e: self._update_ip())
        tk.Label(parent, text='IP:', bg=BG_CARD, fg=TEXT,
                 font=FONT_BTN).grid(row=0, column=6, sticky='w', pady=4)
        self.ip_var = tk.StringVar(value='(填写后自动计算)')
        tk.Label(parent, textvariable=self.ip_var, bg=BG_CARD, fg=ACCENT,
                 font=FONT_CARD).grid(row=0, column=7, sticky='w', padx=(4, 0), pady=4)

        btn_frame = tk.Frame(parent, bg=BG_CARD)
        btn_frame.grid(row=1, column=0, columnspan=8, sticky='ew', pady=(10, 0))
        self.connect_btn = ttk.Button(btn_frame, text='连接设备', style='Primary.TButton',
                                     command=self._connect_device)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.disconnect_btn = ttk.Button(btn_frame, text='断开连接', style='Secondary.TButton',
                                        command=self._disconnect_device, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text='高级设置（日志关键字管理）', style='Secondary.TButton',
                  command=self._open_settings).pack(side=tk.LEFT, padx=(8, 0))

    def _build_log_type_panel(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        self.log_type_frame = tk.Frame(parent, bg=BG_CARD)
        self.log_type_frame.grid(row=0, column=0, sticky='ew')
        self._render_log_type_checkboxes()

    def _render_log_type_checkboxes(self):
        for w in self.log_type_frame.winfo_children():
            w.destroy()
        self.selected_log_types = {}
        cats = list(self.current_log_types_config.keys())
        for i, cat in enumerate(cats):
            var = tk.BooleanVar(value=True)
            self.selected_log_types[cat] = var
            tk.Checkbutton(self.log_type_frame, text=cat, variable=var,
                          bg=BG_CARD, activebackground=BG_CARD, selectcolor=BG_CARD,
                          fg=TEXT, activeforeground=TEXT, cursor='hand2',
                          highlightthickness=0, bd=0, font=FONT_BTN
                          ).grid(row=i // 2, column=i % 2, sticky='w', padx=4, pady=2)

    def _build_log_panel(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)
        action_bar = tk.Frame(parent, bg=BG_CARD)
        action_bar.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Button(action_bar, text='全选', style='Quick.TButton',
                  command=self._select_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_bar, text='取消全选', style='Quick.TButton',
                  command=self._deselect_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_bar, text='展开全部', style='Quick.TButton',
                  command=self._expand_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_bar, text='收起全部', style='Quick.TButton',
                  command=self._collapse_all).pack(side=tk.LEFT, padx=3)
        self.selection_count_var = tk.StringVar(value='已选 0 个文件')
        tk.Label(action_bar, textvariable=self.selection_count_var, bg=BG_CARD,
                fg=ACCENT, font=FONT_BTN).pack(side=tk.RIGHT)

        scroll_frame = tk.Frame(parent, bg=BG_CARD)
        scroll_frame.grid(row=2, column=0, sticky='nsew', pady=(4, 0))
        scroll_frame.grid_columnconfigure(0, weight=1)
        scroll_frame.grid_rowconfigure(0, weight=1)
        self.log_canvas = tk.Canvas(scroll_frame, bg=BG_CARD, highlightthickness=0, borderwidth=0)
        self.log_canvas.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(scroll_frame, orient='vertical', command=self.log_canvas.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.log_canvas.configure(yscrollcommand=sb.set)
        self.logs_inner = tk.Frame(self.log_canvas, bg=BG_CARD)
        self.log_canvas.create_window((0, 0), window=self.logs_inner, anchor='nw', tags='inner_window')
        self.logs_inner.bind('<Configure>',
                            lambda e: self.log_canvas.configure(scrollregion=self.log_canvas.bbox('all')))
        self.log_canvas.bind('<Configure>',
                            lambda e: self.log_canvas.itemconfigure('inner_window', width=e.width))
        self.log_canvas.bind_all('<MouseWheel>',
            lambda e: self.log_canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units'))

        self._empty_label = tk.Label(
            self.logs_inner,
            text='\n\n[ 未扫描 ]\n请连接设备，设置时间范围后点击 [按时间范围筛选]\n\n',
            bg=BG_CARD, fg=TEXT_MUTED, font=FONT_MAIN, justify='center'
        )
        self._empty_label.pack(fill=tk.X, pady=50)

    def _build_time_panel(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        self.current_time_var = tk.StringVar()
        tk.Label(parent, textvariable=self.current_time_var, bg=BG_CARD, fg=SUCCESS,
                font=FONT_BTN).grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
        self._update_current_time()

        quick_frame = tk.Frame(parent, bg=BG_CARD)
        quick_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 8))
        tk.Label(quick_frame, text='快捷:', bg=BG_CARD, fg=TEXT, font=FONT_BTN).pack(side=tk.LEFT)
        for h in [1, 2, 3, 6, 12, 24]:
            ttk.Button(quick_frame, text=f'近{h}小时', style='Quick.TButton',
                      command=lambda hr=h: self._set_quick_time(hr)).pack(side=tk.LEFT, padx=3)

        now = get_beijing_time()
        default_start = now - timedelta(hours=1)

        row1 = tk.Frame(parent, bg=BG_CARD)
        row1.grid(row=2, column=0, columnspan=2, sticky='ew', pady=4)
        tk.Label(row1, text='开始时间:', bg=BG_CARD, fg=TEXT,
                font=FONT_BTN, width=10).pack(side=tk.LEFT)
        self.start_date_var = tk.StringVar(value=default_start.strftime('%Y-%m-%d'))
        ttk.Entry(row1, textvariable=self.start_date_var, width=12,
                 style='Modern.TEntry').pack(side=tk.LEFT, padx=(0, 8))
        self.start_time_var = tk.StringVar(value=default_start.strftime('%H:%M:%S'))
        ttk.Entry(row1, textvariable=self.start_time_var, width=10,
                 style='Modern.TEntry').pack(side=tk.LEFT)

        row2 = tk.Frame(parent, bg=BG_CARD)
        row2.grid(row=3, column=0, columnspan=2, sticky='ew', pady=4)
        tk.Label(row2, text='结束时间:', bg=BG_CARD, fg=TEXT,
                font=FONT_BTN, width=10).pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar(value=now.strftime('%Y-%m-%d'))
        ttk.Entry(row2, textvariable=self.end_date_var, width=12,
                 style='Modern.TEntry').pack(side=tk.LEFT, padx=(0, 8))
        self.end_time_var = tk.StringVar(value=now.strftime('%H:%M:%S'))
        ttk.Entry(row2, textvariable=self.end_time_var, width=10,
                 style='Modern.TEntry').pack(side=tk.LEFT)

        tk.Label(parent, text='日期: YYYY-MM-DD   时间: HH:MM:SS',
                bg=BG_CARD, fg=TEXT_MUTED, font=FONT_SMALL
                ).grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 8))

        self.filter_btn = ttk.Button(parent, text='按时间范围筛选',
                                    style='Primary.TButton', command=self._apply_time_filter)
        self.filter_btn.grid(row=5, column=0, columnspan=2, sticky='ew', pady=(2, 0))

    def _update_current_time(self):
        now = get_beijing_time()
        self.current_time_var.set('当前时间: ' + now.strftime('%Y-%m-%d %H:%M:%S'))
        self.root.after(1000, self._update_current_time)

    def _set_quick_time(self, hours):
        now = get_beijing_time()
        start = now - timedelta(hours=hours)
        self.start_date_var.set(start.strftime('%Y-%m-%d'))
        self.start_time_var.set(start.strftime('%H:%M:%S'))
        self.end_date_var.set(now.strftime('%Y-%m-%d'))
        self.end_time_var.set(now.strftime('%H:%M:%S'))
        self._log(f'已设置时间范围: 近 {hours} 小时')

    def _build_download_panel(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        row1 = tk.Frame(parent, bg=BG_CARD)
        row1.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        row1.grid_columnconfigure(1, weight=1)
        tk.Label(row1, text='保存到:', bg=BG_CARD, fg=TEXT,
                font=FONT_BTN, width=8).grid(row=0, column=0, sticky='w')
        self.dir_var = tk.StringVar(value=self.download_dir)
        ttk.Entry(row1, textvariable=self.dir_var, style='Modern.TEntry'
                 ).grid(row=0, column=1, sticky='ew', padx=(0, 6))
        ttk.Button(row1, text='浏览...', style='Secondary.TButton',
                  command=self._choose_directory).grid(row=0, column=2)

        opt_frame = tk.Frame(parent, bg=BG_CARD)
        opt_frame.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        self.compress_var = tk.BooleanVar(value=True)
        self.extract_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame, text='启用压缩下载（速度更快，推荐）',
                      variable=self.compress_var, bg=BG_CARD, fg=TEXT,
                      activebackground=BG_CARD, activeforeground=TEXT,
                      selectcolor=BG_CARD, font=FONT_BTN, cursor='hand2',
                      highlightthickness=0, bd=0).pack(anchor='w', pady=1)
        tk.Checkbutton(opt_frame, text='下载完成后自动解压',
                      variable=self.extract_var, bg=BG_CARD, fg=TEXT,
                      activebackground=BG_CARD, activeforeground=TEXT,
                      selectcolor=BG_CARD, font=FONT_BTN, cursor='hand2',
                      highlightthickness=0, bd=0).pack(anchor='w', pady=1)

        self.download_btn = ttk.Button(parent, text='开始下载选中日志',
                                      style='Primary.TButton', command=self._start_download,
                                      state=tk.DISABLED)
        self.download_btn.grid(row=2, column=0, sticky='ew')

    def _build_log_output(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        self.log_output = scrolledtext.ScrolledText(
            parent, height=14, wrap=tk.WORD, bg=BG_INPUT, fg=TEXT,
            insertbackground=TEXT, selectbackground=ACCENT, selectforeground='white',
            font=FONT_MONO, relief=tk.FLAT, borderwidth=2,
            highlightthickness=1, highlightbackground=BORDER
        )
        self.log_output.grid(row=0, column=0, sticky='nsew')
        self.log_output.tag_configure('info', foreground=TEXT)
        self.log_output.tag_configure('success', foreground=SUCCESS)
        self.log_output.tag_configure('warning', foreground=WARNING)
        self.log_output.tag_configure('error', foreground=ERROR)

    # ==================== Logic ====================
    def _update_ip(self):
        model = self.model_var.get().strip().upper()
        try:
            num_str = self.device_num_var.get().strip()
            number = int(num_str) if num_str else 0
        except ValueError:
            self.ip_var.set('(编号需为数字)')
            return
        region_code = 'ru' if self.region_var.get() == '俄罗斯' else \
                     'other' if self.region_var.get() == '其他国外' else 'cn'
        if model and number > 0:
            ip = calculate_ip_by_model(model, number, region_code)
            self.ip_var.set(ip if ip else '(无法计算IP)')
        else:
            self.ip_var.set('(填写后自动计算)')

    def _connect_device(self):
        model = self.model_var.get().strip().upper()
        try:
            number = int(self.device_num_var.get().strip())
        except ValueError:
            messagebox.showwarning('提示', '请输入有效的设备编号')
            return
        ip = self.ip_var.get()
        if not ip or ip.startswith('('):
            messagebox.showerror('错误', '请先填写有效的设备信息生成IP')
            return
        self.connect_btn.config(state=tk.DISABLED)
        self.status_var.set('[ 正在连接... ]')
        self._log(f'正在连接设备 {model}-{number} ({ip}) ...')
        threading.Thread(target=self._connect_worker,
                        args=(ip, model, number), daemon=True).start()

    def _connect_worker(self, ip, model, number):
        creds = get_ssh_credentials()
        success, msg = self.ssh_client.connect(
            hostname=ip, username=creds['username'],
            password=creds['password'], port=creds['port']
        )
        self.msg_queue.put(('connect_result', (success, msg, model, number, ip)))

    def _disconnect_device(self):
        self.ssh_client.close()
        self.status_var.set('[ 未连接 ]')
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.download_btn.config(state=tk.DISABLED)
        self.log_data = {}
        self.category_widgets = []
        self._clear_logs_inner()
        self._show_log_hint('[ 已断开连接 ]\n请重新连接设备后点击 [按时间范围筛选]')
        self._log('已断开设备连接')

    def _apply_time_filter(self):
        if not self.ssh_client.connected:
            messagebox.showinfo('提示', '请先连接设备')
            return
        try:
            start = datetime.strptime(f'{self.start_date_var.get()} {self.start_time_var.get()}',
                                     '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(f'{self.end_date_var.get()} {self.end_time_var.get()}',
                                   '%Y-%m-%d %H:%M:%S')
        except ValueError:
            messagebox.showerror('格式错误', '时间格式不正确\n日期: YYYY-MM-DD\n时间: HH:MM:SS')
            return
        if start > end:
            messagebox.showerror('错误', '开始时间不能晚于结束时间')
            return
        active_types = {cat: self.current_log_types_config[cat]
                       for cat, var in self.selected_log_types.items() if var.get()}
        if not active_types:
            messagebox.showinfo('提示', '请至少勾选一个日志类型')
            return
        self._log(f'按时间范围扫描: {start.strftime("%Y-%m-%d %H:%M:%S")} ~ '
                 f'{end.strftime("%Y-%m-%d %H:%M:%S")}')
        self._log(f'扫描 {len(active_types)} 个日志分类...')
        self.filter_btn.config(state=tk.DISABLED)
        self._show_log_hint('[ 扫描中... 请稍候 ]')
        threading.Thread(target=self._filter_worker,
                        args=(start, end, active_types), daemon=True).start()

    def _filter_worker(self, start, end, active_types):
        try:
            logs = scan_remote_logs_with_time_filter(
                self.ssh_client, start, end, log_types=active_types, max_workers=4
            )
            self.msg_queue.put(('logs_result', logs))
        except Exception as e:
            self.msg_queue.put(('logs_result', {'error': str(e)}))

    def _clear_logs_inner(self):
        for w in self.logs_inner.winfo_children():
            w.destroy()

    def _show_log_hint(self, text):
        self._clear_logs_inner()
        self.category_widgets = []
        tk.Label(self.logs_inner, text=text, bg=BG_CARD, fg=TEXT_MUTED,
                font=FONT_MAIN, justify='center').pack(fill=tk.X, pady=50)
        self._update_selection_count()

    def _render_logs(self):
        self._clear_logs_inner()
        self.category_widgets = []
        has_content = False
        total = 0
        sorted_items = sorted(self.log_data.items(),
                             key=lambda kv: len(kv[1]) if isinstance(kv[1], list) else 0)
        for category, log_list in sorted_items:
            if not isinstance(log_list, list) or len(log_list) == 0:
                continue
            has_content = True
            total += len(log_list)
            widget = CollapsibleCategory(self.logs_inner, category, log_list,
                                        on_selection_change=self._update_selection_count)
            widget.pack(fill=tk.X, padx=2, pady=3)
            self.category_widgets.append(widget)
        if not has_content:
            self._show_log_hint('[ 无匹配日志 ]\n时间范围内未找到符合条件的日志，请调整时间范围或日志类型')
            self.download_btn.config(state=tk.DISABLED)
        else:
            self.download_btn.config(state=tk.NORMAL)
        self._update_selection_count()

    def _expand_all(self):
        for w in self.category_widgets:
            w.expand()

    def _collapse_all(self):
        for w in self.category_widgets:
            w.collapse()

    def _select_all(self):
        for w in self.category_widgets:
            w.select_all()

    def _deselect_all(self):
        for w in self.category_widgets:
            w.deselect_all()

    def _update_selection_count(self):
        count = 0
        for w in self.category_widgets:
            count += len(w.get_selected())
        self.selection_count_var.set(f'已选 {count} 个文件')

    def _choose_directory(self):
        directory = filedialog.askdirectory(title='选择下载目录', initialdir=self.dir_var.get())
        if directory:
            self.dir_var.set(directory)
            self.download_dir = directory
            save_last_download_dir(directory)
            self._log(f'下载目录已更新: {directory}')

    def _get_selected_logs(self):
        selected = []
        for w in self.category_widgets:
            selected.extend(w.get_selected())
        return selected

    def _start_download(self):
        selected = self._get_selected_logs()
        if not selected:
            messagebox.showinfo('提示', '请先勾选要下载的日志')
            return
        target_dir = self.dir_var.get().strip()
        if not target_dir:
            messagebox.showerror('错误', '请先设置下载目录')
            return
        try:
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            save_last_download_dir(target_dir)
        except Exception as e:
            messagebox.showerror('错误', f'无法访问下载目录: {e}')
            return
        device_id = f'{self.model_var.get()}-{self.device_num_var.get().strip()}'
        self.download_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        use_compress = self.compress_var.get()
        auto_extract = self.extract_var.get()
        self._log(f'开始下载 {len(selected)} 个日志文件到 {target_dir}')
        threading.Thread(target=self._download_worker,
                        args=(selected, device_id, use_compress, auto_extract, target_dir),
                        daemon=True).start()

    def _download_worker(self, files, device_id, use_compress, auto_extract, target_dir):
        try:
            local_dir = get_local_download_dir(target_dir, device_id)
            if use_compress:
                self.msg_queue.put(('log', ('正在远程压缩日志...', 'info')))
                archive_name = f'agv_{device_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tar.gz'
                remote_archive = f'/tmp/{archive_name}'
                file_paths = [f['full_path'] for f in files]
                quoted = ' '.join(f'"{p}"' for p in file_paths)
                cmd = f'tar -czf "{remote_archive}" {quoted}'
                success, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=600)
                if not success or (stderr and stderr.strip()):
                    self.msg_queue.put(('log',
                        (f'压缩失败，改用逐个文件下载: {stderr or "未知"}', 'warning')))
                    use_compress = False
                else:
                    self.msg_queue.put(('log', ('远程压缩完成，开始下载...', 'success')))
                    local_archive = os.path.join(local_dir, archive_name)
                    ok, msg = self.ssh_client.download_file(remote_archive, local_archive)
                    if ok:
                        self.msg_queue.put(('progress', 80))
                        self.msg_queue.put(('log',
                            (f'下载完成: {os.path.basename(local_archive)}', 'success')))
                        try:
                            self.ssh_client.exec_command(f'rm -f "{remote_archive}"')
                        except Exception:
                            pass
                        if auto_extract:
                            self.msg_queue.put(('log', ('正在自动解压...', 'info')))
                            ok_ex, msg_ex, ex_path = extract_archive(local_archive, local_dir)
                            if ok_ex:
                                self.msg_queue.put(('log', (f'解压完成: {ex_path}', 'success')))
                            else:
                                self.msg_queue.put(('log', (f'解压失败: {msg_ex}', 'warning')))
                        self.msg_queue.put(('progress', 100))
                        self.msg_queue.put(('done', local_dir))
                        return
                    else:
                        self.msg_queue.put(('log',
                            (f'下载失败: {msg}，改用逐个文件下载', 'warning')))
                        use_compress = False

            if not use_compress:
                total = len(files)
                for i, info in enumerate(files):
                    fname = info['filename']
                    fpath = info['full_path']
                    self.msg_queue.put(('log', (f'下载 [{i+1}/{total}]: {fname}', 'info')))
                    local_path = os.path.join(local_dir, fname)
                    ok, msg = self.ssh_client.download_file(fpath, local_path)
                    if ok:
                        self.msg_queue.put(('progress', (i + 1) / total * 100))
                    else:
                        self.msg_queue.put(('log', (f'  失败: {msg}', 'error')))
                self.msg_queue.put(('done', local_dir))
        except Exception as e:
            self.msg_queue.put(('log', (f'下载过程出错: {str(e)}', 'error')))
            self.msg_queue.put(('error', str(e)))

    def _open_settings(self):
        dlg = LogTypesSettingsDialog(self.root)
        self.root.wait_window(dlg)
        result = dlg.get_result()
        if result:
            self.current_log_types_config = result
            self._render_log_type_checkboxes()
            self._log('日志类型配置已更新', 'success')

    # ---- Device list helpers ----
    def _refresh_device_list(self):
        cats = ['全部'] + list(_get_device_categories())
        self.filter_combo['values'] = cats
        if self.device_filter_var.get() not in cats:
            self.device_filter_var.set('全部')
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        devices = _devices_load()
        filter_cat = self.device_filter_var.get()
        devices_sorted = sorted(devices, key=lambda d: d.get('last_used', ''), reverse=True)
        region_map = {'cn': '国内', 'ru': '俄罗斯', 'other': '其他国外'}
        for d in devices_sorted:
            if filter_cat != '全部' and d.get('category', '默认') != filter_cat:
                continue
            model = d.get('model', '')
            number = d.get('number', '')
            region = d.get('region', 'cn')
            rd = region_map.get(region, region)
            ip = ''
            try:
                ip = calculate_ip_by_model(model, int(number), region)
            except (ValueError, TypeError):
                pass
            self.device_tree.insert('', 'end', values=(
                model, number, rd, d.get('category', '默认'), ip, d.get('last_used', '-')
            ))

    def _quick_connect(self):
        sel = self.device_tree.selection()
        if not sel:
            return
        vals = self.device_tree.item(sel[0], 'values')
        if not vals:
            return
        model, number, region_display, category, ip, _ = vals
        region_code_map = {'国内': 'cn', '俄罗斯': 'ru', '其他国外': 'other'}
        rcode = region_code_map.get(region_display, 'cn')
        self.model_var.set(model)
        self.device_num_var.set(str(number))
        self.region_var.set(region_display)
        self._update_ip()
        self.notebook.select(0)
        self._connect_device()

    def _get_selected_device_info(self):
        sel = self.device_tree.selection()
        if not sel:
            return None
        vals = self.device_tree.item(sel[0], 'values')
        if not vals:
            return None
        model, number, region_display, category, ip, _ = vals
        region_code_map = {'国内': 'cn', '俄罗斯': 'ru', '其他国外': 'other'}
        return {'model': model, 'number': int(number),
                'region': region_code_map.get(region_display, 'cn')}

    def _set_device_category(self):
        info = self._get_selected_device_info()
        if not info:
            messagebox.showinfo('提示', '请先选择一个设备')
            return
        dlg = tk.Toplevel(self.root)
        dlg.title('设置设备分类')
        dlg.geometry('340x180')
        dlg.configure(bg=BG_MAIN)
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text=f'设备: {info["model"]}-{info["number"]}',
                bg=BG_MAIN, fg=TEXT, font=FONT_BTN).pack(pady=(16, 4))
        row = tk.Frame(dlg, bg=BG_MAIN)
        row.pack(pady=8)
        tk.Label(row, text='分类名:', bg=BG_MAIN, fg=TEXT,
                font=FONT_BTN).pack(side=tk.LEFT, padx=4)
        var = tk.StringVar(value='默认')
        existing = list(_get_device_categories())
        ttk.Combobox(row, textvariable=var, values=existing if existing else ['默认'],
                    width=18, style='Modern.TCombobox').pack(side=tk.LEFT, padx=4)

        def apply():
            new_cat = var.get().strip() or '默认'
            devices = _devices_load()
            for d in devices:
                if (str(d.get('model', '')) == str(info['model'])
                        and str(d.get('number', '')) == str(info['number'])
                        and d.get('region', 'cn') == info['region']):
                    d['category'] = new_cat
            _devices_save(devices)
            self._refresh_device_list()
            dlg.destroy()

        ttk.Button(dlg, text='确定', style='Primary.TButton', command=apply).pack(pady=8)

    def _delete_selected_device(self):
        info = self._get_selected_device_info()
        if not info:
            messagebox.showinfo('提示', '请先选择一个设备')
            return
        if not messagebox.askyesno('确认删除',
                                  f'确定要从列表中删除设备 {info["model"]}-{info["number"]} 吗？'):
            return
        devices = _devices_load()
        remaining = [d for d in devices
                    if not (str(d.get('model', '')) == str(info['model'])
                            and str(d.get('number', '')) == str(info['number'])
                            and d.get('region', 'cn') == info['region'])]
        _devices_save(remaining)
        self._refresh_device_list()
        self._log(f'已从设备列表移除 {info["model"]}-{info["number"]}', 'info')

    # ---- Queue / Log ----
    def _check_queue(self):
        try:
            while True:
                msg_type, payload = self.msg_queue.get_nowait()
                if msg_type == 'connect_result':
                    success, msg, model, number, ip = payload
                    if success:
                        self.status_var.set(f'[ 已连接: {model}-{number} ]')
                        self.connect_btn.config(state=tk.DISABLED)
                        self.disconnect_btn.config(state=tk.NORMAL)
                        self._log(f'成功连接设备 {model}-{number} ({ip})', 'success')
                        self._log('请设置时间范围和勾选日志类型，然后点击 [按时间范围筛选]')
                        region_code_map = {'国内': 'cn', '俄罗斯': 'ru', '其他国外': 'other'}
                        rcode = region_code_map.get(self.region_var.get(), 'cn')
                        try:
                            dev_info = {
                                'model': model, 'number': int(number), 'region': rcode,
                                'category': _guess_default_category(model, int(number), rcode),
                                'last_used': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            save_device(dev_info)
                            self._refresh_device_list()
                        except Exception:
                            pass
                    else:
                        self.status_var.set('[ 连接失败 ]')
                        self.connect_btn.config(state=tk.NORMAL)
                        self._log(f'连接失败: {msg}', 'error')
                        messagebox.showerror('连接失败', msg)
                elif msg_type == 'logs_result':
                    logs = payload
                    if isinstance(logs, dict) and 'error' in logs:
                        self._log(f'扫描失败: {logs["error"]}', 'error')
                        self._show_log_hint(f'[ 扫描失败: {logs["error"]} ]')
                        messagebox.showerror('扫描错误', logs['error'])
                    else:
                        self.log_data = logs if isinstance(logs, dict) else {}
                        self._render_logs()
                        total = sum(len(v) for v in self.log_data.values() if isinstance(v, list))
                        self._log(f'扫描完成！共找到 {total} 个日志文件', 'success')
                    self.filter_btn.config(state=tk.NORMAL)
                elif msg_type == 'log':
                    if isinstance(payload, tuple):
                        text, tag = payload
                        self._log(text, tag)
                    else:
                        self._log(payload)
                elif msg_type == 'progress':
                    self.progress_var.set(payload)
                elif msg_type == 'done':
                    self._log(f'=== 下载任务完成！文件保存在: {payload} ===', 'success')
                    self.download_btn.config(state=tk.NORMAL)
                    messagebox.showinfo('下载完成', f'日志已下载到:\n{payload}')
                elif msg_type == 'error':
                    self.download_btn.config(state=tk.NORMAL)
                    messagebox.showerror('下载出错', payload)
        except queue.Empty:
            pass
        self.root.after(100, self._check_queue)

    def _log(self, message, tag='info'):
        timestamp = get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
        self.log_output.insert(tk.END, f'[{timestamp}] {message}\n', tag)
        self.log_output.see(tk.END)


def main():
    root = tk.Tk()
    LogDownloaderApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
