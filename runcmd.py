#! /usr/bin/env python

#
# The MIT License (MIT)
#
# Copyright (c) 2014 Wen Shan Chang
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import subprocess
import threading
import os
import sys
import time
import StringIO
import traceback
import signal
import contextlib

__version_info__ = ('0', '2', '4')
__version__ = '.'.join(__version_info__)
__author__ = 'Wen Shan Chang'

# defined WindowsError exception for platforms which
# do not have it
if not getattr(__builtins__, "WindowsError", None):

    class WindowsError(OSError):
        pass


class RunCmdError(Exception):
    """
    Base exception for RunCmd.
    """
    def __init__(self, err_msg):
        self._err_msg = err_msg

    def __str__(self):
        return self._err_msg


class RunCmdInternalError(RunCmdError):
    """
    An internal error has occurred. This is an error you do not want to see.
    """
    def __init__(self, err_msg):
        super(RunCmdInternalError, self).__init__(err_msg)


class RunCmdInvalidInputError(RunCmdError):
    """
    Input(s) to cmd was invalid e.g. using shell=False when the shell was required.
    """
    def __init__(self, err_msg):
        super(RunCmdInvalidInputError, self).__init__(err_msg)


class RunCmdInterruptError(RunCmdError):
    """
    cmd was interrupted.
    """
    def __init__(self, cmd, err_msg):
        self._cmd = cmd
        super(RunCmdInterruptError, self).__init__(err_msg)

    def __str__(self):
        return 'Command "{}" raised exception\n. {}'.format(self._cmd, self._err_msg)


class _PipeData(threading.Thread):
    """ A pipe which continuously reads from a source and writes to a destination file object
    in the background.

    Use the "with" statement to manage the context of the _PipeData instance,
    e.g.:
        is_keep_reading = True
        with _PipeData(out_file) as pipe:
            while is_keep_reading and not pipe.is_error:
                # do something.

            if pipe.is_error:
                print pipe.error_msg

    Once the pipe has finished, it cannot be reused. Instead, a new PipeData instance must be
    created.

    Attributes:
        is_stop     : boolean indicating if the pipe has finished reading from the source.
        in_fd       : file descriptor representing the input to the pipe. Pass this to the
                      source of the data to be read
        dest_file   : the destination file object. This is the file where the data is
                      written out to
        is_error    : error status. True if an unrecoverable error has occurred. The caller
                      should monitor this value regularly.
        error_msg   : contains the error message. If no error had occurred, this is set to None.

        _out_file   : an internal file object representing the output of pipe.
        _finish_read : boolean to indicate when the pipe has finished reading from the source.
        _buffer     : a buffer used to temporarily store the chunks of data read from the source.
    """
    # Number of bytes to read in at a time.
    CHUNK_SIZE = 1

    def __init__(self, dest_file):
        """ Constructor

        Args:
            dest_file: file object where the data will be written into.
        """
        r, w = os.pipe()
        # set both is_stop and finish_read to True during init to avoid hanging if _PipeData
        # fails to initialise. Set both booleans to False upon __enter__
        self.is_stop = True
        self._finish_read = True
        self.in_fd = w
        self.is_error = False
        self.error_msg = None
        self._dest_file = dest_file
        self._out_file = os.fdopen(r, 'rb')
        self._buffer = bytearray(_PipeData.CHUNK_SIZE)

        # we expect a valid dest file to be passed in. The dest_file is not guaranteed to be a
        # file (e.g. StringIO) hence we cannot check its mode directly.
        try:
            dest_file.write('')
        except (IOError, ValueError):
            raise RunCmdInvalidInputError('Error: file object passed in is not writable '
                                          '/ closed.')

        super(_PipeData, self).__init__()

    def __enter__(self):
        self._finish_read = False
        self.is_stop = False
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop()

    def run(self):
        """ Continuously read from the source and write to the destination file object until
        user calls stop().

        This runs in a background thread.
        """
        while not self.is_stop and not self.is_error:
            self._read()
            time.sleep(0.2)

        # read all remaining buffer input from pipe.
        if not self.is_error:
            self._read()
        self._finish_read = True

    def _read(self):
        """ Read all content buffered in the pipe one chunk at a time and write to the
        destination file object.
        """
        try:
            # this blocks until out_file writes at least CHUNK_SIZE worth of data.
            read_size = self._out_file.readinto(self._buffer)
            while read_size:
                self._dest_file.write(self._buffer[:read_size])
                read_size = self._out_file.readinto(self._buffer)
            self._dest_file.flush()
        except Exception as e:
            self.is_error = True
            self.error_msg = "{} raised exception {}".format(self.__class__.__name__, str(e))

    def _stop(self):
        """ Signal to pipe to stop reading from in_fd and write everything out.

        Once this is called, this object cannot be run again.
        """
        if self.is_stop:
            return

        # Close the write end of pipe. Wait until everything has been read
        # from the pipe before closing the read end of the pipe as well.
        self.is_stop = True
        os.close(self.in_fd)
        while not self._finish_read:
            time.sleep(0.1)

        self._out_file.close()
        self.join()

    def __del__(self):
        """ Stop the monitoring process if object gets deleted.
        """
        self._stop()


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
        self.return_code = -1
        self.cmd = ''

    def run(self, cmd, timeout=0, shell=False, cwd=None):
        """ Runs the command and return the return code and output.

        This is similar to Popen.communicate().Note that it is assumed the output of the command
        will not exceed the available memory. For larger outputs, use cmd_fd()

        Args:
            cmd     : Command to run.
            timeout : Seconds to wait before terminating command. Timeout must be an positive
                      integer. If timeout <= 0, RunCmd will wait indefinitely. Defaults to 0.
            shell   : Boolean to indicate if the shell should be invoked or not.
                      Defaults to False.
            cwd:    : Directory to run command in. If none is given the command will be run in
                      the current directory. Default is None.
        Returns:
            A tuple of (returncode, out) where returncode is the returncode from the subprocess
            and out is a buffer containing the output.

        Exceptions:
            RunCmdInvalidInputError : Command had invalid parameters.
            RunCmdInterruptError    : Command was interrupted, e.g. a Keyboard interrupt signal.
        """
        buff = None
        with contextlib.closing(StringIO.StringIO()) as f:
            self.run_fd(cmd, f, timeout, shell, cwd)
            buff = f.getvalue()

        return self.return_code, buff

    def run_fd(self, cmd, out_file, timeout=0, shell=False, cwd=None):
        """ Runs the command and writes the output into the user specified file object.

        Similar to RunCmd.run() but allows user to specify a file object where the output will be
        written into. The returncode can be retrieved from the member value, returncode.

        Args:
            cmd     : Command to run.
            out_file: File object which the command will write its output to.
            timeout : Seconds to wait before terminating command. Timeout must be an positive
                      integer. If timeout <= 0, RunCmd will wait indefinitely. Defaults to 0.
            shell   : Boolean to indicate if the shell should be invoked or not.
                      Defaults to False.
            cwd:    : Directory to run command in. If none is given the command will be run in
                      the current directory. Default is None.
        Exceptions:
            RunCmdInvalidInputError : Command had invalid parameters.
            RunCmdInterruptError    : Command was interrupted, e.g. a Keyboard interrupt signal.
        """
        self.cmd = cmd

        # if no command was sent in, consider it successful and return.
        if cmd is None or len(cmd) == 0:
            self.return_code = 0
            return

        if not out_file:
            raise RunCmdInvalidInputError("Error: out_file is None; expected file object.")

        timeout = sys.maxint if int(timeout) <= 0 else int(timeout)
        with _PipeData(out_file) as pipe:
            p = None
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

                # Continuously poll the process "p" until either the process has finished or
                # process timeout. If the process has exceeded the timeout limit, kill it.
                # Note the "pipe" is continuously reading the output in a the background thread.
                curr_time = 0
                while p.poll() is None and curr_time < timeout and not pipe.is_error:
                    curr_time += RunCmd.WAIT_INTERVAL
                    time.sleep(RunCmd.WAIT_INTERVAL)

                if pipe.is_error:
                    # pipe error
                    self._kill(p.pid)
                    raise RunCmdInternalError(pipe.error_msg)
                elif curr_time >= timeout:
                    # timeout
                    self.return_code = RunCmd.TIMEOUT_ERR
                    self._kill(p.pid)
                else:
                    #normal case
                    self.return_code = p.returncode

            except (WindowsError, OSError):
                self.return_code = RunCmd.INVALID_INPUT_ERR
                raise RunCmdInvalidInputError(traceback.format_exc())

            except KeyboardInterrupt:
                self.return_code = RunCmd.INTERRUPT_ERR
                self._kill(p.pid)
                raise RunCmdInterruptError(cmd, traceback.format_exc())

    @staticmethod
    def _kill(pid):
        """ Kill the process immediately.

        Args:
            pid: pid of process to be killed.
        """
        # Popen.kill() does not kill processes in Windows, only attempts to terminate it, hence
        # we need to kill process here.
        if sys.platform == 'win32':
            k = subprocess.Popen('TASKKILL /PID {} /T /F >NUL 2>&1'.format(pid), shell=True)
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
                      help='Command to run. Must be enclosed in double quotes, '
                           'e.g. -c"echo Hello"')

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
    return_code, out = cmd.run(options.cmd.strip('"'),
                               timeout=options.timeout,
                               shell=options.is_shell,
                               cwd=options.dir)
    print out
    return return_code


if __name__ == "__main__":
    ret = main()
    sys.exit(ret)


