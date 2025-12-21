from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout

class AssetCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setObjectName("assetCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        layout.addLayout(top)

        # "иконка" — просто квадрат с буквами NORD (пока одинаковая)
        icon = QLabel("NORD")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(64, 64)
        icon.setStyleSheet("border-radius: 12px; border: 1px solid #3a3a3a;")
        f = QFont()
        f.setBold(True)
        icon.setFont(f)
        top.addWidget(icon)

        titles = QVBoxLayout()
        top.addLayout(titles, 1)

        self.title_lbl = QLabel(title)
        tf = QFont()
        tf.setPointSize(12)
        tf.setBold(True)
        self.title_lbl.setFont(tf)
        titles.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(subtitle)
        self.subtitle_lbl.setStyleSheet("color: #aaa;")
        titles.addWidget(self.subtitle_lbl)

        self.status_lbl = QLabel("● offline")
        self.status_lbl.setStyleSheet("color: #d66;")
        layout.addWidget(self.status_lbl)

        self.setMinimumHeight(130)
        self.setStyleSheet("""
            QFrame#assetCard {
                border: 1px solid #2b2b2b;
                border-radius: 16px;
            }
            QFrame#assetCard:hover {
                border: 1px solid #4a4a4a;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
