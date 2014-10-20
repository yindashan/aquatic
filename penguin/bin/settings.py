# -*- coding:utf-8 -*-
import redis
from redis.connection import BlockingConnectionPool

# 当前机房对应的机房编号
NOCID_LIST = 'BGP-QD-EXN-1,BGP-BJ-ShuBei-1,BGP-NJ-DX-1'

# 监控类型
MONITOR_TYPE = 'http'

# 监控服务器主机
HOST = '10.2.161.15'

# 监控服务器端口
PORT = 8022

# ------------ redis 相关配置 ------------
#REDIS_HOST = '10.2.161.15'
REDIS_HOST = '192.168.56.15'

REDIS_PORT = 6379

REDIS_DB_NUM = 0

REDIS_PASSWORD = 'N6MXWf'

# ------------- 连接池 --------------- 
# redis数据库
# 阻塞式连接池
pool = BlockingConnectionPool(max_connections=20, timeout=5, socket_timeout=5, \
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB_NUM, password=REDIS_PASSWORD)
REDIS_DB = redis.StrictRedis(connection_pool=pool)

