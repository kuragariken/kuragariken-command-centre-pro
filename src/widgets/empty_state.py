"""
empty_state.py — Shared empty-state placeholder for QListWidget panels.

Several panels (History, Tickets, Reminders, ...) show a QListWidget
that is simply blank when there's no data yet — no message, no
guidance. This drops in a single non-interactive row with a short,
friendly message so an empty panel reads as "nothing here yet"
instead of "is this broken?".

Usage — call at the end of refresh(), after populating the list:
    show_empty_state(self._list, "No tickets logged yet.")
It's a no-op if the list already has real rows.
"""
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QLabel
from PyQt6.QtCore import Qt

FONT = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"


def show_empty_state(list_widget: QListWidget, message: str, icon: str = "◌"):
    """
    Insert a single non-interactive placeholder row into an otherwise
    empty QListWidget. No-ops if the widget already has rows — safe
    to call unconditionally right after populating a list in refresh().
    """
    if list_widget.count() > 0:
        return

    item = QListWidgetItem()
    item.setFlags(Qt.ItemFlag.NoItemFlags)  # not selectable / not clickable
    list_widget.addItem(item)

    label = QLabel(f"{icon}   {message}")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:transparent;color:#6b83a0;font-size:11px;"
        f"font-style:italic;padding:28px 20px;border:none;"
        f"font-family:{FONT};")

    item.setSizeHint(label.sizeHint())
    list_widget.setItemWidget(item, label)
