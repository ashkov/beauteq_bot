from abc import ABC, abstractmethod
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)


class BaseView(ABC):
    """Базовый класс для всех View (как в Django)"""

    @abstractmethod
    def get_name(self) -> str:
        """Возвращает имя view (аналог name в urls.py)"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Возвращает описание view для LLM"""
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Возвращает параметры view"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Выполняет view и возвращает сырые данные (аналог get() в Django)"""
        pass

    @abstractmethod
    def render(self, result: Any, **kwargs) -> str:
        """Преобразует сырые данные в HTML/текст для пользователя (аналог template)"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует view в dict для LLM"""
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "parameters": self.get_parameters()
        }