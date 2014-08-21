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

__version_info__ = ('0', '1', '0')
__version__ = '.'.join(__version_info__)

# defined WindowsError exception for platforms which
# do not have it
if not getattr(__builtins__, "WindowsError", None):
    class WindowsError(OSError):
        pass


class RunCmdError(Exception):
    """
    Base exception for RunCmd.
    """
    def __init__(self, cmd, out):
        self._cmd = cmd
        self._out = out

    def __str__(self):
        return 'Command \"%s\" raised exception\n. %s' % (self._cmd, self._out)


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
    """ A pipe which continuously reads from a source and writes to a destination file object
    in a background thread.

    Once the pipe has finished reading, it cannot be restarted. Instead, a
    new PipeData object must be created.

    Attributes:
        is_stop     : boolean indicating if the pipe has finished reading from the source.
        in_fd       : file descriptor representing the input to the pipe. Pass this to the
                      source of the data to be read
        dest_file   : the destination file object. This is the file where the data is written out to

        _out_file   : an internal file object representing the output of pipe.
        _finish_read : boolean to indicate when the pipe has finished reading from the source.
        _buffer     : a buffer used to temporarily store the chunks of data read from the source.
    """
    CHUNK_SIZE = 1024

    def __init__(self, dest_file):
        """ Constructor

        Args:
            dest_file: file object where the data will be written into.
        """
        # we expect the dest file to be passed in.
        assert dest_file

        r, w = os.pipe()
        self._out_file = os.fdopen(r, 'rb')
        self.in_fd = w
        self._dest_file = dest_file
        self._finish_read = True
        self.is_stop = True
        self._buffer = array.array('B', (0 for _ in xrange(_PipeData.CHUNK_SIZE)))

        super(_PipeData, self).__init__()

    def start_monitor(self):
        """ Start reading from the source.

         Users must first set "in_fd" to a source first before calling this.
        """
        self._finish_read = False
        self.is_stop = False
        self.start()

    def run(self):
        """ Continuously read from the source and write to the destination file object until
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
        """ Read all content buffered in the pipe one chunk at a time and write to the
        destination file object.
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
        """ Stop the monitoring process if object gets deleted.
        """
        self.stop_monitor()


class RunCmd(object):
    """ Runs a command in a subprocess and wait for it to return or timeout.

    This is a substitute for a common subprocess usage pattern:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ret, out = p.communicate()

    With additional support for a timeout for the command. This is a blocking call,
    which will wait for either the command to complete or a timeout to occur.

    Attributes:
        returncode  : The return code as returned from the process. There are also special
                      returncode values set if RunCmd encounters issues running the command.
                      See Error ReturnCode section for more details.
        cmd         : The command used.

    Error ReturnCode:
        INVALID_INPUT_ERR: Invalid parameters were used.
        INTERRUPT_ERR    : Command was interrupted, e.g. Keyboard interrupt signal sent
        TIMEOUT_ERR      : Runtime of command has exceed set timeout and was forced to
                           terminate.
    """

    WAIT_INTERVAL = 0.5
    INVALID_INPUT_ERR = -4
    INTERRUPT_ERR = -3
    TIMEOUT_ERR = -2

    def __init__(self):
        """ Constructor
        """
        self.returncode = -1
        self.cmd = ''

    def run(self, cmd, timeout=0, shell=False, cwd=None):
        """ Runs the command and return the return code and output.

        This is similar to Popen.communicate().Note that it is assumed the output of the command
        will not exceed the available memory. For larger outputs, use cmd_fd()

        Args:
            cmd     : Command to run.
            timeout : Seconds to wait before terminating command. Timeout must be an positive integer.
                      If timeout <= 0, RunCmd will wait indefinitely. Defaults to 0.
            shell   : Boolean to indicate if the shell should be invoked or not. Defaults to False.
            cwd:    : Directory to run command in. If none is given the command will be run in the
                      current directory. Default is None.
        Returns:
            A tuple of (returncode, out) where returncode is the returncode from the subprocess and
            out is a buffer containing the output.

        Exceptions:
            RunCmdInvalidInputError : Command had invalid parameters.
            RunCmdInterruptError    : Command was interrupted, e.g. a Keyboard interrupt signal.
        """
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
        """ Runs the command and writes the output into the user specified file object.

        Similar to RunCmd.run() but allows user to specify a file object where the output will be
        written into. The returncode can be retrieved from the member value, returncode.

        Args:
            cmd     : Command to run.
            out_file: File object which the command will write its output to.
            timeout : Seconds to wait before terminating command. Timeout must be an positive integer.
                      If timeout <= 0, RunCmd will wait indefinitely. Defaults to 0.
            shell   : Boolean to indicate if the shell should be invoked or not. Defaults to False.
            cwd:    : Directory to run command in. If none is given the command will be run in the
                      current directory. Default is None.
        Exceptions:
            RunCmdInvalidInputError : Command had invalid parameters.
            RunCmdInterruptError    : Command was interrupted, e.g. a Keyboard interrupt signal.
        """
        self.cmd = cmd
        if cmd is None or len(cmd) == 0:
            self.returncode = 0
            return

        if out_file is None:
            raise RunCmdInvalidInputError(cmd,
                                          'Error: "out_file" parameter expected a file object,'
                                          'receive None instead')

        timeout = sys.maxint if int(timeout) <= 0 else int(timeout)
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

        except (ValueError, WindowsError, OSError):
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
            k = subprocess.Popen('TASKKILL /PID %d /T /F >NUL 2>&1' % (pid), shell=True)
            k.communicate()
        else:
            pid = -pid
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)


def main():
    """ Provides a command line interface to RunCmd.run(). The output is printed out to stdout.

    Returns 0 if command was run successfully, otherwise an error had occurred.
    """
    import optparse

    parser = optparse.OptionParser()
    parser.add_option('-c', '--cmd',
                      action='store',
                      type='string',
                      dest='cmd',
                      help='Command to run. Must be enclosed in double quotes, e.g. -c"echo Hello"')

    parser.add_option('-t', '--timeout',
                      action='store',
                      type='int',
                      default=0,
                      dest='timeout',
                      help='Time in seconds to wait for the command to finish before forcibly '
                           'terminating it. Defaults to 0 which makes it wait indefinitely.')

    parser.add_option('-s', '--shell',
                      action='store_true',
                      default=False,
                      dest='is_shell',
                      help='Set to run command with a shell. Defaults to no shell.')

    parser.add_option('-d', '--cwd',
                      action='store',
                      type='string',
                      dest='dir',
                      help="Path to directory where the command will be run in. "
                           "Default is the current directory")

    (options, args) = parser.parse_args()

    if options.cmd is None:
        print "No command supplied. Exiting now."
        return 0

    cmd = RunCmd()
    returncode, out = cmd.run(options.cmd.strip('"'),
                              timeout=options.timeout,
                              shell=options.is_shell,
                              cwd=options.dir)
    print out
    return returncode



if __name__ == "__main__":
    returncode = main()
    sys.exit(returncode)


