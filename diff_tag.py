#! /usr/bin/env python
#
# Copyright (c) 2014 Citrix Systems, Inc.
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

from sys import argv, stderr
from optparse import OptionParser
from os import listdir
from json import dumps

try:
    from subprocess import check_output, PIPE, CalledProcessError
except ImportError:
    # from https://gist.github.com/edufelipe/1027906
    from subprocess import Popen, PIPE, CalledProcessError
    def check_output(*popenargs, **kwargs):
        r"""Run command with arguments and return its output as a byte string.

        Backported from Python 2.7 as it's implemented as pure python on stdlib.

        >>> check_output(['/usr/bin/python', '--version'])
        Python 2.6.2
        """
        process = Popen(stdout=PIPE, *popenargs, **kwargs)
        output, _ = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            error = CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output

#Option parsing
def read_options():
    """Read command line options"""
    parser = OptionParser(usage="usage: %prog [options] TAG")

    parser.add_option('-r', '--repository-base', metavar='REPOBASE',
                      default='/home/xc_source/git/xenclient',
                      help='create branch in repos at REPOBASE')
    parser.add_option('-v', '--verbose', help='produce debug output', 
                      action='store_true')
    parser.add_option('-j', '--json-file', help='places output in json format in FILENAME', 
                      action='store', metavar='FILENAME')
    parser.add_option('-p', '--prefix', help='the prefix of build number',
                      action='store')
    parser.add_option('-s', '--suffix', help='the suffix of build number',
                      action='store')
    global options
    options, args = parser.parse_args()

    #Check that tag was provided
    if len(args) != 1:
        parser.print_help()
        exit(1)

    global currentTag
    currentTag = args[0]

#Collect command line options
read_options()
    
data = []

#Print out for info only
if options.verbose:
    print 'Finding previous tag to ' + currentTag

#Get the list of files & directories in repo base
for item in listdir(options.repository_base):
    #Be considerate: do not assume everything in the folder is a git repo...
    if item.find('.git') == -1:
        continue

    #Check if the argument tag exists and find the previous tag. Use 'git tag'
    #as an efficient way to filter tags based on prefix and suffix, but check
    #that what's between them is just a build number. Otherwise, searching for
    #the suffix '-bar' would find tags for branch 'foo-bar' as well as 'bar'.
    repod = options.repository_base + '/' + item
    filter = options.prefix + '*' + options.suffix
    foundCurrentTag = False
    previousTag = None

    for tag in check_output(['git', '--git-dir='+repod, 'tag', '-l', filter]).splitlines():
        if tag == currentTag:
            foundCurrentTag = True

        if ('-' not in tag[len(options.prefix):-len(options.suffix)] and
            tag < currentTag and
            (previousTag is None or tag > previousTag)):
            previousTag = tag

    #Filter out repos that have no idea about the current tag
    if not foundCurrentTag:
        if options.verbose:
            print 'Repo: ' + item + ': tag ' + currentTag + ' not found'
        continue

    #Filter out repos where the current tag is the first
    if previousTag is None:
        print 'Repo: ' + item + ' is new and is the first time it has been tagged.'
        continue

    if options.verbose:
        print 'Repo: ' + item + ': previous tag is ' + previousTag

    #Set up range string and get logs between the tags for the current repo
    grange = currentTag + '...' + previousTag
    logOutput = check_output(['git', '--git-dir='+repod, 'log', grange])

    #Check that there is some log output
    if len(logOutput) == 0:
        continue

    #If being verbose print out the output
    if options.verbose:
        print item + ':'
        print logOutput

    #Get info from git log in line broken form and split to a list
    lineBreakOutput = check_output(['git', '--git-dir='+repod, 'log', "--pretty=format:%H%n%an%n%s", grange]).splitlines()
    linesPerEntry = 3 #Handy little var for code maintenence in the below loops

    if not options.json_file:
        continue

    record = {}
    for i, line in enumerate(lineBreakOutput):
        record[ ['hash', 'author', 'subject'][i%linesPerEntry]] = line
        if i%(linesPerEntry) == linesPerEntry-1:
          record['repo'] = item
          data.append(record)
          record = {}

if options.json_file:
    if options.verbose:
        print 'Writing output in json to', options.json_file
    fj = open(options.json_file, 'w')
    fj.write(dumps(data))
    fj.close()
