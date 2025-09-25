# -*- coding: utf8 -*-

import json
import sys
import os
import os.path
import inspect
import copy
import ctypes
from functools import wraps
from ctypes import WinDLL, create_string_buffer, WINFUNCTYPE

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WeChatManager')


def is_64bit():
    return sys.maxsize > 2 ** 32


def c_string(data):
    return ctypes.c_char_p(data.encode('utf-8'))


class MessageType:
    MT_DEBUG_LOG = 11024
    MT_USER_LOGIN = 11025
    MT_USER_LOGOUT = 11026
    MT_USER_LOGOUT = 11027
    MT_SEND_TEXTMSG = 11036


class CallbackHandler:
    pass


_GLOBAL_CONNECT_CALLBACK_LIST = []
_GLOBAL_RECV_CALLBACK_LIST = []
_GLOBAL_CLOSE_CALLBACK_LIST = []


def CONNECT_CALLBACK(in_class=False):
    def decorator(f):
        wraps(f)
        if in_class:
            f._wx_connect_handled = True
        else:
            _GLOBAL_CONNECT_CALLBACK_LIST.append(f)
        return f

    return decorator


def RECV_CALLBACK(in_class=False):
    def decorator(f):
        wraps(f)
        if in_class:
            f._wx_recv_handled = True
        else:
            _GLOBAL_RECV_CALLBACK_LIST.append(f)
        return f

    return decorator


def CLOSE_CALLBACK(in_class=False):
    def decorator(f):
        wraps(f)
        if in_class:
            f._wx_close_handled = True
        else:
            _GLOBAL_CLOSE_CALLBACK_LIST.append(f)
        return f

    return decorator


def add_callback_handler(callbackHandler):
    for dummy, handler in inspect.getmembers(callbackHandler, callable):
        if hasattr(handler, '_wx_connect_handled'):
            _GLOBAL_CONNECT_CALLBACK_LIST.append(handler)
        elif hasattr(handler, '_wx_recv_handled'):
            _GLOBAL_RECV_CALLBACK_LIST.append(handler)
        elif hasattr(handler, '_wx_close_handled'):
            _GLOBAL_CLOSE_CALLBACK_LIST.append(handler)


@WINFUNCTYPE(None, ctypes.c_void_p)
def wechat_connect_callback(client_id):
    for func in _GLOBAL_CONNECT_CALLBACK_LIST:
        func(client_id)


@WINFUNCTYPE(None, ctypes.c_long, ctypes.c_char_p, ctypes.c_ulong)
def wechat_recv_callback(client_id, data, length):
    data = copy.deepcopy(data)
    json_data = data.decode('utf-8')
    dict_data = json.loads(json_data)
    for func in _GLOBAL_RECV_CALLBACK_LIST:
        func(client_id, dict_data['type'], dict_data['data'])


@WINFUNCTYPE(None, ctypes.c_ulong)
def wechat_close_callback(client_id):
    for func in _GLOBAL_CLOSE_CALLBACK_LIST:
        func(client_id)


class NoveLoader:
    # 加载器
    loader_module_base: int = 0

    # 偏移
    _InitWeChatSocket: int = 0xB080
    _GetUserWeChatVersion: int = 0xCB80
    _InjectWeChat: int = 0xCC10
    _SendWeChatData: int = 0xAF90
    _DestroyWeChat: int = 0xC540
    _UseUtf8: int = 0xC680
    _InjectWeChat2: int = 0xCC30
    _InjectWeChatPid: int = 0xB750
    _InjectWeChatMultiOpen: int = 0xC780

    # _GetInstallWeixinVersion: int = 0x0
    # _InjectWeixin: int = 0x0
    # _InjectWeixin2: int = 0x0
    # _SetWeixinDataLocationPath: int = 0x0
    # _GetWeixinDataLocationPath: int = 0x0

    def __init__(self, loader_path: str):
        loader_path = os.path.realpath(loader_path)
        if not os.path.exists(loader_path):
            logger.error('libs path error or loader not exist')
            return

        loader_module = WinDLL(loader_path)
        self.loader_module_base = loader_module._handle

        # 使用utf8编码
        self.UseUtf8()

        # 初始化接口回调
        self.InitWeChatSocket(wechat_connect_callback, wechat_recv_callback, wechat_close_callback)

    def __get_non_exported_func(self, offset: int, arg_types, return_type):
        func_addr = self.loader_module_base + offset
        if arg_types:
            func_type = ctypes.WINFUNCTYPE(return_type, *arg_types)
        else:
            func_type = ctypes.WINFUNCTYPE(return_type)
        return func_type(func_addr)

    def add_callback_handler(self, callback_handler):
        add_callback_handler(callback_handler)

    def InitWeChatSocket(self, connect_callback, recv_callback, close_callback):
        func = self.__get_non_exported_func(self._InitWeChatSocket, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p], ctypes.c_bool)
        return func(connect_callback, recv_callback, close_callback)

    def GetUserWeChatVersion(self) -> str:
        func = self.__get_non_exported_func(self._GetUserWeChatVersion, None, ctypes.c_bool)
        out = create_string_buffer(20)
        if func(out):
            return out.value.decode('utf-8')
        else:
            return ''

    def InjectWeChat(self, dll_path: str) -> ctypes.c_uint32:
        func = self.__get_non_exported_func(self._InjectWeChat, [ctypes.c_char_p], ctypes.c_uint32)
        return func(c_string(dll_path))

    def SendWeChatData(self, client_id: int, message: str) -> ctypes.c_bool:
        func = self.__get_non_exported_func(self._SendWeChatData, [ctypes.c_uint32, ctypes.c_char_p], ctypes.c_bool)
        return func(client_id, c_string(message))

    def DestroyWeChat(self) -> ctypes.c_bool:
        func = self.__get_non_exported_func(self._DestroyWeChat, None, ctypes.c_bool)
        return func()

    def UseUtf8(self):
        func = self.__get_non_exported_func(self._UseUtf8, None, ctypes.c_bool)
        return func()

    def InjectWeChat2(self, dll_path: str, exe_path: str) -> ctypes.c_uint32:
        func = self.__get_non_exported_func(self._InjectWeChat2, [ctypes.c_char_p, ctypes.c_char_p], ctypes.c_uint32)
        return func(c_string(dll_path), c_string(exe_path))

    def InjectWeChatPid(self, pid: int, dll_path: str) -> ctypes.c_uint32:
        func = self.__get_non_exported_func(self._InjectWeChatPid, [ctypes.c_uint32, ctypes.c_char_p], ctypes.c_uint32)
        return func(pid, c_string(dll_path))

    def InjectWeChatMultiOpen(self, dll_path: str, exe_path: str) -> ctypes.c_uint32:
        func = self.__get_non_exported_func(self._InjectWeChatMultiOpen, [ctypes.c_char_p, ctypes.c_char_p], ctypes.c_uint32)
        return func(c_string(dll_path), c_string(exe_path))

    def GetInstallWeixinVersion(self) -> str:
        func = self.__get_non_exported_func(self._GetInstallWeixinVersion, None, ctypes.c_bool)
        out = create_string_buffer(20)
        if func(out):
            return out.value.decode('utf-8')
        else:
            return ''


# --- MAIN EXECUTION LOGIC ---
if __name__ == '__main__':
    # 定义 DLL 文件的完整路径
    loader_path = r"D:\软件\大客户个微版本\大客户\4.1\NoveLoader.dll"
    dll_path = r"D:\软件\大客户个微版本\大客户\4.1\NoveHelper.dll"

    # 实例化 NoveLoader 类，传入 loader_path
    loader = NoveLoader(loader_path)

    # 调用 InjectWeChat 方法，传入 dll_path
    # 这将启动一个微信实例并注入你的辅助 DLL
    client_id = loader.InjectWeChat(dll_path)

    if client_id:
        print(f"成功注入微信，客户端 ID 为: {client_id}")
        # 在这里可以添加更多逻辑，例如发送消息
        # 保持脚本运行，以便接收回调
        input("注入完成。按 Enter 键退出...")
        loader.DestroyWeChat()
    else:
        print("注入微信失败。")