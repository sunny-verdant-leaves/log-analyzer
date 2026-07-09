""" 服务器日志分析器 
Bilibili@碧叶晴天呀 设计
"""
import flet as ft
from pathlib import Path
from typing import List, Callable, Optional, Dict, Any, Type
import asyncio
import importlib.util
import sys
import inspect
from dataclasses import dataclass
from abc import ABC, abstractmethod
import uuid  # 用于生成唯一模块名


# ==================== 插件接口定义 ====================
class LogAnalysisPlugin(ABC):
    """日志分析插件基类，所有外部分析方法必须继承此类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件显示名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> List[Dict[str, Any]]:
        """
        返回参数配置列表，每个参数是一个字典：
        {
            "name": "参数名",
            "type": "str/int/float/bool/choice",
            "label": "显示标签",
            "default": 默认值,
            "options": [...]  # 仅type=choice时需要
        }
        """
        pass
    
    @abstractmethod
    def analyze(self, log_files: List[Path], params: Dict[str, Any]) -> str:
        """
        执行分析
        :param log_files: 选中的日志文件路径列表
        :param params: 参数字典
        :return: 分析结果字符串
        """
        pass

# ==================== 内置插件示例（保留原有分析方法） ====================
class TimelineAnalysisPlugin(LogAnalysisPlugin):
    @property
    def name(self) -> str:
        return "时间线分析"
    
    @property
    def description(self) -> str:
        return "按时间维度分析日志事件分布"
    
    def get_parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "time_pattern",
                "type": "str",
                "label": "时间格式正则",
                "default": r"\d{4}-\d{2}-\d{2}"
            },
            {
                "name": "show_distribution",
                "type": "bool",
                "label": "显示时间分布图",
                "default": True
            }
        ]
    
    def analyze(self, log_files: List[Path], params: Dict[str, Any]) -> str:
        result = f"【时间线分析】\n"
        result += f"分析文件数: {len(log_files)}\n"
        result += f"时间正则: {params.get('time_pattern')}\n"
        result += f"显示分布图: {params.get('show_distribution')}\n"
        result += "\n[时间线分析结果示例]\n"
        for file in log_files:
            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
                result += f"- {file.name}: 已提取时间戳 {len(content) // 1000} 个\n"
            except Exception as e:
                result += f"- {file.name}: 读取失败 ({str(e)})\n"
        return result

class ErrorStatisticsPlugin(LogAnalysisPlugin):
    @property
    def name(self) -> str:
        return "错误统计"
    
    @property
    def description(self) -> str:
        return "统计日志中的错误类型和出现次数"
    
    def get_parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "error_keywords",
                "type": "str",
                "label": "错误关键字",
                "default": "ERROR,Exception,Failed"
            },
            {
                "name": "stat_dimension",
                "type": "choice",
                "label": "统计维度",
                "default": "按类型",
                "options": ["按类型", "按时间", "按文件"]
            }
        ]
    
    def analyze(self, log_files: List[Path], params: Dict[str, Any]) -> str:
        keywords = params.get('error_keywords', '').split(',')
        result = f"【错误统计】\n"
        result += f"分析文件数: {len(log_files)}\n"
        result += f"错误关键字: {keywords}\n"
        result += f"统计维度: {params.get('stat_dimension')}\n"
        result += "\n[错误统计结果示例]\n"
        
        error_count = 0
        for file in log_files:
            try:
                content = file.read_text(encoding='utf-8', errors='ignore')
                count = sum(content.count(kw.strip()) for kw in keywords if kw.strip())
                error_count += count
                result += f"- {file.name}: 匹配错误 {count} 次\n"
            except Exception as e:
                result += f"- {file.name}: 读取失败 ({str(e)})\n"
        result += f"\n总计错误数: {error_count}\n"
        return result

# ==================== 主应用类 ====================
class LogAnalyzerApp:
    def __init__(self):
        self.selected_folder: Optional[Path] = None
        self.plugin_folder: Optional[Path] = None  # 插件文件夹路径
        self.log_files: List[Path] = []
        self.selected_logs: List[Path] = []
        
        # 插件相关
        self.builtin_plugins: Dict[str, LogAnalysisPlugin] = {}  # 内置插件
        self.external_plugins: Dict[str, LogAnalysisPlugin] = {}  # 外部插件
        self.all_plugins: Dict[str, LogAnalysisPlugin] = {}      # 所有插件（内置+外部）
        
        # 全选状态
        self.select_all_state: bool = False
        self.log_checkboxes: List[ft.Checkbox] = []  # 存储所有日志复选框引用
        
        # 加载内置插件
        self._load_builtin_plugins()

    def _load_builtin_plugins(self):
        """加载内置插件"""
        builtin_plugin_classes = [TimelineAnalysisPlugin, ErrorStatisticsPlugin]
        for plugin_class in builtin_plugin_classes:
            plugin = plugin_class()
            self.builtin_plugins[plugin.name] = plugin
        self.all_plugins.update(self.builtin_plugins)

    def main(self, page: ft.Page):
        page.title = "日志分析工具"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window_width = 1400
        page.window_height = 800
        
        # 状态栏
        self.status_text = ft.Text("就绪", size=12, color=ft.colors.GREY_400)
        
        # 文件夹选择区域
        self.folder_path_text = ft.Text("未选择文件夹", size=14, color=ft.colors.GREY_400)
        self.log_list_view = ft.ListView(expand=True, spacing=2, auto_scroll=False)
        
        # 全选按钮
        self.select_all_btn = ft.ElevatedButton(
            "全选",
            icon=ft.icons.CHECK_BOX,
            on_click=self._toggle_select_all,
            disabled=True,
            width=120
        )
        
        # 日志内容显示区域
        self.log_content = ft.TextField(
            multiline=True,
            read_only=True,
            expand=True,
            text_size=12,
            min_lines=20,
            border_color=ft.colors.BLUE_GREY_700,
            bgcolor=ft.colors.BLACK87
        )
        
        # 多选分析区域
        self.selected_logs_text = ft.Text("已选择: 0 个文件", size=14)
        self.analysis_result = ft.TextField(
            multiline=True,
            read_only=True,
            expand=True,
            text_size=12,
            min_lines=15,
            border_color=ft.colors.BLUE_GREY_700,
            bgcolor=ft.colors.BLACK87
        )
        
        # 插件和分析方法相关
        self.plugin_folder_text = ft.Text("未选择插件文件夹", size=14, color=ft.colors.GREY_400)
        self.method_dropdown = ft.Dropdown(
            label="选择分析方法（插件）",
            options=[ft.dropdown.Option(name) for name in self.all_plugins.keys()],
            width=300,
            disabled=True,  # 初始禁用，选择日志后启用
            on_change=self._on_method_change  # 选择插件时触发参数面板更新
        )
        
        # 插件描述文本
        self.plugin_desc_text = ft.Text(
            "", 
            size=12, 
            color=ft.colors.BLUE_400,
            italic=True
        )
        
        # 分析方法参数区域（动态生成）
        self.method_params = ft.Column([])
        self.params_container_ref = ft.Ref[ft.Container]()
        
        # 构建UI
        page.add(
            ft.Column([
                # 标题
                ft.Text("🔍 日志分析工具（插件版）", size=28, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                
                # 主布局：三列
                ft.Row([
                    # 左列：文件夹选择和日志列表（新增插件文件夹选择）
                    self._build_left_panel(),
                    
                    # 中列：单日志查看
                    self._build_center_panel(),
                    
                    # 右列：多选分析和插件选择
                    self._build_right_panel(),
                    
                ], expand=True, spacing=20),
                
                # 底部状态栏
                ft.Divider(),
                self.status_text,
                
            ], expand=True)
        )
        
    def _build_left_panel(self) -> ft.Container:
        """构建左侧面板：文件夹选择、插件文件夹选择和日志列表"""
        return ft.Container(
            content=ft.Column([
                ft.Text("📁 数据源与插件", size=16, weight=ft.FontWeight.BOLD),
                
                # 日志文件夹选择
                ft.Row([
                    ft.ElevatedButton(
                        "选择日志文件夹",
                        icon=ft.icons.FOLDER_OPEN,
                        on_click=self._pick_log_folder,
                        style=ft.ButtonStyle(
                            color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                            bgcolor={ft.MaterialState.DEFAULT: ft.colors.BLUE_600}
                        )
                    ),
                    self.folder_path_text,
                ], spacing=10),
                
                # 插件文件夹选择
                ft.Row([
                    ft.ElevatedButton(
                        "选择插件文件夹",
                        icon=ft.icons.EXTENSION,
                        on_click=self._pick_plugin_folder,
                        style=ft.ButtonStyle(
                            color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                            bgcolor={ft.MaterialState.DEFAULT: ft.colors.PURPLE_600}
                        )
                    ),
                    self.plugin_folder_text,
                ], spacing=10),
                
                # 单文件插件选择
                ft.Row([
                    ft.ElevatedButton(
                        "加载单个插件文件",
                        icon=ft.icons.FILE_OPEN,
                        on_click=self._pick_plugin_file,
                        style=ft.ButtonStyle(
                            color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                            bgcolor={ft.MaterialState.DEFAULT: ft.colors.ORANGE_600}
                        )
                    ),
                    ft.Text("支持直接选择.py文件加载", size=12, color=ft.colors.GREY_400),
                ], spacing=10),
                
                ft.Divider(),
                
                # 日志文件列表标题和全选按钮
                ft.Row([
                    ft.Text("日志文件列表", size=14, weight=ft.FontWeight.W_500, expand=True),
                    self.select_all_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Container(
                    content=self.log_list_view,
                    border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                    border_radius=8,
                    padding=10,
                    expand=True,
                    bgcolor=ft.colors.BLACK12
                ),
                
                # 操作按钮
                ft.Row([
                    ft.ElevatedButton(
                        "刷新日志列表",
                        icon=ft.icons.REFRESH,
                        on_click=self._refresh_logs,
                        disabled=True,
                        ref=self.refresh_btn_ref
                    ),
                    ft.ElevatedButton(
                        "刷新插件列表",
                        icon=ft.icons.UPDATE,
                        on_click=self._refresh_plugins,
                        disabled=True,
                        ref=self.refresh_plugin_btn_ref
                    ),
                ]),
                
            ], expand=True),
            width=350,
            border=ft.border.all(1, ft.colors.BLUE_GREY_800),
            border_radius=12,
            padding=15,
            bgcolor=ft.colors.BLUE_GREY_900
        )
    
    def _build_center_panel(self) -> ft.Container:
        """构建中间面板：单日志查看"""
        return ft.Container(
            content=ft.Column([
                ft.Text("📄 单日志查看", size=16, weight=ft.FontWeight.BOLD),
                
                ft.Row([
                    ft.Text("当前查看: ", size=12),
                    ft.Text("无", size=12, color=ft.colors.BLUE_400, ref=self.current_file_ref)
                ]),
                
                ft.Container(
                    content=self.log_content,
                    border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                    border_radius=8,
                    expand=True,
                    padding=10
                ),
                
                # 单日志操作按钮
                ft.Row([
                    ft.ElevatedButton(
                        "清除选择",
                        icon=ft.icons.CLEAR,
                        on_click=self._clear_single_selection
                    ),
                    ft.ElevatedButton(
                        "复制内容",
                        icon=ft.icons.COPY,
                        on_click=self._copy_content
                    ),
                ], alignment=ft.MainAxisAlignment.END),
                
            ], expand=True),
            expand=True,
            border=ft.border.all(1, ft.colors.BLUE_GREY_800),
            border_radius=12,
            padding=15,
            bgcolor=ft.colors.BLUE_GREY_900
        )
    
    def _build_right_panel(self) -> ft.Container:
        """构建右侧面板：多选分析和插件选择"""
        return ft.Container(
            content=ft.Column([
                ft.Text("📊 批量分析（插件版）", size=16, weight=ft.FontWeight.BOLD),
                
                # 已选择文件统计
                self.selected_logs_text,
                
                # 插件选择区域
                ft.Container(
                    content=ft.Column([
                        ft.Text("分析插件", size=14, weight=ft.FontWeight.W_500),
                        self.method_dropdown,
                        self.plugin_desc_text,  # 插件描述
                        
                        # 动态参数区域
                        ft.Container(
                            content=self.method_params,
                            border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                            border_radius=8,
                            padding=10,
                            visible=False,
                            ref=self.params_container_ref
                        ),
                        
                        # 执行分析按钮
                        ft.ElevatedButton(
                            "执行分析",
                            icon=ft.icons.PLAY_ARROW,
                            on_click=self._run_analysis,
                            disabled=True,
                            width=300,
                            style=ft.ButtonStyle(
                                color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                                bgcolor={ft.MaterialState.DEFAULT: ft.colors.GREEN_600}
                            ),
                            ref=self.run_analysis_btn_ref
                        ),
                        
                    ]),
                    padding=10,
                    bgcolor=ft.colors.BLACK12,
                    border_radius=8
                ),
                
                ft.Divider(),
                
                # 分析结果显示
                ft.Text("分析结果", size=14, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.analysis_result,
                    border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                    border_radius=8,
                    expand=True,
                    padding=10
                ),
                
                # 结果操作
                ft.Row([
                    ft.ElevatedButton(
                        "导出结果",
                        icon=ft.icons.DOWNLOAD,
                        on_click=self._export_result
                    ),
                    ft.ElevatedButton(
                        "清空结果",
                        icon=ft.icons.DELETE,
                        on_click=self._clear_result
                    ),
                ], alignment=ft.MainAxisAlignment.END),
                
            ], expand=True, scroll=ft.ScrollMode.AUTO),
            width=400,
            border=ft.border.all(1, ft.colors.BLUE_GREY_800),
            border_radius=12,
            padding=15,
            bgcolor=ft.colors.BLUE_GREY_900
        )
    
    # 引用存储
    refresh_btn_ref = ft.Ref[ft.ElevatedButton]()
    refresh_plugin_btn_ref = ft.Ref[ft.ElevatedButton]()
    current_file_ref = ft.Ref[ft.Text]()
    run_analysis_btn_ref = ft.Ref[ft.ElevatedButton]()
    
    # ==================== 日志文件夹相关方法 ====================
    def _pick_log_folder(self, e):
        """打开日志文件夹选择对话框"""
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.path:
                self.selected_folder = Path(e.path)
                self.folder_path_text.value = str(self.selected_folder)
                self.folder_path_text.color = ft.colors.GREEN_400
                self._load_log_files()
                self.refresh_btn_ref.current.disabled = False
                self.refresh_btn_ref.current.update()
                self.status_text.value = f"已加载日志文件夹: {self.selected_folder}"
                self.status_text.color = ft.colors.GREY_400
                self.status_text.update()
        
        file_picker = ft.FilePicker(on_result=on_dialog_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.get_directory_path()
    
    def _load_log_files(self):
        """加载日志文件列表"""
        if not self.selected_folder:
            return
            
        # 支持的日志扩展名
        log_extensions = {'.log', '.txt', '.out', '.err', '.debug'}
        
        self.log_files = [
            f for f in self.selected_folder.iterdir() 
            if f.is_file() and f.suffix.lower() in log_extensions
        ]
        
        # 清空之前的复选框引用
        self.log_checkboxes.clear()
        self.select_all_state = False
        self.select_all_btn.text = "全选"
        self.select_all_btn.icon = ft.icons.CHECK_BOX
        
        # 更新列表视图
        self.log_list_view.controls.clear()
        
        for log_file in sorted(self.log_files):
            # 创建可选择的项目
            checkbox = ft.Checkbox(
                label=log_file.name,
                value=False,
                on_change=lambda e, f=log_file: self._on_log_checkbox_change(e, f)
            )
            self.log_checkboxes.append(checkbox)
            
            log_item = ft.Container(
                content=ft.Row([
                    checkbox,
                    ft.IconButton(
                        icon=ft.icons.VISIBILITY,
                        tooltip="查看此日志",
                        icon_size=18,
                        on_click=lambda e, f=log_file: self._view_single_log(f)
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.BLUE_GREY_800)),
                padding=5
            )
            self.log_list_view.controls.append(log_item)
        
        # 启用全选按钮
        self.select_all_btn.disabled = len(self.log_files) == 0
        
        self.log_list_view.update()
        self.select_all_btn.update()
        self.status_text.value = f"找到 {len(self.log_files)} 个日志文件"
        self.status_text.update()
    
    def _toggle_select_all(self, e):
        """全选/取消全选所有日志"""
        self.select_all_state = not self.select_all_state
        
        # 更新按钮文本和图标
        if self.select_all_state:
            self.select_all_btn.text = "取消全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX_OUTLINE_BLANK
            self.selected_logs = self.log_files.copy()
        else:
            self.select_all_btn.text = "全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX
            self.selected_logs.clear()
        
        # 更新所有复选框状态
        for checkbox in self.log_checkboxes:
            checkbox.value = self.select_all_state
        
        # 更新UI
        count = len(self.selected_logs)
        self.selected_logs_text.value = f"已选择: {count} 个文件"
        
        # 启用/禁用分析插件选择和执行按钮
        self.method_dropdown.disabled = count == 0
        self.run_analysis_btn_ref.current.disabled = count == 0
        
        # 如果有选择且已选插件，显示参数区域
        if count > 0 and self.method_dropdown.value:
            self._show_plugin_params(self.method_dropdown.value)
        elif count == 0:
            if self.params_container_ref.current:
                self.params_container_ref.current.visible = False
                self.params_container_ref.current.update()
        
        self.log_list_view.update()
        self.select_all_btn.update()
        self.selected_logs_text.update()
        self.method_dropdown.update()
        self.run_analysis_btn_ref.current.update()
        
        self.status_text.value = f"已{'全选' if self.select_all_state else '取消全选'} {len(self.log_files)} 个文件"
        self.status_text.update()
    
    def _on_log_checkbox_change(self, e, file_path: Path):
        """处理日志文件多选"""
        if e.control.value:
            if file_path not in self.selected_logs:
                self.selected_logs.append(file_path)
        else:
            if file_path in self.selected_logs:
                self.selected_logs.remove(file_path)
        
        # 更新全选按钮状态
        if len(self.selected_logs) == len(self.log_files) and len(self.log_files) > 0:
            self.select_all_state = True
            self.select_all_btn.text = "取消全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX_OUTLINE_BLANK
        else:
            self.select_all_state = False
            self.select_all_btn.text = "全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX
        
        # 更新选择计数
        count = len(self.selected_logs)
        self.selected_logs_text.value = f"已选择: {count} 个文件"
        
        # 启用/禁用分析插件选择和执行按钮
        self.method_dropdown.disabled = count == 0
        self.run_analysis_btn_ref.current.disabled = count == 0
        
        # 如果有选择且已选插件，显示参数区域
        if count > 0 and self.method_dropdown.value:
            self._show_plugin_params(self.method_dropdown.value)
        
        self.selected_logs_text.update()
        self.method_dropdown.update()
        self.run_analysis_btn_ref.current.update()
        self.select_all_btn.update()
        
        if self.params_container_ref.current:
            self.params_container_ref.current.visible = count > 0
            self.params_container_ref.current.update()
    
    # ==================== 插件相关方法（修复后） ====================
    def _pick_plugin_folder(self, e):
        """打开插件文件夹选择对话框"""
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.path:
                self.plugin_folder = Path(e.path)
                self.plugin_folder_text.value = str(self.plugin_folder)
                self.plugin_folder_text.color = ft.colors.PURPLE_400
                self.refresh_plugin_btn_ref.current.disabled = False
                self.refresh_plugin_btn_ref.current.update()
                self._load_external_plugins()  # 自动加载插件
                self.status_text.value = f"已选择插件文件夹: {self.plugin_folder}"
                self.status_text.color = ft.colors.GREY_400
                self.status_text.update()
        
        file_picker = ft.FilePicker(on_result=on_dialog_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.get_directory_path()
    
    def _pick_plugin_file(self, e):
        """打开单个插件文件选择对话框"""
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                file_path = Path(e.files[0].path)
                if file_path.suffix == '.py':
                    self._load_single_plugin_file(file_path)
                else:
                    self.status_text.value = "请选择Python文件(.py)"
                    self.status_text.color = ft.colors.RED_400
                    self.status_text.update()
        
        file_picker = ft.FilePicker(on_result=on_dialog_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.pick_files(
            dialog_title="选择插件文件",
            allowed_extensions=["py"],
            file_type=ft.FilePickerFileType.CUSTOM
        )

    def _load_single_plugin_file(self, file_path: Path):
        """加载单个插件文件"""
        try:
            unique_name = f"{file_path.stem}_{uuid.uuid4().hex[:8]}"
            spec = importlib.util.spec_from_file_location(unique_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[unique_name] = module
            spec.loader.exec_module(module)
            
            loaded_count = 0
            
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # 跳过抽象类和基类本身
                if inspect.isabstract(obj):
                    continue
                
                # 检查是否是插件：必须有 name, description 属性和 analyze, get_parameters 方法
                has_name = hasattr(obj, 'name') and isinstance(obj.name, property)
                has_desc = hasattr(obj, 'description') and isinstance(obj.description, property)
                has_analyze = hasattr(obj, 'analyze') and callable(getattr(obj, 'analyze'))
                has_params = hasattr(obj, 'get_parameters') and callable(getattr(obj, 'get_parameters'))
                
                # 或者检查是否继承自 LogAnalysisPlugin（兼容两种方式）
                is_subclass = False
                try:
                    # 获取模块中导入的 LogAnalysisPlugin
                    module_base = getattr(module, 'LogAnalysisPlugin', None)
                    if module_base and obj is not module_base:
                        # 检查是否是子类
                        if issubclass(obj, module_base):
                            is_subclass = True
                except:
                    pass
                
                # 检查是否继承自主程序的基类
                if not is_subclass:
                    try:
                        if issubclass(obj, LogAnalysisPlugin) and obj is not LogAnalysisPlugin:
                            is_subclass = True
                    except:
                        pass
                
                # 如果是有效的插件类
                if (has_name and has_desc and has_analyze and has_params) or is_subclass:
                    try:
                        plugin = obj()
                        # 验证实例是否有效
                        if not hasattr(plugin, 'name') or not hasattr(plugin, 'analyze'):
                            continue
                        
                        # 检查名称是否已存在
                        if plugin.name in self.all_plugins:
                            self.status_text.value = f"警告: 插件 '{plugin.name}' 已存在，将被覆盖"
                            self.status_text.color = ft.colors.ORANGE_400
                            self.status_text.update()
                        
                        self.external_plugins[plugin.name] = plugin
                        loaded_count += 1
                        self.status_text.value = f"已加载插件: {plugin.name} (来自 {file_path.name})"
                        self.status_text.color = ft.colors.GREEN_400
                        self.status_text.update()
                    except Exception as e:
                        print(f"实例化插件失败: {name}, 错误: {e}")
            
            if loaded_count == 0:
                self.status_text.value = f"文件 {file_path.name} 中未找到有效的插件类（需要包含 name, description, get_parameters, analyze）"
                self.status_text.color = ft.colors.ORANGE_400
                self.status_text.update()
            else:
                self.all_plugins = {**self.builtin_plugins, **self.external_plugins}
                self._update_plugin_dropdown()
                
        except Exception as ex:
            self.status_text.value = f"加载插件文件 {file_path.name} 失败: {str(ex)}"
            self.status_text.color = ft.colors.RED_400
            self.status_text.update()
            import traceback
            traceback.print_exc()  # 打印详细错误到控制台

    def _load_external_plugins(self):
        """加载外部插件文件"""
        if not self.plugin_folder:
            return
        
        self.external_plugins.clear()
        plugin_files = [f for f in self.plugin_folder.iterdir() if f.suffix == '.py' and f.is_file()]
        
        loaded_plugins = []
        failed_files = []
        
        for plugin_file in plugin_files:
            try:
                # 使用唯一模块名避免冲突
                unique_name = f"{plugin_file.stem}_{uuid.uuid4().hex[:8]}"
                spec = importlib.util.spec_from_file_location(unique_name, plugin_file)
                module = importlib.util.module_from_spec(spec)
                sys.modules[unique_name] = module
                spec.loader.exec_module(module)
                
                # 查找继承自LogAnalysisPlugin的类
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, LogAnalysisPlugin) and 
                        obj is not LogAnalysisPlugin and 
                        not inspect.isabstract(obj)):
                        # 实例化插件
                        plugin = obj()
                        # 检查名称冲突
                        if plugin.name in self.builtin_plugins:
                            self.status_text.value = f"警告: 插件 '{plugin.name}' 与内置插件重名，已跳过"
                            self.status_text.color = ft.colors.ORANGE_400
                            self.status_text.update()
                            continue
                        self.external_plugins[plugin.name] = plugin
                        loaded_plugins.append(plugin.name)
                        
            except Exception as ex:
                failed_files.append(f"{plugin_file.name}: {str(ex)}")
        
        # 更新所有插件列表并刷新下拉框（修复：确保下拉框刷新）
        self.all_plugins = {**self.builtin_plugins, **self.external_plugins}
        self._update_plugin_dropdown()
        
        # 汇总状态
        if loaded_plugins:
            self.status_text.value = f"已加载 {len(loaded_plugins)} 个插件: {', '.join(loaded_plugins)}"
            self.status_text.color = ft.colors.GREEN_400
        elif failed_files:
            self.status_text.value = f"加载失败: {len(failed_files)} 个文件"
            self.status_text.color = ft.colors.RED_400
        else:
            self.status_text.value = "插件文件夹中没有找到有效插件"
            self.status_text.color = ft.colors.GREY_400
        self.status_text.update()
    
    def _refresh_plugins(self, e):
        """刷新插件列表"""
        if self.plugin_folder:
            self._load_external_plugins()
            self.status_text.value = "插件列表已刷新"
            self.status_text.color = ft.colors.GREY_400
            self.status_text.update()
    
    def _update_plugin_dropdown(self):
        """更新插件下拉选择框（修复：添加空值处理和当前选择保持）"""
        # 保存当前选择
        current_selection = self.method_dropdown.value
        
        # 更新选项
        self.method_dropdown.options = [ft.dropdown.Option(name) for name in self.all_plugins.keys()]
        
        # 如果当前选择仍然有效，保持选择并更新参数面板
        if current_selection and current_selection in self.all_plugins:
            self.method_dropdown.value = current_selection
            # 更新描述和参数
            self._update_plugin_description(current_selection)
            if len(self.selected_logs) > 0:
                self._show_plugin_params(current_selection)
        else:
            # 当前选择无效，清空
            self.method_dropdown.value = None
            self.plugin_desc_text.value = ""
            self.plugin_desc_text.update()
            if self.params_container_ref.current:
                self.params_container_ref.current.visible = False
                self.params_container_ref.current.update()
        
        self.method_dropdown.update()
    
    def _update_plugin_description(self, plugin_name: str):
        """更新插件描述文本"""
        plugin = self.all_plugins.get(plugin_name)
        if plugin:
            self.plugin_desc_text.value = f"插件描述: {plugin.description}"
        else:
            self.plugin_desc_text.value = ""
        self.plugin_desc_text.update()
    
    def _on_method_change(self, e):
        """选择插件时更新参数面板和描述"""
        plugin_name = self.method_dropdown.value
        if not plugin_name or plugin_name not in self.all_plugins:
            # 清空参数区域
            self.method_params.controls.clear()
            self.plugin_desc_text.value = ""
            if self.params_container_ref.current:
                self.params_container_ref.current.visible = False
                self.params_container_ref.current.update()
            self.plugin_desc_text.update()
            self.method_params.update()
            return
        
        # 更新描述
        self._update_plugin_description(plugin_name)
        
        # 显示插件参数
        if len(self.selected_logs) > 0:
            self._show_plugin_params(plugin_name)
    
    def _show_plugin_params(self, plugin_name: str):
        """根据插件生成参数输入控件"""
        self.method_params.controls.clear()
        plugin = self.all_plugins.get(plugin_name)
        
        if not plugin:
            return
        
        # 获取插件参数配置
        params_config = plugin.get_parameters()
        
        for param in params_config:
            param_name = param["name"]
            param_type = param["type"]
            param_label = param["label"]
            param_default = param["default"]
            
            # 根据参数类型创建不同的输入控件
            if param_type == "str":
                control = ft.TextField(
                    label=param_label,
                    value=str(param_default),
                    width=280,
                    data=param_name  # 存储参数名
                )
            elif param_type == "int":
                control = ft.TextField(
                    label=param_label,
                    value=str(param_default),
                    width=280,
                    input_filter=ft.InputFilter(allow=True, regex_string=r"^\d+$"),
                    data=param_name
                )
            elif param_type == "float":
                control = ft.TextField(
                    label=param_label,
                    value=str(param_default),
                    width=280,
                    input_filter=ft.InputFilter(allow=True, regex_string=r"^\d+\.?\d*$"),
                    data=param_name
                )
            elif param_type == "bool":
                control = ft.Checkbox(
                    label=param_label,
                    value=param_default,
                    data=param_name
                )
            elif param_type == "choice":
                control = ft.Dropdown(
                    label=param_label,
                    options=[ft.dropdown.Option(opt) for opt in param["options"]],
                    value=param_default,
                    width=280,
                    data=param_name
                )
            else:
                # 默认字符串类型
                control = ft.TextField(
                    label=param_label,
                    value=str(param_default),
                    width=280,
                    data=param_name
                )
            
            self.method_params.controls.append(control)
        
        # 显示参数容器
        if self.params_container_ref.current:
            self.params_container_ref.current.visible = True
            self.params_container_ref.current.update()
        self.method_params.update()
    
    # ==================== 日志查看和操作方法 ====================
    def _view_single_log(self, file_path: Path):
        """查看单个日志文件内容"""
        try:
            # 限制读取大小，避免大文件卡顿
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if len(content) > 100000:  # 限制显示100KB
                content = content[:100000] + "\n\n... [文件过大，仅显示前100KB]"
            
            self.log_content.value = content
            self.current_file_ref.current.value = file_path.name
            self.current_file_ref.current.color = ft.colors.GREEN_400
            
        except Exception as ex:
            self.log_content.value = f"读取文件失败: {str(ex)}"
            self.current_file_ref.current.value = "错误"
            self.current_file_ref.current.color = ft.colors.RED_400
        
        self.log_content.update()
        self.current_file_ref.current.update()
        self.status_text.value = f"正在查看: {file_path.name}"
        self.status_text.color = ft.colors.GREY_400
        self.status_text.update()
    
    def _clear_single_selection(self, e):
        """清除单日志选择"""
        self.log_content.value = ""
        self.current_file_ref.current.value = "无"
        self.current_file_ref.current.color = ft.colors.BLUE_400
        self.log_content.update()
        self.current_file_ref.current.update()
    
    def _copy_content(self, e):
        """复制当前日志内容到剪贴板"""
        if self.log_content.value:
            e.page.set_clipboard(self.log_content.value)
            self.status_text.value = "内容已复制到剪贴板"
            self.status_text.color = ft.colors.GREEN_400
            self.status_text.update()
    
    def _refresh_logs(self, e):
        """刷新日志列表"""
        self._load_log_files()
        self.status_text.value = "日志列表已刷新"
        self.status_text.color = ft.colors.GREY_400
        self.status_text.update()
    
    # ==================== 分析执行和结果处理 ====================
    def _run_analysis(self, e):
        """执行插件分析"""
        if not self.selected_logs or not self.method_dropdown.value:
            return
        
        plugin_name = self.method_dropdown.value
        plugin = self.all_plugins.get(plugin_name)
        
        if not plugin:
            self.status_text.value = f"插件 {plugin_name} 未找到"
            self.status_text.color = ft.colors.RED_400
            self.status_text.update()
            return
        
        self.status_text.value = f"正在执行 {plugin_name}..."
        self.status_text.color = ft.colors.BLUE_400
        self.status_text.update()
        
        try:
            # 收集参数
            params = self._collect_plugin_params()
            
            # 执行插件分析
            result = plugin.analyze(self.selected_logs, params)
            
            # 显示结果
            self.analysis_result.value = result
            self.analysis_result.update()
            self.status_text.value = f"{plugin_name} 执行完成"
            self.status_text.color = ft.colors.GREEN_400
            
        except Exception as ex:
            self.analysis_result.value = f"分析执行失败: {str(ex)}"
            self.analysis_result.update()
            self.status_text.value = f"{plugin_name} 执行出错"
            self.status_text.color = ft.colors.RED_400
        
        self.status_text.update()
    
    def _collect_plugin_params(self) -> Dict[str, Any]:
        """收集插件参数（修复：添加异常处理）"""
        params = {}
        
        if not self.method_dropdown.value:
            return params
        
        plugin = self.all_plugins.get(self.method_dropdown.value)
        if not plugin:
            return params
        
        # 获取参数配置用于类型转换
        params_config = {p["name"]: p for p in plugin.get_parameters()}
        
        for control in self.method_params.controls:
            param_name = control.data
            if not param_name:
                continue
            
            # 获取参数配置
            param_config = params_config.get(param_name)
            if not param_config:
                continue  # 跳过未定义的参数
            
            param_type = param_config["type"]
            
            # 根据控件类型获取值并转换类型
            if isinstance(control, ft.TextField):
                if param_type == "int":
                    try:
                        params[param_name] = int(control.value) if control.value else 0
                    except ValueError:
                        params[param_name] = 0
                elif param_type == "float":
                    try:
                        params[param_name] = float(control.value) if control.value else 0.0
                    except ValueError:
                        params[param_name] = 0.0
                else:
                    params[param_name] = control.value
            
            elif isinstance(control, ft.Checkbox):
                params[param_name] = control.value
            
            elif isinstance(control, ft.Dropdown):
                params[param_name] = control.value
        
        return params
    
    def _export_result(self, e):
        """导出分析结果"""
        if not self.analysis_result.value:
            return
            
        def on_save_result(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    Path(e.path).write_text(self.analysis_result.value, encoding='utf-8')
                    self.status_text.value = f"结果已保存到: {e.path}"
                    self.status_text.color = ft.colors.GREEN_400
                except Exception as ex:
                    self.status_text.value = f"保存失败: {str(ex)}"
                    self.status_text.color = ft.colors.RED_400
                self.status_text.update()
        
        file_picker = ft.FilePicker(on_result=on_save_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.save_file(file_name="analysis_result.txt")
    
    def _clear_result(self, e):
        """清空分析结果"""
        self.analysis_result.value = ""
        self.analysis_result.update()
        self.status_text.value = "分析结果已清空"
        self.status_text.color = ft.colors.GREY_400
        self.status_text.update()


def main():
    app = LogAnalyzerApp()
    ft.app(target=app.main)


if __name__ == "__main__":
    main()