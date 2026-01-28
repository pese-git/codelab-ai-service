"""
Интерфейсы domain слоя.

Этот модуль содержит абстрактные интерфейсы, определяющие контракты
для взаимодействия между слоями приложения в соответствии с Clean Architecture.
"""

from app.domain.interfaces.stream_handler import IStreamHandler

__all__ = ["IStreamHandler"]
