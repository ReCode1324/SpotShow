# -*- coding: utf-8 -*-
"""
SpotShow
========

Open-source course/library frontend for SpotPlayer libraries.

Features:
- Read SpotPlayer SQLite metadata in read-only mode
- Browse courses and lessons
- Search
- Locate .spot media files
- Play ordinary media internally
- Open protected .spot media through the official SpotPlayer installation
- Export non-sensitive library metadata

SpotShow does not decrypt protected .spot files and does not access
license keys / encrypted license secrets.

License: MIT
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    Qt,
    QUrl,
    QSize,
    Signal,
    QThread,
)

from PySide6.QtGui import (
    QAction,
    QFont,
    QIcon,
    QKeySequence,
)

from PySide6.QtMultimedia import (
    QAudioOutput,
    QMediaPlayer,
)

from PySide6.QtMultimediaWidgets import (
    QVideoWidget,
)

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "SpotShow"
APP_VERSION = "0.1.0"

LOCAL_APPDATA = Path(
    os.getenv(
        "LOCALAPPDATA",
        str(Path.home())
    )
)

APP_DIR = LOCAL_APPDATA / "SpotShow"
SETTINGS_FILE = APP_DIR / "settings.json"

DEFAULT_SPOTPLAYER_DIR = (
    LOCAL_APPDATA / "SpotPlayer"
)


# ================================================================
# Models
# ================================================================

@dataclass
class Course:
    lid: bytes
    cid: bytes
    info: str
    path: str
    sync: int
    star: int
    last: int

    @property
    def title(self) -> str:
        if self.info:
            try:
                obj = json.loads(self.info)

                if isinstance(obj, dict):
                    for key in (
                        "title",
                        "name",
                        "courseName",
                        "course",
                    ):
                        value = obj.get(key)

                        if value:
                            return str(value)

            except Exception:
                pass

        if self.path:
            try:
                name = Path(self.path).name

                if name:
                    return name
            except Exception:
                pass

        return hex_blob(self.cid)[:16]


@dataclass
class Lesson:
    row_id: int
    lid: bytes
    cid: bytes
    mid: bytes
    low: int
    size: int
    name: str
    media_path: Optional[Path] = None


# ================================================================
# Helpers
# ================================================================

def hex_blob(value) -> str:
    if value is None:
        return ""

    if isinstance(value, memoryview):
        value = value.tobytes()

    if isinstance(value, bytes):
        return value.hex()

    return str(value)


def human_size(value: int) -> str:
    try:
        size = float(value)
    except Exception:
        return "-"

    units = ["B", "KB", "MB", "GB", "TB"]

    for unit in units:
        if size < 1024:
            return (
                f"{size:.0f} {unit}"
                if unit == "B"
                else f"{size:.2f} {unit}"
            )

        size /= 1024

    return f"{size:.2f} PB"


def load_json(path: Path) -> dict:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}


def save_json(path: Path, data: dict):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ================================================================
# SQLite
# ================================================================

class SpotDatabase:

    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self):
        uri = self.path.resolve().as_uri()

        return sqlite3.connect(
            uri + "?mode=ro",
            uri=True,
        )

    def courses(self) -> list[Course]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT
                    lid,
                    cid,
                    info,
                    path,
                    sync,
                    star,
                    last
                FROM courses
                ORDER BY
                    COALESCE(last, 0) DESC
                """
            ).fetchall()

        return [
            Course(
                lid=row[0],
                cid=row[1],
                info=row[2] or "",
                path=row[3] or "",
                sync=row[4] or 0,
                star=row[5] or 0,
                last=row[6] or 0,
            )
            for row in rows
        ]

    def lessons(
        self,
        course: Course,
    ) -> list[Lesson]:

        with self.connect() as db:
            rows = db.execute(
                """
                SELECT
                    id,
                    lid,
                    cid,
                    mid,
                    low,
                    size,
                    name
                FROM downloads
                WHERE lid = ? AND cid = ?
                ORDER BY id
                """,
                (
                    course.lid,
                    course.cid,
                )
            ).fetchall()

        return [
            Lesson(
                row_id=row[0],
                lid=row[1],
                cid=row[2],
                mid=row[3],
                low=row[4] or 0,
                size=row[5] or 0,
                name=row[6] or "Untitled",
            )
            for row in rows
        ]


# ================================================================
# Scanner
# ================================================================

class ScanThread(QThread):

    completed = Signal(dict)

    def __init__(self, roots: list[Path]):
        super().__init__()

        self.roots = roots

    def run(self):
        mapping = {}

        visited = set()

        for root in self.roots:
            try:
                root = Path(root)

                if not root.exists():
                    continue

                resolved = str(
                    root.resolve()
                ).lower()

                if resolved in visited:
                    continue

                visited.add(resolved)

                if root.is_file():

                    if root.suffix.lower() == ".spot":
                        mapping[
                            root.stem.lower()
                        ] = root

                    continue

                for media in root.rglob("*.spot"):
                    mapping[
                        media.stem.lower()
                    ] = media

            except Exception:
                continue

        self.completed.emit(mapping)


# ================================================================
# Styling
# ================================================================

STYLE = """
QMainWindow, QWidget {
    background: #0d1117;
    color: #e6edf3;
    font-family: "Segoe UI";
    font-size: 13px;
}

QToolBar {
    background: #161b22;
    border-bottom: 1px solid #30363d;
    spacing: 8px;
    padding: 8px;
}

QLineEdit, QComboBox {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 8px 12px;
    color: #e6edf3;
}

QLineEdit:focus {
    border: 1px solid #58a6ff;
}

QListWidget {
    background: #0d1117;
    border: none;
    outline: none;
}

QListWidget::item {
    border-radius: 10px;
    padding: 10px;
    margin: 2px 4px;
}

QListWidget::item:selected {
    background: #1f6feb;
    color: white;
}

QPushButton {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 8px 14px;
}

QPushButton:hover {
    background: #30363d;
}

QPushButton#primaryButton {
    background: #238636;
    border-color: #2ea043;
    font-weight: 600;
}

QPushButton#primaryButton:hover {
    background: #2ea043;
}

QFrame#card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 14px;
}

QSlider::groove:horizontal {
    height: 5px;
    background: #30363d;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #58a6ff;
    border-radius: 7px;
}
"""


# ================================================================
# Main application
# ================================================================

class SpotShow(QMainWindow):

    def __init__(self):
        super().__init__()

        APP_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.settings = load_json(
            SETTINGS_FILE
        )

        self.database: Optional[
            SpotDatabase
        ] = None

        self.courses: list[
            Course
        ] = []

        self.filtered_courses: list[
            Course
        ] = []

        self.lessons: list[
            Lesson
        ] = []

        self.media_map = {}

        self.scan_thread = None

        self.player = QMediaPlayer(
            self
        )

        self.audio_output = QAudioOutput(
            self
        )

        self.player.setAudioOutput(
            self.audio_output
        )

        self.audio_output.setVolume(
            0.75
        )

        self.build_ui()
        self.restore_library()

    # ------------------------------------------------------------
    # UI
    # ------------------------------------------------------------

    def build_ui(self):

        self.setWindowTitle(
            f"{APP_NAME} {APP_VERSION}"
        )

        self.resize(
            1420,
            860
        )

        self.setMinimumSize(
            1000,
            650
        )

        self.setStyleSheet(
            STYLE
        )

        toolbar = QToolBar()

        toolbar.setMovable(
            False
        )

        self.addToolBar(
            toolbar
        )

        logo = QLabel(
            "  ◉ SpotShow  "
        )

        logo_font = QFont()
        logo_font.setPointSize(17)
        logo_font.setBold(True)

        logo.setFont(
            logo_font
        )

        toolbar.addWidget(
            logo
        )

        toolbar.addSeparator()

        open_db = QAction(
            "Open Library",
            self
        )

        open_db.triggered.connect(
            self.choose_database
        )

        toolbar.addAction(
            open_db
        )

        choose_root = QAction(
            "Media Folder",
            self
        )

        choose_root.triggered.connect(
            self.choose_media_root
        )

        toolbar.addAction(
            choose_root
        )

        toolbar.addSeparator()

        self.search = QLineEdit()

        self.search.setPlaceholderText(
            "Search courses..."
        )

        self.search.setMaximumWidth(
            360
        )

        self.search.textChanged.connect(
            self.filter_courses
        )

        toolbar.addWidget(
            self.search
        )

        container = QWidget()

        layout = QVBoxLayout(
            container
        )

        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        splitter = QSplitter(
            Qt.Horizontal
        )

        layout.addWidget(
            splitter
        )

        # Left pane

        left = QFrame()
        left.setObjectName(
            "card"
        )

        left_layout = QVBoxLayout(
            left
        )

        title = QLabel(
            "Courses"
        )

        f = title.font()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)

        left_layout.addWidget(
            title
        )

        self.course_list = QListWidget()

        self.course_list.currentRowChanged.connect(
            self.course_selected
        )

        left_layout.addWidget(
            self.course_list
        )

        splitter.addWidget(
            left
        )

        # Center pane

        center = QFrame()
        center.setObjectName(
            "card"
        )

        center_layout = QVBoxLayout(
            center
        )

        self.course_title = QLabel(
            "Select a course"
        )

        f = self.course_title.font()
        f.setPointSize(18)
        f.setBold(True)

        self.course_title.setFont(
            f
        )

        center_layout.addWidget(
            self.course_title
        )

        self.course_meta = QLabel()

        self.course_meta.setStyleSheet(
            "color:#8b949e"
        )

        center_layout.addWidget(
            self.course_meta
        )

        self.lesson_list = QListWidget()

        self.lesson_list.itemDoubleClicked.connect(
            lambda _: self.play_selected()
        )

        center_layout.addWidget(
            self.lesson_list
        )

        controls = QHBoxLayout()

        self.play_button = QPushButton(
            "▶ Play"
        )

        self.play_button.setObjectName(
            "primaryButton"
        )

        self.play_button.clicked.connect(
            self.play_selected
        )

        controls.addWidget(
            self.play_button
        )

        folder_button = QPushButton(
            "Open Folder"
        )

        folder_button.clicked.connect(
            self.open_media_folder
        )

        controls.addWidget(
            folder_button
        )

        controls.addStretch()

        center_layout.addLayout(
            controls
        )

        splitter.addWidget(
            center
        )

        # Right pane / player

        right = QFrame()

        right.setObjectName(
            "card"
        )

        right_layout = QVBoxLayout(
            right
        )

        player_title = QLabel(
            "Player"
        )

        f = player_title.font()
        f.setPointSize(15)
        f.setBold(True)

        player_title.setFont(
            f
        )

        right_layout.addWidget(
            player_title
        )

        self.video = QVideoWidget()

        self.video.setMinimumSize(
            QSize(420, 240)
        )

        self.video.setStyleSheet(
            "background:black;border-radius:10px;"
        )

        self.player.setVideoOutput(
            self.video
        )

        right_layout.addWidget(
            self.video,
            1
        )

        self.now_playing = QLabel(
            "Nothing playing"
        )

        self.now_playing.setWordWrap(
            True
        )

        right_layout.addWidget(
            self.now_playing
        )

        self.position = QSlider(
            Qt.Horizontal
        )

        self.position.setRange(
            0,
            0
        )

        self.position.sliderMoved.connect(
            self.player.setPosition
        )

        right_layout.addWidget(
            self.position
        )

        media_controls = QHBoxLayout()

        pause = QPushButton(
            "Play / Pause"
        )

        pause.clicked.connect(
            self.toggle_playback
        )

        media_controls.addWidget(
            pause
        )

        stop = QPushButton(
            "Stop"
        )

        stop.clicked.connect(
            self.player.stop
        )

        media_controls.addWidget(
            stop
        )

        self.volume = QSlider(
            Qt.Horizontal
        )

        self.volume.setRange(
            0,
            100
        )

        self.volume.setValue(
            75
        )

        self.volume.valueChanged.connect(
            lambda v:
                self.audio_output.setVolume(
                    v / 100
                )
        )

        media_controls.addWidget(
            self.volume
        )

        right_layout.addLayout(
            media_controls
        )

        self.player.positionChanged.connect(
            self.on_position
        )

        self.player.durationChanged.connect(
            self.on_duration
        )

        splitter.addWidget(
            right
        )

        splitter.setSizes(
            [300, 500, 500]
        )

        self.setCentralWidget(
            container
        )

        self.statusBar().showMessage(
            "SpotShow ready"
        )

    # ------------------------------------------------------------
    # Database
    # ------------------------------------------------------------

    def restore_library(self):

        path = self.settings.get(
            "database"
        )

        if path and Path(path).exists():
            self.load_database(
                Path(path)
            )

        elif (
            DEFAULT_SPOTPLAYER_DIR
            / "sp5.db"
        ).exists():

            self.load_database(
                DEFAULT_SPOTPLAYER_DIR
                / "sp5.db"
            )

    def choose_database(self):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open SpotPlayer database",
            str(DEFAULT_SPOTPLAYER_DIR),
            "SQLite (*.db);;All Files (*)",
        )

        if filename:
            self.load_database(
                Path(filename)
            )

    def load_database(
        self,
        path: Path,
    ):

        try:
            db = SpotDatabase(
                path
            )

            courses = db.courses()

        except Exception as exc:
            QMessageBox.critical(
                self,
                APP_NAME,
                str(exc),
            )

            return

        self.database = db
        self.courses = courses

        self.settings[
            "database"
        ] = str(path)

        save_json(
            SETTINGS_FILE,
            self.settings
        )

        self.filter_courses()

        self.statusBar().showMessage(
            f"{len(courses)} courses loaded"
        )

        self.start_media_scan()

    # ------------------------------------------------------------
    # Courses
    # ------------------------------------------------------------

    def filter_courses(self):

        query = (
            self.search.text()
            .strip()
            .lower()
        )

        if not query:
            self.filtered_courses = (
                list(self.courses)
            )

        else:
            self.filtered_courses = [
                course
                for course in self.courses
                if query
                in (
                    course.title
                    + " "
                    + course.info
                    + " "
                    + course.path
                ).lower()
            ]

        self.course_list.clear()

        for course in (
            self.filtered_courses
        ):

            label = course.title

            if course.star:
                label = "★ " + label

            item = QListWidgetItem(
                label
            )

            item.setToolTip(
                course.path
            )

            self.course_list.addItem(
                item
            )

    def course_selected(
        self,
        index: int,
    ):

        if (
            index < 0
            or index
            >= len(
                self.filtered_courses
            )
        ):
            return

        course = (
            self.filtered_courses[
                index
            ]
        )

        self.course_title.setText(
            course.title
        )

        self.course_meta.setText(
            f"CID: {hex_blob(course.cid)}"
        )

        if not self.database:
            return

        try:
            self.lessons = (
                self.database.lessons(
                    course
                )
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                APP_NAME,
                str(exc),
            )

            return

        self.resolve_lessons()
        self.render_lessons()

    # ------------------------------------------------------------
    # Lessons
    # ------------------------------------------------------------

    def resolve_lessons(self):

        for lesson in self.lessons:

            mid = hex_blob(
                lesson.mid
            ).lower()

            lesson.media_path = (
                self.media_map.get(mid)
            )

    def render_lessons(self):

        self.lesson_list.clear()

        for lesson in self.lessons:

            status = (
                "●"
                if lesson.media_path
                else "○"
            )

            text = (
                f"{status}  {lesson.name}\n"
                f"     {human_size(lesson.size)}"
            )

            item = QListWidgetItem(
                text
            )

            if lesson.media_path:
                item.setToolTip(
                    str(
                        lesson.media_path
                    )
                )

            self.lesson_list.addItem(
                item
            )

    def selected_lesson(
        self,
    ) -> Optional[Lesson]:

        index = (
            self.lesson_list.currentRow()
        )

        if (
            index < 0
            or index
            >= len(self.lessons)
        ):
            return None

        return self.lessons[
            index
        ]

    # ------------------------------------------------------------
    # Media scan
    # ------------------------------------------------------------

    def choose_media_root(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose media directory",
            self.settings.get(
                "media_root",
                str(
                    DEFAULT_SPOTPLAYER_DIR
                ),
            ),
        )

        if not folder:
            return

        self.settings[
            "media_root"
        ] = folder

        save_json(
            SETTINGS_FILE,
            self.settings
        )

        self.start_media_scan()

    def start_media_scan(self):

        roots = [
            DEFAULT_SPOTPLAYER_DIR
        ]

        root = self.settings.get(
            "media_root"
        )

        if root:
            roots.append(
                Path(root)
            )

        self.statusBar().showMessage(
            "Scanning .spot files..."
        )

        self.scan_thread = ScanThread(
            roots
        )

        self.scan_thread.completed.connect(
            self.scan_finished
        )

        self.scan_thread.start()

    def scan_finished(
        self,
        mapping: dict,
    ):

        self.media_map = mapping

        self.resolve_lessons()
        self.render_lessons()

        self.statusBar().showMessage(
            f"{len(mapping)} .spot files indexed"
        )

    # ------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------

    def play_selected(self):

        lesson = self.selected_lesson()

        if not lesson:
            return

        if not lesson.media_path:
            QMessageBox.information(
                self,
                APP_NAME,
                "Media file not found.",
            )

            return

        path = lesson.media_path

        if (
            path.suffix.lower()
            == ".spot"
        ):
            self.launch_official_player(
                path
            )

            return

        self.play_standard_media(
            path
        )

    def play_standard_media(
        self,
        path: Path,
    ):

        self.now_playing.setText(
            path.name
        )

        self.player.setSource(
            QUrl.fromLocalFile(
                str(path)
            )
        )

        self.player.play()

    def launch_official_player(
        self,
        path: Path,
    ):

        exe = self.find_spotplayer()

        try:

            if exe:
                subprocess.Popen(
                    [
                        str(exe),
                        str(path),
                    ]
                )

            else:
                os.startfile(
                    str(path)
                )

            self.now_playing.setText(
                "Opened with SpotPlayer:\n"
                + path.name
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                APP_NAME,
                f"Could not open media:\n{exc}",
            )

    def find_spotplayer(
        self,
    ) -> Optional[Path]:

        configured = (
            self.settings.get(
                "spotplayer_exe"
            )
        )

        candidates = []

        if configured:
            candidates.append(
                Path(configured)
            )

        candidates.extend(
            [
                DEFAULT_SPOTPLAYER_DIR
                / "SpotPlayer.exe",

                Path(
                    r"C:\Program Files\SpotPlayer\SpotPlayer.exe"
                ),

                Path(
                    r"C:\Program Files (x86)\SpotPlayer\SpotPlayer.exe"
                ),
            ]
        )

        for path in candidates:

            if path.exists():
                return path

        return None

    def toggle_playback(self):

        if (
            self.player.playbackState()
            == QMediaPlayer.PlayingState
        ):
            self.player.pause()
        else:
            self.player.play()

    def on_position(
        self,
        value: int,
    ):

        if not self.position.isSliderDown():
            self.position.setValue(
                value
            )

    def on_duration(
        self,
        value: int,
    ):

        self.position.setRange(
            0,
            value
        )

    # ------------------------------------------------------------
    # Explorer
    # ------------------------------------------------------------

    def open_media_folder(self):

        lesson = self.selected_lesson()

        if (
            not lesson
            or not lesson.media_path
        ):
            return

        try:
            subprocess.Popen(
                [
                    "explorer.exe",
                    "/select,",
                    str(
                        lesson.media_path
                    ),
                ]
            )
        except Exception:
            pass


# ================================================================
# Entrypoint
# ================================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setApplicationVersion(
        APP_VERSION
    )

    window = SpotShow()

    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
