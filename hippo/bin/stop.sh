#! /bin/bash
PID=`ps -eo pid,cmd |grep -E "hippo" |grep -v grep |sed 's/^ *//g' |cut -d " " -f 1`
kill -9 $PID

