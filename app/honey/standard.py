import functools
import json
import os
import re
import subprocess
import time
import requests
from PySide2.QtCore import QThreadPool, QProcess, QStringListModel
from PySide2.QtWidgets import QAction, QWidget

from app.lib.global_var import G
from app.honey.worker import Worker
from app.honey.diy_ui import AppDiv
from app.lib.helper import extract, diff_pip
from app.lib.path_lib import find_file, join_path


class Actions(dict):
    DOWNLOAD = 'download'
    INSTALL = "install"
    UNINSTALL = "uninstall"
    UPGRADE = "upgrade"
    RUN = "run"
    CANCEL = "cancel"

    __map = {
        DOWNLOAD: "下载",
        INSTALL: "安装",
        UNINSTALL: "卸载",
        UPGRADE: "升级",
        RUN: "启动",
        CANCEL: "取消"}

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
        self.cancel = False
        for i in G.config.installed_apps.values():
            if i['cls_name'] == self.cls_name and self.install_version == i['install_version']:
                self._tip({"msg": "此版本已下载"})
                return
        self.start_time = time.time()
        self.count = 0
        self._progress_show()
        self.div.progress_msg.setText("获取中...")
        self.action = Actions.CANCEL
        self.div.action.setText(Actions.to_zn(self.action))
        self.thread_pool.start(Worker(handler, self, succ_callback=self.on_download_success,
                                      fail_callback=self.on_download_fail))

    return wrap


def before_install(handler):
    @functools.wraps(handler)
    def wrap(self):
        # if not G.config.choice_python:
        #     self._tip({"msg": "未指定python版本"})
        #     return
        # self.cancel = False
        # self.div.progressbar.setVisible(True)
        # self.div.progress_msg.setVisible(True)
        # self.action = Actions.CANCEL
        # self.div.action.setText(Actions.to_zn(self.action))
        self.thread_pool.start(Worker(handler, self, succ_callback=self.on_install_success,
                                      fail_callback=self.on_install_fail))

    return wrap


def before_run(handler):
    @functools.wraps(handler)
    def wrap(self):
        self.thread_pool.start(Worker(handler, self))

    return wrap


def before_uninstall(handler):
    @functools.wraps(handler)
    def wrap(self):
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
    install_version = ""  # 安装版本
    app_folder = ""  # 应用安装路径
    entry = ""  # 启动文件
    requirement = ""  # 依赖

    def __init__(self, parent: QWidget, **kwargs):
        self.cls_name = self.__class__.__name__
        self.parent = parent
        self.action = kwargs.get("action", Actions.DOWNLOAD)
        self.thread_pool = QThreadPool()
        self.app_info(**kwargs)
        self.div: AppDiv
        self.div_init()
        self.count = 0
        self.start_time = 0
        self.cancel = False

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

    def _transfer(self, parent, func, *args):
        self.div.job.div_signal.emit(self.div.transfer(parent, func, *args))

    def _progress_hide(self):
        self._transfer("progressbar", "setVisible", False)
        self._transfer("progress_msg", "setVisible", False)

    def _progress_show(self):
        self._transfer("progressbar", "setVisible", True)
        self._transfer("progress_msg", "setVisible", True)

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
            act = QAction(Actions.to_zn(Actions.UNINSTALL), self.parent)
            setattr(self.div, f"act_uninstall", act)
            self.div.menu.addAction(act)
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
        self.action = Actions.to_en(q.text())
        self.action_handler()

    @before_download
    def download_handler(self):
        url = self.versions[self.install_version]
        postfix = os.path.splitext(url)[-1]
        self.app_folder = os.path.join(G.config.install_path, self.pack_name)
        self.file_temp = self.app_folder + postfix  # 压缩文件
        response = requests.get(url, stream=True, params={})
        try:
            response.raise_for_status()
        except Exception as e:
            print(e)
            return False
        chunk_size = 1024  # 单次请求最大值
        is_chunked = response.headers.get('transfer-encoding', '') == 'chunked'
        content_length_s = response.headers.get('content-length')
        if not is_chunked and content_length_s.isdigit():
            content_size = int(content_length_s)
            self._transfer("progressbar", "setRange", 0, content_size)
        else:
            content_size = None
        with open(self.file_temp, "wb") as file:
            s = response.iter_content(chunk_size=chunk_size)
            for data in s:
                if self.cancel or G.pool_done:
                    return False
                file.write(data)  ##
                self.count += 1
                ##show
                if content_size:
                    current = chunk_size * self.count
                    self._transfer("progressbar", "setValue", current)
                    self._transfer("progress_msg", "setText", str(current * 100 // content_size) + '%')
                else:
                    speed = format_size((chunk_size * self.count) / (time.time() - self.start_time))
                    self._transfer("progress_msg", "setText", speed + "/s")
        return True

    def on_download_success(self):
        extract(self.file_temp)  # 解压
        self.action = Actions.DOWNLOAD
        self._progress_hide()
        self._transfer("action", "setText", Actions.to_zn(self.action))
        data = {"cls_name": self.cls_name,
                "install_version": self.install_version,
                "action": Actions.RUN,
                "app_folder": self.app_folder,
                "entry": "",
                "requirement": ""
                }
        record = {self.pack_name: data}
        G.config.installed_apps.update(record)
        G.config.to_file()
        self.div.add_installed_layout(data)

    def on_download_fail(self):
        """隐藏进度条"""
        self._progress_hide()
        if os.path.exists(self.file_temp) and os.path.isfile(self.file_temp):
            os.remove(self.file_temp)
        self.action = Actions.DOWNLOAD
        self._transfer("action", "setText", Actions.to_zn(self.action))

    @before_install
    def install_handler(self):
        """解析 build.json"""
        path = find_file(self.app_folder, 'build.json')
        if path:
            with open(path[0], 'r')as f:
                build = json.load(f)
            try:
                entry = find_file(self.app_folder, build['entry'])[0]
                required = find_file(self.app_folder, build['requirement'])[0]
            except KeyError:
                self._tip('请确保build.json中含有entry和requirement')
                return
            except IndexError:
                self._tip("未找到entry文件或requirement文件")
                return
            record = {"launch_cmd": [join_path(self.app_folder, "venv", "Scripts", "python.exe"), entry]}
            G.config.installed_apps[self.pack_name].update(record)

        else:
            self._tip("未找到文件build.json")
            return

        py_version = G.config.python_path[G.config.choice_python]
        python_ = py_version
        img_ = ["-i", G.config.pypi_source] if G.config.pypi_use else []
        virtualenv = "virtualenv"
        if self.cancel or G.pool_done:
            return False

        try:
            ####
            self._transfer("progress_msg", "setText", "检查环境中...")
            ####
            cmd_ = [python_, "-m", "pip", "list"]
            out_bytes = subprocess.check_output(cmd_, stderr=subprocess.STDOUT)
            if virtualenv not in out_bytes.decode():
                ####
                self._transfer("progress_msg", "setText", "安装virtualenv中...")
                ####
                cmd_ = [python_, "-m", "pip", "install", virtualenv] + img_
                out_bytes = subprocess.check_output(cmd_, stderr=subprocess.STDOUT)
                kw = "Successfully installed virtualenv"
                if kw not in out_bytes.decode():
                    self._transfer("progress_msg", "setText", "安装virtualenv失败.")
                    return
            ####
            self._transfer("progress_msg", "setText", "创建虚拟环境中...")
            venv = join_path(self.app_folder, 'venv')
            if not os.path.exists(venv):
                cmd_ = [virtualenv, "-p", python_, "--no-site-packages", venv]
                out_bytes = subprocess.check_output(cmd_, stderr=subprocess.STDOUT)
                if "done" not in out_bytes.decode():
                    self._tip("虚拟环境创建失败.")
                    return
            ####
            self._transfer("progress_msg", "setText", "安装依赖中...")
            ####
            pip = join_path(self.app_folder, 'venv', 'Scripts', 'pip.exe')
            if not os.path.exists(pip):
                self._tip("未找到" + pip)
                return False
            f = open(required, 'r').readlines()
            for line in f:
                self._transfer("progress_msg", "setText", line.strip())
                cmd_ = [pip, "install", line] + img_
                out_bytes = subprocess.check_output(cmd_, stderr=subprocess.STDOUT)
            return True
        except subprocess.CalledProcessError as e:
            out_bytes = e.output.decode()  # Output generated before error
            code = e.returncode
            self._tip(out_bytes)
            return False

    def on_install_success(self):
        self._progress_hide()
        self.action = Actions.RUN
        record = {"action": Actions.RUN}
        G.config.installed_apps[self.pack_name].update(record)
        G.config.to_file()
        self._transfer("action", "setText", Actions.to_zn(self.action))

    def on_install_fail(self):
        self._progress_hide()
        self.action = Actions.INSTALL
        self.div.action.setText(Actions.to_zn(self.action))

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
                self._tip('请确保build.json中含有entry和requirement')
                return
            except IndexError:
                self._tip("未找到entry文件或requirement文件")
                return
            except json.JSONDecodeError:
                self._tip("build.json 有错误")
                return
            return entry, requirement
        else:
            self._tip("未找到文件build.json")
            return

    @before_run
    def run_handler(self):
        try:
            entry, requirement = self.get_build()
            py_ = G.config.python_path[G.config.choice_python]
            ##检测依赖
            output = subprocess.check_output([py_, "-m", 'pip', "freeze"]).decode()
            output = output.splitlines()
            with open(requirement, 'r') as f:
                requirement = f.read().splitlines()
            dissatisfy, version_less = diff_pip(output, requirement)
            if dissatisfy:
                self._tip(msg="\n".join(dissatisfy))
                return
            ##run
            cmd = [py_, entry]
            output = subprocess.check_output(cmd).decode()
        except subprocess.CalledProcessError as e:
            out_bytes = e.output.decode('utf8')  # Output generated before error
            code = e.returncode
            self._tip(out_bytes)
        except TypeError:
            pass

    def upgrade_handler(self):
        pass

    @before_uninstall
    def uninstall_handler(self):
        import shutil
        try:
            if os.path.exists(self.app_folder) and os.path.isdir(self.app_folder):
                shutil.rmtree(self.app_folder)
        except Exception as e:
            self._tip({"msg": str(e)})
        finally:
            for name, attr in self.div.__dict__.items():
                if name != 'widget' and name != 'job':
                    attr.deleteLater()
            G.config.installed_apps.pop(self.pack_name, None)
            G.config.to_file()

    def cancel_handler(self):
        self.cancel = True
        self.div.progress_msg.setText("正在释放资源...")

    def action_handler(self):
        if self.action == Actions.DOWNLOAD:
            self.download_handler()
        elif self.action == Actions.CANCEL:
            self.cancel_handler()
        elif self.action == Actions.INSTALL:
            self.install_handler()
        elif self.action == Actions.RUN:
            self.run_handler()
        elif self.action == Actions.UNINSTALL:
            self.uninstall_handler()
        elif self.action == Actions.UPGRADE:
            self.upgrade_handler()
