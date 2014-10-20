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



def test():
    post_data = {'nocid_list':['BGP-QD-EXN-1', 'BGP-BJ-ShuBei-1']}
    post_data = json.dumps(post_data)
#    HOST = 'localhost'
#    PORT = 8000
    HOST = '10.2.161.15'
    PORT = 8022
    app_timestamp_data = send_info(HOST, PORT, 'getAppTimeStamp', post_data)
    print app_timestamp_data


def main():
    post_data = {'nocid_list':['BGP-QD-EXN-1', 'BGP-BJ-ShuBei-1'], 'appname':'busEngine#http'}
    post_data = json.dumps(post_data)
    HOST = 'localhost'
    PORT = 8000
#    HOST = '10.2.161.15'
#    PORT = 8022
    appname_config = send_info(HOST, PORT, 'getAppConfig', post_data)
    print appname_config



if __name__ == '__main__':
#    test()
    main()





