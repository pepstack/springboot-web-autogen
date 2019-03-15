#-*- coding: UTF-8 -*-
# @file: graceful_exit_event.py
#
#   此文件必须仅仅在主 app 中被引入一次
#
# @refer:
#   http://stackoverflow.com/questions/26414704/how-does-a-python-process-exit-gracefully-after-receiving-sigterm-while-waiting?rq=1
#   http://www.cnblogs.com/kaituorensheng/p/4445418.html
#
# @author: master@pepstack
#
# @create: 2016-07-13
#
# @update: 2019-03-15 11:55:28
#
# @version: 2019-03-15 11:55:28
#
#######################################################################
import os, sys, time, fileinput
import utility as util

#######################################################################

class AutoExitPid(object):
    def __init__(self, pid, pname, pidfile, lock):
        self.pid = pid
        self.pname = pname

        self._lock = lock
        self._pidfile = pidfile
        self._pidstr = "{{%d}}" % pid

        with lock:
            fd = open(pidfile, 'a')
            with fd:
                fd.write("{}=>{}\n".format(self._pidstr, pname))
        pass


    def __del__(self):
        with self._lock:
            for line in fileinput.input(self._pidfile, backup='.bak', inplace=True):
                if line.startswith(self._pidstr):
                    # 删除含有某一关键词的行
                    pass
                else:
                    # 保留行
                    print(line.rstrip())
                pass
        pass


class GracefulExitEvent(object):

    def __init__(self, lock, appfile):
        self.glock = lock
        self.workers = {}

        self.stopfile = appfile + ".FORCESTOP"
        self.pidfile = appfile + ".PID"

        util.info("stopfile: {}".format(self.stopfile))
        util.info("pidfile: {}".format(self.pidfile))

        self.curtime = time.time()
        pass


    def register_worker(self, pname, wp):
        # According to multiprocess daemon documentation by setting daemon=True
        #  when your script ends its job will try to kill all subprocess.
        # That occurs before they can start to write so no output will be produced.
        wp.daemon = True

        if self.workers.has_key(pname):
            util.error("duplicated worker process name: %s", pname)
            sys.exit(-1)

        self.workers[pname] = wp
        pass


    def start_workers(self):
        with self.glock:
            if util.file_exists(self.pidfile):
                util.error("pidfile already exists: " + self.pidfile)
                sys.exit(-1)

        for pname in self.workers.keys():
            util.info("{}: worker starting...".format(pname))
            self.workers[pname].start()
        pass


    def update_time(self):
        self.curtime = time.time()
        return self.curtime


    def acquire_pid(self):
        pid, pname = util.pidname()
        return (AutoExitPid(pid, pname, self.pidfile, self.glock), pid, pname)


    def is_stop(self):
        return util.file_exists(self.stopfile)


    def lock(self):
        self.glock.acquire()


    def unlock(self):
        self.glock.release()


    def pid_status(self):
        allrows = []
        with self.glock:
            if util.file_exists(self.pidfile):
                fd = open(self.pidfile, 'r')
                with fd:
                    allrows = fd.readlines()
        return allrows


    def check_forcestop(self, forcestop, exitCode = 0):
        if forcestop:
            self.notify_stop(exitCode)
        else:
            util.remove_file_nothrow(self.stopfile)
        pass


    def notify_stop(self, exitCode = 0):
        try:
            self.lock()

            if not util.file_exists(self.stopfile):
                os.mknod(self.stopfile)
            else:
                util.warn("stopfile already exists: " + self.stopfile)
        except:
            util.except_print("notify_stop")
        finally:
            try:
                self.unlock()
            except:
                util.except_print("unlock")
                pass

        if not exitCode is None:
            sys.exit(exitCode)
        pass


    def forever(self, interval_seconds = 1, cb_interval_func = None, func_data = None):
        counter = 0

        interval = interval_seconds * 10

        while not self.is_stop():
            time.sleep(0.1)

            counter += 1

            if counter == interval:
                counter = 0

                if cb_interval_func:
                    try:
                        cb_interval_func(func_data)
                    except:
                        util.except_print("cb_interval_func")
                        pass
                pass

        # block wait child processes exit
        for pname in self.workers.keys():
            self.workers[pname].join()
            util.warn("{}: worker stopped.".format(pname))

        with self.glock:
            util.remove_file_nothrow(self.pidfile)
            util.remove_file_nothrow(self.stopfile)
        pass
