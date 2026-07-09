"""
主应用 UI 与业务逻辑
负责界面布局、用户交互、调用插件管理器
"""
import flet as ft
from pathlib import Path
from typing import List, Optional

from plugins import PluginManager, LogAnalysisPlugin


class LogAnalyzerApp:
    def __init__(self):
        self.selected_folder: Optional[Path] = None
        self.log_files: List[Path] = []
        self.selected_logs: List[Path] = []
        self.select_all_state: bool = False
        self.log_checkboxes: List[ft.Checkbox] = []

        # 插件管理器（新抽取的）
        self.plugin_manager = PluginManager()

    def main(self, page: ft.Page):
        page.title = "日志分析工具"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window_width = 1400
        page.window_height = 800

        # 状态栏
        self.status_text = ft.Text("就绪", size=12, color=ft.colors.GREY_400)

        # 日志相关
        self.folder_path_text = ft.Text("未选择文件夹", size=14, color=ft.colors.GREY_400)
        self.log_list_view = ft.ListView(expand=True, spacing=2, auto_scroll=False)
        self.select_all_btn = ft.ElevatedButton(
            "全选", icon=ft.icons.CHECK_BOX, on_click=self._toggle_select_all,
            disabled=True, width=120
        )

        # 单日志查看
        self.log_content = ft.TextField(
            multiline=True, read_only=True, expand=True, text_size=12,
            min_lines=20, border_color=ft.colors.BLUE_GREY_700, bgcolor=ft.colors.BLACK87
        )

        # 批量分析
        self.selected_logs_text = ft.Text("已选择: 0 个文件", size=14)
        self.analysis_result = ft.TextField(
            multiline=True, read_only=True, expand=True, text_size=12,
            min_lines=15, border_color=ft.colors.BLUE_GREY_700, bgcolor=ft.colors.BLACK87
        )

        # 插件相关
        self.plugin_folder_text = ft.Text("未选择插件文件夹", size=14, color=ft.colors.GREY_400)
        self.plugin_desc_text = ft.Text("", size=12, color=ft.colors.BLUE_400, italic=True)
        self.method_params = ft.Column([])
        self.params_container_ref = ft.Ref[ft.Container]()

        self.method_dropdown = ft.Dropdown(
            label="选择分析方法（插件）",
            options=[ft.dropdown.Option(name) for name in self.plugin_manager.plugin_names],
            width=300, disabled=True, on_change=self._on_method_change
        )

        # 构建UI
        page.add(
            ft.Column([
                ft.Text("🔍 日志分析工具（插件版）", size=28, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([
                    self._build_left_panel(),
                    self._build_center_panel(),
                    self._build_right_panel(),
                ], expand=True, spacing=20),
                ft.Divider(),
                self.status_text,
            ], expand=True)
        )

    # ==================== UI 构建 ====================
    refresh_btn_ref = ft.Ref[ft.ElevatedButton]()
    refresh_plugin_btn_ref = ft.Ref[ft.ElevatedButton]()
    current_file_ref = ft.Ref[ft.Text]()
    run_analysis_btn_ref = ft.Ref[ft.ElevatedButton]()

    def _build_left_panel(self) -> ft.Container:
        """构建左侧面板：文件夹选择、插件文件夹选择和日志列表"""
        return ft.Container(
            content=ft.Column([
                ft.Text("📁 数据源与插件", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.ElevatedButton(
                        "选择日志文件夹", icon=ft.icons.FOLDER_OPEN,
                        on_click=self._pick_log_folder,
                        style=ft.ButtonStyle(
                            color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                            bgcolor={ft.MaterialState.DEFAULT: ft.colors.BLUE_600}
                        )
                    ),
                    self.folder_path_text,
                ], spacing=10),
                ft.Row([
                    ft.ElevatedButton(
                        "选择插件文件夹", icon=ft.icons.EXTENSION,
                        on_click=self._pick_plugin_folder,
                        style=ft.ButtonStyle(
                            color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                            bgcolor={ft.MaterialState.DEFAULT: ft.colors.PURPLE_600}
                        )
                    ),
                    self.plugin_folder_text,
                ], spacing=10),
                ft.Row([
                    ft.ElevatedButton(
                        "加载单个插件文件", icon=ft.icons.FILE_OPEN,
                        on_click=self._pick_plugin_file,
                        style=ft.ButtonStyle(
                            color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                            bgcolor={ft.MaterialState.DEFAULT: ft.colors.ORANGE_600}
                        )
                    ),
                    ft.Text("支持直接选择.py文件加载", size=12, color=ft.colors.GREY_400),
                ], spacing=10),
                ft.Divider(),
                ft.Row([
                    ft.Text("日志文件列表", size=14, weight=ft.FontWeight.W_500, expand=True),
                    self.select_all_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(
                    content=self.log_list_view,
                    border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                    border_radius=8, padding=10, expand=True, bgcolor=ft.colors.BLACK12
                ),
                ft.Row([
                    ft.ElevatedButton("刷新日志列表", icon=ft.icons.REFRESH,
                                      on_click=self._refresh_logs, disabled=True,
                                      ref=self.refresh_btn_ref),
                    ft.ElevatedButton("刷新插件列表", icon=ft.icons.UPDATE,
                                      on_click=self._refresh_plugins, disabled=True,
                                      ref=self.refresh_plugin_btn_ref),
                ]),
            ], expand=True),
            width=350, border=ft.border.all(1, ft.colors.BLUE_GREY_800),
            border_radius=12, padding=15, bgcolor=ft.colors.BLUE_GREY_900
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
                ft.Container(content=self.log_content, border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                             border_radius=8, expand=True, padding=10),
                ft.Row([
                    ft.ElevatedButton("清除选择", icon=ft.icons.CLEAR, on_click=self._clear_single_selection),
                    ft.ElevatedButton("复制内容", icon=ft.icons.COPY, on_click=self._copy_content),
                ], alignment=ft.MainAxisAlignment.END),
            ], expand=True),
            expand=True, border=ft.border.all(1, ft.colors.BLUE_GREY_800),
            border_radius=12, padding=15, bgcolor=ft.colors.BLUE_GREY_900
        )

    def _build_right_panel(self) -> ft.Container:
        """构建右侧面板：多选分析和插件选择"""
        return ft.Container(
            content=ft.Column([
                ft.Text("📊 批量分析（插件版）", size=16, weight=ft.FontWeight.BOLD),
                self.selected_logs_text,
                ft.Container(
                    content=ft.Column([
                        ft.Text("分析插件", size=14, weight=ft.FontWeight.W_500),
                        self.method_dropdown,
                        self.plugin_desc_text,
                        ft.Container(
                            content=self.method_params,
                            border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                            border_radius=8, padding=10, visible=False,
                            ref=self.params_container_ref
                        ),
                        ft.ElevatedButton(
                            "执行分析", icon=ft.icons.PLAY_ARROW, on_click=self._run_analysis,
                            disabled=True, width=300,
                            style=ft.ButtonStyle(
                                color={ft.MaterialState.DEFAULT: ft.colors.WHITE},
                                bgcolor={ft.MaterialState.DEFAULT: ft.colors.GREEN_600}
                            ),
                            ref=self.run_analysis_btn_ref
                        ),
                    ]),
                    padding=10, bgcolor=ft.colors.BLACK12, border_radius=8
                ),
                ft.Divider(),
                ft.Text("分析结果", size=14, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=self.analysis_result,
                    border=ft.border.all(1, ft.colors.BLUE_GREY_700),
                    border_radius=8, expand=True, padding=10
                ),
                ft.Row([
                    ft.ElevatedButton("导出结果", icon=ft.icons.DOWNLOAD, on_click=self._export_result),
                    ft.ElevatedButton("清空结果", icon=ft.icons.DELETE, on_click=self._clear_result),
                ], alignment=ft.MainAxisAlignment.END),
            ], expand=True, scroll=ft.ScrollMode.AUTO),
            width=400, border=ft.border.all(1, ft.colors.BLUE_GREY_800),
            border_radius=12, padding=15, bgcolor=ft.colors.BLUE_GREY_900
        )

    # ==================== 日志操作 ====================
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
                self._set_status(f"已加载日志文件夹: {self.selected_folder}")

        file_picker = ft.FilePicker(on_result=on_dialog_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.get_directory_path()

    def _load_log_files(self):
        """加载日志文件列表"""
        if not self.selected_folder:
            return
        log_extensions = {'.log', '.txt', '.out', '.err', '.debug'}
        self.log_files = [
            f for f in self.selected_folder.iterdir()
            if f.is_file() and f.suffix.lower() in log_extensions
        ]
        self.log_checkboxes.clear()
        self.select_all_state = False
        self.select_all_btn.text = "全选"
        self.select_all_btn.icon = ft.icons.CHECK_BOX
        self.log_list_view.controls.clear()

        for log_file in sorted(self.log_files):
            checkbox = ft.Checkbox(
                label=log_file.name, value=False,
                on_change=lambda e, f=log_file: self._on_log_checkbox_change(e, f)
            )
            self.log_checkboxes.append(checkbox)
            self.log_list_view.controls.append(
                ft.Container(
                    content=ft.Row([
                        checkbox,
                        ft.IconButton(
                            icon=ft.icons.VISIBILITY, tooltip="查看此日志",
                            icon_size=18, on_click=lambda e, f=log_file: self._view_single_log(f)
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.BLUE_GREY_800)),
                    padding=5
                )
            )

        self.select_all_btn.disabled = len(self.log_files) == 0
        self.log_list_view.update()
        self.select_all_btn.update()
        self._set_status(f"找到 {len(self.log_files)} 个日志文件")

    def _toggle_select_all(self, e):
        """全选/取消全选所有日志"""
        self.select_all_state = not self.select_all_state
        if self.select_all_state:
            self.select_all_btn.text = "取消全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX_OUTLINE_BLANK
            self.selected_logs = self.log_files.copy()
        else:
            self.select_all_btn.text = "全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX
            self.selected_logs.clear()

        for cb in self.log_checkboxes:
            cb.value = self.select_all_state

        count = len(self.selected_logs)
        self.selected_logs_text.value = f"已选择: {count} 个文件"
        self.method_dropdown.disabled = count == 0
        self.run_analysis_btn_ref.current.disabled = count == 0

        if count > 0 and self.method_dropdown.value:
            self._show_plugin_params(self.method_dropdown.value)
        elif count == 0 and self.params_container_ref.current:
            self.params_container_ref.current.visible = False
            self.params_container_ref.current.update()

        self.log_list_view.update()
        self.select_all_btn.update()
        self.selected_logs_text.update()
        self.method_dropdown.update()
        self.run_analysis_btn_ref.current.update()
        self._set_status(f"已{'全选' if self.select_all_state else '取消全选'} {len(self.log_files)} 个文件")

    def _on_log_checkbox_change(self, e, file_path: Path):
        """处理日志文件多选"""
        if e.control.value:
            if file_path not in self.selected_logs:
                self.selected_logs.append(file_path)
        else:
            if file_path in self.selected_logs:
                self.selected_logs.remove(file_path)

        if len(self.selected_logs) == len(self.log_files) and len(self.log_files) > 0:
            self.select_all_state = True
            self.select_all_btn.text = "取消全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX_OUTLINE_BLANK
        else:
            self.select_all_state = False
            self.select_all_btn.text = "全选"
            self.select_all_btn.icon = ft.icons.CHECK_BOX

        count = len(self.selected_logs)
        self.selected_logs_text.value = f"已选择: {count} 个文件"
        self.method_dropdown.disabled = count == 0
        self.run_analysis_btn_ref.current.disabled = count == 0

        if count > 0 and self.method_dropdown.value:
            self._show_plugin_params(self.method_dropdown.value)

        self.selected_logs_text.update()
        self.method_dropdown.update()
        self.run_analysis_btn_ref.current.update()
        self.select_all_btn.update()
        if self.params_container_ref.current:
            self.params_container_ref.current.visible = count > 0
            self.params_container_ref.current.update()

    def _view_single_log(self, file_path: Path):
        """查看单个日志文件内容"""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if len(content) > 100000:
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
        self._set_status(f"正在查看: {file_path.name}")

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
            self._set_status("内容已复制到剪贴板", ft.colors.GREEN_400)

    def _refresh_logs(self, e):
        """刷新日志列表"""
        self._load_log_files()
        self._set_status("日志列表已刷新")

    # ==================== 插件操作 ====================
    def _pick_plugin_folder(self, e):
        """打开插件文件夹选择对话框"""
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.path:
                folder = Path(e.path)
                self.plugin_manager.set_plugin_folder(folder)
                self.plugin_folder_text.value = str(folder)
                self.plugin_folder_text.color = ft.colors.PURPLE_400
                self.refresh_plugin_btn_ref.current.disabled = False
                self.refresh_plugin_btn_ref.current.update()
                self._load_external_plugins()
                self._set_status(f"已选择插件文件夹: {folder}")

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
                    success, msg = self.plugin_manager.load_from_file(file_path)
                    if success:
                        self._update_plugin_dropdown()
                        self._set_status(msg, ft.colors.GREEN_400)
                    else:
                        self._set_status(msg, ft.colors.ORANGE_400)
                else:
                    self._set_status("请选择Python文件(.py)", ft.colors.RED_400)

        file_picker = ft.FilePicker(on_result=on_dialog_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.pick_files(
            dialog_title="选择插件文件", allowed_extensions=["py"],
            file_type=ft.FilePickerFileType.CUSTOM
        )

    def _load_external_plugins(self):
        """从文件夹加载插件（通过 PluginManager）"""
        loaded, failed = self.plugin_manager.load_from_folder()
        self._update_plugin_dropdown()

        if loaded:
            self._set_status(f"已加载 {len(loaded)} 个插件: {', '.join(loaded)}", ft.colors.GREEN_400)
        elif failed:
            self._set_status(f"加载失败: {len(failed)} 个文件", ft.colors.RED_400)
        else:
            self._set_status("插件文件夹中没有找到有效插件")

    def _refresh_plugins(self, e):
        """刷新插件列表"""
        if self.plugin_manager.plugin_folder:
            self._load_external_plugins()
            self._set_status("插件列表已刷新")

    def _update_plugin_dropdown(self):
        """更新插件下拉选择框"""
        current = self.method_dropdown.value
        self.method_dropdown.options = [
            ft.dropdown.Option(name) for name in self.plugin_manager.plugin_names
        ]
        if current and self.plugin_manager.has_plugin(current):
            self.method_dropdown.value = current
            self._update_plugin_description(current)
            if len(self.selected_logs) > 0:
                self._show_plugin_params(current)
        else:
            self.method_dropdown.value = None
            self.plugin_desc_text.value = ""
            self.plugin_desc_text.update()
            if self.params_container_ref.current:
                self.params_container_ref.current.visible = False
                self.params_container_ref.current.update()
        self.method_dropdown.update()

    def _update_plugin_description(self, plugin_name: str):
        """更新插件描述文本"""
        plugin = self.plugin_manager.get_plugin(plugin_name)
        self.plugin_desc_text.value = f"插件描述: {plugin.description}" if plugin else ""
        self.plugin_desc_text.update()

    def _on_method_change(self, e):
        """选择插件时更新参数面板和描述"""
        plugin_name = self.method_dropdown.value
        if not plugin_name or not self.plugin_manager.has_plugin(plugin_name):
            self.method_params.controls.clear()
            self.plugin_desc_text.value = ""
            if self.params_container_ref.current:
                self.params_container_ref.current.visible = False
                self.params_container_ref.current.update()
            self.plugin_desc_text.update()
            self.method_params.update()
            return

        self._update_plugin_description(plugin_name)
        if len(self.selected_logs) > 0:
            self._show_plugin_params(plugin_name)

    def _show_plugin_params(self, plugin_name: str):
        """根据插件生成参数输入控件"""
        self.method_params.controls.clear()
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return

        for param in plugin.get_parameters():
            p_name = param["name"]
            p_type = param["type"]
            p_label = param["label"]
            p_default = param["default"]

            if p_type == "str":
                ctrl = ft.TextField(label=p_label, value=str(p_default), width=280, data=p_name)
            elif p_type == "int":
                ctrl = ft.TextField(label=p_label, value=str(p_default), width=280,
                                    input_filter=ft.InputFilter(allow=True, regex_string=r"^\d+$"),
                                    data=p_name)
            elif p_type == "float":
                ctrl = ft.TextField(label=p_label, value=str(p_default), width=280,
                                    input_filter=ft.InputFilter(allow=True, regex_string=r"^\d+\.?\d*$"),
                                    data=p_name)
            elif p_type == "bool":
                ctrl = ft.Checkbox(label=p_label, value=p_default, data=p_name)
            elif p_type == "choice":
                ctrl = ft.Dropdown(label=p_label, width=280, data=p_name,
                                   options=[ft.dropdown.Option(opt) for opt in param["options"]],
                                   value=p_default)
            else:
                ctrl = ft.TextField(label=p_label, value=str(p_default), width=280, data=p_name)

            self.method_params.controls.append(ctrl)

        if self.params_container_ref.current:
            self.params_container_ref.current.visible = True
            self.params_container_ref.current.update()
        self.method_params.update()

    # ==================== 分析执行 ====================
    def _run_analysis(self, e):
        """执行插件分析"""
        if not self.selected_logs or not self.method_dropdown.value:
            return

        plugin_name = self.method_dropdown.value
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if not plugin:
            self._set_status(f"插件 {plugin_name} 未找到", ft.colors.RED_400)
            return

        self._set_status(f"正在执行 {plugin_name}...", ft.colors.BLUE_400)

        try:
            params = self._collect_plugin_params()
            result = plugin.analyze(self.selected_logs, params)
            self.analysis_result.value = result
            self.analysis_result.update()
            self._set_status(f"{plugin_name} 执行完成", ft.colors.GREEN_400)
        except Exception as ex:
            self.analysis_result.value = f"分析执行失败: {str(ex)}"
            self.analysis_result.update()
            self._set_status(f"{plugin_name} 执行出错", ft.colors.RED_400)

    def _collect_plugin_params(self) -> dict:
        """收集插件参数（修复：添加异常处理）"""
        params = {}
        if not self.method_dropdown.value:
            return params

        plugin = self.plugin_manager.get_plugin(self.method_dropdown.value)
        if not plugin:
            return params

        params_config = {p["name"]: p for p in plugin.get_parameters()}

        for control in self.method_params.controls:
            p_name = control.data
            if not p_name or p_name not in params_config:
                continue

            p_type = params_config[p_name]["type"]

            if isinstance(control, ft.TextField):
                if p_type == "int":
                    try:
                        params[p_name] = int(control.value) if control.value else 0
                    except ValueError:
                        params[p_name] = 0
                elif p_type == "float":
                    try:
                        params[p_name] = float(control.value) if control.value else 0.0
                    except ValueError:
                        params[p_name] = 0.0
                else:
                    params[p_name] = control.value
            elif isinstance(control, ft.Checkbox):
                params[p_name] = control.value
            elif isinstance(control, ft.Dropdown):
                params[p_name] = control.value

        return params

    def _export_result(self, e):
        """导出分析结果"""
        if not self.analysis_result.value:
            return

        def on_save_result(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    Path(e.path).write_text(self.analysis_result.value, encoding='utf-8')
                    self._set_status(f"结果已保存到: {e.path}", ft.colors.GREEN_400)
                except Exception as ex:
                    self._set_status(f"保存失败: {str(ex)}", ft.colors.RED_400)

        file_picker = ft.FilePicker(on_result=on_save_result)
        e.page.overlay.append(file_picker)
        e.page.update()
        file_picker.save_file(file_name="analysis_result.txt")

    def _clear_result(self, e):
        """清空分析结果"""
        self.analysis_result.value = ""
        self.analysis_result.update()
        self._set_status("分析结果已清空")

    # ==================== 辅助方法 ====================
    def _set_status(self, message: str, color=ft.colors.GREY_400):
        """统一设置状态栏"""
        self.status_text.value = message
        self.status_text.color = color
        self.status_text.update()
