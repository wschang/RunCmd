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


#
# generate_output.py
#
# Generate an output of a specified size to stdout.
#
# This is useful for testing how RunCmd handles large output. For example
# the snippet of code below will generate 50 MB of data and pipe the data to a file
# named 'tmp' via RunCmd.
#
# from runcmd import *
#
# with open('tmp', 'wb') as f:
#   c = RunCmd()
#   c.run_fd('python generate_output.py 50 m', out_file=f)
#


__author__ = 'Wen Shan Chang'

import sys

#number of bytes per KB, MB, GB
UNIT_VALUES = {
    'k': 1024,
    'm': 1048576,
    'g': 1073741824,
}

STRING = 'This is a test string from generate_output.py: '

def main(size, file_obj):
    if size <= 0:
        return

    written_bytes = 0
    i = 0
    while written_bytes < size:
        line = "{}{}\n".format(STRING, i)
        file_obj.write(line)
        i += 1
        written_bytes += len(line)

    file_obj.write("Written {} bytes.\n".format(written_bytes))

if __name__ == "__main__":

    if (len(sys.argv) != 3):
        print "Usage: python generate_output.py size unit, where size is an integer, unit is [k|m|g]"
        print " e.g. Generate a 2 megabyte worth of output: python generate_output.py 2 m"
        sys.exit(1)

    is_error = True
    data_size = 0
    try:
        data_size = int(sys.argv[1])
        data_size *= UNIT_VALUES[sys.argv[2].lower()]
        is_error = False

    except ValueError:
        print "Error: size must be an integer"

    except KeyError:
        print "Error: unknown unit {}. Possible units are {}".\
              format(sys.argv[2], [u for u in UNIT_VALUES.iterkeys()])

    if data_size <= 0:
        print "Error: size must be > 0"
        is_error = True

    if not is_error:
        main(data_size, sys.stdout)
    else:
        print "Exiting."
        sys.exit(1)

