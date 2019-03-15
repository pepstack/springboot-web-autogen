#!/usr/bin/python
#-*- coding: UTF-8 -*-
#
# @file: process_stat.py
#    statistics and report in main app with child processes
#
# @author: ZhangLiang, 350137278@qq.com
#
#
# @create: 2018-06-25
#
# @update: 2019-03-15 11:55:28
#
########################################################################
import os, time, inspect

########################################################################
# ! DO NOT CHANGE BELOW !
logger_module_name, _ = os.path.splitext(os.path.basename(inspect.getfile(inspect.currentframe())))

########################################################################

class ProcessStat(object):
    ARROW_UP = '\033[32m↑\033[0m'
    ARROW_DOWN = '\033[31m↓\033[0m'
    ARROW_NONE = ' '

    def __init__(self, topic, manager):
        self._lock = manager.Lock()

        self.rows_dict = manager.dict()
        self.keys_dict = manager.dict()

        self.start_time = time.time()
        self.curr_time = self.start_time

        self.topic = topic
        pass


    def lock(self):
        self._lock.acquire()
        pass


    def unlock(self):
        self._lock.release()
        pass


    def set_stat_row(self, rowkey, rowdata = None):
        self.rows_dict[rowkey] = rowdata
        pass


    def get_stat_row(self, rowkey):
        return self.rows_dict.get(rowkey)


    def save_key_value(self, key, newval, defval = 0):
        oldval = self.keys_dict.get(key, defval)
        self.keys_dict[key] = newval

        if newval > oldval:
            arrow = ProcessStat.ARROW_UP
        elif newval < oldval:
            arrow = ProcessStat.ARROW_DOWN
        else:
            arrow = ProcessStat.ARROW_NONE
        return (arrow, oldval)


    def update_time(self):
        self.curr_time = time.time()
        return self.curr_time


    def elapsed_seconds(self):
        d = self.curr_time - self.start_time;
        if d <= 0.0001:
            d = 0.001
        return d
