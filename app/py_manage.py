import os
import subprocess

from PySide2.QtCore import QThreadPool, QObject, Signal, Slot, Qt, QUrl, QProcess
from PySide2.QtGui import QDesktopServices
from PySide2.QtWidgets import QWidget, QFileDialog, QTableWidgetItem, QAbstractItemView, QMessageBox, QTableWidget, \
    QDialog, QMenu

from app.lib.global_var import G
from app.lib.path_lib import get_py_version, join_path, venv_path, py_path_check
from app.progressmsg import ProgressMsgDialog
from app.tip import TipDialog
from app.ui import qss
from app.ui.ui_py_manage import Ui_Form
from app.ui.ui_interpretes import Ui_Interpreters
from app.ui.ui_new_env import Ui_NewEnv
from app.ui.ui_modify_env import Ui_Modify
from app.honey.worker import Worker


class PyManageWidget(QWidget, Ui_Form):
    """python解释器以及pip包"""

    def __init__(self, home, app_name=None):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.setStyleSheet(qss)
        self.home = home
        self.interpreter = None
        self.p = QProcess()
        self.thread_pool = QThreadPool()
        # btn
        self.py_setting_btn.clicked.connect(self.py_setting_slot)
        self.set_app_py.clicked.connect(self.set_app_py_slot)
        #
        self.py_box.currentTextChanged.connect(self.py_change_slot)
        self.pip_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pip_list.customContextMenuRequested.connect(self.generate_menu)  ####右键菜单
        #
        self.load_py()
        if not app_name:
            """用于设置窗口"""
            self.app_name.hide()
            self.set_app_py.hide()
            self.cur_py.hide()
            self.label_3.hide()
        else:
            """用于应用窗口"""
            self.app_name.setText(app_name)
            self.app_name.setStyleSheet("""color:#BE9117""")
            self.cur_py.setStyleSheet("""color:#168AD5""")
            path = G.config.installed_apps[app_name].get('py_', '未选择')
            for name, p in G.config.python_path.items():
                if path == p:
                    self.cur_py.setText(name)
                else:
                    self.cur_py.setText(path)

    def load_py(self):
        """加载PY列表"""
        self.py_box.clear()
        for k, v in G.config.python_path.items():
            self.py_box.addItem(k)

    def load_pip(self, py_):
        """加载pip包列表"""
        self.pip_list.clear()
        # self.p.readyReadStandardOutput.connect(self.readout)
        self.p.finished.connect(self.pip_finish_slot)
        self.p.start(' '.join([py_, '-m', 'pip', 'freeze']))

    def pip_finish_slot(self):
        try:
            output = self.p.readAllStandardOutput().data().decode()
            for i in output.splitlines():
                self.pip_list.addItem(i)
        except RuntimeError:
            pass

    def generate_menu(self, pos):
        row_num = -1
        for i in self.pip_list.selectionModel().selection().indexes():
            row_num = i.row()
        if row_num < 0:
            return
        menu = QMenu()
        item1 = menu.addAction("uninstall")
        action = menu.exec_(self.pip_list.mapToGlobal(pos))
        row_data = self.pip_list.item(row_num)
        if action == item1 and row_data:
            pack = row_data.text()
            py_ = self.path.text()
            self.thread_pool.start(Worker(self.uninstall_pip, py_, pack))
            self.pip_list.takeItem(row_num)

    def uninstall_pip(self, py_, pack):
        cmd = [py_, '-m', 'pip', 'uninstall', pack, '-y']
        subprocess.check_output(cmd)

    def set_app_py_slot(self):
        """设置为当前app解释器"""
        py_ = self.path.text()
        G.config.installed_apps[self.app_name.text()].update({"py_": py_})
        G.config.to_file()
        self.cur_py.setText(self.py_box.currentText())
        TipDialog("设置成功")

    def py_setting_slot(self):
        self.interpreter = InterpreterWidget(self)
        self.interpreter.exec_()

    def py_change_slot(self, name):
        if name.strip():
            path = G.config.python_path[name]
            self.path.setText(path)
            self.load_pip(path)

    def window_cleanup(self):
        """关闭的事后处理"""
        if self.interpreter:
            self.interpreter.window_cleanup()
        self.close()


class InterpreterWidget(QDialog, Ui_Interpreters):
    """所有解释器list 列表"""

    def __init__(self, py_manage):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.setStyleSheet(qss)
        self.py_manage = py_manage
        self.py_table.horizontalHeader().setStretchLastSection(True)  # 最后一列自适应表格宽度
        self.py_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.py_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 单元格不可编辑
        #
        self.new_env = None
        self.modify_env = None
        # btn
        self.add_btn.clicked.connect(self.add_btn_slot)
        self.del_btn.clicked.connect(self.del_btn_slot)
        self.change_btn.clicked.connect(self.change_btn_slot)
        #
        self.py_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.py_table.customContextMenuRequested.connect(self.generate_menu)
        #
        self.load_py()

    def load_py(self):
        """加载py列表"""
        self.py_table.setRowCount(0)
        for k, v in G.config.python_path.items():
            self.py_table.insertRow(0)
            self.py_table.setItem(0, 0, QTableWidgetItem(str(k)))
            self.py_table.setItem(0, 1, QTableWidgetItem(str(v)))

    def generate_menu(self, pos):
        row_num = -1
        for i in self.py_table.selectionModel().selection().indexes():
            row_num = i.row()
        menu = QMenu()
        item1 = menu.addAction("打开所在文件夹")
        action = menu.exec_(self.py_table.mapToGlobal(pos))
        row_data = self.py_table.item(row_num, 1)
        if action == item1 and row_data:
            path = row_data.text()
            QDesktopServices.openUrl(QUrl("file:" + os.path.dirname(path)))

    def add_btn_slot(self):
        self.new_env = NewEnvWidget(self)
        self.new_env.exec_()

    def del_btn_slot(self):
        row = self.py_table.currentRow()
        name = self.py_table.item(row, 0).text()
        path = self.py_table.item(row, 1).text()
        replay = QMessageBox.question(self, '提示', f'确定删除[ {name} ]吗？\n(不删除本地环境)', QMessageBox.Yes | QMessageBox.No,
                                      QMessageBox.No)
        if replay == QMessageBox.Yes:
            G.config.python_path.pop(name, None)
            for p in G.config.installed_apps.values():
                if path == p.get('py_', ""):
                    p.pop('py_')
            G.config.to_file()
            self.load_py()
            TipDialog("已删除")

    def change_btn_slot(self):
        row = self.py_table.currentRow()
        name = self.py_table.item(row, 0).text()
        path = self.py_table.item(row, 1).text()
        self.modify_env = ModifyEnvWidget(self, name, path)
        self.modify_env.exec_()

    def closeEvent(self, event):
        self.py_manage.load_py()
        event.accept()

    def window_cleanup(self):
        if self.new_env:
            self.new_env.window_cleanup()
        if self.modify_env:
            self.modify_env.window_cleanup()
        self.close()


class NewEnvObject(QObject):
    sig = Signal(str)

    def __init__(self):
        super().__init__()


class NewEnvWidget(QDialog, Ui_NewEnv):
    """新建虚拟环境  或  导入外部环境"""

    def __init__(self, interpreter):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.setStyleSheet(qss)
        self.interpreter = interpreter
        self.job = NewEnvObject()
        self.job.sig.connect(self.tip_)
        self.thread_pool = QThreadPool()
        # rex
        # btn
        self.name.textChanged.connect(self.name_change_slot)
        self.exis_path.textChanged.connect(self.exis_path_change_slot)
        self.env_radio.clicked.connect(self.env_radio_slot)
        self.exit_radio.clicked.connect(self.exit_radio_slot)
        self.path_btn.clicked.connect(self.path_btn_slot)
        self.exit_path_btn.clicked.connect(self.exit_path_btn_slot)
        self.ok_btn.clicked.connect(self.ok_btn_slot)
        self.cancel_btn.clicked.connect(self.close)
        self.ready_action()

    def ready_action(self):
        self.env_radio_slot()
        self.name_change_slot()
        self.load_py()
        self.path.setText(venv_path)

    def load_py(self):
        for k, v in G.config.python_path.items():
            self.base_py_list.addItem(k)

    def name_change_slot(self):
        name = self.name.text()
        if name.strip() and name not in G.config.python_path:
            self.name.setStyleSheet("color:green")
            self.ok_btn.setEnabled(True)
        else:
            self.name.setStyleSheet("color:red")
            self.ok_btn.setDisabled(True)

    def env_radio_slot(self):
        self.exis_path.setDisabled(True)
        self.exit_path_btn.setDisabled(True)
        #
        self.path.setEnabled(True)
        self.path_btn.setEnabled(True)
        self.base_py_list.setEnabled(True)

    def exit_radio_slot(self):
        self.path.setDisabled(True)
        self.path_btn.setDisabled(True)
        self.base_py_list.setDisabled(True)
        #
        self.exis_path.setEnabled(True)
        self.exit_path_btn.setEnabled(True)

    def path_btn_slot(self):
        path = QFileDialog.getExistingDirectory(self, "新建虚拟环境至", '/')
        self.path.setText(path)

    def exit_path_btn_slot(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择Python解释器", '/', 'Python Interpreter (*.exe)')
        if py_path_check(path):
            self.exis_path.setText(path)

    def exis_path_change_slot(self):
        path = self.exis_path.text()
        if py_path_check(path):
            self.exis_path.setText(path)
        else:
            self.exis_path.setText("")

    def ok_btn_slot(self):
        name = self.name.text()
        if self.env_radio.isChecked():
            path = self.path.text()
            py_ = G.config.python_path[self.base_py_list.currentText()]
            vir_path = os.path.join(path, name)
            self.create_env(py_, vir_path, name)
        if self.exit_radio.isChecked():
            path = self.exis_path.text()
            G.config.python_path.update({name: path})
            G.config.to_file()
            self.close()

    @Slot(str)
    def tip_(self, msg):
        QMessageBox.information(self, "提示", msg)
        self.close()

    def readout_slot(self):
        output = self.p.readAllStandardOutput().data().decode()
        self.infobox.sig.msg.emit(output)

    def finished_slot(self):
        if self.infobox_flag:
            self.infobox.close()
            G.config.to_file()
            self.job.sig.emit("创建完成")

    def create_env(self, py_, vir_path, name):
        self.infobox = ProgressMsgDialog(msg="准备中...")
        self.infobox.show()
        self.infobox.raise_()
        self.infobox_flag = False
        self.p = QProcess()
        self.p.readyReadStandardOutput.connect(self.readout_slot)
        self.p.finished.connect(self.finished_slot)
        virtualenv_ = "virtualenv"
        img_ = G.config.get_pypi_source()
        cmd = " ".join([py_, "-m", 'pip', 'install', virtualenv_] + img_)
        self.p.start(cmd)
        self.p.waitForFinished()
        # 开始新建venv
        self.infobox.sig.msg.emit('新建虚拟环境中...')
        cmd = " ".join([py_, "-m", virtualenv_, "--no-site-packages", vir_path])
        self.p.start(cmd)
        self.infobox_flag = True
        # record
        py_path = join_path(vir_path, 'Scripts', 'python.exe')
        G.config.python_path.update({name: py_path})

    def closeEvent(self, event):
        self.interpreter.load_py()
        event.accept()

    def window_cleanup(self):
        self.close()


class ModifyEnvWidget(QDialog, Ui_Modify):
    """ 修改名称或解释器路径"""

    def __init__(self, interpreter, name, path):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.setStyleSheet(qss)
        self.interpreter = interpreter
        self.raw_name = name
        self.raw_path = path
        self.name.setText(name)
        self.path.setText(path)
        self.name.textChanged.connect(self.name_change_slot)
        self.path.textChanged.connect(self.path_change_slot)
        self.path_btn.clicked.connect(self.path_btn_slot)
        self.save_btn.clicked.connect(self.save_btn_slot)
        self.cancel_btn.clicked.connect(self.close)

    def name_change_slot(self):
        name = self.name.text()
        if name.strip() and name not in G.config.python_path:
            self.name.setStyleSheet("color:green")
            self.save_btn.setEnabled(True)
        else:
            self.name.setStyleSheet("color:red")
            self.save_btn.setDisabled(True)

    def path_change_slot(self):
        path = self.path.text()
        if py_path_check(path):
            self.path.setText(path)
            self.path.setEnabled(True)
        else:
            self.save_btn.setDisabled(True)

    def path_btn_slot(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择Python路径', '/', 'Python Interpreter(*.exe)')
        if not path:
            return
        if py_path_check(path):
            self.path.setText(path)
            self.path.setEnabled(True)
        else:
            self.save_btn.setDisabled(True)

    def save_btn_slot(self):
        name = self.name.text()
        path = self.path.text()
        if os.path.exists(path) and os.path.isfile(path):
            G.config.python_path.pop(self.raw_name)
            G.config.python_path.update({name: path})
            G.config.to_file()
            TipDialog("修改成功")
            self.close()
        else:
            TipDialog("未知路径")

    def closeEvent(self, event):
        self.interpreter.load_py()
        event.accept()

    def window_cleanup(self):
        self.close()
