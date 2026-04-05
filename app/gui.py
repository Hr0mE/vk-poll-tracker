"""GUI entry point — PyQt6 modern dark theme."""
import asyncio
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import keyring
from PyQt6.QtCore import (
    QDate, QRectF, QThread, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QConicalGradient, QPainter, QPen, QTextCharFormat, QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.config import settings
from app.keywords import load_keywords, save_keywords
from app.exporters.excel_exporter import export
from app.services.analytics_service import build_summary
from app.services.poll_service import fetch_polls
from app.services.user_service import fetch_members, fetch_votes_for_poll
from app.vk.client import VKClient
from app.vk.rate_limiter import RateLimiter

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#1e1e2e"
SURFACE  = "#2a2a3d"
BORDER   = "#3d3d55"
ACCENT   = "#7c6af7"
ACCENT_H = "#9d8fff"
TEXT     = "#cdd6f4"
SUBTEXT  = "#a6adc8"
GREEN    = "#a6e3a1"
RED      = "#f38ba8"
YELLOW   = "#f9e2af"
BLUE     = "#89b4fa"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Inter', 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}}
QDialog {{
    background-color: {BG};
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 14px 14px 14px;
    font-weight: 600;
    color: {SUBTEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    top: -1px;
    padding: 0 6px;
    background-color: {BG};
}}
QLineEdit, QDateEdit, QComboBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QDateEdit::drop-down, QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
    background-color: {SURFACE};
}}
QDateEdit::down-arrow, QComboBox::down-arrow {{
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {SUBTEXT};
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 7px;
    selection-background-color: {ACCENT};
    color: {TEXT};
    padding: 4px;
}}
QPushButton {{
    background-color: {ACCENT};
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover {{ background-color: {ACCENT_H}; }}
QPushButton:disabled {{ background-color: {BORDER}; color: {SUBTEXT}; }}
QPushButton#secondary {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QPushButton#secondary:hover {{ border: 1px solid {ACCENT}; color: {ACCENT_H}; }}
QPushButton#icon {{
    background-color: transparent;
    color: {SUBTEXT};
    border: none;
    padding: 4px 8px;
    font-size: 16px;
}}
QPushButton#icon:hover {{ color: {TEXT}; }}
QPushButton#square {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 0px;
    font-size: 18px;
    font-weight: 400;
}}
QPushButton#square:hover {{ border: 1px solid {ACCENT}; color: {ACCENT_H}; }}
QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    height: 8px;
}}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 6px; }}
QTextEdit {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
    color: {TEXT};
}}
QLabel#title {{ font-size: 22px; font-weight: 700; color: {TEXT}; }}
QLabel#subtitle {{ font-size: 12px; color: {SUBTEXT}; }}
QLabel#step {{ font-size: 12px; color: {SUBTEXT}; }}
QFrame#divider {{ background-color: {BORDER}; max-height: 1px; }}
QDialogButtonBox QPushButton {{ min-width: 80px; }}
"""

# ── Keyring helpers ───────────────────────────────────────────────────────────
_SVC   = "vk_poll_tracker"
_TOKEN = "vk_token"


def _load_token() -> str:
    return keyring.get_password(_SVC, _TOKEN) or settings.vk_token


def _save_token(token: str) -> None:
    keyring.set_password(_SVC, _TOKEN, token)


# ── Peer storage (JSON в домашней папке) ──────────────────────────────────────
_PEERS_FILE = Path.home() / ".config" / "vk_poll_tracker" / "peers.json"


def _load_peers() -> list[dict]:
    if _PEERS_FILE.exists():
        try:
            return json.loads(_PEERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Начальная запись из .env, если файла нет
    return [{"name": "Беседа по умолчанию", "peer_id": settings.peer_id}]


def _save_peers(peers: list[dict]) -> None:
    _PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PEERS_FILE.write_text(json.dumps(peers, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Spinner widget ────────────────────────────────────────────────────────────
class Spinner(QWidget):
    """Вращающаяся дуга на QPainter."""

    def __init__(self, parent: QWidget | None = None, size: int = 32) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle  = 0
        self._timer  = QTimer(self)
        self._timer.setInterval(16)   # ~60 fps
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self) -> None:
        self._angle = 0
        self.show()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, _event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        size   = min(self.width(), self.height())
        margin = size * 0.12
        rect   = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

        # Gradient arc: from transparent to accent color
        grad = QConicalGradient(rect.center(), -self._angle)
        grad.setColorAt(0.0,  QColor(ACCENT))
        grad.setColorAt(0.75, QColor(0, 0, 0, 0))

        pen = QPen(grad, size * 0.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, int(-self._angle * 16), int(-270 * 16))
        p.end()


# ── Settings dialog ───────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # ── Токен ──
        layout.addWidget(QLabel("Токен VK"))
        self.token_input = QLineEdit(_load_token())
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("vk1.a.…")
        layout.addWidget(self.token_input)

        hint = QLabel("Токен хранится в защищённом хранилище ОС (Keychain / Credential Manager).")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        show_btn = QPushButton("Показать токен")
        show_btn.setObjectName("secondary")
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda on: self.token_input.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(show_btn)

        # ── Разделитель ──
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        layout.addWidget(div)

        # ── Ключевые слова ──
        kw_label = QLabel("Ключевые слова для классификации ответов")
        kw_label.setObjectName("subtitle")
        layout.addWidget(kw_label)

        kw = load_keywords()

        layout.addWidget(QLabel("Буду (через запятую)"))
        self.yes_input = QLineEdit(", ".join(kw["yes"]))
        layout.addWidget(self.yes_input)

        layout.addWidget(QLabel("Не буду (через запятую)"))
        self.no_input = QLineEdit(", ".join(kw["no"]))
        layout.addWidget(self.no_input)

        layout.addWidget(QLabel("Организатор (через запятую)"))
        self.org_input = QLineEdit(", ".join(kw["org"]))
        layout.addWidget(self.org_input)

        # ── Кнопки ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # ── Подпись ──
        footer = QLabel('made by <a href="https://github.com/Hr0mE" style="color: #7c6af7;">Fes</a> with ♥')
        footer.setOpenExternalLinks(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setObjectName("subtitle")
        layout.addWidget(footer)

    def _on_save(self) -> None:
        token = self.token_input.text().strip()
        if token:
            _save_token(token)

        def _parse(field: QLineEdit) -> list[str]:
            return [w.strip() for w in field.text().split(",") if w.strip()]

        save_keywords({
            "yes": _parse(self.yes_input),
            "no":  _parse(self.no_input),
            "org": _parse(self.org_input),
        })
        self.accept()


# ── Add peer dialog ───────────────────────────────────────────────────────────
class AddPeerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить беседу")
        self.setMinimumWidth(360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Название беседы"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: Спортзал — общий чат")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Peer ID"))
        self.peer_input = QLineEdit()
        self.peer_input.setPlaceholderText("2000000001")
        layout.addWidget(self.peer_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Добавить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        name = self.name_input.text().strip()
        peer = self.peer_input.text().strip()
        if not name or not peer:
            QMessageBox.warning(self, "Ошибка", "Заполните оба поля.")
            return
        try:
            int(peer)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Peer ID должен быть числом.")
            return
        self.accept()

    def result_peer(self) -> dict:
        return {"name": self.name_input.text().strip(), "peer_id": int(self.peer_input.text())}


# ── Error hints ───────────────────────────────────────────────────────────────
_HINTS: list[tuple[str, str]] = [
    ("error 5",   "Токен недействителен или истёк. Откройте ⚙ Настройки и обновите токен VK."),
    ("error 7",   "Токен не имеет доступа к сообщениям. Убедитесь, что при получении токена запрошено разрешение messages."),
    ("error 100", "Неверный Peer ID. Проверьте, правильно ли указан идентификатор беседы в списке бесед."),
    ("error 917", "Нет доступа к беседе. Убедитесь, что аккаунт, которому принадлежит токен, является участником беседы."),
    ("error 925", "Нет доступа к беседе. Убедитесь, что аккаунт, которому принадлежит токен, является участником беседы."),
    ("failed after", "Превышен лимит повторных попыток. VK временно ограничил запросы — попробуйте уменьшить RATE_LIMIT_PER_SEC в .env и запустить снова."),
    ("connection",       "Нет соединения с VK. Проверьте интернет-подключение."),
    ("errno -2",         "Нет соединения с VK. Проверьте интернет-подключение."),
    ("name or service",  "Нет соединения с VK. Проверьте интернет-подключение."),
    ("неизвестное имя",  "Нет соединения с VK. Проверьте интернет-подключение."),
    ("timed out",        "Сервер VK не ответил вовремя. Попробуйте запустить снова."),
]


def _hint_for_error(message: str) -> str:
    lower = message.lower()
    for marker, hint in _HINTS:
        if marker in lower:
            return f"Совет: {hint}"
    return ""


# ── Worker thread ─────────────────────────────────────────────────────────────
class PipelineWorker(QThread):
    log_line = pyqtSignal(str, str)   # (message, level)
    progress = pyqtSignal(int, str)   # (value 0-100, step label)
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(
        self,
        date_from: datetime,
        date_to: datetime,
        output: Path,
        token: str,
        peer_id: int,
    ) -> None:
        super().__init__()
        self.date_from = date_from
        self.date_to   = date_to
        self.output    = output
        self.token     = token
        self.peer_id   = peer_id

    def run(self) -> None:
        asyncio.run(self._pipeline())

    async def _pipeline(self) -> None:
        limiter = RateLimiter(
            rate_per_sec=settings.rate_limit_per_sec,
            max_concurrent=settings.max_concurrent_requests,
        )
        try:
            async with VKClient(self.token, settings.vk_api_version, limiter) as client:
                self.progress.emit(10, "Загружаем участников...")
                self.log_line.emit("Загружаем участников беседы", "info")
                members = await fetch_members(client, self.peer_id)
                self.log_line.emit(f"Участников: {len(members)}", "ok")

                self.progress.emit(30, "Ищем опросы...")
                self.log_line.emit(
                    f"Ищем опросы с {self.date_from.date()} по {self.date_to.date()}", "info"
                )
                polls = await fetch_polls(client, self.peer_id, self.date_from, self.date_to)

                if not polls:
                    self.log_line.emit("Опросы не найдены в указанном периоде", "warn")
                    self.finished.emit(False, "Опросы не найдены")
                    return

                self.log_line.emit(f"Найдено опросов: {len(polls)}", "ok")
                self.progress.emit(50, "Собираем голоса...")

                all_records = []
                for i, poll in enumerate(polls):
                    self.log_line.emit(
                        f"Опрос {i + 1}/{len(polls)}: {poll.date.strftime('%d.%m.%Y')}", "info"
                    )
                    records = await fetch_votes_for_poll(client, poll, members)
                    all_records.extend(records)
                    self.progress.emit(50 + int(40 * (i + 1) / len(polls)), f"Голоса {i + 1}/{len(polls)}")

                self.progress.emit(95, "Формируем отчёт...")
                self.log_line.emit("Формируем Excel-отчёт...", "info")
                summary = build_summary(all_records, members)
                export(all_records, members, summary, self.output)

                self.progress.emit(100, "Готово")
                self.log_line.emit(f"Отчёт сохранён: {self.output}", "ok")
                self.finished.emit(True, str(self.output))

        except Exception as e:
            self.log_line.emit(f"Ошибка: {e}", "error")
            hint = _hint_for_error(str(e))
            if hint:
                self.log_line.emit(hint, "warn")
            self.finished.emit(False, "")


# ── Main window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VK Poll Tracker")
        self.setMinimumSize(720, 780)
        self.resize(780, 820)
        self._worker: PipelineWorker | None = None
        self._peers: list[dict] = _load_peers()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # ── Header ──
        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        header_col.setSpacing(2)
        title = QLabel("VK Poll Tracker")
        title.setObjectName("title")
        subtitle = QLabel("Анализ посещаемости по опросам в беседе")
        subtitle.setObjectName("subtitle")
        header_col.addWidget(title)
        header_col.addWidget(subtitle)
        header_row.addLayout(header_col, 1)

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("icon")
        settings_btn.setToolTip("Настройки (токен VK)")
        settings_btn.setFixedSize(36, 36)
        settings_btn.clicked.connect(self._open_settings)
        header_row.addWidget(settings_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        # ── Беседа ──
        peer_group = QGroupBox("Беседа")
        peer_layout = QHBoxLayout(peer_group)
        peer_layout.setSpacing(8)

        self.peer_combo = QComboBox()
        self.peer_combo.setSizePolicy(
            self.peer_combo.sizePolicy().horizontalPolicy(),
            self.peer_combo.sizePolicy().verticalPolicy(),
        )
        self._refresh_peer_combo()

        add_peer_btn = QPushButton("+")
        add_peer_btn.setObjectName("square")
        add_peer_btn.setFixedSize(34, 34)
        add_peer_btn.setToolTip("Добавить беседу")
        add_peer_btn.clicked.connect(self._add_peer)

        del_peer_btn = QPushButton("−")
        del_peer_btn.setObjectName("square")
        del_peer_btn.setFixedSize(34, 34)
        del_peer_btn.setToolTip("Удалить выбранную беседу")
        del_peer_btn.clicked.connect(self._delete_peer)

        peer_layout.addWidget(self.peer_combo, 1)
        peer_layout.addWidget(add_peer_btn)
        peer_layout.addWidget(del_peer_btn)
        layout.addWidget(peer_group)

        # ── Период ──
        period = QGroupBox("Период")
        period_layout = QHBoxLayout(period)
        period_layout.setSpacing(16)

        today = QDate.currentDate()
        from_label = QLabel("С")
        self.date_from = QDateEdit(today.addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")

        to_label = QLabel("По")
        self.date_to = QDateEdit(today)
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")

        period_layout.addWidget(from_label)
        period_layout.addWidget(self.date_from, 1)
        period_layout.addWidget(to_label)
        period_layout.addWidget(self.date_to, 1)
        layout.addWidget(period)

        # ── Файл отчёта ──
        output_group = QGroupBox("Файл отчёта")
        output_layout = QHBoxLayout(output_group)
        output_layout.setSpacing(10)

        self.output_input = QLineEdit("report.xlsx")
        browse_btn = QPushButton("Обзор")
        browse_btn.setObjectName("secondary")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_output)

        output_layout.addWidget(self.output_input, 1)
        output_layout.addWidget(browse_btn)
        layout.addWidget(output_group)

        # ── Кнопка запуска + спиннер ──
        run_row = QHBoxLayout()
        run_row.setSpacing(14)

        self.run_btn = QPushButton("▶  Запустить")
        self.run_btn.setFixedHeight(42)
        self.run_btn.clicked.connect(self._run)

        self.spinner = Spinner(size=36)

        run_row.addWidget(self.run_btn, 1)
        run_row.addWidget(self.spinner)
        layout.addLayout(run_row)

        # ── Прогресс ──
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(4)

        self.step_label = QLabel("")
        self.step_label.setObjectName("step")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)

        progress_layout.addWidget(self.step_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        # ── Лог ──
        log_label = QLabel("Лог")
        log_label.setObjectName("subtitle")
        layout.addWidget(log_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(160)
        layout.addWidget(self.log_view, 1)

    # ── Peers ─────────────────────────────────────────────────────────────────

    def _refresh_peer_combo(self) -> None:
        self.peer_combo.blockSignals(True)
        self.peer_combo.clear()
        for p in self._peers:
            self.peer_combo.addItem(f"{p['name']}  ({p['peer_id']})", userData=p["peer_id"])
        self.peer_combo.blockSignals(False)

    def _add_peer(self) -> None:
        dlg = AddPeerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._peers.append(dlg.result_peer())
            _save_peers(self._peers)
            self._refresh_peer_combo()
            self.peer_combo.setCurrentIndex(len(self._peers) - 1)

    def _delete_peer(self) -> None:
        idx = self.peer_combo.currentIndex()
        if idx < 0:
            return
        name = self._peers[idx]["name"]
        box = QMessageBox(self)
        box.setWindowTitle("Удалить беседу")
        box.setText(f"Удалить «{name}»?")
        yes_btn = box.addButton("Удалить", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == yes_btn:
            self._peers.pop(idx)
            _save_peers(self._peers)
            self._refresh_peer_combo()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    # ── Run ───────────────────────────────────────────────────────────────────

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт", self.output_input.text(), "Excel (*.xlsx)"
        )
        if path:
            self.output_input.setText(path)

    def _run(self) -> None:
        peer_id = self.peer_combo.currentData()
        if peer_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите беседу.")
            return

        date_from = datetime(
            self.date_from.date().year(),
            self.date_from.date().month(),
            self.date_from.date().day(),
        )
        date_to = datetime(
            self.date_to.date().year(),
            self.date_to.date().month(),
            self.date_to.date().day(),
            23, 59, 59,
        )

        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(False)
        self.spinner.start()

        self._worker = PipelineWorker(
            date_from=date_from,
            date_to=date_to,
            output=Path(self.output_input.text()),
            token=_load_token(),
            peer_id=peer_id,
        )
        self._worker.log_line.connect(self._append_log)
        self._worker.progress.connect(self._update_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    # ── Log ───────────────────────────────────────────────────────────────────

    def _append_log(self, message: str, level: str) -> None:
        colors  = {"ok": GREEN, "warn": YELLOW, "error": RED, "info": BLUE}
        prefixes = {"ok": "✓", "warn": "⚠", "error": "✗", "info": "›"}
        color  = colors.get(level, TEXT)
        prefix = prefixes.get(level, "›")
        ts     = datetime.now().strftime("%H:%M:%S")

        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt_ts = QTextCharFormat()
        fmt_ts.setForeground(QColor(SUBTEXT))
        cursor.setCharFormat(fmt_ts)
        cursor.insertText(f"{ts}  ")

        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(QColor(color))
        cursor.setCharFormat(fmt_msg)
        cursor.insertText(f"{prefix} {message}\n")

        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def _update_progress(self, value: int, label: str) -> None:
        self.progress_bar.setValue(value)
        self.step_label.setText(label)

    def _on_finished(self, success: bool, message: str) -> None:
        self.spinner.stop()
        self.run_btn.setEnabled(True)
        if success:
            self._append_log(f"Готово → {message}", "ok")
        else:
            self._append_log("Выполнение прервано.", "error")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
