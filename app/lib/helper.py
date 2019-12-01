import gzip
import os
import re
import tarfile
import zipfile
import rarfile


def un_gz(filepath):
    """un gz file"""
    f_name = filepath.replace(".gz", "")
    # 获取文件的名称，去掉
    g_file = gzip.GzipFile(filepath)
    # 创建gzip对象
    open(f_name, "w+").write(g_file.read())
    # gzip对象用read()打开后，写入open()建立的文件里。
    g_file.close()


def un_tar(filepath):
    """un tar file"""
    tar = tarfile.open(filepath)
    names = tar.getnames()
    folder = filepath.replace(".tar", "")
    if os.path.isdir(folder):
        pass
    else:
        os.mkdir(folder)
    # 因为解压后是很多文件，预先建立同名目录
    for name in names:
        tar.extract(name, folder)
    tar.close()


def un_zip(filepath: str):
    """un zip file"""
    zip_file = zipfile.ZipFile(filepath)
    folder = filepath.replace(".zip", "")
    if os.path.isdir(folder):
        pass
    else:
        os.mkdir(folder)
    for names in zip_file.namelist():
        zip_file.extract(names, folder)
    zip_file.close()


def un_rar(filepath):
    """un rar file"""
    rar = rarfile.RarFile(filepath)
    folder = filepath.replace(".rar", "")
    if os.path.isdir(folder):
        pass
    else:
        os.mkdir(folder)
    os.chdir(folder)
    rar.extractall()
    rar.close()


def extract(filepath):
    postfix = re.findall('\.(zip|rar)', filepath)
    if postfix:
        postfix = postfix[0]
        if postfix == 'zip':
            un_zip(filepath)
        elif postfix == 'rar':
            un_rar(filepath)
        elif postfix == 'tar':
            un_tar(filepath)
        else:
            raise TypeError("Unknown Zip File Type")
    else:
        return
    if os.path.exists(filepath) and os.path.isfile(filepath):
        os.remove(filepath)


def diff_pip(cur: list, need: list):
    """

    :param cur: 当前环境
    :param need:  所需依赖
    :return:  （不满足,满足但版本旧）
    """
    pack_part = "(.*)[>|=]=.*"
    v_part = "[>|=]=(.*)"
    cur_store = {}
    dissatisfy = []
    version_less = []
    for i in cur:
        i = i.replace(" ", "")
        if "=" in i:
            pack = re.findall(pack_part, i)[0]
            v = re.findall(v_part, i)[0]
        else:
            pack = i
            v = ""
        cur_store[pack] = v
    for i in need:
        i = i.replace(" ", "")
        if "=" in i:
            pack = re.findall(pack_part, i)[0]
            v = re.findall(v_part, i)[0]
        else:
            pack = i
            v = ""
        try:
            c_v = cur_store[pack]
            if v > c_v:
                version_less.append(i)
        except KeyError:
            dissatisfy.append(i)
    return dissatisfy, version_less
