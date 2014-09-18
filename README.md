# RunCmd #

RunCmd is ia Python module which allows you to run a command **with a timeout option**.

## Introduction ##

RunCmd can be considered a substitute for a common subprocess usage pattern:

```python
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
ret, out = p.communicate()
```

But with additional option to **set a timeout** for the command. Like `subprocess.Popen`, this is a blocking call, and will wait for either the command to complete or a timeout to occur.

RunCmd is not meant to be a replacement for subprocess module itself.

## Compatibility ##

* supports **Python 2.6x** and **Python 2.7x**. 
* runs under both **Windows** and **Linux**. It should run under **OSX**.

## How to run ##

### Installation ###
Just copy the the runcmd.py file into your directory. Or use the [setup.py](./setup.py) if you wish to install it.

### Example Code ###
RunCmd has two methods: `RunCmd.run()` and `RunCmd.run_fd()`.

`RunCmd.run()` reads the output into am internal buffer and return the output to the user as a tuple of (returncode, output).

```python
from runcmd import RunCmd

cmd = RunCmd()
#run the command using the shell and a timeout of 5 seconds.
returncode, out = cmd.run('echo Hello World', shell=True, timeout=5)
print "returncode is %d. Output is %s" % (returncode, out)
```

`RunCmd.run()` is not suitable for handling processes with large volume of data as it attempts to buffer the entire output. Instead, use`RunCmd.run_fd()`, which allows a user to pass in a file object where the output will be written into. 

```python
from runcmd import RunCmd

with open('tmp.txt', 'wb') as f:
    cmd = RunCmd()
    # run the command using the shell and a timeout of 5 seconds.
    cmd.run_fd('echo Hello World', f, shell=True, timeout=5)

print "returncode is %d. Output is %s" % (cmd.returncode, open('tmp.txt', 'rb').read())
```

`RunCmd.run_fd` can handle large volume of data; there is a utility script under [./util/generate_output.py](./util/generate_output.py) which can simulate output of different sizes. Try simulating a *1GB* output :-).


RunCmd has a CLI as well. For example,
```python
python runcmd.py --cmd="echo Hello World" --shell --timeout=5
```

### Testing ###
RunCmd has a unittests script. See [./tests/test_runcmd.py](./tests/test_runcmd.py).

## License ##
RunCmd is released under the MIT license. See [LICENSE.txt](./LICENSE.txt)
