# -*- coding:utf-8 -*-
#############################
# 执行短信发送
# 需要引入sms_tool中的类
#############################

# standard lib
import re
import time
import socket
import httplib
import urllib
import urllib2
import urlparse
import redis, json
from datetime import datetime, timedelta
import logging, traceback
from celery import task
from urllib import quote
from redis.connection import ConnectionPool, BlockingConnectionPool
from redis.exceptions import RedisError
import xml.etree.ElementTree as ET

# our own lib
from common import QueueItem
from common import LoopTimer
from common import send_info


# 检查动作
@task
def app_monitor(queueItem):
    logger = logging.getLogger('monitor')
    logger.debug(u'当前应用：%s,对应的时间戳：%s'%(queueItem.appname, queueItem.timestamp))
    try:
        # 应用名称
        appname = queueItem.appname
        
        url_list = queueItem.url_list
        server = queueItem.server
        
        # 监控服务器地址
        host = queueItem.host
        port = queueItem.port
        port = int(port)
        
        
        # 检查状态并发送
        dd = {}
        dd['appname'] = appname
        dd['ip'] = server
        dd['status'] = []
        for url_dict in url_list:
            url_id = url_dict['url_id']
            url_value = url_dict['url_value']
            temp_url = url_value.replace('{ip}', server)
            
            # 1.状态检查
            item_status = {}
            item_status['name'] = 'url_' + str(url_id) + '_status'
            item_status['value'] = 0
            # 检查此URL返回的状态码是否为200或304，是则表示正常，其他的状态码都表示异常
            if check_status(appname, temp_url):
                item_status['value'] = 1
            dd['status'].append(item_status)
            
            # 2.响应时间检查
            if url_dict.has_key('responsetime'):
                responsetime = url_dict['responsetime']
                responsetime = int(responsetime)
                item_responsetime = {}
                item_responsetime['name'] = 'url_' + str(url_id) + '_responsetime'
                item_responsetime['value'] = get_check_responsetime(appname, temp_url)
#                # 检查此URL的响应时间是否小于预定的结果
#                if check_responsetime(appname, temp_url, responsetime):
#                    item_responsetime['value'] = 1
                dd['status'].append(item_responsetime)
                
            # 3.返回内容检查
            if url_dict.has_key('type') and url_dict.has_key('target') and url_dict.has_key('value'):
                type_tmp = url_dict['type']
                target = url_dict['target']
                value = url_dict['value']
                item_content = {}
                item_content['name'] = 'url_' + str(url_id) + '_content'
                item_content['value'] = 0
                # 检查此URL返回的结果与预定的结果是否一致
                if check_content(appname, temp_url, type_tmp, target, value):
                    item_content['value'] = 1
                dd['status'].append(item_content)
        # 发送给监控服务器
        data = json.dumps(dd)
        send_info(host, port, 'app_status', data)
        logger.debug(u'URL监控数据上报:%s', data)
    except Exception, e:
        logger.error(u'配置文件解析失败：%s,当前应用：%s'%(e, queueItem.appname))



# 如果xml的编码为gbk或gb2312,则将其转换为utf-8
def changeXMLEncode(data):
    index = data.find('?>')
    # 特殊情况,响应为空的情况,或格式错误
    if index == -1:
        return data
        
    code_sign = data[0:index + 2].lower()

    if code_sign.find('gbk')!=-1 or data.find('gb2312')!=-1:
        data = data[index + 2 :]
        data = "<?xml version='1.0' encoding='utf-8' ?>" + data.decode('gbk').encode('utf-8')
        return data
    else:
        return data


def getXMLData(path):
    logger = logging.getLogger('monitor')
    try:
        fp = open(path, 'r')
        data = fp.read()
        fp.close()
    except BaseException, e:
        logger.error(u'获取XML配置信息失败:%s', e)
    
    # 对& 字符进行转义，否则xml解析器无法解析
    data = data.replace('&amp;', '&')
    data = data.replace('&', '&amp;')
    return data

    
    
    

# 检查URL的返回内容与预定结果是否一致
def check_content(appname, url, type_tmp, target_tmp, value):
    logger = logging.getLogger('monitor')
    flag = False
    data = None
    try:
        fp = urllib2.urlopen(url, timeout=5)
        data = fp.read()
        fp.close()
        
        node_list = target_tmp.split('#')
        # type_tmp:json,xml,text
        if type_tmp == 'xml':
            data = changeXMLEncode(data)
            root = ET.fromstring(data)
            target = root
            for node in node_list:
                target = target.find(node)
                if target._children:
                    continue
                else:
                    target = target.text
            if target == value:
                flag = True
        elif type_tmp == 'json':
            data = json.loads(data)
            target = data
            for node in node_list:
                target = target[node]
            if target == value:
                flag = True
        elif type_tmp == 'text':
            target = data
            if target == value:
                flag = True
        return flag
    except BaseException, e:
        logger.error(u'检查URL返回内容出错：%s,当前URL为：%s,所属应用：%s'%(e, url, appname))
        return flag
    


# 检查URL的响应时间是否小于预定的数值
def check_responsetime(appname, url, responsetime):
    logger = logging.getLogger('monitor')
    try:
        # 第一次发送请求
        s1 = time.time()
        ff = urllib2.urlopen(urllib2.Request(url), timeout=5)
        s2 = time.time()
        s = s2 - s1
        if s <= responsetime:
            return True
        else:
            # 第二次发送请求
            s1 = time.time()
            ff = urllib2.urlopen(urllib2.Request(url), timeout=5)
            s2 = time.time()
            s = s2 - s1
            if s <= responsetime:
                return True
            else:
                # 第三次发送请求
                s1 = time.time()
                ff = urllib2.urlopen(urllib2.Request(url), timeout=5)
                s2 = time.time()
                s = s2 - s1
                if s <= responsetime:
                    return True
                else:
                    return False
    except BaseException, e:
        logger.error(u'检查URL响应时间出错：%s,当前URL为：%s,所属应用：%s'%(e, url, appname))
        return False
    



# 获取URL的响应时间
def get_check_responsetime(appname, url):
    logger = logging.getLogger('monitor')
    s1 = time.time()
    try:
        ff = urllib2.urlopen(urllib2.Request(url), timeout=5)
    except BaseException, e:
        logger.error(u'检查URL响应时间出错：%s,当前URL为：%s,所属应用：%s'%(e, url, appname))
    finally:
        s2 = time.time()
        s = s2 - s1
        return int(s*1000)



# 检查URL的状态码是否为200或304
def check_status(appname, url):
    logger = logging.getLogger('monitor')
    flag = False
    host, path = urlparse.urlsplit(url)[1:3]
    if ':' in host:
        host, port = host.split(':', 1)
        try:
            port = int(port)
        except ValueError:
            #print 'invalid port number %r' %(port,)
            logger.debug(u'当前%s中端口异常,所属应用：%s'%(url, appname))
            return flag
    else:
        port=80
    
    try:
        conn = httplib.HTTPConnection(host, port, timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        status = response.status
        if status == 200 or status == 304:
            flag = True
            return flag
    except BaseException, e:
        logger.error(u'检查URL返回状态码出错：%s,当前URL为：%s,所属应用：%s'%(e, url, appname))
        return flag

    
    
    
    
