from typing import Dict, List, Any
from views import MastersListView, ServicesListView, UserAppointmentsView, CreateAppointmentView
from database import Database
from base_view import BaseView


class ViewRouter:
    """Роутер для управления View (аналог urlpatterns в Django)"""

    def __init__(self, db: Database):
        self.db = db
        self.views: Dict[str, BaseView] = {}
        self._register_views()

    def _register_views(self):
        """Регистрирует все View (аналог urlpatterns)"""
        self.views = {
            "masters_list": MastersListView(self.db),
            "services_list": ServicesListView(self.db),
            "user_appointments": UserAppointmentsView(self.db),
            "create_appointment": CreateAppointmentView(self.db)
        }

    def get_available_views(self) -> List[Dict[str, Any]]:
        """Возвращает список View для LLM"""
        return [view.to_dict() for view in self.views.values()]

    def execute_view(self, view_name: str, parameters: Dict[str, Any]) -> Any:
        """Выполняет View по имени"""
        if view_name not in self.views:
            raise ValueError(f"View не найден: {view_name}")

        view = self.views[view_name]
        return view.execute(**parameters)

    def render_view(self, view_name: str, result: Any, **kwargs) -> str:
        """Рендерит результат View"""
        if view_name not in self.views:
            return f"Ошибка: View {view_name} не найден"

        view = self.views[view_name]
        return view.render(result, **kwargs)

    def get_view(self, view_name: str) -> BaseView:
        """Возвращает View по имени"""
        return self.views.get(view_name)