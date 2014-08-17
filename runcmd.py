#! /usr/bin/env python

import subprocess
import threading
import os
import sys
import time
import cStringIO
import traceback
import signal
import array

class CmdRunError(Exception):
    """
    Base exception for runcmd.
    """
    def __init__(self, cmd, out):
        self._cmd = cmd
        self._out = out

    def __str__(self):
        return 'Command \"{0}\" raised exception\n. {1}'.format(self._cmd, self._out)

class CmdRunInterruptError(CmdRunError):
    """
    cmd was interrupted.
    """
    def __init__(self, cmd, out):
        super(CmdRunInterruptError, self).__init__(cmd, out)


class PipeData(threading.Thread):
    """

    """

    CHUNK_SIZE = 1024

    def __init__(self, target_file):
        r, w = os.pipe()
        self._read_file     = os.fdopen(r, 'rb')
        self.write_fd       = w
        self._target_file   = target_file
        self._finish_read   = False
        self._is_stop       = False
        self._buffer        = array.array('B', (0 for i in xrange(PipeData.CHUNK_SIZE)))

        super(PipeData, self).__init__()

    def run(self):
        """ Continuously read in data from the pipe and write to the target file until
        user calls stop().

        This runs in a background thread.
        """
        while not self._is_stop:
            self._read()
            time.sleep(0.2)

        # read all remaining buffer input from pipe.
        self._read()
        self._finish_read = True

    def _read(self):
        """ Read all buffered input from pipe one chunk at a time and write to pipe.
        """
        while self._read_file.readinto(self._buffer) > 0:
            self._target_file.write(self._buffer.tostring())
        self._target_file.flush()

    def stop(self):
        if not self._is_stop:
            # close write pipe and wait for all reads to be complete.
            self._is_stop = True
            os.close(self.write_fd)
            while not self._finish_read:
                time.sleep(0.1)

            self._read_file.close()

    def __del__(self):
        self.stop()

class runcmd(object):

    WAIT_INTERVAL = 0.5
    INTERRUPT_ERR = -3
    TIMEOUT_ERR   = -2

    def __init__(self):
        self.returncode = -1

    def run(self, cmd, timeout=0, shell=False, cwd=None):
        f = cStringIO.StringIO()
        self.run_fd(cmd, f, timeout, shell, cwd)
        buff = f.getvalue()
        f.close()
        return self.returncode, buff


    def run_fd(self, cmd, out_file, timeout=0, shell=False, cwd=None):

        timeout = sys.maxint if timeout == 0 else timeout
        pipe = PipeData(out_file)

        try:
            if sys.platform == 'win32':
                p = subprocess.Popen(cmd,
                                     shell=shell,
                                     cwd=cwd,
                                     stdout=pipe.write_fd,
                                     stderr=subprocess.STDOUT)
            else:
                # in unix-like system group all predecessors of a process under the same id,
                # making it easier to them all at once. Windows already does this.
                p = subprocess.Popen(cmd,
                                     shell=shell,
                                     cwd=cwd,
                                     stdout=pipe.write_fd,
                                     stderr=subprocess.STDOUT,
                                     preexec_fn=os.setsid)

            # Continuously poll the process "p" until either the process has finished or process timout.
            # if process has timeout, kill it. The "pipe" is reading the output in the background thread,
            # hence it seems as though nothing is happening here.
            curr_time = 0
            pipe.start()
            while p.poll() is None and curr_time < timeout:
                curr_time += runcmd.WAIT_INTERVAL
                time.sleep(runcmd.WAIT_INTERVAL)

            if curr_time >= timeout:
                self.returncode = runcmd.TIMEOUT_ERR
                self._kill(p.pid)
                p.wait()
            else:
                self.returncode = p.returncode

        except (OSError, KeyboardInterrupt, SystemExit, WindowsError):
            # system error or keyboard interrupt
            self.returncode = runcmd.INTERRUPT_ERR

            _tmp = cStringIO.StringIO()
            traceback.print_exc(file=_tmp)
            _tmp_stacktrace = _tmp.getvalue()
            _tmp.close()

            raise CmdRunInterruptError(cmd, _tmp_stacktrace)

        finally:
            pipe.stop()
            pipe.join()


    @staticmethod
    def _kill(pid):
        """ Kill the process, including all of its children.

        Args:
            pid: pid of process
        """
        # Popen.kill() does not kill processes in Windows, only attempts to terminate it, hence
        # we need to kill process here.
        if sys.platform == 'win32':
            k = subprocess.Popen('TASKKILL /PID {0} /T /F >NUL 2>&1'.format(pid), shell=True)
            k.communicate()
        else:
            pid = -pid
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)


def main():

    if sys.platform == 'win32':
        sleep_cmd = 'ping -w 1000 -n {0} 1.1.1.1 >NUL'
    else:
        sleep_cmd = 'sleep {0}'

    cmd = runcmd()
    print cmd.run(sleep_cmd.format(10), timeout=2, shell=True)[1]



if __name__ == "__main__":
    main()
