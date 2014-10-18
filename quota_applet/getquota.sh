#!/bin/sh
# USED QUOTA_TOTAL FREE_on_HOME
FREE=`df ${HOME} -k|tail -n 1|awk '{print $4}'`
QUOTA=`quota -w |grep homes|awk '{print $2,$3}'`
echo ${QUOTA} ${FREE}
