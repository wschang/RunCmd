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

class RunCmdError(Exception):
    """
    Base exception for RunCmd.
    """
    def __init__(self, cmd, out):
        self._cmd = cmd
        self._out = out

    def __str__(self):
        return 'Command \"{0}\" raised exception\n. {1}'.format(self._cmd, self._out)


class RunCmdInvalidInputError(RunCmdError):
    """
    Input(s) to cmd was invalid e.g. using shell=False when the shell was required.
    """
    def __init__(self, cmd, out):
        super(RunCmdInvalidInputError, self).__init__(cmd, out)


class RunCmdInterruptError(RunCmdError):
    """
    cmd was interrupted.
    """
    def __init__(self, cmd, out):
        super(RunCmdInterruptError, self).__init__(cmd, out)


class _PipeData(threading.Thread):
    """

    """
    CHUNK_SIZE = 1024

    def __init__(self, dest_file):
        r, w = os.pipe()
        self._out_file    = os.fdopen(r, 'rb')
        self.in_fd        = w
        self._dest_file = dest_file
        self._finish_read = True
        self.is_stop     = True
        self._buffer     = array.array('B', (0 for i in xrange(_PipeData.CHUNK_SIZE)))

        super(_PipeData, self).__init__()

    def start_monitor(self):
        self._finish_read = False
        self.is_stop = False
        self.start()

    def run(self):
        """ Continuously read from pipe and write to the destination file object until
        user calls stop().

        This runs in a background thread.
        """
        while not self.is_stop:
            self._read()
            time.sleep(0.2)

        # read all remaining buffer input from pipe.
        self._read()
        self._finish_read = True

    def _read(self):
        """ Read all buffered input from pipe one chunk at a time and write to pipe.
        """
        read_size = self._out_file.readinto(self._buffer)
        while read_size > 0:
            self._dest_file.write(self._buffer[:read_size].tostring())
            read_size = self._out_file.readinto(self._buffer)
        self._dest_file.flush()

    def stop_monitor(self):
        """ Signal to pipe to stop reading from in_fd and write everything out.

        Once this is called, this object cannot be run again.
        """
        if not self.is_stop:
            # Close the write end of pipe. Wait until everything has been read
            # from the pipe before closing the read end of the pipe as well.
            self.is_stop = True
            os.close(self.in_fd)
            while not self._finish_read:
                time.sleep(0.1)

            self._out_file.close()

    def __del__(self):
        self.stop_monitor()


class RunCmd(object):

    WAIT_INTERVAL = 0.5
    INVALID_INPUT_ERR = -4
    INTERRUPT_ERR = -3
    TIMEOUT_ERR = -2

    def __init__(self):
        self.returncode = -1
        self.cmd = ''

    def run(self, cmd, timeout=0, shell=False, cwd=None):
        f = cStringIO.StringIO()
        # In the event of an exception, we attempt to close the string buffer "f"
        # before raising the exception
        try:
            self.run_fd(cmd, f, timeout, shell, cwd)
            buff = f.getvalue()
        finally:
            f.close()

        return self.returncode, buff

    def run_fd(self, cmd, out_file, timeout=0, shell=False, cwd=None):
        timeout = sys.maxint if timeout == 0 else timeout
        self.cmd = cmd
        pipe = _PipeData(out_file)

        try:
            if sys.platform == 'win32':
                p = subprocess.Popen(cmd,
                                     shell=shell,
                                     cwd=cwd,
                                     stdout=pipe.in_fd,
                                     stderr=subprocess.STDOUT)
            else:
                # in unix-like system group all predecessors of a process under the same id,
                # making it easier to them all at once. Windows already does this.
                p = subprocess.Popen(cmd,
                                     shell=shell,
                                     cwd=cwd,
                                     stdout=pipe.in_fd,
                                     stderr=subprocess.STDOUT,
                                     preexec_fn=os.setsid)

        except (ValueError, WindowsError):
            self.returncode = RunCmd.INVALID_INPUT_ERR

            _tmp = cStringIO.StringIO()
            traceback.print_exc(file=_tmp)
            _tmp_stacktrace = _tmp.getvalue()
            _tmp.close()
            raise RunCmdInvalidInputError(cmd, _tmp_stacktrace)

        try:
            # Continuously poll the process "p" until either the process has finished or process timeout.
            # if process has timeout, kill it. The "pipe" is reading the output in the background thread,
            # hence it seems as though nothing is happening here.
            curr_time = 0
            pipe.start_monitor()
            while p.poll() is None and curr_time < timeout:
                curr_time += RunCmd.WAIT_INTERVAL
                time.sleep(RunCmd.WAIT_INTERVAL)

            if curr_time < timeout:
                self.returncode = p.returncode
            else:
                self.returncode = RunCmd.TIMEOUT_ERR
                self._kill(p.pid)
                p.wait()

        except (OSError, KeyboardInterrupt, SystemExit, WindowsError):
            # system error or keyboard interrupt
            self.returncode = RunCmd.INTERRUPT_ERR

            _tmp = cStringIO.StringIO()
            traceback.print_exc(file=_tmp)
            _tmp_stacktrace = _tmp.getvalue()
            _tmp.close()
            raise RunCmdInterruptError(cmd, _tmp_stacktrace)

        finally:
            pipe.stop_monitor()
            pipe.join()

    @staticmethod
    def _kill(pid):
        """ Kill the process immediately.

        Args:
            pid: pid of process to be killed.
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

    test = '{0} -c "print \'Hello World\'"'.format(sys.executable)
    test = 'echo Hello'
    test = '{0} -c "import sys\nsys.exit(-1)"'.format(sys.executable)

    cmd = RunCmd()
    print cmd.run(sleep_cmd.format(10), timeout=0, shell=True)



if __name__ == "__main__":
    main()
