import webbrowser

from PySide2.QtCore import QObject, Signal, Qt
from PySide2.QtGui import QMouseEvent, QFont
from PySide2.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QProgressBar, QToolButton, QMenu, QFrame, QPushButton


class AppDivJob(QObject):
    div_signal = Signal(dict)

    def __init__(self):
        super(self.__class__, self).__init__()


class AppDiv:
    """
    +------1--------------2------------3-------------------+
    |  +--------+                   +----------------+     |
    |  |  label | --label---name--  | install|version | ⚙ |
    |  |  image |                   +-----------------+    |
    |  +--------+   --label----describe----                |
    |                     4                                |
    |  -------progressbar------------    ----progressmsg-- |
    +------------------------------------------------------+
    """

    def __init__(self, widget):
        self.widget = widget
        self.job = AppDivJob()
        self.job.div_signal.connect(self.set_progress_slot)
        self.layout = QVBoxLayout()
        self.app_layout = QHBoxLayout()
        ### 1
        self.icon = QLabel(self.widget)
        ####  2
        self.name = QLabel(self.widget)
        self.desc = MyLabel(self.widget)
        self.desc_layout = QVBoxLayout()
        self.desc_layout.addWidget(self.name)
        self.desc_layout.addWidget(self.desc)
        ####  3
        self.menu = QMenu(self.widget)
        self.action = QToolButton(self.widget)
        self.action.setPopupMode(QToolButton.MenuButtonPopup)
        self.action.setMenu(self.menu)
        #
        self.setting = QPushButton(self.widget)
        self.setting.setText("⚙")
        self.setting.setObjectName('app_setting_btn')
        self.setting.clicked.connect(self.setting_slot)
        ###
        self.app_layout.addWidget(self.icon)
        self.app_layout.addLayout(self.desc_layout)
        self.app_layout.addWidget(self.action)
        self.app_layout.addWidget(self.setting)
        self.app_layout.setStretch(0, 3)
        self.app_layout.setStretch(1, 4)
        self.app_layout.setStretch(2, 2)
        self.app_layout.setStretch(3, 1)
        ##  4
        self.progress_layout = QHBoxLayout()
        self.progressbar = QProgressBar()
        self.progressbar.setStyleSheet("""
        QProgressBar {  
    border-radius: 5px;  
    text-align: center;  
    border: 1px solid #5CACEE;  
    }  
      
    QProgressBar::chunk {  
        width: 2px;   
        margin: 0.5px;  
        background-color: #1B89CA;  
    }  
        """)
        self.progressbar.setFixedHeight(8)
        self.progressbar.setTextVisible(False)
        self.progressbar.setRange(0, 0)
        self.progressbar.setVisible(False)
        self.progress_msg = QLabel(self.widget)
        self.progress_msg.setVisible(False)
        self.progress_layout.addWidget(self.progressbar)
        self.progress_layout.addWidget(self.progress_msg)

        self.layout.addLayout(self.app_layout)
        self.layout.addLayout(self.progress_layout)

    def transfer(self, widget, func, *args):
        return {"widget": widget, "func": func, "args": args}

    def set_progress_slot(self, data):
        widget = getattr(self, data['widget'])
        func = getattr(widget, data['func'])
        func(*data['args'])

    def setting_slot(self):
        pass



class MyLabel(QLabel):
    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)
        font = QFont()
        font.setUnderline(True)
        self.setFont(font)
        self.url = None

    def mousePressEvent(self, e: QMouseEvent):
        if self.url:
            try:
                webbrowser.get('chrome').open_new_tab(self.url)
            except Exception as e:
                webbrowser.open_new_tab(self.url)
