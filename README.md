# RunCmd #

RunCmd is ia Python module which allows you to run a command in the background
but **with the addition of a timeout option**.

## Introduction ##

RunCmd can be considered a substitute for  a common subprocess usage pattern:

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ret, out = p.communicate()

But with additional option to set a timeout for the command.
Like ```subprocess.Popen```, this is a blocking call, and will wait for either
the command to complete or a timeout to occur.

RunCmd is not meant to be a replacement for subprocess module itself.

## Compatibility ##

* supports **Python 2.6x** and **Python 2.7x**. It does not support
**Python 3.x**.
* runs under both **Windows** and **Linux**. It should run under **OSX**
but this has not been tested.

## Setup ##

### Installation ###
Just copy the the runcmd.py file into your directory. In the future,
perhaps a setup.py file could be added.

### Example Code ###
RunCmd has two methods: ```RunCmd.run()``` and ```RunCmd.run_fd()```.

```RunCmd.run()``` reads the output into am internal buffer and return the
output to the user as a tuple of (returncode, output)

    from runcmd import RunCmd

    cmd = RunCmd()
    # run the command using the shell and a timeout of 5 seconds.
    returncode, out = cmd.run('echo Hello World', shell=True, timeout=5)
    print "returncode is %d. Output is %s" % (returncode, out)

```RunCmd.run_fd()``` is similar to ```RunCmd.run```, excepts it allows
the user to pass in a file object where the output will be written into.
This is useful when a large amount of output is expected.

    from runcmd import RunCmd

    with open('tmp.txt', 'wb') as f:
        cmd = RunCmd()
        # run the command using the shell and a timeout of 5 seconds.
        cmd.run_fd('echo Hello World', f, shell=True, timeout=5)

    print "returncode is %d. Output is %s" % (cmd.returncode, open('tmp.txt', 'rb').read())

In addition, RunCmd has a CLI as well. For example,

    python runcmd.py --cmd="echo Hello World" --shell --timeout=5


### Testing ###
RunCmd has a unittests script See [./tests/test_runcmd.py](./tests/test_runcmd.py).

## License ##
RunCmd is released under the MIT license. See [LICENSE.txt](./LICENSE.txt)
