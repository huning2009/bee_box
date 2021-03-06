import functools
import json
import os
import shutil
import time
import requests
from PySide2.QtCore import QThreadPool, QProcess
from PySide2.QtWidgets import QAction, QWidget, QMessageBox

from app.lib.global_var import G
from app.honey.worker import Worker
from app.honey.diy_ui import AppDiv
from app.lib.helper import extract, diff_pip
from app.lib.path_lib import find_file, join_path
from app.py_manage import PyManageWidget
from app.tip import TipDialog


class Actions(dict):
    DOWNLOAD = 'download'
    UNINSTALL = "uninstall"
    UPGRADE = "upgrade"
    RUN = "run"
    CANCEL = "cancel"

    __map = {
        DOWNLOAD: "下载 ",
        UNINSTALL: "卸载 ",
        UPGRADE: "升级 ",
        RUN: "启动 ",
        CANCEL: "取消 "}

    @classmethod
    def to_zn(cls, act):
        return cls.__map[act]

    @classmethod
    def to_en(cls, act):
        for k, v in cls.__map.items():
            if v == act:
                return k


def format_size(bytes):
    try:
        bytes = float(bytes)
        kb = bytes / 1024
    except:
        print("传入的字节格式不对")
        return "Error"
    if kb >= 1024:
        M = kb / 1024
        if M >= 1024:
            G = M / 1024
            return "%.3fG" % (G)
        else:
            return "%.3fM" % (M)
    else:
        return "%.3fK" % (kb)


def before_download(handler):
    @functools.wraps(handler)
    def wrap(self):
        """主线程中UI处理"""
        for i in G.config.installed_apps.values():
            if i['cls_name'] == self.cls_name and self.install_version == i['install_version']:
                self._tip("此版本已下载")
                return
        self.start_time = time.time()
        self.count = 0
        self.before_handle()
        self.thread_pool.start(Worker(handler, self, callback=self.on_download_callback))

    return wrap


def before_install(handler):
    @functools.wraps(handler)
    def wrap(self):
        """主线程中UI处理
        检查py_ ,requirement
        """
        self.before_handle()
        self.thread_pool.start(Worker(handler, self, callback=self.on_install_callback))

    return wrap


def before_uninstall(handler):
    @functools.wraps(handler)
    def wrap(self):
        replay = QMessageBox.information(self.parent, "提示", "确定卸载吗?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if replay == QMessageBox.Yes:
            self.div.progress_msg.setText("卸载中...")
            self.thread_pool.start(Worker(handler, self))

    return wrap


class Standard(object):
    """Action
    download ---|--> install --|-->  ==  run
                v              v     \\
              cancel        cancel   uninstall
    """
    # common
    name = ""  # 应用名称
    desc = ""  # 应用描述
    icon = ""  # 应用图标
    app_url = ""  # 应用地址
    versions = {}  # 应用版本及下载地址

    # installed
    install_version = ""  # 选择安装的版本
    app_folder = ""  # 应用安装路径

    py_ = ""  # 解释器 (G 中实时获取)
    entry_ = ""  # 启动文件 (build.json实时获取)
    requirement_ = ""  # 缺失依赖

    def __init__(self, parent: QWidget, **kwargs):
        self.cls_name = self.__class__.__name__
        self.parent = parent
        self.action = kwargs.get("action", Actions.DOWNLOAD)
        self.thread_pool = QThreadPool()
        self.check(**kwargs)
        self.div: AppDiv
        self.div_init()
        self.count = 0
        self.start_time = 0
        self.cancel = False
        self.process = QProcess(self.parent)
        self.process.readyReadStandardOutput.connect(self.on_readoutput)
        self.process.readyReadStandardError.connect(self.on_readerror)

    def check(self, **kwargs):
        """检查已下载应用参数"""

        self.app_folder = kwargs.get("app_folder")  # 应用安装路径
        self.install_version = kwargs.get('install_version')  # 应用安装路径
        self.app_info(**kwargs)

    def app_info(self, **kwargs):
        raise NotImplementedError

    @property
    def pack_name(self):
        """安装后id"""
        return self.cls_name + "_" + self.install_version.replace('.', '_')

    @property
    def ui_name(self):
        """ui中id"""
        return self.cls_name + "_app"

    def _transfer(self, widget, value=None):
        if widget == 'bar':
            self.div.job.progressbar_signal.emit(value)
        elif widget == 'msg':
            self.div.job.msg_signal.emit(value)
        elif widget == 'switch':
            self.div.job.switch_signal.emit()
        elif widget == 'action':
            self.div.job.action_signal.emit(value)

    def before_handle(self):
        self.action = Actions.CANCEL
        self.cancel = False
        self.div.action.setText(Actions.to_zn(self.action))
        self._transfer('switch')

    def _tip(self, msg):
        self.parent.mainwindow.job.msg_box_signal.emit({"msg": str(msg)})

    def div_init(self):
        self.div = AppDiv(self.parent)
        self.div.icon.setStyleSheet(f"image: url({self.icon});")
        self.div.name.setText(self.name)
        self.div.action.setText(Actions.to_zn(self.action))
        self.div.action.clicked.connect(self.action_handler)
        if self.action == Actions.DOWNLOAD:
            for i in self.versions.keys():
                act = QAction(i, self.parent)
                setattr(self.div, f"act_{'_'.join([j for j in i if i.isalnum()])}", act)
                self.div.menu.addAction(act)
            self.div.menu.triggered[QAction].connect(self.version_action_triggered)
            self.div.desc.setText(self.desc)
            self.div.desc.url = self.app_url  # 可点击
            setattr(self.parent, self.ui_name, self)
            self.parent.apps_layout.addLayout(self.div.layout)
        elif self.action == Actions.RUN:
            act_uninstall = QAction(Actions.to_zn(Actions.UNINSTALL), self.parent)
            act_setting = QAction("解释器", self.parent)
            act_upgrade = QAction(Actions.to_zn(Actions.UPGRADE), self.parent)
            setattr(self.div, f"act_uninstall", act_uninstall)
            setattr(self.div, f"act_setting", act_setting)
            setattr(self.div, f"act_upgrade", act_upgrade)
            self.div.menu.addAction(act_setting)
            self.div.menu.addAction(act_upgrade)
            self.div.menu.addAction(act_uninstall)
            self.div.menu.triggered[QAction].connect(self.menu_action_triggered)
            self.div.desc.setText(self.install_version)
            setattr(self.parent, self.pack_name, self)
            self.parent.installed_layout.addLayout(self.div.layout)

    def version_action_triggered(self, q):
        """点击版本号直接下载"""
        if self.action == Actions.CANCEL:
            return
        self.install_version = q.text()
        self.action_handler()

    def menu_action_triggered(self, q):
        """卸载/更新处理"""
        if self.action == Actions.CANCEL:
            return
        act = q.text()
        if act == "解释器":
            self.act_setting_slot()
        elif Actions.to_en(act) == Actions.UNINSTALL:
            self.uninstall_handler()
        elif Actions.to_en(act) == Actions.UPGRADE:
            self.upgrade_handler()

    def act_setting_slot(self):
        self.py_manage = PyManageWidget(self.parent, self.pack_name)
        self.py_manage.show()

    @before_download
    def download_handler(self):
        """
        版本号
        下载目录
        """
        url = self.versions[self.install_version]
        postfix = os.path.splitext(url)[-1]  # .zip
        self.app_folder = os.path.join(G.config.install_path, self.pack_name)
        file_temp = self.app_folder + postfix  # 压缩文件路径
        ## 文件续传
        if os.path.exists(file_temp):
            local_file = os.path.getsize(file_temp)
            headers = {'Range': 'bytes=%d-' % local_file}
            mode = 'ab'
        else:
            local_file = 0
            headers = {}
            mode = 'wb'
        # download
        self._transfer("msg", "获取中...")
        try:
            response = requests.get(url, stream=True, headers=headers)
            response.raise_for_status()
        except Exception as e:
            return False
        content_size = float(response.headers.get('Content-Length', 0))
        self._transfer("bar", dict(range=[0, content_size]))
        # save
        with open(file_temp, mode) as file:
            chunk_size = 1024
            for data in response.iter_content(chunk_size=chunk_size):
                if self.cancel or G.pool_done:
                    return False
                file.write(data)  ##
                self.count += 1
                ##show
                current = chunk_size * self.count + local_file
                if content_size:
                    self._transfer("bar", dict(value=current))
                speed = format_size(current / (time.time() - self.start_time))
                self._transfer("msg",
                               f"{round(current / 1024, 2)}KB/{round(content_size / 1024, 2) or '-'}KB | {speed}/s")
        extract(file_temp)  # 解压
        return True

    def on_download_callback(self, res):
        self._transfer('switch')
        if res is True:
            data = {"cls_name": self.cls_name,
                    "install_version": self.install_version,
                    "action": Actions.RUN,
                    "app_folder": self.app_folder,
                    "py_": ""
                    }
            G.config.installed_apps.update({self.pack_name: data})
            G.config.to_file()
            self.div.add_installed_layout(data)
        elif res is False:
            pass
        self.action = Actions.DOWNLOAD
        self._transfer("action", Actions.to_zn(self.action))

    def get_build(self):
        """
        :return:  path 路径
        """
        path = find_file(self.app_folder, 'build.json')
        if path:
            try:
                with open(path[0], 'r')as f:
                    build = json.load(f)
                entry = find_file(self.app_folder, build['entry'])[0]
                requirement = find_file(self.app_folder, build['requirement'])[0]
            except KeyError:
                raise Exception('请确保build.json中含有entry和requirement')
            except IndexError:
                raise Exception("未找到entry文件或requirement文件")
            except json.JSONDecodeError:
                raise Exception("build.json 有错误")
            return entry, requirement
        else:
            raise Exception("未找到文件build.json")

    @before_install
    def install_handler(self):
        """解析 build.json"""
        for line in self.requirement_:
            line = line.strip().replace('==', '>=')
            cmd_ = [self.py_, "-m", "pip", "install", line] + G.config.get_pypi_source()
            if self.cancel or G.pool_done:
                return False
            self.process.start(" ".join(cmd_))
            self.process.waitForFinished()
        return True

    def on_readoutput(self):
        output = self.process.readAllStandardOutput().data().decode()
        self._transfer("msg", output.replace('\n', ''))

    def on_readerror(self):
        error = self.process.readAllStandardError().data().decode()
        self._tip(error)

    def on_install_callback(self, res):
        self._transfer('switch')
        self.action = Actions.RUN
        self._transfer("action", Actions.to_zn(self.action))

    def run_handler(self):
        self.py_ = G.config.installed_apps[self.pack_name].get('py_')
        if not self.py_:
            QMessageBox.warning(self.parent, "提示", "未选择Python解释器")
            self.act_setting_slot()
            return
        if not os.path.exists(self.py_) or not os.path.isfile(self.py_):
            QMessageBox.warning(self.parent, "提示", f"{self.py_} 不存在")
            return
        try:
            self.entry_, requirement_ = self.get_build()
        except Exception as e:
            QMessageBox.warning(self.parent, "提示", str(e))
            return
        ##检测依赖
        p = QProcess()
        p.start(' '.join(([self.py_, "-m", 'pip', "freeze"])))
        p.waitForFinished()
        out = p.readAllStandardOutput().data().decode()
        output = out.splitlines()
        with open(requirement_, 'r') as f:
            requirement = f.read().splitlines()
        dissatisfy, version_less = diff_pip(output, requirement)
        if dissatisfy:
            msgbox = QMessageBox(self.parent)
            msgbox.setWindowTitle("缺少依赖")
            msgbox.setText("\n".join(dissatisfy[:15]) + "\n...")
            yes = msgbox.addButton('立即安装', QMessageBox.AcceptRole)
            no = msgbox.addButton('稍后', QMessageBox.RejectRole)
            msgbox.setDefaultButton(yes)
            reply = msgbox.exec_()
            if reply == QMessageBox.AcceptRole:
                self.requirement_ = dissatisfy
                self.install_handler()
            return
        # run
        TipDialog("正在启动...")
        cmd = ' '.join([self.py_, self.entry_])
        QProcess().startDetached(cmd)

    def upgrade_handler(self):
        pass

    @before_uninstall
    def uninstall_handler(self):
        try:
            if os.path.exists(self.app_folder) and os.path.isdir(self.app_folder):
                shutil.rmtree(self.app_folder)
        except Exception as e:
            self._tip({"msg": str(e)})
        finally:
            for name, attr in self.div.__dict__.items():
                if name not in self.div.not_widget:
                    attr.deleteLater()
            G.config.installed_apps.pop(self.pack_name, None)
            G.config.to_file()

    def cancel_handler(self):
        self.cancel = True
        self._transfer("msg", "Releasing...")

    def action_handler(self):
        if self.action == Actions.DOWNLOAD:
            self.download_handler()
            # self.git_download_handler()
        elif self.action == Actions.CANCEL:
            self.cancel_handler()
        elif self.action == Actions.RUN:
            self.run_handler()
