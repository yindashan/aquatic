#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import json
import logging
import httplib
import socket

# 向状态转发服务器发送信息
def send_info(host, port, target, msg_body):
    logger = logging.getLogger('monitor')
    headers = {}
    try:
        conn = httplib.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/" + target, msg_body, headers)
        response = conn.getresponse()
        data = response.read()
        logger.debug(u'返回结果status:%s, reason:%s, 返回输出:%s', str(response.status), str(response.reason), str(data))
        conn.close()
        if response.status == 200:
            return data
        else:
            return None
    except socket.error, e:
        logger.error('send_info执行失败，exception:%s', str(e))
        return None


def main():
    nocid_list = ['BGP-BJ-ShuBei-1', 'BGP-BJ-SD-1', 'BGP-NJ-DX-1', 'BJM1']
    post_data = {'nocid_list':nocid_list, 'appname':'lse2_VIP_QR_TCP'}
    post_data = json.dumps(post_data)
    
    HOST = 'status.mon.autonavi.com'
    
    PORT = 80
    
    tcp_config = send_info(HOST, PORT, 'getTcpConfig', post_data)
    print tcp_config
    
    

if __name__ == '__main__':
    main()





