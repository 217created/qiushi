from abc import ABC, abstractmethod
from rich.console import Console


class BaseRenderer(ABC):
    """渲染器基类 — 接收纯数据字典，执行一次性渲染"""

    def __init__(self, console: Console):
        self.console = console

    @abstractmethod
    def render(self, data: dict) -> None:
        ...
