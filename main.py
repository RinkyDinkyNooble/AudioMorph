from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QLabel,
    QHBoxLayout, QPushButton, QComboBox, QStatusBar, QFileDialog, QProgressBar,
    QLineEdit, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import QThread, pyqtSignal, QRegularExpression, Qt
from PyQt6.QtGui import QRegularExpressionValidator, QIcon
import sys
import os
import subprocess
import threading
from yt_dlp import YoutubeDL

#----------------------------------------------------------------------#------#

if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

FFMPEG_PATH = os.path.join(BASE_PATH, "assets", "ffmpeg", "bin", "ffmpeg.exe")
FFPROBE_PATH = os.path.join(
    BASE_PATH, "assets", "ffmpeg", "bin", "ffprobe.exe"
)

AUDIO_FORMATS = (
    "aac", "aiff", "flac", "mp3", "m4a", "ogg", "wav"
)
filter_parts = []
for format in AUDIO_FORMATS:
    description = format.upper() + " Files"
    pattern = f"*.{format}"
    filter_parts.append(f"{description} ({pattern})")
AUDIO_FORMATS_FILTER = (
    f"All Files (*);;{";;".join(filter_parts)}"
)

if os.name == 'nt':
    DOWNLOADS_DIRECTORY = os.path.join(os.environ['USERPROFILE'], 'Downloads')
elif os.name == 'posix':
    DOWNLOADS_DIRECTORY =  os.path.join(os.path.expanduser('~'), 'Downloads')
else:
    DOWNLOADS_DIRECTORY = ""

BORDER_COLOR = "rgb(255, 255, 255)"
BORDER_SIZE = "2px"
BACKGROUND_COLOR = "rgb(58, 58, 58)"
SECONDARY_COLOR = "rgb(46, 46, 46)"
BORDER_RADIUS = "7px"
FOCUS_BORDER_SIZE = "3px"
FOCUS_COLOR = "rgb(137, 207, 240)"

#----------------------------------------------------------------------#------#

class ShadowEffect(QGraphicsDropShadowEffect):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setBlurRadius(10)
        self.setOffset(2, 4)
        self.setColor(Qt.GlobalColor.black)


class SelectFile(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.selected_file_path = ""
        self.selected_file_name = ""

        self.DEFAULT_LABEL_TEXT = "Drag and Drop a File or"
        self.DEFAULT_BUTTON_TEXT = "Browse Files"

        self.setAcceptDrops(True)
        self.setFixedHeight(300)

        # Horizontal Layout
        self.file_drop_layout = QHBoxLayout()
        self.setLayout(self.file_drop_layout)
        self.file_drop_layout.addStretch(1)

        # File Drop Label
        self.file_drop_label = QLabel(self)
        self.file_drop_label.setText(self.DEFAULT_LABEL_TEXT)
        self.file_drop_layout.addWidget(self.file_drop_label)

        # Browse Files Button
        self.browse_files = QPushButton(self)
        self.browse_files.setGraphicsEffect(ShadowEffect())
        self.browse_files.setText(self.DEFAULT_BUTTON_TEXT)
        self.browse_files.clicked.connect(self.select_file)
        self.file_drop_layout.addWidget(self.browse_files)
        self.file_drop_layout.addStretch(1)

    def compare_selected_file(self, file_path: str):
        self.selected_file_name = os.path.basename(file_path)
        self.selected_file_path = file_path
        if file_path == "":
            self.file_drop_label.setText(self.DEFAULT_LABEL_TEXT)
            self.browse_files.setText(self.DEFAULT_BUTTON_TEXT)
        else:
            self.file_drop_label.setText(self.selected_file_name)
            self.browse_files.setText("Change Selected File")

    def select_file(self):
        global AUDIO_FORMATS_FILTER
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select an Audio File", filter=AUDIO_FORMATS_FILTER
        )
        self.compare_selected_file(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if os.path.isdir(event.mimeData().urls()[0].toLocalFile()):
                event.ignore()
            else:
                event.acceptProposedAction()

    def dropEvent(self, event):
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.compare_selected_file(file_path)
        

class Execute(QThread):
    success = pyqtSignal(bool)

    def __init__(self, parent, process: callable, keyword_arguments: dict):
        super().__init__(parent)
        self.process = process
        self.keyword_arguments = keyword_arguments
    
    def run(self):
        try:
            self.process(**self.keyword_arguments)
            self.success.emit(True)
        except Exception:
            self.success.emit(False)


class AudioConverter(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("AudioConverter")
        self.DURATION = 6000
        self.CONVERT_TEXT = "Convert"
        self.DIRECTORY_TEXT = "Select Output Directory"
        if (
            os.path.exists(DOWNLOADS_DIRECTORY) 
            and os.path.isdir(DOWNLOADS_DIRECTORY)
        ):
            self.selected_output_directory_path = DOWNLOADS_DIRECTORY
            self.selected_output_directory_name = os.path.basename(
                DOWNLOADS_DIRECTORY
            )
        else:
            self.selected_output_directory_path = ""
            self.selected_output_directory_name = ""

        # Base Vertical Layout
        self.base_layout = QVBoxLayout()
        self.setLayout(self.base_layout)

        # File Drop
        self.file_drop = SelectFile(self)
        self.base_layout.addWidget(self.file_drop)

        # Format Horizontal Layout
        self.format_layout = QHBoxLayout()
        self.base_layout.addLayout(self.format_layout)
        self.format_layout.addStretch(1)

        # Format Label
        self.format_label = QLabel("Output Format:", self)
        self.format_layout.addWidget(self.format_label)

        # Format Combo Box
        self.format_select = QComboBox(self)
        self.format_select.setEditable(True)
        self.format_select.setFixedHeight(30)
        self.format_select.addItems(AUDIO_FORMATS)
        self.format_layout.addWidget(self.format_select)
        self.format_layout.addStretch(1)

        # Directory Horizontal Layout
        self.directory_layout = QHBoxLayout()
        self.base_layout.addLayout(self.directory_layout)
        self.directory_layout.addStretch(1)

        # Directory Select Button
        if self.selected_output_directory_path != "":
            name = self.selected_output_directory_path.replace("\\", "/")
        else:
            name = self.DIRECTORY_TEXT
        self.directory_select_button = QPushButton(name, self)
        self.directory_select_button.setGraphicsEffect(ShadowEffect())
        self.directory_select_button.clicked.connect(self.select_directory)
        self.directory_layout.addWidget(self.directory_select_button)
        self.directory_layout.addStretch(1)

        self.base_layout.addStretch(1)

        # Convert Horizontal Layout
        self.convert_layout = QHBoxLayout()
        self.base_layout.addLayout(self.convert_layout)
        self.convert_layout.addStretch(1)

        # Convert Button
        self.convert_button = QPushButton(self.CONVERT_TEXT, self)
        self.convert_button.setGraphicsEffect(ShadowEffect())
        self.convert_button.clicked.connect(self.convert)
        self.convert_layout.addWidget(self.convert_button)
        self.convert_layout.addStretch(1)

        # Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.base_layout.addWidget(self.progress_bar)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.base_layout.addWidget(self.status_bar)

    def select_directory(self):
        file_path = QFileDialog.getExistingDirectory(
            self, "Select a Directory"
        )
        self.selected_output_directory_path = file_path
        self.selected_output_directory_name = os.path.basename(file_path)
        if file_path == "":
            self.directory_select_button.setText(self.DIRECTORY_TEXT)
        else:
            self.directory_select_button.setText(file_path.replace("\\", "/"))
        
    def on_complete(self, success: bool):
        if success:
            self.status_bar.showMessage(
                "Successfully Converted", self.DURATION
            )
        else:
            self.status_bar.showMessage(
                "ERROR: 1) Validate your file. 2) Validate your format. "
                + "3) Validate your directory. 4) Ensure FFmpeg compatibility",
                self.DURATION
            )
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.convert_thread = None
        self.convert_button.setVisible(True)
    
    def run_command(self, input_file: str, output_file: str):
        result = subprocess.run([
                FFPROBE_PATH, "-show_entries", "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", input_file
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        total_length_ms = float(result.stdout.strip())*1000000
        process = None
        event = threading.Event()

        def run():
            nonlocal process
            process = subprocess.Popen([
                    FFMPEG_PATH, '-i', input_file, "-progress", "pipe:1", 
                    "-stats_period", "0.05", "-loglevel", "-8", "-y", 
                    output_file
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            event.set()

        thread = threading.Thread(target=run)
        thread.start()
        event.wait()
        for lines in process.stdout:
            line = lines.strip().split("=")
            if line[0] == "out_time_ms":
                self.progress_bar.setValue(
                    int((int(line[1])/total_length_ms)*100)
                )
        if not os.path.exists(output_file):
            raise Exception

    def convert(self):
        if self.file_drop.selected_file_path == "":
            self.status_bar.showMessage("Select a file", self.DURATION)
            return
        if self.format_select.currentText() == "":
            self.status_bar.showMessage("Select a format", self.DURATION)
            return
        if self.selected_output_directory_path == "":
            self.status_bar.showMessage("Select a directory", self.DURATION)
            return
        self.convert_button.setVisible(False)
        self.progress_bar.setVisible(True)
        file_name_without_extension = os.path.splitext(
            self.file_drop.selected_file_name
        )[0]
        output_file_path = os.path.join(
            self.selected_output_directory_path, 
            f"{file_name_without_extension}.{self.format_select.currentText()}"
        )
        output_file_path = output_file_path.replace("\\", "/")
        self.convert_thread = Execute(self, self.run_command, {
            "input_file": self.file_drop.selected_file_path,
            "output_file": output_file_path
        })
        self.convert_thread.success.connect(self.on_complete)
        self.convert_thread.start()


class MyLogger:
    def debug(self, msg):
        pass
    def info(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass


class YouTubeDownloader(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.OUTPUT_FORMAT = "flac"
        self.DURATION = 6000
        self.DOWNLOAD_TEXT = "Download"
        self.DIRECTORY_TEXT = "Select Output Directory"
        if (
            os.path.exists(DOWNLOADS_DIRECTORY) 
            and os.path.isdir(DOWNLOADS_DIRECTORY)
        ):
            self.selected_output_directory_path = DOWNLOADS_DIRECTORY
            self.selected_output_directory_name = os.path.basename(
                DOWNLOADS_DIRECTORY
            )
        else:
            self.selected_output_directory_path = ""
            self.selected_output_directory_name = ""

        # Base Vertical Layout
        self.base_layout = QVBoxLayout()
        self.setLayout(self.base_layout)
        self.base_layout.addStretch(1)

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Enter a YouTube video link.")
        self.base_layout.addWidget(self.line_edit)

        # Directory Horizontal Layout
        self.directory_layout = QHBoxLayout()
        self.base_layout.addLayout(self.directory_layout)
        self.directory_layout.addStretch(1)

        # Directory Select Button
        if self.selected_output_directory_path != "":
            name = self.selected_output_directory_path.replace("\\", "/") + "/"
        else:
            name = self.DIRECTORY_TEXT
        self.directory_select_button = QPushButton(name, self)
        self.directory_select_button.setGraphicsEffect(ShadowEffect())
        self.directory_select_button.clicked.connect(self.select_directory)
        self.directory_layout.addWidget(self.directory_select_button)

        # File Name Line Edit
        self.file_name = QLineEdit(self)
        self.file_name.setValidator(
            QRegularExpressionValidator(
                QRegularExpression(
                    "^[a-zA-Z0-9 _\\-\\.\\+\\=\\(\\)\\{\\}\\[\\]#&^!]*$"
                )
            )
        )
        self.directory_layout.addWidget(self.file_name)

        # File Extension Label
        self.file_extension_label = QLabel("." + self.OUTPUT_FORMAT, self)
        self.directory_layout.addWidget(self.file_extension_label)
        self.directory_layout.addStretch(1)

        self.base_layout.addStretch(1)

        # Download Horizontal Layout
        self.download_layout = QHBoxLayout()
        self.base_layout.addLayout(self.download_layout)
        self.download_layout.addStretch(1)

        # Download Button
        self.download_button = QPushButton(self.DOWNLOAD_TEXT, self)
        self.download_button.setGraphicsEffect(ShadowEffect())
        self.download_button.clicked.connect(self.download)
        self.download_layout.addWidget(self.download_button)
        self.download_layout.addStretch(1)

        # Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.base_layout.addWidget(self.progress_bar)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.base_layout.addWidget(self.status_bar)
    
    def select_directory(self):
        file_path = QFileDialog.getExistingDirectory(
            self, "Select a Directory"
        )
        self.selected_output_directory_path = file_path
        self.selected_output_directory_name = os.path.basename(file_path)
        if file_path == "":
            self.directory_select_button.setText(self.DIRECTORY_TEXT)
        else:
            self.directory_select_button.setText(
                file_path.replace("\\", "/") + "/"
            )

    def on_complete(self, success: bool):
        if success:
            self.status_bar.showMessage(
                "Successfully Downloaded", self.DURATION
            )
        else:
            self.status_bar.showMessage(
                "ERROR: 1) Verify your internet connection. "
                + "2) Validate the YouTube URL. "
                + "3) Verify application permissions. "
                + "4) Retry after completing 1, 2, 3. "
                + "5) It may be a bug. Move on.", self.DURATION
            )
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.download_thread = None
        self.download_button.setVisible(True)

    def run_command(self, url: str, output_file_path: str): 
        def progress_hook(download):
            if download['status'] == 'downloading':
                self.progress_bar.setValue(
                    int(
                        download["downloaded_bytes"] * 100
                        / download["total_bytes"]
                    )
                )

        download_options = {
            "progress_hooks": [progress_hook],
            "format": "bestaudio/best",
            "outtmpl": output_file_path + ".%(ext)s",
            "ffmpeg_location": FFMPEG_PATH,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": self.OUTPUT_FORMAT,
                "preferredquality": "0",
            }],
            "quiet": True,
            "no_warnings": True,
            "logtostderr": True, 
            "logger": MyLogger(),
            "noplaylist": True
        }
        with YoutubeDL(download_options) as downloader:
            downloader.download([url])

        if not os.path.exists(output_file_path + ".flac"):
            raise Exception

    def download(self):
        if self.line_edit.text() == "":
            self.status_bar.showMessage("Type in a link", self.DURATION)
            return
        if self.selected_output_directory_path == "":
            self.status_bar.showMessage("Select a directory", self.DURATION)
            return
        if self.file_name.text() == "":
            self.status_bar.showMessage("Type in a name", self.DURATION)
            return
        self.download_button.setVisible(False)
        self.progress_bar.setVisible(True)
        output_file_path = self.selected_output_directory_path.replace(
            "\\", "/"
        )
        full_output_path = f"{output_file_path}/{self.file_name.text()}"
        existing_name = f"{full_output_path}.{self.OUTPUT_FORMAT}"
        if os.path.exists(existing_name):
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            self.download_button.setVisible(True)
            self.status_bar.showMessage(
                f"File already exists: {existing_name}", self.DURATION
            )
            return
        self.download_thread = Execute(self, self.run_command, {
            "url": self.line_edit.text(),
            "output_file_path": full_output_path,
        })
        self.download_thread.success.connect(self.on_complete)
        self.download_thread.start()


class AudioMorph(QApplication):
    def __init__(self, argv):
        super().__init__(argv)

        # Main Window
        self.main_window = QMainWindow()
        self.main_window.setWindowTitle("AudioMorph")
        self.main_window.setMinimumSize(400, 500)
        self.setWindowIcon(
            QIcon(os.path.join(BASE_PATH, "assets", "Icon.png"))
        )

        # Tab Widget
        self.tabs = QTabWidget(self.main_window)
        self.main_window.setCentralWidget(self.tabs)
        
        # Audio Converter Widget
        self.audio_converter_tab = AudioConverter(self.tabs)
        self.tabs.addTab(self.audio_converter_tab, "Audio Converter")

        # YouTube Audio Downloader
        self.YouTube_downloader = YouTubeDownloader(self.tabs)
        self.tabs.addTab(self.YouTube_downloader, "YouTube Downloader")

        self.main_window.setStyleSheet(f"""
            QTabBar::tab {{
                background-color: {SECONDARY_COLOR}; 
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS};
                padding: 5px;
                font-weight: bold;
                font-size: 16px; 
            }}
            QTabBar::tab:focus {{
                border: {FOCUS_BORDER_SIZE} solid {FOCUS_COLOR};
                outline: none;
            }}

            QTabBar::tab:selected {{
                background-color: {BACKGROUND_COLOR};
                border-bottom: 0px;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: 0px;
                padding-left: 15px;
                padding-right: 15px;
            }}

            QTabBar::tab:hover {{
                background-color:rgb(255, 255, 255);
                color: rgb(0, 0, 0);
            }}

            QWidget {{
                background-color: {BACKGROUND_COLOR};
                font-family: 'Dancing Script', 'Pacifico', cursive;
                font-size: 12px;
            }}

            QPushButton {{
                background-color: {SECONDARY_COLOR};
                border: {BORDER_SIZE} solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS};
                padding: 5px;
            }}

            QPushButton:hover {{
                background-color:rgb(255, 255, 255);
                color: rgb(0, 0, 0);
            }}

            QPushButton:focus {{
                border: {FOCUS_BORDER_SIZE} solid {FOCUS_COLOR};
                outline: none;
            }}

            QLineEdit {{
                padding: 5px;
                font-family: 'Dancing Script', 'Pacifico', cursive;
                font-size: 12px;
            }}

            QLineEdit:focus {{
                border: {FOCUS_BORDER_SIZE} solid {FOCUS_COLOR};
                outline: none;
            }}

            QComboBox:focus {{
                border: {FOCUS_BORDER_SIZE} solid {FOCUS_COLOR};
                outline: none;
            }}
        """)
        self.main_window.show()


#----------------------------------------------------------------------#------#
 
if __name__ == "__main__":
    sys.exit(AudioMorph(sys.argv).exec())