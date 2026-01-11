from __future__ import annotations

from PySide6.QtWidgets import QMessageBox
from nord_skc.config import AssetConfig


def _classify_net_error(e: Exception) -> str:
    """Грубая классификация сетевых ошибок для понятных сообщений оператору."""
    s = str(e).lower()

    # timeout / нет ответа
    if "timed out" in s or "timeout" in s:
        return "timeout"

    # Windows: удалённый хост принудительно разорвал (WinError 10054)
    if "10054" in s or "forcibly closed" in s or "connection reset" in s:
        return "reset"

    # Windows: нет ответа (WinError 10060)
    if "10060" in s:
        return "timeout"

    # отказ в подключении (порт закрыт / сервис не запущен)
    if "refused" in s or "10061" in s:
        return "refused"

    # нет маршрута / сеть недоступна / unreachable peer
    if "unreachable" in s or "no route" in s or "network is unreachable" in s:
        return "unreachable"

    # прочее
    return "other"


def make_connect_error_box(parent, a: AssetConfig, e: Exception) -> QMessageBox:
    """
    Красивое сообщение для оператора + технические детали в "Подробности".
    """
    kind = _classify_net_error(e)

    title = "Ошибка подключения"
    header = f"Не удалось подключиться к флоту {a.fleet_no:02d} ({a.id})."

    if kind == "timeout":
        title = "Нет связи с агрегатом"
        body = (
            "Агрегат не отвечает на запросы.\n\n"
            "Возможные причины:\n"
            "• агрегат выключен или нет питания\n"
            "• потеря связи (сеть/кабель/роутер)\n\n"
            "Что делать:\n"
            "• проверьте, что агрегат включён\n"
            "• попробуйте ещё раз через 10–20 секунд\n"
            "• если повторяется — сообщите инженеру"
        )
    elif kind == "reset":
        title = "Связь прервана"
        body = (
            "Соединение было разорвано во время подключения.\n\n"
            "Возможные причины:\n"
            "• агрегат перезагружается\n"
            "• кратковременный сбой сети\n\n"
            "Что делать:\n"
            "• подождите 10–20 секунд и попробуйте снова\n"
            "• если повторяется — сообщите инженеру"
        )
    elif kind == "unreachable":
        title = "Агрегат недоступен"
        body = (
            "До агрегата не удаётся добраться по сети.\n\n"
            "Возможные причины:\n"
            "• нет сети на площадке\n"
            "• оборван кабель / отключен коммутатор\n\n"
            "Что делать:\n"
            "• проверьте сеть/кабель\n"
            "• если не помогло — сообщите инженеру"
        )
    elif kind == "refused":
        title = "Сервис не отвечает"
        body = (
            "Подключение отклонено.\n\n"
            "Возможные причины:\n"
            "• сервис на агрегате не запущен\n"
            "• неверные настройки подключения\n\n"
            "Что делать:\n"
            "• попробуйте позже\n"
            "• если повторяется — сообщите инженеру"
        )
    else:
        title = "Ошибка подключения"
        body = (
            "Не удалось установить соединение.\n\n"
            "Что делать:\n"
            "• попробуйте ещё раз\n"
            "• если повторяется — сообщите инженеру"
        )

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(title)
    box.setText(header)
    box.setInformativeText(body)

    # Технические детали — инженеру (оператор может не открывать)
    details = (
        f"asset_id: {a.id}\n"
        f"fleet_no: {a.fleet_no}\n"
        f"type: {a.type}\n"
        f"ip: {a.ip}\n"
        f"extra: {a.extra}\n\n"
        f"raw_error: {repr(e)}"
    )
    box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.Ok)
    return box


def humanize_runtime_error(asset_id: str, error_text: str) -> str:
    """
    Для статуса в AssetWindow (коротко, без TCP и WinError).
    """
    s = (error_text or "").lower()
    if "timed out" in s or "timeout" in s or "10060" in s:
        return f"{asset_id}: НЕТ СВЯЗИ (агрегат не отвечает)"
    if "10054" in s or "forcibly closed" in s or "connection reset" in s:
        return f"{asset_id}: СВЯЗЬ ПРЕРВАНА (попробуйте ещё раз)"
    if "unreachable" in s or "no route" in s or "network is unreachable" in s:
        return f"{asset_id}: АГРЕГАТ НЕДОСТУПЕН (проблема сети)"
    if "refused" in s or "10061" in s:
        return f"{asset_id}: ОТКАЗ В ПОДКЛЮЧЕНИИ (сервис не запущен)"
    return f"{asset_id}: ОШИБКА СВЯЗИ"
