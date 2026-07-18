"""widgets/template_dialog.py — Fill in {1} {2} {3} template variables"""
import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
)


class TemplateDialog(QDialog):
    def __init__(self, label: str, template: str, parent=None):
        super().__init__(parent)
        self._template   = template
        self.result_text = template
        self.setWindowTitle(f"Fill Template: {label}")
        self.setModal(True)
        self.resize(400, 200)
        self._build(template)

    def _build(self, template: str):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # Find all {N} placeholders
        placeholders = sorted(set(re.findall(r'\{(\d+)\}', template)))
        self._inputs = {}

        for ph in placeholders:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Variable {{{ph}}}:"))
            edit = QLineEdit()
            row.addWidget(edit, 1)
            self._inputs[ph] = edit
            lay.addLayout(row)

        if not placeholders:
            lay.addWidget(QLabel("No variables found in template."))

        preview = QLabel(template[:100] + ("…" if len(template) > 100 else ""))
        preview.setObjectName("DimLabel")
        preview.setWordWrap(True)
        lay.addWidget(preview)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Copy"); ok.setObjectName("AccentBtn"); ok.clicked.connect(self._ok)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

        if self._inputs:
            list(self._inputs.values())[0].setFocus()

    def _ok(self):
        text = self._template
        for ph, edit in self._inputs.items():
            text = text.replace(f"{{{ph}}}", edit.text())
        self.result_text = text
        self.accept()
