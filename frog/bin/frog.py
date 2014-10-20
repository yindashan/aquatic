#!/usr/bin/python
# -*- coding:utf-8 -*-
###########################################################
#  frog
#  每个机房部署一套,ping主动监控
#  1) 返回丢包率
#  2) 返回最大响应时间
#  3) 返回平均响应时间
###########################################################
import socket
import httplib
import os
import time, random
import datetime
import json, logging
from threading import Thread, Event
from xml.dom import minidom
import xml.etree.ElementTree as ET
import Queue

# our own lib
from settings import NOCID_LIST, MONITOR_TYPE, MONITOR_HOST, MONITOR_PORT
from daemon import Daemon
from log_record import initlog
from pinglib import quiet_ping


# 存储对象的临时缓存，用字典主要是看重字典的覆盖功能比较方便
appconfig_dict = {}


# 应用配置信息类
class AppConfig(object):
    def __init__(self, appname, server_list, timestamp):
        # 应用名
        self.appname = appname
        # server列表
        self.server_list = server_list
        # 时间戳
        self.timestamp = timestamp

# 队列元素类
class QueueItem(object):
    def __init__(self, appname, server):
        # 应用名
        self.appname = appname
        # server
        self.server = server

def getAppConfig(appname):
    """
    从临时缓存中根据应用名获取应用对象，如果不存在返回None
    """
    if appconfig_dict.has_key(appname):
        return appconfig_dict[appname]
    else:
        return None


def setAppConfig(appconfig):
    """
    往临时缓存中添加对象，应用名称作为唯一标识，如果已经存在，则替换，如果不存在，直接添加
    """
    appconfig_dict[appconfig.appname.strip()] = appconfig


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

class ThreadPing(Thread):
    """ping主动检查线程类"""
    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue
    
    def run(self):
        logger = logging.getLogger('monitor')
        logger.debug(u'守护线程开始执行,当前线程名：%s', self.getName())
        while True:
            try:
                queueItem = self.queue.get()
                
                logger.debug(u'当前执行线程：%s, 当前应用：%s, 当前Server：%s', self.getName(),
                        queueItem.appname, queueItem.server)
                # 执行检查操作
                app_monitor(queueItem)
                
                #signals to queue job is done
                self.queue.task_done() 
            except Exception, e:
                logger.error(u'执行队列中当前元素出错：%s,当前执行线程：%s, 当前应用：%s, 当前Server：%s',
                    e, self.getName(), queueItem.appname, queueItem.server)

def parseData(appname, timestamp, data):
    """
    创建AppConfig对象
    """
    logger = logging.getLogger('monitor')
    
    
    try:
        root = ET.fromstring(data)
        # ip 列表 
        node_ip_list = root.find('ip_list')
        
        ip_list = []
        for node in node_ip_list.findall('ip'):
            ip_list.append(node.text)
        
        # 创建对象，并把创建好的对象放到临时缓存中
        appconfig = AppConfig(appname=appname, server_list=ip_list, timestamp=timestamp)
        logger.debug(u'重新生成应用配置信息成功，当前应用：%s', appname)
        return appconfig
    except BaseException, e:
        logger.error(u"数据解析失败：%s", e)
        return None

def createQueueItem(queue):
    """
    根据本地临时缓存appconfig_dict中数据初始化队列元素
    """
    logger = logging.getLogger('monitor')
    try:
        d1 = datetime.datetime.now()
        for appconfig in appconfig_dict.itervalues():
            for server in appconfig.server_list:
                item = QueueItem(appname=appconfig.appname, server=server)
                queue.put(item)
        d2 = datetime.datetime.now()
        d = d2 - d1
        logger.debug(u'初始化队列元素成功,队列中元素个数为：%s,所花时间为：%s', str(queue.qsize()), str(d))
    except Exception, e:
        logger.error(u'初始化队列元素失败：%s', e)

# ping检查
def check_ping(appname, server):
    logger = logging.getLogger('monitor')
    try:
        percent_lost, max_trip, avg_trip = quiet_ping(server)
        if max_trip is None:
            max_trip = 10000
        else:
            max_trip = ("%.2f") % (max_trip)
        if avg_trip is None:
            avg_trip = 10000
        else:
            avg_trip = ("%.2f") % (avg_trip)
        return percent_lost, max_trip, avg_trip
    except BaseException, e:
        logger.error(u'ping检查出错：%s,当前server为：%s,所属应用：%s'%(e, server, appname))

def app_monitor(queueItem):
    logger = logging.getLogger('monitor')
    # 应用名称
    appname = queueItem.appname
    server = queueItem.server
    
    dd = {}
    dd['appname'] = appname
    dd['ip'] = server
    dd['status'] = []
    
    percent_lost, max_trip, avg_trip = check_ping(appname, server)
    
    item_percent = {}
    item_percent['name'] = 'ping_lost_package'
    item_percent['value'] = percent_lost
    dd['status'].append(item_percent)
    
    item_max = {}
    item_max['name'] = 'ping_max_reach'
    item_max['value'] = max_trip
    dd['status'].append(item_max)
    
    item_avg = {}
    item_avg['name'] = 'ping_avg_reach'
    item_avg['value'] = avg_trip
    dd['status'].append(item_avg)
    
    # 发送给监控服务器
    # 如果100%丢包则无需上报状态
    if percent_lost != 1:
        data = json.dumps(dd)
        send_info(MONITOR_HOST, MONITOR_PORT, 'app_status', data)
        logger.debug(u'ping监控数据上报:%s', data)
        

def save_config_file(project_path, appname, data):
    doc = minidom.parseString(data)
    data = doc.toprettyxml(indent = "\t", newl="\n", encoding="UTF-8")
    file = os.path.join(project_path, 'config', appname + '.xml') 
    fp = open(file, 'w')
    fp.write(data)
    fp.close( )
      
## 重新获取应用的配置
def get_app_config(project_path, appname, nocid_list, timestamp):
    post_data = {'nocid_list':NOCID_LIST, 'appname':appname}
    post_data = json.dumps(post_data)
    data = send_info(MONITOR_HOST, MONITOR_PORT, 'getPingIpList', post_data)
    if data:
        # 1. 将配置信息记录在文件中
        save_config_file(project_path, appname, data)
        
        # 2. 将配置信息记录在内存中
        appconfig = parseData(appname, timestamp, data)
        if appconfig:
            setAppConfig(appconfig)
            
            
def cron_job(project_path, queue):
    logger = logging.getLogger('monitor')
    logger.debug(u'开始执行cron_job!')
    
    dd = {'nocid_list':NOCID_LIST, 'monitor_type':MONITOR_TYPE}
    data = json.dumps(dd)
    app_timestamp_data = send_info(MONITOR_HOST, MONITOR_PORT, 'getAppTimeStamp', data)
    
    if app_timestamp_data:
        # 解析应用时间戳字典
        app_timestamp_dict = json.loads(app_timestamp_data)
        for appname, timestamp in app_timestamp_dict.iteritems():
            curr = getAppConfig(appname)
            if curr: # 临时缓存中已经存在当前应用的配置信息
                if curr.timestamp != timestamp: 
                    get_app_config(project_path, appname, NOCID_LIST, timestamp)
            else: # 临时缓存区中不存在当前应用的配置信息,重新向海鸥发送请求
                get_app_config(project_path, appname, NOCID_LIST, timestamp)
        
    # 根据本地临时缓存appconfig_dict中数据创建队列元素
    createQueueItem(queue)

# 向状态转发服务器发送信息
def send_info(host, port, target, msg_body):
    logger = logging.getLogger('monitor')
    headers = {}
    try:
        conn = httplib.HTTPConnection(host, port, timeout=7)
        conn.request("POST", "/" + target, msg_body, headers)
        response = conn.getresponse()
        data = response.read()
        logger.debug(u'返回结果status:%s, reason:%s, 返回输出:%s', response.status, response.reason, data)
        conn.close()
        if response.status == 200:
            return data
        else:
            return None
    except BaseException, e:
        logger.error('exception:%s', e)
        return None

class Agent(Daemon):
    def __init__(self, project_path):
        path = os.path.join(project_path, 'tmp')
        pidfile = os.path.join(path, 'monitor.pid')
        stdout_path = os.path.join(path, 'monitor.out')
        super(Agent, self).__init__(pidfile=pidfile, stdout=stdout_path, 
            stderr=stdout_path)
        self.project_path = project_path
        
    def run(self):
        logger = logging.getLogger('monitor')
        logger.debug('Agent start.')
        
        # 1) 创建队列
        queue = Queue.Queue()
        logger.debug(u'创建队列')
        
        # 2) 初始化线程
        #spawn a pool of threads, and pass them queue instance 
        for i in range(5):
            t = ThreadPing(queue)
            t.setDaemon(True)
            t.start()
        logger.debug(u'线程初始化成功')
        
        # 3) 先向此应用发送一次请求
        # ------------------------
        cron_job(self.project_path, queue)
        
        # 4) 启动定时器
        # ------------------------
        # 主动监控 间隔:30秒
        t = LoopTimer(30, cron_job, [self.project_path, queue])
        t.start()
        
def main():
    # 主程序所在目录
    path = os.path.dirname(os.path.abspath(__file__))
    
    project_path = os.path.dirname(path)
    
    log_path = os.path.join(project_path, 'log')
    
    # 日志logger 初始化
    # 硬件配置及监控数据上报日志
    initlog('monitor', log_path, 'monitor.log', logging.DEBUG)
    
    logger = logging.getLogger('monitor')
    logger.info('monitor start.')
    
    # 启动定时器
    agent = Agent(project_path)
    agent.restart()
    
if __name__ == '__main__':
    main()





