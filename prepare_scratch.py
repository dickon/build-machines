#! /usr/bin/env python
#
# Copyright (c) 2013 Citrix Systems, Inc.
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

from optparse import OptionParser
from os.path import exists, abspath, realpath, split, islink, join
from subprocess import check_call, call, PIPE, CalledProcessError, Popen
from os import mkdir, chown, chdir, getcwd, readlink
from time import time, sleep
from sys import stderr

def check_output(*popenargs, **kwargs):
    """Run command with arguments and return its output as a byte string."""
    process = Popen(stdout=PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        error = CalledProcessError(retcode, cmd)
        error.output = output
        raise error
    return output

parser = OptionParser()
parser.add_option('-u', '--user', metavar='USER', help='Chown directory to USER', default='build')
parser.add_option('-d', '--directory', metavar='DIRECTORY', help='Prepare DIRECTORY', default='scratch')
parser.add_option('-b', '--block-device', metavar='DEVICE', help='Use DEVICE to store DIRECTORY', default='/dev/md/buildtemp')
options, _ = parser.parse_args()

directory = abspath(options.directory)
block_device = realpath(options.block_device)
print 'INFO: looking for users of', block_device
make_it = lambda: check_call(['mkdir', '-p', directory])
if not exists(options.block_device):
    check_call(['rm', '-rf', directory])
    make_it()
else:
    t0 = time()
    while True:
        mountpoint = None
        for line in file('/proc/mounts').readlines():
            spl = line.split()
            if spl and spl[0] == block_device:
                mountpoint = spl[1] # assume no spaces in directory name
        if mountpoint is None:
            break
        print 'INFO:', block_device, 'mounted at', mountpoint
        td = time() - t0
        if td > 60:
            print >>stderr, 'ERROR: unable to umount', directory, 'after', td, 'seconds'
            exit(1)
        rc = call(['fuser', '-v', '-k', '-M', '-m', mountpoint])
        if rc != 0:
            print >>stderr, 'ERROR: fuser -k failed with code', rc
        rc2 = call(['umount', mountpoint])
        if rc2 != 0:
            print >>stderr, 'ERROR: umount failed with code', rc2
        sleep(1)
    check_call(['mkfs.ext3', block_device])
    make_it()
    check_call(['mount', block_device, directory])

check_call(['chown', options.user, directory])

