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


__author__ = 'Wen Shan Chang'

import unittest
import os
import sys
import StringIO

# add module's root folder as part of search path
ROOT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
sys.path.insert(0, ROOT_DIR)

from runcmd import *

# Dictionary of commands for each platform. Each entry in dictionary is the
# output of sys.platform.
_cmds = {

    'win32': {
        'sleep': 'ping -w 1000 -n %d 1.1.1.1 >NUL',
        'ls'   : 'dir',
        'echo' : 'echo %s',
        'no_shell': '%s -c "print \'Hello World\'"' % (sys.executable)
    },

    'linux2': {
        'sleep': 'sleep %d',
        'ls'   : 'ls',
        'echo' : 'echo %s',
        'no_shell': 'ls'
    }
}

# points to the correct set of commands per platform. Defaults to
# the linux set of commands if the platform cannot be found.
try:
    test_cmds = _cmds[sys.platform]
except KeyError:
    test_cmds = _cmds['linux2']


class RunCmdTest(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_cmd(self):
        """ A simple cmd to list contents of current directory.
        """
        cmd = RunCmd()
        ret, out = cmd.run(test_cmds['ls'], timeout=0, shell=True)

        p = subprocess.Popen(test_cmds['ls'],
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        o = p.communicate()[0]

        self.assertEqual(ret, cmd.return_code)
        self.assertEqual(ret, 0)
        self.assertEqual(out, o)

    def test_timeout(self):
        """ Run a sleep command for 10s timeout in 2s
        """
        cmd = RunCmd()
        cmd.run(test_cmds['sleep'] % (10), timeout=1, shell=True)
        self.assertEqual(cmd.return_code, RunCmd.TIMEOUT_ERR)

    def test_set_cwd(self):
        """ Change the current working directory using cwd
        """
        cmd = RunCmd()
        parent_dir = os.path.join('..')
        ret, out = cmd.run(test_cmds['ls'], timeout=0, shell=True, cwd=parent_dir)

        p = subprocess.Popen(test_cmds['ls'],
                             cwd=parent_dir,
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        o = p.communicate()[0]

        self.assertEqual(ret, cmd.return_code)
        self.assertEqual(ret, 0)
        self.assertEqual(out, o)

    def test_no_cmd(self):
        """ pass in no command, either as None or empty string.
        """
        cmd = RunCmd()

        ret, out = cmd.run(None)
        self.assertEqual(ret, cmd.return_code)
        self.assertEqual(ret, 0)

        ret, out = cmd.run('')
        self.assertEqual(ret, cmd.return_code)
        self.assertEqual(ret, 0)

    def test_null_fd(self):
        """ Passed in None for the file object
        """
        try:
            cmd = RunCmd()
            cmd.run_fd(test_cmds['no_shell'], None)
        except RunCmdInvalidInputError:
            return

        self.assertTrue(False)

    def test_no_shell(self):
        """ Run a command without using the shell.
        """
        cmd = RunCmd()
        ret, out = cmd.run(test_cmds['no_shell'], timeout=0, shell=False)

        p = subprocess.Popen(test_cmds['no_shell'],
                             shell=False,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        o = p.communicate()[0]

        self.assertEqual(ret, cmd.return_code)
        self.assertEqual(ret, 0)
        self.assertEqual(out, o)

    def test_cmd_fd(self):
        """ use RunCmd.run_fd() instead of RunCmd.run().
        Pass in a file descriptor to the command.
        """
        f = StringIO.StringIO()
        cmd = RunCmd()
        cmd.run_fd(test_cmds['echo'] % 'Hello', f, timeout=0, shell=True)
        out = f.getvalue()
        f.close()

        p = subprocess.Popen(test_cmds['echo'] % 'Hello',
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        o = p.communicate()[0]

        self.assertEqual(cmd.return_code, 0)
        self.assertEqual(out, o)

    def test_invalid_input(self):
        """ Check command throws an exception when the command is invalid.
        For example, running a shell command with shell=False

        """
        cmd = RunCmd()
        try:
            print cmd.run(test_cmds['echo'] % ('Hello'), shell=False)
        except RunCmdInvalidInputError:
            return

        self.assertTrue(False)

    #TODO
    #   1. Test for RunCmdInterruptError.
    #   2. Test forced killing of children process.
    #   3. Test _PipeData?

def main():
    unittest.main()

if __name__ == "__main__":
    main()
