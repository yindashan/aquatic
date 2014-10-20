#!/usr/bin/python
# -*- coding:utf-8 -*-

import os
import json
import logging
import httplib
import socket

# 向状态转发服务器发送信息
def send_info(host, port, target, msg_body):
    headers = {}
    try:
        conn = httplib.HTTPConnection(host, port)
        conn.request("POST", "/" + target, msg_body, headers)
        response = conn.getresponse()
        data = response.read()
        print u'返回结果status:%s, reason:%s, 返回输出:%s' % (response.status, response.reason, data)
        conn.close()
        return data
    except socket.error, e:
        print 'exception:%s' % (e)

def main():
    post_data = {'nocid':'BGP-QD-EXN-1', 'appname':'SYS_PING'}
    post_data = json.dumps(post_data)
#    HOST = 'localhost'
#    PORT = 8000
    HOST = '10.2.161.15'
    PORT = 8022
    server_list = send_info(HOST, PORT, 'getPingIpList', post_data)
    print server_list

if __name__ == '__main__':
    main()





