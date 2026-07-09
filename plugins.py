"""
插件系统
负责插件接口定义、内置插件、插件加载与管理
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import importlib.util
import sys
import inspect
import uuid


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


# ==================== 内置插件 ====================
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


# ==================== 插件管理器 ====================
class PluginManager:
    """
    插件生命周期管理器
    负责加载、验证、管理所有插件（内置 + 外部）
    """

    def __init__(self):
        self.builtin_plugins: Dict[str, LogAnalysisPlugin] = {}
        self.external_plugins: Dict[str, LogAnalysisPlugin] = {}
        self.all_plugins: Dict[str, LogAnalysisPlugin] = {}
        self.plugin_folder: Optional[Path] = None
        self._load_builtin_plugins()

    # ---------- 属性访问 ----------
    @property
    def plugin_names(self) -> List[str]:
        """获取所有插件名称列表"""
        return list(self.all_plugins.keys())

    def get_plugin(self, name: str) -> Optional[LogAnalysisPlugin]:
        """根据名称获取插件实例"""
        return self.all_plugins.get(name)

    def has_plugin(self, name: str) -> bool:
        """检查是否存在指定插件"""
        return name in self.all_plugins

    # ---------- 内置插件加载 ----------
    def _load_builtin_plugins(self):
        """加载内置插件"""
        builtin_classes = [TimelineAnalysisPlugin, ErrorStatisticsPlugin]
        for cls in builtin_classes:
            plugin = cls()
            self.builtin_plugins[plugin.name] = plugin
        self._sync_all_plugins()

    # ---------- 外部插件加载（单文件） ----------
    def load_from_file(self, file_path: Path) -> Tuple[bool, str]:
        """
        从单个 .py 文件加载插件
        :return: (是否成功, 状态消息)
        """
        if not file_path.suffix == '.py':
            return False, f"{file_path.name} 不是 Python 文件"

        try:
            unique_name = f"{file_path.stem}_{uuid.uuid4().hex[:8]}"
            spec = importlib.util.spec_from_file_location(unique_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[unique_name] = module
            spec.loader.exec_module(module)

            loaded_names = []
            module_base = getattr(module, 'LogAnalysisPlugin', None)

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if not self._is_valid_plugin_class(obj, module, module_base):
                    continue

                plugin = self._try_instantiate_plugin(obj, file_path.name)
                if not plugin:
                    continue

                # 外部插件允许覆盖其他外部插件，但不覆盖内置
                if plugin.name in self.builtin_plugins:
                    return False, f"插件 '{plugin.name}' 与内置插件重名"

                self.external_plugins[plugin.name] = plugin
                loaded_names.append(plugin.name)

            self._sync_all_plugins()

            if not loaded_names:
                return False, f"{file_path.name} 中未找到有效插件类"
            return True, f"已加载插件: {', '.join(loaded_names)}"

        except Exception as ex:
            return False, f"加载失败: {str(ex)}"

    # ---------- 外部插件加载（文件夹） ----------
    def set_plugin_folder(self, folder_path: Path):
        """设置插件文件夹路径"""
        self.plugin_folder = folder_path

    def load_from_folder(self) -> Tuple[List[str], List[str]]:
        """
        从插件文件夹批量加载
        :return: (成功加载的插件名列表, 失败的文件信息列表)
        """
        if not self.plugin_folder:
            return [], ["未设置插件文件夹"]

        self.external_plugins.clear()
        plugin_files = [f for f in self.plugin_folder.iterdir()
                        if f.suffix == '.py' and f.is_file()]

        loaded = []
        failed = []

        for plugin_file in plugin_files:
            success, msg = self._load_one_file_internal(plugin_file)
            if success:
                loaded.extend(msg.replace("已加载插件: ", "").split(", "))
            else:
                failed.append(f"{plugin_file.name}: {msg}")

        self._sync_all_plugins()
        return loaded, failed

    def refresh_folder(self) -> Tuple[List[str], List[str]]:
        """刷新插件文件夹"""
        return self.load_from_folder()

    # ---------- 内部辅助方法 ----------
    def _load_one_file_internal(self, file_path: Path) -> Tuple[bool, str]:
        """内部使用的单文件加载（不清理已有外部插件，不触发 sync）"""
        try:
            unique_name = f"{file_path.stem}_{uuid.uuid4().hex[:8]}"
            spec = importlib.util.spec_from_file_location(unique_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[unique_name] = module
            spec.loader.exec_module(module)

            loaded_names = []
            module_base = getattr(module, 'LogAnalysisPlugin', None)

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if not self._is_valid_plugin_class(obj, module, module_base):
                    continue

                plugin = self._try_instantiate_plugin(obj, file_path.name)
                if not plugin:
                    continue

                if plugin.name in self.builtin_plugins:
                    return False, f"插件 '{plugin.name}' 与内置插件重名，已跳过"

                self.external_plugins[plugin.name] = plugin
                loaded_names.append(plugin.name)

            if not loaded_names:
                return False, f"未找到有效插件类"
            return True, f"已加载插件: {', '.join(loaded_names)}"

        except Exception as ex:
            return False, str(ex)

    def _sync_all_plugins(self):
        """同步 all_plugins 字典"""
        self.all_plugins = {**self.builtin_plugins, **self.external_plugins}

    def _is_valid_plugin_class(self, obj, module, module_base=None) -> bool:
        """插件类统一验证"""
        if inspect.isabstract(obj):
            return False

        # 检测1：继承自主程序基类
        try:
            if issubclass(obj, LogAnalysisPlugin) and obj is not LogAnalysisPlugin:
                return True
        except:
            pass

        # 检测2：继承自模块内部基类
        if module_base and obj is not module_base:
            try:
                if issubclass(obj, module_base):
                    return True
            except:
                pass

        # 检测3：鸭子类型
        has_name = hasattr(obj, 'name')
        has_desc = hasattr(obj, 'description')
        has_analyze = hasattr(obj, 'analyze') and callable(getattr(obj, 'analyze'))
        has_params = hasattr(obj, 'get_parameters') and callable(getattr(obj, 'get_parameters'))

        if has_name:
            attr = getattr(obj, 'name')
            has_name = isinstance(attr, property) or isinstance(attr, str)
        if has_desc:
            attr = getattr(obj, 'description')
            has_desc = isinstance(attr, property) or isinstance(attr, str)

        return has_name and has_desc and has_analyze and has_params

    def _try_instantiate_plugin(self, obj, source_name: str) -> Optional[LogAnalysisPlugin]:
        """安全实例化插件"""
        try:
            plugin = obj()
            if not hasattr(plugin, 'name') or not hasattr(plugin, 'analyze'):
                return None
            _ = plugin.name
            _ = plugin.description
            return plugin
        except Exception as e:
            print(f"实例化失败 [{source_name}]: {e}")
            return None
