#!/usr/bin/python
# -*- coding:utf-8 -*-
###########################################################
#  penguin
#  每个机房部署一套
#  1) 检查URL返回状态码
#  2) 检查URL响应时间
#  3) 检查URL返回内容
###########################################################
import urllib,urllib2
import xml.etree.ElementTree as ET
import socket
import httplib
import os
import sys
import urlparse

import time, random
import datetime
import json, logging
from threading import Thread, Event
import subprocess
from xml.dom import minidom

import Queue

# our own lib
from settings import NOCID_LIST, MONITOR_TYPE, HOST, PORT
from daemon import Daemon
from log_record import initlog

from common import QueueItem
from common import LoopTimer
from common import send_info
from async_task.tasks import app_monitor


# 存储对象的临时缓存，用字典主要是看重字典的覆盖功能比较方便
appconfig_dict = {}


# 应用配置信息类
class AppConfig(object):
    def __init__(self, appname, url_list, server_list, host, port, timestamp):
        # 应用名
        self.appname = appname
        # URL列表
        self.url_list = url_list
        # server列表
        self.server_list = server_list
        # 监控服务器host
        self.host = host
        # 监控服务器port
        self.port = port
        # 时间戳
        self.timestamp = timestamp


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
    往监时缓存中添加对象，应用名称作为唯一标识，如果已经存在，则替换，如果不存在，直接添加
    """
    appconfig_dict[appconfig.appname.strip()] = appconfig





class ThreadHttp(Thread):
    """http主动检查线程类"""
    def __init__(self, project_path, queue):
        Thread.__init__(self)
        self.project_path = project_path
        self.queue = queue
    
    def run(self):
        logger = logging.getLogger('monitor')
        logger.debug(u'守护线程开始执行,当前线程名：%s', self.getName())
        while True:
            try:
                #host = self.queue.get(1, 5) # get(self, block=True, timeout=None) ,1就是阻塞等待,5是超时5秒
                # 调用队列对象的get()方法从队头删除并返回一个项目。可选参数为block，默认为True。如果队列为空且block为True，get()就使调用线程暂停，直至有项目可用。如果队列为空且block为False，队列将引发Empty异常。
#                queueItem = self.queue.get(1, 5)
                # 1) 取出任务
                queueItem = self.queue.get()
                
                logger.debug(u'当前执行线程：%s, 当前应用：%s, 当前Server：%s', self.getName(), queueItem.appname, queueItem.server)
                # 2) 往redis中推送一个异步任务
                app_monitor.apply_async((queueItem,), queue='_check_url_task')
                logger.info(u'【获取任务】%s,推送至redis.', unicode(queueItem))
                
                #signals to queue job is done
                #self.queue.task_done() # 这行代码解除注释后队列里面的数据执行完后启动的线程会关闭,注释后启动的线程会一直监听
            except Exception, e:
                logger.error(u'执行队列中当前元素出错：%s,当前执行线程：%s, 当前应用：%s, 当前Server：%s', e, self.getName(), queueItem.appname, queueItem.server)
                #break






def parseXmlData(project_path, timestamp, xml_data):
    try:
        root = ET.fromstring(xml_data)
        
        # 应用名称
        appname_tmp = root.find('appname').text.strip()
        
        url_list = []
        urllist_node = root.find('urlList')
        server_list = []
        serverlist_node = root.find('serverList')
        
        # 监控服务器地址
        monitor_node = root.find('monitor')
        host = monitor_node.find('host').text.strip()
        port = monitor_node.find('port').text.strip()
        
        for node in serverlist_node.findall('server'):
            server_list.append(node.text.strip())
        
        
        for urlnode in urllist_node.findall('url'):
            item = {}
            url_id = urlnode.find('url_id').text.strip()
            url_value = urlnode.find('url_value').text.strip()
            
            item['url_id'] = url_id
            item['url_value'] = url_value
            
            
            responsetime = urlnode.find('responsetime')
            if responsetime is not None:
                responsetime = responsetime.text.strip()
                item['responsetime'] = responsetime
                
                
            type_tmp = urlnode.find('type')
            target = urlnode.find('target')
            value = urlnode.find('value')
            if type_tmp is not None and target is not None and value is not None:
                type_tmp = type_tmp.text.strip()
                target = target.text.strip()
                value = value.text.strip()
                
                item['type'] = type_tmp
                item['target'] = target
                item['value'] = value
            
            url_list.append(item)
            
        # 生成XML文件
        createXml(project_path, timestamp, appname_tmp, server_list, url_list)
        
        # 创建对象，并把创建好的对象放到临时缓存区
        appconfig = AppConfig(appname = appname_tmp, url_list = url_list, server_list = server_list, host = host, port = port, timestamp = timestamp)
        
        return appconfig
            
    except Exception, e:
        print u'配置文件解析失败：%s.' % (e)
        return None



def createXml(project_path, timestamp, appname, server_list, url_list):
    try:
        # 指定监控服务器的host和port
        host = HOST
        port = str(PORT)
        
        doc = minidom.Document()
        
        rootNode = doc.createElement("config")
        doc.appendChild(rootNode)
        
        node_appname = doc.createElement('appname')
        text_node_appname = doc.createTextNode(appname) #元素内容写入
        node_appname.appendChild(text_node_appname)
        rootNode.appendChild(node_appname)
        
        node_urlList = doc.createElement('urlList')
        
        for url_dict in url_list:
            node_url = doc.createElement('url')
            
            node_url_id = doc.createElement('url_id')
            text_node_url_id = doc.createTextNode(str(url_dict['url_id']))
            node_url_id.appendChild(text_node_url_id)
            node_url.appendChild(node_url_id)
            
            node_url_value = doc.createElement('url_value')
            text_node_url_value = doc.createTextNode(url_dict['url_value'])
            node_url_value.appendChild(text_node_url_value)
            node_url.appendChild(node_url_value)
            
            if url_dict.has_key('responsetime'):
                node_responsetime = doc.createElement('responsetime')
                text_node_responsetime = doc.createTextNode(str(url_dict['responsetime']))
                node_responsetime.appendChild(text_node_responsetime)
                node_url.appendChild(node_responsetime)
                
            if url_dict.has_key('type') and url_dict.has_key('target') and url_dict.has_key('value'):
                node_type = doc.createElement('type')
                text_node_type = doc.createTextNode(url_dict['type'])
                node_type.appendChild(text_node_type)
                node_url.appendChild(node_type)
                
                node_target = doc.createElement('target')
                text_node_target = doc.createTextNode(url_dict['target'])
                node_target.appendChild(text_node_target)
                node_url.appendChild(node_target)
                
                node_value = doc.createElement('value')
                text_node_value = doc.createTextNode(url_dict['value'])
                node_value.appendChild(text_node_value)
                node_url.appendChild(node_value)
            
            node_urlList.appendChild(node_url)
        
        rootNode.appendChild(node_urlList)
        
        node_monitor = doc.createElement('monitor')
        
        node_monitor_host = doc.createElement('host')
        text_node_monitor_host = doc.createTextNode(host)
        node_monitor_host.appendChild(text_node_monitor_host)
        node_monitor.appendChild(node_monitor_host)
        
        node_monitor_port = doc.createElement('port')
        text_node_monitor_port = doc.createTextNode(port)
        node_monitor_port.appendChild(text_node_monitor_port)
        node_monitor.appendChild(node_monitor_port)
        
        rootNode.appendChild(node_monitor)
        
        node_serverList = doc.createElement('serverList')
        for server in server_list:
            node_server = doc.createElement('server')
            text_node_server = doc.createTextNode(server)
            node_server.appendChild(text_node_server)
            node_serverList.appendChild(node_server)
        
        rootNode.appendChild(node_serverList)
        
        
#        xmlfile = doc.toxml("UTF-8")
#        print xmlfile
#        xmlfile_format = doc.toprettyxml(indent = "\t", newl="\n", encoding="UTF-8")
#        print xmlfile_format
        
#        path = os.path.dirname(os.path.abspath(__file__))
#        project_path = os.path.dirname(path)
        config_path = os.path.join(project_path, 'config')
        filename = appname + '_' + timestamp + '.xml'
        config_file = os.path.join(config_path, filename)
        # 生成XML文件
        fd = open(config_file, "w")
        doc.writexml(fd, indent = "", addindent="\t", newl="\n", encoding="UTF-8")
        fd.close()
        
    except Exception, e:
        print e
    




def createQueueItem(queue):
    """
    根据本地临时缓存appconfig_dict中数据初始化队列元素
    """
    logger = logging.getLogger('monitor')
    try:
        d1 = datetime.datetime.now()
        for appconfig in appconfig_dict.itervalues():
            for server in appconfig.server_list:
                item = QueueItem(appname = appconfig.appname, 
                                 url_list = appconfig.url_list, 
                                 server = server, 
                                 host = appconfig.host, 
                                 port = appconfig.port, 
                                 timestamp = appconfig.timestamp)
                queue.put(item)
        d2 = datetime.datetime.now()
        d = d2 - d1
        logger.debug(u'初始化队列元素成功,队列中元素个数为：%s,所花时间为：%s', str(queue.qsize()), str(d))
    except Exception, e:
        logger.error(u'初始化队列元素失败：%s', e)






def cron_job(project_path, queue):
    logger = logging.getLogger('monitor')
    logger.debug(u'开始执行cron_job!')
    
    nocid_list = NOCID_LIST.split(',')
    dd = {'nocid_list':nocid_list, 'monitor_type':MONITOR_TYPE}
    data = json.dumps(dd)
    app_timestamp_data = send_info(HOST, PORT, 'getAppTimeStamp', data)
    
    if app_timestamp_data is not None:
        # 解析应用时间戳字典
        app_timestamp_dict = json.loads(app_timestamp_data)
        for key, value in app_timestamp_dict.iteritems():
            execute_appconfig = None
            appconfig = getAppConfig(key)
            if appconfig: # 临时缓存中已经存在当前应用的配置信息
                if appconfig.timestamp == value: # 时间戳相同,直接从临时缓存区中取配置信息
                    logger.debug(u'从临时缓存中获取数据!')
                    execute_appconfig = appconfig
                    # 执行检查操作
#                    app_monitor(project_path, execute_appconfig)
                else: # 时间戳不相同,重新向海鸥发送请求
                    post_data = {'nocid_list':nocid_list, 'appname':key}
                    post_data = json.dumps(post_data)
                    logger.debug(u'向监控服务器发送请求获取数据!')
                    appname_config = send_info(HOST, PORT, 'getAppConfig', post_data)
                    if appname_config is not None:
                        execute_appconfig = parseXmlData(project_path, value, appname_config)
                        setAppConfig(execute_appconfig)
                        # 执行检查操作
#                        app_monitor(project_path, execute_appconfig)
            else: # 临时缓存区中不存在当前应用的配置信息,重新向海鸥发送请求
                post_data = {'nocid_list':nocid_list, 'appname':key}
                post_data = json.dumps(post_data)
                logger.debug(u'向监控服务器发送请求获取数据!')
                appname_config = send_info(HOST, PORT, 'getAppConfig', post_data)
                if appname_config is not None:
                    execute_appconfig = parseXmlData(project_path, value, appname_config)
                    setAppConfig(execute_appconfig)
                    # 执行检查操作
#                    app_monitor(project_path, execute_appconfig)
        
        # 根据本地临时缓存appconfig_dict中数据创建队列元素
        createQueueItem(queue)

   

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
            t = ThreadHttp(self.project_path, queue)
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
        
        # 5) 对队列执行 join 操作，实际上意味着等到队列为空，再退出主程序。
        queue.join()
        logger.debug(u'此打印语句在queue.join()函数之后')
        
        
        
        
    

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





