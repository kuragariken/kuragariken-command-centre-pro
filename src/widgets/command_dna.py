"""
command_dna.py — Organic root/branch tree visualisation of command usage.

Instead of bar charts, renders your command usage as a living "DNA tree" —
a central trunk that branches based on category, with branch thickness
proportional to usage count. More-used commands get thicker, more
luminous branches. Looks like a glowing organism made of habits.
"""
import math, random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui     import (QPainter, QColor, QPen, QBrush,
                              QPainterPath, QRadialGradient, QFont)


class CommandDNA(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background:transparent;")
        self._data    = {}   # {category: [(label, count), ...]}
        self._accent  = "#00e87a"
        self._accent2 = "#38bdf8"
        self._t       = 0.0
        self._branches = []   # computed branch geometry, cached

        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(33)

    def set_data(self, category_counts: dict, accent: str, accent2: str):
        """category_counts: {category: [(label, count), ...]}"""
        self._data    = category_counts
        self._accent  = accent
        self._accent2 = accent2
        self._compute_branches()
        self.update()

    def _tick(self):
        self._t += 0.012
        self.update()

    def _compute_branches(self):
        """Pre-compute branch tree geometry from command usage data."""
        self._branches = []
        if not self._data:
            return

        w, h = max(self.width(), 400), max(self.height(), 220)
        root_x, root_y = w * 0.5, h * 0.95

        categories = list(self._data.items())
        n_cats = len(categories)
        if n_cats == 0:
            return

        max_count = max(
            (count for cmds in self._data.values() for _, count in cmds),
            default=1
        ) or 1

        for ci, (cat, cmds) in enumerate(categories):
            # Spread category trunks across an arc
            angle_spread = math.pi * 0.7
            base_angle = -math.pi/2 - angle_spread/2 + (
                (ci + 0.5) / n_cats) * angle_spread

            trunk_len = h * 0.35
            tx = root_x + math.cos(base_angle) * trunk_len
            ty = root_y + math.sin(base_angle) * trunk_len

            cat_total = sum(c for _, c in cmds) or 1
            trunk_w = 2 + min(8, cat_total / 3)

            self._branches.append({
                "type": "trunk", "x0": root_x, "y0": root_y,
                "x1": tx, "y1": ty, "width": trunk_w,
                "intensity": min(1.0, cat_total / max_count / 2),
            })

            # Sub-branches per command
            n_cmds = len(cmds)
            for j, (label, count) in enumerate(cmds[:6]):  # cap visual clutter
                sub_spread = math.pi * 0.5
                sub_angle = base_angle + (-sub_spread/2 + (
                    (j + 0.5) / max(1, n_cmds)) * sub_spread)
                sub_len = h * 0.18 * (0.5 + min(1.0, count / max_count))
                sx = tx + math.cos(sub_angle) * sub_len
                sy = ty + math.sin(sub_angle) * sub_len
                branch_w = 1 + min(5, count / 2)

                self._branches.append({
                    "type": "branch", "x0": tx, "y0": ty,
                    "x1": sx, "y1": sy, "width": branch_w,
                    "intensity": min(1.0, count / max_count),
                    "label": label, "count": count,
                    "phase": random.uniform(0, math.tau),
                })

    def resizeEvent(self, e):
        self._compute_branches()
        super().resizeEvent(e)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if not self._branches:
            p.setPen(QColor(74, 85, 104))
            p.setFont(QFont("Segoe UI Variable Text", 11))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                      "No usage data yet — start copying commands")
            return

        ac1 = QColor(self._accent)
        ac2 = QColor(self._accent2)

        # Root glow
        root_x, root_y = w * 0.5, h * 0.95
        rg = QRadialGradient(QPointF(root_x, root_y), 60)
        rgc = QColor(ac1); rgc.setAlpha(40)
        rg.setColorAt(0, rgc)
        rg.setColorAt(1, QColor(0,0,0,0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(rg))
        p.drawEllipse(QPointF(root_x, root_y), 60, 60)

        # Draw branches
        for br in self._branches:
            t = br["intensity"]
            col = QColor(
                int(ac1.red()   * (1-t) + ac2.red()   * t),
                int(ac1.green() * (1-t) + ac2.green() * t),
                int(ac1.blue()  * (1-t) + ac2.blue()  * t),
            )

            # Pulsing glow for high-usage branches
            phase = br.get("phase", 0)
            pulse = (math.sin(self._t * 2 + phase) + 1) / 2 if br["type"] == "branch" else 0
            glow_alpha = int(30 + pulse * 40 * t)

            # Outer glow line
            glow_c = QColor(col); glow_c.setAlpha(glow_alpha)
            p.setPen(QPen(glow_c, br["width"] + 4))
            p.drawLine(QPointF(br["x0"], br["y0"]), QPointF(br["x1"], br["y1"]))

            # Core line
            core_c = QColor(col); core_c.setAlpha(220)
            p.setPen(QPen(core_c, br["width"]))
            p.drawLine(QPointF(br["x0"], br["y0"]), QPointF(br["x1"], br["y1"]))

            # End node — glowing dot for branches with labels
            if br["type"] == "branch":
                node_r = 2 + t * 3
                ng = QRadialGradient(QPointF(br["x1"], br["y1"]), node_r * 3)
                nc = QColor(col); nc.setAlpha(int(180 + pulse*60))
                ng.setColorAt(0, nc)
                ng.setColorAt(1, QColor(0,0,0,0))
                p.setBrush(QBrush(ng))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(br["x1"], br["y1"]), node_r*3, node_r*3)

                solid = QColor(255,255,255, int(180+pulse*60))
                p.setBrush(QBrush(solid))
                p.drawEllipse(QPointF(br["x1"], br["y1"]), node_r*0.6, node_r*0.6)

        # Root base glow ring
        p.setPen(QPen(ac1, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(root_x, root_y), 5, 5)
