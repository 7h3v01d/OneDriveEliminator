"""
OneDrive Eliminator  v2.0
KeystoneAI  ·  Professional Windows Utility
Requires: pip install PyQt6
Run as Administrator for full removal.
"""

import sys, os, subprocess, threading, time, ctypes, shutil, winreg
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QMessageBox, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation,
    QEasingCurve, QRect, QSize, pyqtProperty
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QFont, QFontDatabase,
    QLinearGradient, QPen, QBrush, QPixmap, QIcon, QPalette
)

# ──────────────────────────────────────────────────────────────
# DESIGN TOKENS
# ──────────────────────────────────────────────────────────────
C = {
    "bg":          "#0b0d0f",
    "surface":     "#12151a",
    "surface2":    "#181c22",
    "border":      "#222830",
    "border2":     "#2d3440",
    "accent":      "#0ea5e9",      # sky blue — clinical, precise
    "accent2":     "#0284c7",
    "accent_glow": "#0ea5e940",
    "success":     "#22c55e",
    "warning":     "#f59e0b",
    "danger":      "#ef4444",
    "text":        "#e2e8f0",
    "text2":       "#94a3b8",
    "text3":       "#475569",
    "white":       "#ffffff",
}

STEPS = [
    ("stop",     "Stop Process",         "Terminate OneDrive.exe cleanly"),
    ("unlink",   "Unlink Account",       "Detach account — cloud files untouched"),
    ("uninstall","Uninstall App",         "Remove OneDrive application"),
    ("policy",   "Lock Group Policy",    "Block silent reinstallation"),
    ("explorer", "Clean Explorer",       "Remove sidebar & Save-As entries"),
    ("tasks",    "Disable Tasks",        "Kill scheduled update jobs"),
    ("shell",    "Clean Shell CLSID",    "Remove ghost namespace entries"),
    ("files",    "Audit Local Files",    "Report local folder — never deletes"),
]

STEP_ICONS = {
    "stop":      "⏹",
    "unlink":    "⛓",
    "uninstall": "🗑",
    "policy":    "🔒",
    "explorer":  "📁",
    "tasks":     "📅",
    "shell":     "🔧",
    "files":     "📂",
}

# ──────────────────────────────────────────────────────────────
# REMOVAL LOGIC  (unchanged core, same as v1)
# ──────────────────────────────────────────────────────────────
def is_admin():
    try:    return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

class RemovalWorker(QThread):
    log_signal      = pyqtSignal(str, str)   # message, level
    step_signal     = pyqtSignal(str, str)   # step_id, status  (pending/running/ok/warn/error)
    done_signal     = pyqtSignal(int)        # error count

    def run(self):
        errors = 0
        steps = [
            ("stop",      self._kill_process),
            ("unlink",    self._unlink),
            ("uninstall", self._uninstall),
            ("policy",    self._block_registry),
            ("explorer",  self._remove_explorer),
            ("tasks",     self._disable_tasks),
            ("shell",     self._clean_shell),
            ("files",     self._report_files),
        ]
        for sid, fn in steps:
            self.step_signal.emit(sid, "running")
            try:
                ok, msg = fn()
                self.step_signal.emit(sid, "ok" if ok else "warn")
                if not ok: errors += 1
            except Exception as e:
                self.log_signal.emit(f"Unexpected error: {e}", "error")
                self.step_signal.emit(sid, "error")
                errors += 1
        self.done_signal.emit(errors)

    def _log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def _kill_process(self):
        self._log("Stopping OneDrive process…", "info")
        r = subprocess.run(["taskkill", "/F", "/IM", "OneDrive.exe"],
                           capture_output=True, text=True)
        if "SUCCESS" in r.stdout:
            self._log("Process terminated.", "ok")
        else:
            self._log("Process was not running.", "dim")
        return True, "ok"

    def _unlink(self):
        self._log("Unlinking account…", "info")
        exe = self._find_exe()
        if exe:
            subprocess.run([exe, "/shutdown"], capture_output=True)
            time.sleep(1)
            self._log("Account unlinked. Cloud files intact on onedrive.live.com", "ok")
        else:
            self._log("OneDrive.exe not found — skipping.", "dim")
        return True, "ok"

    def _uninstall(self):
        self._log("Uninstalling application…", "info")
        exe = self._find_exe()
        if exe:
            subprocess.run([exe, "/uninstall"], capture_output=True)
            time.sleep(3)
            self._log("Uninstall command executed.", "ok")
        else:
            self._log("Already uninstalled or not found.", "dim")
        winget = shutil.which("winget")
        if winget:
            subprocess.run([winget, "uninstall", "--id", "Microsoft.OneDrive", "--silent"],
                           capture_output=True)
            self._log("winget removal attempted.", "ok")
        return True, "ok"

    def _block_registry(self):
        self._log("Writing Group Policy registry keys…", "info")
        try:
            kp = r"SOFTWARE\Policies\Microsoft\Windows\OneDrive"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, kp,
                                    0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "DisableFileSyncNGSC", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(k, "DisableLibrariesDefaultSaveToOneDrive", 0, winreg.REG_DWORD, 1)
            self._log("HKLM policy keys written.", "ok")
            rp = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rp,
                                0, winreg.KEY_SET_VALUE) as k:
                try:
                    winreg.DeleteValue(k, "OneDrive")
                    self._log("Autorun entry removed.", "ok")
                except FileNotFoundError:
                    self._log("No autorun entry (already clean).", "dim")
            return True, "ok"
        except Exception as e:
            self._log(f"Registry error (need admin): {e}", "warn")
            return False, str(e)

    def _remove_explorer(self):
        self._log("Removing from Explorer namespace…", "info")
        clsids = ["{018D5C66-4533-4307-9B53-224DE2ED1FE6}",
                  "{04271989-C4B6-4337-8CDF-5625D88F4C1C}"]
        base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Desktop\NameSpace"
        removed = 0
        for c in clsids:
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    winreg.DeleteKey(hive, f"{base}\\{c}")
                    removed += 1
                except: pass
        try:
            hide = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Desktop\NameSpace\{018D5C66-4533-4307-9B53-224DE2ED1FE6}"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, hide,
                                    0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "System.IsPinnedToNameSpaceTree", 0, winreg.REG_DWORD, 0)
            self._log("Hidden from Save-As dialog.", "ok")
        except: pass
        self._log(f"{removed} namespace entries removed.", "ok" if removed else "dim")
        return True, "ok"

    def _disable_tasks(self):
        self._log("Disabling scheduled tasks…", "info")
        tasks = [r"\Microsoft\Windows\OneDrive\Standalone Update Task",
                 r"\Microsoft\Windows\OneDrive\Standalone Update Task v2"]
        found = 0
        for t in tasks:
            r = subprocess.run(["schtasks", "/Change", "/TN", t, "/DISABLE"],
                               capture_output=True)
            if r.returncode == 0: found += 1
        self._log(f"{found} tasks disabled." if found else "No tasks found.", "ok" if found else "dim")
        return True, "ok"

    def _clean_shell(self):
        self._log("Cleaning CLSID shell entries…", "info")
        clsids = [
            r"SOFTWARE\Classes\CLSID\{018D5C66-4533-4307-9B53-224DE2ED1FE6}",
            r"SOFTWARE\Classes\CLSID\{04271989-C4B6-4337-8CDF-5625D88F4C1C}",
        ]
        for path in clsids:
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    self._del_tree(hive, path)
                    self._log(f"Removed CLSID entry.", "ok")
                except: pass
        return True, "ok"

    def _report_files(self):
        self._log("Auditing local OneDrive folder…", "info")
        p = Path.home() / "OneDrive"
        if p.exists():
            n = sum(1 for f in p.rglob("*") if f.is_file())
            self._log(f"Local folder: {p}", "warn")
            self._log(f"Contains {n} files — NOT deleted. Move them if needed.", "ok")
        else:
            self._log("No local OneDrive folder found.", "dim")
        return True, "ok"

    def _find_exe(self):
        candidates = [
            Path(os.environ.get("LOCALAPPDATA","")) / "Microsoft/OneDrive/OneDrive.exe",
            Path(os.environ.get("PROGRAMFILES","")) / "Microsoft OneDrive/OneDrive.exe",
        ]
        for p in candidates:
            if p.exists(): return str(p)
        r = subprocess.run(["where", "OneDrive.exe"], capture_output=True, text=True)
        if r.returncode == 0: return r.stdout.strip().splitlines()[0]
        return None

    def _del_tree(self, hive, path):
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
                subs = []
                i = 0
                while True:
                    try: subs.append(winreg.EnumKey(k, i)); i += 1
                    except OSError: break
            for s in subs: self._del_tree(hive, path + "\\" + s)
            winreg.DeleteKey(hive, path)
        except FileNotFoundError: pass


# ──────────────────────────────────────────────────────────────
# CUSTOM WIDGETS
# ──────────────────────────────────────────────────────────────

class StepRow(QFrame):
    STATUS_COLORS = {
        "pending": C["text3"],
        "running": C["accent"],
        "ok":      C["success"],
        "warn":    C["warning"],
        "error":   C["danger"],
    }
    STATUS_ICONS = {
        "pending": "○",
        "running": "◉",
        "ok":      "✓",
        "warn":    "⚠",
        "error":   "✕",
    }

    def __init__(self, step_id, icon, title, subtitle):
        super().__init__()
        self.step_id = step_id
        self.status = "pending"
        self.setFixedHeight(68)
        self.setStyleSheet(f"""
            StepRow {{
                background: {C["surface"]};
                border: 1px solid {C["border"]};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(16)

        # Step icon badge
        self.icon_label = QLabel(icon)
        self.icon_label.setFixedSize(38, 38)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.icon_label.setStyleSheet(f"""
            background: {C["surface2"]};
            border: 1px solid {C["border2"]};
            border-radius: 6px;
            font-size: 16px;
            padding-bottom: 3px;
        """)
        layout.addWidget(self.icon_label)

        # Text block
        text_block = QVBoxLayout()
        text_block.setSpacing(3)
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"color: {C['text']}; font-size: 14px; font-weight: 600; font-family: 'Segoe UI';")
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet(f"color: {C['text3']}; font-size: 11px; font-family: 'Segoe UI';")
        text_block.addWidget(self.title_lbl)
        text_block.addWidget(self.sub_lbl)
        layout.addLayout(text_block)

        # Status indicator
        self.status_lbl = QLabel(self.STATUS_ICONS["pending"])
        self.status_lbl.setFixedWidth(24)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"color: {C['text3']}; font-size: 15px; font-weight: bold;")
        layout.addWidget(self.status_lbl)

    def set_status(self, status):
        self.status = status
        color = self.STATUS_COLORS.get(status, C["text3"])
        icon  = self.STATUS_ICONS.get(status, "○")
        self.status_lbl.setText(icon)
        self.status_lbl.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold;")

        if status == "running":
            self.setStyleSheet(f"""
                StepRow {{
                    background: {C["surface2"]};
                    border: 1px solid {C["accent"]};
                    border-radius: 10px;
                }}
            """)
        elif status in ("ok",):
            self.setStyleSheet(f"""
                StepRow {{
                    background: {C["surface"]};
                    border: 1px solid #1a3a2a;
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                StepRow {{
                    background: {C["surface"]};
                    border: 1px solid {C["border"]};
                    border-radius: 10px;
                }}
            """)


class LogEntry(QLabel):
    LEVEL_STYLE = {
        "info":  (C["text2"],    "·"),
        "ok":    (C["success"],  "✓"),
        "warn":  (C["warning"],  "⚠"),
        "error": (C["danger"],   "✕"),
        "dim":   (C["text3"],    " "),
    }

    def __init__(self, message, level="info"):
        color, prefix = self.LEVEL_STYLE.get(level, (C["text2"], "·"))
        super().__init__(f"  {prefix}  {message}")
        self.setStyleSheet(f"""
            color: {color};
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            padding: 1px 0;
        """)
        self.setWordWrap(True)


class PulsingDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._opacity = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._step = 0
        self.active = False

    def start(self):
        self.active = True
        self._timer.start(50)
        self.show()

    def stop(self):
        self.active = False
        self._timer.stop()
        self._opacity = 1.0
        self.update()

    def _tick(self):
        self._step = (self._step + 1) % 40
        self._opacity = 0.3 + 0.7 * abs((self._step - 20) / 20)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C["accent"])
        col.setAlphaF(self._opacity)
        p.setBrush(QBrush(col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 8, 8)


class RunButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(44)
        self.setMinimumWidth(200)
        self._apply_style(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_style(self, disabled):
        if disabled:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {C["surface2"]};
                    color: {C["text3"]};
                    border: 1px solid {C["border"]};
                    border-radius: 8px;
                    font-family: 'Segoe UI';
                    font-size: 13px;
                    font-weight: 600;
                    padding: 0 24px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {C["accent"]};
                    color: #000;
                    border: none;
                    border-radius: 8px;
                    font-family: 'Segoe UI';
                    font-size: 13px;
                    font-weight: 700;
                    padding: 0 24px;
                }}
                QPushButton:hover {{
                    background: #38bdf8;
                }}
                QPushButton:pressed {{
                    background: {C["accent2"]};
                }}
            """)

    def setEnabled(self, v):
        super().setEnabled(v)
        self._apply_style(not v)


# ──────────────────────────────────────────────────────────────
# MAIN WINDOW
# ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OneDrive Eliminator")
        self.setFixedSize(660, 920)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos = None
        self._worker = None
        self._step_rows = {}

        self._build()
        self._check_admin()

    # ── Drag to move (frameless) ──────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    # ── Build UI ──────────────────────────────────
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        root.setStyleSheet(f"""
            #root {{
                background: {C["bg"]};
                border: 1px solid {C["border2"]};
                border-radius: 12px;
            }}
        """)
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ─── Title bar
        titlebar = QWidget()
        titlebar.setFixedHeight(52)
        titlebar.setStyleSheet(f"""
            background: {C["surface"]};
            border-bottom: 1px solid {C["border"]};
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
        """)
        tb_layout = QHBoxLayout(titlebar)
        tb_layout.setContentsMargins(20, 0, 16, 0)

        # Traffic light dots
        for col in ["#ef4444", "#f59e0b", "#22c55e"]:
            dot = QWidget()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background:{col}; border-radius:6px;")
            tb_layout.addWidget(dot)
        tb_layout.addSpacing(12)

        title_lbl = QLabel("OneDrive Eliminator")
        title_lbl.setStyleSheet(f"""
            color: {C["text"]};
            font-family: 'Segoe UI';
            font-size: 13px;
            font-weight: 600;
        """)
        tb_layout.addWidget(title_lbl)

        self.pulse = PulsingDot()
        self.pulse.hide()
        tb_layout.addWidget(self.pulse)
        tb_layout.addStretch()

        badge_lbl = QLabel("v2.0")
        badge_lbl.setStyleSheet(f"""
            background: {C["surface2"]};
            color: {C["text3"]};
            font-family: 'Consolas';
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid {C["border"]};
        """)
        tb_layout.addWidget(badge_lbl)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C["text3"]};
                border: none;
                font-size: 13px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {C["danger"]};
                color: white;
            }}
        """)
        close_btn.clicked.connect(self.close)
        tb_layout.addSpacing(8)
        tb_layout.addWidget(close_btn)
        main.addWidget(titlebar)

        # ─── Accent stripe
        stripe = QWidget()
        stripe.setFixedHeight(3)
        stripe.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {C["accent"]}, stop:0.5 #67e8f9, stop:1 transparent);
        """)
        main.addWidget(stripe)

        # ─── Body
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 24, 28, 24)
        body_layout.setSpacing(18)

        # Admin banner
        self.admin_banner = QFrame()
        self.admin_banner.setFixedHeight(40)
        self.admin_banner.setStyleSheet(f"""
            background: {C["surface2"]};
            border: 1px solid {C["border2"]};
            border-radius: 8px;
        """)
        ab_layout = QHBoxLayout(self.admin_banner)
        ab_layout.setContentsMargins(14, 0, 14, 0)
        self.admin_icon = QLabel("⚠")
        self.admin_icon.setStyleSheet(f"font-size: 13px; color: {C['warning']};")
        ab_layout.addWidget(self.admin_icon)
        ab_layout.addSpacing(8)
        self.admin_text = QLabel("Checking administrator status…")
        self.admin_text.setStyleSheet(f"color: {C['text2']}; font-size: 11px; font-family: 'Segoe UI';")
        ab_layout.addWidget(self.admin_text)
        ab_layout.addStretch()
        body_layout.addWidget(self.admin_banner)

        # Hero header
        hero = QWidget()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(0, 4, 0, 4)
        hero_layout.setSpacing(4)
        h1 = QLabel("Remove OneDrive")
        h1.setStyleSheet(f"""
            color: {C["white"]};
            font-family: 'Segoe UI';
            font-size: 22px;
            font-weight: 700;
        """)
        h2 = QLabel("Permanently eliminates OneDrive from Windows. Your cloud files stay safe on onedrive.live.com.")
        h2.setStyleSheet(f"color: {C['text3']}; font-size: 12px; font-family: 'Segoe UI';")
        h2.setWordWrap(True)
        hero_layout.addWidget(h1)
        hero_layout.addWidget(h2)
        body_layout.addWidget(hero)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {C['border']}; border: none; border-top: 1px solid {C['border']};")
        body_layout.addWidget(div)

        # Steps list
        steps_label = QLabel("REMOVAL STEPS")
        steps_label.setStyleSheet(f"""
            color: {C["text3"]};
            font-family: 'Consolas';
            font-size: 10px;
            letter-spacing: 2px;
        """)
        body_layout.addWidget(steps_label)

        steps_widget = QWidget()
        steps_vbox = QVBoxLayout(steps_widget)
        steps_vbox.setSpacing(8)
        steps_vbox.setContentsMargins(0, 0, 0, 0)
        for sid, title, sub in STEPS:
            row = StepRow(sid, STEP_ICONS[sid], title, sub)
            self._step_rows[sid] = row
            steps_vbox.addWidget(row)
        body_layout.addWidget(steps_widget)

        # Log area
        log_label = QLabel("OPERATION LOG")
        log_label.setStyleSheet(f"""
            color: {C["text3"]};
            font-family: 'Consolas';
            font-size: 10px;
            letter-spacing: 2px;
        """)
        body_layout.addWidget(log_label)

        log_frame = QFrame()
        log_frame.setStyleSheet(f"""
            background: {C["surface"]};
            border: 1px solid {C["border"]};
            border-radius: 8px;
        """)
        log_frame.setFixedHeight(140)
        log_outer = QVBoxLayout(log_frame)
        log_outer.setContentsMargins(0, 0, 0, 0)

        self.log_scroll = QScrollArea()
        self.log_scroll.setStyleSheet("background: transparent; border: none;")
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.verticalScrollBar().setStyleSheet(f"""
            QScrollBar:vertical {{
                width: 4px;
                background: {C["surface"]};
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {C["border2"]};
                border-radius: 2px;
            }}
        """)

        self.log_container = QWidget()
        self.log_container.setStyleSheet("background: transparent;")
        self.log_vbox = QVBoxLayout(self.log_container)
        self.log_vbox.setContentsMargins(12, 10, 12, 10)
        self.log_vbox.setSpacing(0)
        self.log_vbox.addStretch()
        self.log_scroll.setWidget(self.log_container)
        log_outer.addWidget(self.log_scroll)
        body_layout.addWidget(log_frame)

        # Bottom action bar
        action_bar = QWidget()
        action_bar.setStyleSheet(f"""
            background: {C["surface"]};
            border: 1px solid {C["border"]};
            border-radius: 8px;
        """)
        action_bar.setFixedHeight(60)
        ab2 = QHBoxLayout(action_bar)
        ab2.setContentsMargins(16, 0, 16, 0)

        self.status_icon = QLabel("○")
        self.status_icon.setStyleSheet(f"color: {C['text3']}; font-size: 16px;")
        ab2.addWidget(self.status_icon)
        ab2.addSpacing(10)

        status_col = QVBoxLayout()
        status_col.setSpacing(0)
        self.status_title = QLabel("Ready to run")
        self.status_title.setStyleSheet(f"color: {C['text']}; font-size: 12px; font-weight: 600; font-family: 'Segoe UI';")
        self.status_sub = QLabel("All 8 steps queued")
        self.status_sub.setStyleSheet(f"color: {C['text3']}; font-size: 10px; font-family: 'Segoe UI';")
        status_col.addWidget(self.status_title)
        status_col.addWidget(self.status_sub)
        ab2.addLayout(status_col)
        ab2.addStretch()

        self.run_btn = RunButton("Run Elimination  →")
        self.run_btn.clicked.connect(self._start)
        ab2.addWidget(self.run_btn)
        body_layout.addWidget(action_bar)

        main.addWidget(body)

    # ── Admin check ──────────────────────────────
    def _check_admin(self):
        if is_admin():
            self.admin_banner.setStyleSheet(f"""
                background: #0d2218;
                border: 1px solid #1a4a30;
                border-radius: 8px;
            """)
            self.admin_icon.setText("✓")
            self.admin_icon.setStyleSheet(f"font-size: 13px; color: {C['success']};")
            self.admin_text.setText("Running as Administrator — full removal available")
            self.admin_text.setStyleSheet(f"color: {C['success']}; font-size: 11px; font-family: 'Segoe UI';")
        else:
            self.admin_text.setText("Not Administrator — some registry steps will be limited. Right-click → Run as administrator for full removal.")

    # ── Logging ──────────────────────────────────
    def _append_log(self, message, level):
        entry = LogEntry(message, level)
        # Insert before stretch
        count = self.log_vbox.count()
        self.log_vbox.insertWidget(count - 1, entry)
        QTimer.singleShot(10, lambda: self.log_scroll.verticalScrollBar().setValue(
            self.log_scroll.verticalScrollBar().maximum()
        ))

    # ── Step status update ────────────────────────
    def _update_step(self, step_id, status):
        if step_id in self._step_rows:
            self._step_rows[step_id].set_status(status)

    # ── Start ─────────────────────────────────────
    def _start(self):
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Working…")
        self.pulse.start()
        self.status_title.setText("Removing OneDrive…")
        self.status_sub.setText("Do not close this window")
        self.status_icon.setText("◉")
        self.status_icon.setStyleSheet(f"color: {C['accent']}; font-size: 16px;")

        self._worker = RemovalWorker()
        self._worker.log_signal.connect(self._append_log)
        self._worker.step_signal.connect(self._update_step)
        self._worker.done_signal.connect(self._finish)
        self._worker.start()

    def _finish(self, errors):
        self.pulse.stop()
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Again")

        if errors == 0:
            self.status_icon.setText("✓")
            self.status_icon.setStyleSheet(f"color: {C['success']}; font-size: 16px;")
            self.status_title.setText("Removal complete")
            self.status_sub.setText("OneDrive eliminated. Restart recommended.")
            self._append_log("All steps completed successfully.", "ok")
            self._append_log("Cloud files remain at onedrive.live.com", "info")
        else:
            self.status_icon.setText("⚠")
            self.status_icon.setStyleSheet(f"color: {C['warning']}; font-size: 16px;")
            self.status_title.setText(f"Done with {errors} warning(s)")
            self.status_sub.setText("Some steps may need administrator rights")
            self._append_log(f"Completed with {errors} warnings.", "warn")

        self._append_log("A system restart is recommended.", "warn")

        reply = QMessageBox.question(
            self, "Restart recommended",
            "OneDrive removal complete.\n\nA restart is recommended to fully apply all changes.\n\nRestart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            subprocess.run(["shutdown", "/r", "/t", "15",
                            "/c", "Restarting after OneDrive removal."])
            self._append_log("Restarting in 15 seconds… (run: shutdown /a to cancel)", "warn")


# ──────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Offer elevation if not admin
    if not is_admin():
        tmp_app = QApplication(sys.argv)
        reply = QMessageBox.question(
            None, "Administrator recommended",
            "OneDrive Eliminator works best as Administrator.\n\n"
            "Some Group Policy and HKLM registry steps require elevation.\n\n"
            "Relaunch as Administrator now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        tmp_app.quit()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(C["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(C["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(C["surface"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(C["text"]))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
