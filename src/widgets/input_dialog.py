"""widgets/input_dialog.py — Simple input dialog"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton


def quick_input(parent, title: str, prompt: str, default: str = "") -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.resize(320, 120)
    lay = QVBoxLayout(dlg)
    lay.setSpacing(10)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.addWidget(QLabel(prompt))
    edit = QLineEdit(default)
    edit.selectAll()
    lay.addWidget(edit)
    row = QHBoxLayout()
    row.addStretch()
    cancel = QPushButton("Cancel")
    cancel.clicked.connect(dlg.reject)
    row.addWidget(cancel)
    ok = QPushButton("OK")
    ok.setObjectName("AccentBtn")
    ok.clicked.connect(dlg.accept)
    row.addWidget(ok)
    lay.addLayout(row)
    edit.returnPressed.connect(dlg.accept)
    if dlg.exec():
        return edit.text().strip() or None
    return None
