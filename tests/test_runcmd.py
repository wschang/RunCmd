#! /usr/bin/env python

__author__ = 'Chang'


import os
import sys
import subprocess
import unittest

# add module's root folder as part of search path
ROOT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
sys.path.insert(0, ROOT_DIR)

from runcmd import *

# Dictionary of commands for each platform. Each entry in dictionary is the output of sys.platform.
_cmds = {

    'win32': {
        'sleep': 'ping -w 1000 -n {0} 1.1.1.1 >NUL',
        'ls'   : 'dir/w',
        'echo' : 'echo {0}',
        'hello': '{0} -c "print \'Hello World\'"'.format(sys.executable)
    },

    'linux': {
        'sleep': 'sleep {0}',
        'ls'   : 'ls',
        'echo' : 'echo {0}',
        'hello': '{0} -c "print \'Hello World\'"'.format(sys.executable)
    }
}

# points to the correct set of commands per platform
test_cmds = _cmds[sys.platform]


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
        cmd.run(test_cmds['sleep'].format(10), timeout=1, shell=True)
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

    def test_no_shell(self):
        """ run a command without using the shell. Pass a simple print statement
            to the python interpreter.
        """
        cmd = RunCmd()
        ret, out = cmd.run(test_cmds['hello'], timeout=0, shell=False)

        p = subprocess.Popen(test_cmds['hello'],
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
            print cmd.run(test_cmds['echo'].format('Hello'), timeout=0, shell=False)
        except RunCmdInvalidInputError:
            return

        self.assertTrue(False)

    #TODO
    #   1. Test how it handles interrupts
    #   2. Test forced killing of children process.

def main():
    unittest.main()

if __name__ == "__main__":
    main()
