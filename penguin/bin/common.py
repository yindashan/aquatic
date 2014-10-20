# -*- coding:utf-8 -*-
##############################
# 公共类
##############################
import time
import random
import logging
import socket
import httplib
from threading import Thread, Event


# 队列元素类
class QueueItem(object):
    def __init__(self, appname, url_list, server, host, port, timestamp):
        # 应用名
        self.appname = appname
        # URL列表
        self.url_list = url_list
        # server
        self.server = server
        # 监控服务器host
        self.host = host
        # 监控服务器port
        self.port = port
        # 时间戳
        self.timestamp = timestamp




class LoopTimer(Thread):
    """重写了Threading.Timer 类,以定时循环执行"""
    # interval    --单位:秒
    def __init__(self, interval,function, args=[], kwargs={}):
        Thread.__init__(self)
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.finished = Event()

    def cancel(self):
        """停止定时器"""
        self.finished.set()

    def run(self):
        # 随机休眠一段时间, 再开始循环
        t = random.randint(0, self.interval)
        time.sleep(t)
        while not self.finished.is_set():
            self.finished.wait(self.interval)
            if not self.finished.is_set():
                self.function(*self.args, **self.kwargs)



# 向状态转发服务器发送信息
def send_info(host, port, target, msg_body):
    logger = logging.getLogger('monitor')
    headers = {}
    try:
        conn = httplib.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/" + target, msg_body, headers)
        response = conn.getresponse()
        data = response.read()
        logger.debug(u'返回结果status:%s, reason:%s, 返回输出:%s', response.status, response.reason, data)
        conn.close()
        if response.status == 200:
            return data
        else:
            return None
    except socket.error, e:
        logger.error('exception:%s', e)
        return None


