import os
import time

from PySide2.QtCore import QThread, QObject, Signal
from PySide2.QtWidgets import QWidget

from app.lib.path_lib import config_path, install_path, find_py_path
import json
from app.lib.global_var import G
from app.ui.ui_initial import Ui_Form

qss = """
QProgressBar {  
    border-radius: 5px;  
    text-align: center;  
    border: 1px solid #5CACEE;  
}  
  
QProgressBar::chunk {  
    width: 5px;   
    margin: 0.5px;  
    background-color: #1B89CA;  
}  
"""


class InitialWidget(QWidget, Ui_Form):
    def __init__(self, mainwindow):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.setStyleSheet(qss)
        self.mainwindow = mainwindow
        self.progressBar.setFixedHeight(10)
        self.thread = QThread()
        self.job = InitJob()
        self.job.sig_progress.connect(self.show_progress)
        self.job.moveToThread(self.thread)
        self.thread.started.connect(self.job.box_init)
        self.thread.start()

    def show_progress(self, pro, msg):
        self.progressBar.setValue(pro)
        self.msg.setText(msg)
        if pro == -1:
            self.mainwindow.home_handler()
            self.thread.quit()
            self.close()


class InitJob(QObject):
    sig_progress = Signal(int, str)

    def __init__(self):
        super(self.__class__, self).__init__()

    def box_init(self):
        self.sig_progress.emit(5, "正在查找Python路径..")
        py_ = find_py_path()
        self.sig_progress.emit(5, "正在加载配置..")
        if not os.path.exists(config_path):
            open(config_path, 'w')
            G.config.python_path = py_
            G.config.install_path = install_path
            G.config.to_file()
        else:
            try:
                with open(config_path, 'r')as fp:
                    G.config.update(json.load(fp))
                    G.config.python_path.update(py_)
            except Exception as e:
                os.remove(config_path)
                self.sig_progress.emit(5, "配置文件损坏")
                self.box_init()
        self.sig_progress.emit(100, "初始化完成")
        time.sleep(0.5)
        self.sig_progress.emit(-1, "")
