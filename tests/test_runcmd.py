#! /usr/bin/env python

__author__ = 'Chang'


import os
import sys
import subprocess
import cStringIO
import unittest

# add module's root folder as part of search path
ROOT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
sys.path.insert(0, ROOT_DIR)

from runcmd import *

# Dictionary of commands for each platform. Each entry in dictionary is the output of sys.platform.
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

        self.assertEqual(ret, cmd.returncode)
        self.assertEqual(ret, 0)
        self.assertEqual(out, o)

    def test_timeout(self):
        """ Run a sleep command for 10s timeout in 2s
        """
        cmd = RunCmd()
        cmd.run(test_cmds['sleep'] % (10), timeout=1, shell=True)
        self.assertEqual(cmd.returncode, RunCmd.TIMEOUT_ERR)

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

        self.assertEqual(ret, cmd.returncode)
        self.assertEqual(ret, 0)
        self.assertEqual(out, o)

    def test_no_cmd(self):
        """ pass in no command, either as None or empty string.
        """
        cmd = RunCmd()

        ret, out = cmd.run(None)
        self.assertEqual(ret, cmd.returncode)
        self.assertEqual(ret, 0)

        ret, out = cmd.run('')
        self.assertEqual(ret, cmd.returncode)
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

        self.assertEqual(ret, cmd.returncode)
        self.assertEqual(ret, 0)
        self.assertEqual(out, o)

    def test_cmd_fd(self):
        """ use RunCmd.run_fd() instead of RunCmd.run().
        Pass in a file descriptor to the command.
        """
        f = cStringIO.StringIO()
        cmd = RunCmd()
        cmd.run_fd(test_cmds['ls'], f, timeout=0, shell=True)
        out = f.getvalue()
        f.close()

        p = subprocess.Popen(test_cmds['ls'],
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        o = p.communicate()[0]

        self.assertEqual(cmd.returncode, 0)
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
