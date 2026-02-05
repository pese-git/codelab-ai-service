"""
Dependency Resolver для управления зависимостями между подзадачами.

Определяет порядок выполнения подзадач и обнаруживает циклические зависимости.
"""

import logging
from typing import List, Set, Dict

from app.domain.execution_context.entities import ExecutionPlan, Subtask
from app.domain.execution_context.value_objects import SubtaskId

logger = logging.getLogger("agent-runtime.execution_context.dependency_resolver")


class DependencyError(Exception):
    """Базовая ошибка зависимостей."""
    pass


class CircularDependencyError(DependencyError):
    """Ошибка циклической зависимости."""
    pass


class DependencyResolver:
    """
    Resolver для управления зависимостями между подзадачами.
    
    Основные функции:
    - Определение готовых к выполнению подзадач
    - Обнаружение циклических зависимостей
    - Валидация графа зависимостей
    - Топологическая сортировка
    
    Использует DFS (Depth-First Search) для обнаружения циклов.
    
    Example:
        >>> resolver = DependencyResolver()
        >>> ready = resolver.get_ready_subtasks(plan)
        >>> for subtask in ready:
        ...     print(f"Ready: {subtask.description}")
    """
    
    def get_ready_subtasks(self, plan: ExecutionPlan) -> List[Subtask]:
        """
        Получить подзадачи готовые к выполнению.
        
        Подзадача готова если:
        - Статус PENDING
        - Все зависимости выполнены (status=DONE)
        
        Args:
            plan: План с подзадачами
            
        Returns:
            Список готовых подзадач (может быть пустым)
            
        Example:
            >>> resolver = DependencyResolver()
            >>> ready = resolver.get_ready_subtasks(plan)
            >>> for subtask in ready:
            ...     print(f"Ready: {subtask.description}")
        """
        # Получить ID завершённых подзадач
        completed_ids = [
            st.id for st in plan.subtasks
            if st.status.is_done()
        ]
        
        # Найти готовые подзадачи
        ready = []
        for subtask in plan.subtasks:
            if subtask.status.is_pending():
                # Проверить, все ли зависимости выполнены
                if subtask.is_ready(completed_ids):
                    ready.append(subtask)
        
        pending_count = sum(1 for st in plan.subtasks if st.status.is_pending())
        logger.debug(
            f"Found {len(ready)} ready subtasks out of {pending_count} pending"
        )
        
        return ready
    
    def has_cyclic_dependencies(self, plan: ExecutionPlan) -> bool:
        """
        Проверить наличие циклических зависимостей в плане.
        
        Использует DFS (Depth-First Search) для обнаружения циклов.
        
        Args:
            plan: План для проверки
            
        Returns:
            True если есть циклы, False иначе
            
        Example:
            >>> resolver = DependencyResolver()
            >>> if resolver.has_cyclic_dependencies(plan):
            ...     print("ERROR: Cyclic dependencies detected!")
        """
        # Построить граф зависимостей
        graph = self._build_dependency_graph(plan)
        
        # DFS для обнаружения циклов
        visited: Set[SubtaskId] = set()
        rec_stack: Set[SubtaskId] = set()  # Recursion stack для текущего пути
        
        for subtask_id in graph.keys():
            if subtask_id not in visited:
                if self._has_cycle_dfs(subtask_id, graph, visited, rec_stack):
                    logger.warning(f"Cyclic dependency detected in plan {plan.id}")
                    return True
        
        return False
    
    def _build_dependency_graph(self, plan: ExecutionPlan) -> Dict[SubtaskId, List[SubtaskId]]:
        """
        Построить граф зависимостей.
        
        Args:
            plan: План
            
        Returns:
            Словарь {subtask_id: [dependency_ids]}
        """
        graph = {}
        for subtask in plan.subtasks:
            graph[subtask.id] = subtask.dependencies.copy()
        
        return graph
    
    def _has_cycle_dfs(
        self,
        node: SubtaskId,
        graph: Dict[SubtaskId, List[SubtaskId]],
        visited: Set[SubtaskId],
        rec_stack: Set[SubtaskId]
    ) -> bool:
        """
        DFS для обнаружения циклов.
        
        Args:
            node: Текущий узел (subtask ID)
            graph: Граф зависимостей
            visited: Множество посещённых узлов
            rec_stack: Стек рекурсии (текущий путь)
            
        Returns:
            True если обнаружен цикл
        """
        # Пометить узел как посещённый
        visited.add(node)
        rec_stack.add(node)
        
        # Проверить всех соседей
        for neighbor in graph.get(node, []):
            # Если сосед не посещён, рекурсивно проверить
            if neighbor not in visited:
                if self._has_cycle_dfs(neighbor, graph, visited, rec_stack):
                    return True
            # Если сосед в текущем пути → цикл
            elif neighbor in rec_stack:
                logger.warning(f"Cycle detected: {node} -> {neighbor}")
                return True
        
        # Убрать из стека рекурсии
        rec_stack.remove(node)
        return False
    
    def get_execution_order(self, plan: ExecutionPlan) -> List[List[Subtask]]:
        """
        Получить порядок выполнения подзадач по уровням.
        
        Возвращает подзадачи сгруппированные по уровням зависимостей.
        Подзадачи в одном уровне могут выполняться параллельно.
        
        Args:
            plan: План
            
        Returns:
            Список уровней, каждый уровень - список подзадач
            
        Raises:
            ValueError: Если есть циклические зависимости
            
        Example:
            >>> resolver = DependencyResolver()
            >>> levels = resolver.get_execution_order(plan)
            >>> for i, level in enumerate(levels):
            ...     print(f"Level {i}: {[st.description for st in level]}")
        """
        # Проверить циклы
        if self.has_cyclic_dependencies(plan):
            raise ValueError("Cannot determine execution order: cyclic dependencies detected")
        
        # Топологическая сортировка по уровням
        levels: List[List[Subtask]] = []
        remaining = {st.id: st for st in plan.subtasks}
        completed: Set[SubtaskId] = set()
        
        while remaining:
            # Найти подзадачи без невыполненных зависимостей
            current_level = []
            for subtask_id, subtask in list(remaining.items()):
                if all(dep_id in completed for dep_id in subtask.dependencies):
                    current_level.append(subtask)
                    del remaining[subtask_id]
            
            # Если не нашли ни одного → deadlock (не должно случиться после проверки циклов)
            if not current_level:
                logger.error(
                    f"Deadlock detected in plan {plan.id}. "
                    f"Remaining subtasks: {list(remaining.keys())}"
                )
                raise ValueError("Deadlock in dependency graph")
            
            # Добавить уровень
            levels.append(current_level)
            
            # Пометить как завершённые для следующей итерации
            completed.update(st.id for st in current_level)
        
        logger.debug(f"Execution order: {len(levels)} levels")
        return levels
    
    def validate_dependencies(self, plan: ExecutionPlan) -> List[str]:
        """
        Валидировать зависимости плана.
        
        Проверяет:
        - Нет циклических зависимостей
        - Все зависимости существуют
        - Нет самозависимостей
        
        Args:
            plan: План для валидации
            
        Returns:
            Список ошибок (пустой если всё OK)
            
        Example:
            >>> resolver = DependencyResolver()
            >>> errors = resolver.validate_dependencies(plan)
            >>> if errors:
            ...     for error in errors:
            ...         print(f"ERROR: {error}")
        """
        errors = []
        
        # Проверка 1: Циклические зависимости
        if self.has_cyclic_dependencies(plan):
            errors.append("Cyclic dependencies detected")
        
        # Проверка 2: Все зависимости существуют
        subtask_ids = {st.id for st in plan.subtasks}
        for subtask in plan.subtasks:
            for dep_id in subtask.dependencies:
                if dep_id not in subtask_ids:
                    errors.append(
                        f"Subtask {subtask.id} depends on non-existent subtask {dep_id}"
                    )
        
        # Проверка 3: Нет самозависимостей
        for subtask in plan.subtasks:
            if subtask.id in subtask.dependencies:
                errors.append(
                    f"Subtask {subtask.id} has self-dependency"
                )
        
        if errors:
            logger.warning(
                f"Dependency validation failed for plan {plan.id}: "
                f"{len(errors)} errors"
            )
        else:
            logger.debug(f"Dependency validation passed for plan {plan.id}")
        
        return errors
    
    def get_dependent_subtasks(
        self,
        plan: ExecutionPlan,
        subtask_id: SubtaskId
    ) -> List[Subtask]:
        """
        Получить подзадачи, которые зависят от указанной.
        
        Полезно для определения влияния ошибки подзадачи на план.
        
        Args:
            plan: План
            subtask_id: ID подзадачи
            
        Returns:
            Список зависимых подзадач
            
        Example:
            >>> resolver = DependencyResolver()
            >>> dependents = resolver.get_dependent_subtasks(plan, SubtaskId("st-1"))
            >>> if dependents:
            ...     print(f"Failure of st-1 will affect {len(dependents)} subtasks")
        """
        dependents = []
        for subtask in plan.subtasks:
            if subtask_id in subtask.dependencies:
                dependents.append(subtask)
        
        return dependents
