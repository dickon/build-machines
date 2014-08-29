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

from optparse import OptionParser
from os import umask, geteuid
from json import loads, dump
from sys import stderr
from time import time

GIT_TAG_PREFIX = 'tag: '

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

def read_options():
    """Read command line options"""
    parser = OptionParser()

    parser.add_option('-b', '--branch', metavar='BRANCH', action='append',
                      default=list(), help='create tag or inspect BRANCH')
    parser.add_option('-l', '--branches-file', metavar='FILENAME',
                      help='Read branches list from FILENAME')
    parser.add_option('-r', '--repository-base', metavar='REPOBASE',
                      default='/home/xc_source/git/xenclient',
                      help='create branch in repos at REPOBASE')
    parser.add_option('-s', '--server', 
                      metavar='SERVER', help='ssh to SERVER to run commands')
    parser.add_option('-u', '--user', default='git',
                      metavar='USER', help='ssh as USER')
    parser.add_option('-t', '--tag', action='store_true', help='create tag')
    parser.add_option('-v', '--verbose', help='produce debug output', 
                      action='store_true')
    parser.add_option('-f', '--force', help='create tag even if unnecessary',
                      action='store_true')
    parser.add_option('--time-commands', help='show subprocess runtimes',
                      action='store_true')
    parser.add_option('-i', '--inspection-repository', metavar='REPO',
                      help='Look in REPO for tags and repositories.txt', 
                      default='build-config')
    parser.add_option('--tag-format', default='%s%06d-%s', metavar='PATTERN',
                      help='Tag format is pATTERN, interpolated with prefix, tag number and branch')
    parser.add_option('-d', '--dump-json', action='store',metavar='FILE',
                      help='dump JSON record of repositories to FILE')
    global options, args
    options, args = parser.parse_args()

def command(args, **kw):
    """Run command described by args on server"""
    t0 = time()
    try:
        if options.server:
            out = check_output(['ssh', options.user+'@'+options.server, 
                                " ".join("'" + x.replace("'", "'\"'\"'") + "'" for x in args)], **kw)
        else:
            out = check_output(args, **kw)
    finally:
        t1 = time()
        if options.time_commands:
            print >>stderr, '%dms for %s' % ((t1-t0)*1000, ' '.join(args))
    return out

def get_repositories(branch):
    """Return contents of repositories list on branch and its format"""
    extns =['json', 'txt']
    for extn in extns:
        gdo = '--git-dir='+options.repository_base+'/'+options.inspection_repository+'.git'
        tfile = branch+':repositories.'+extn
        try:
            return command(['git', gdo, 'show', tfile]), extn
        except CalledProcessError:
            if extn == extns[-1]:
                raise

def get_head(branch, repod):
    """Get head on branch"""
    return command(['git', '--git-dir='+ repod, 'rev-parse', '-q', '--verify', branch]).strip()

def find_highest_tag_number(repod, branch=None):
    """Work out next tag number on repod across all branches or
    a specific branch"""
    postfix = ('-'+branch) if branch else ''
    filter = tag_prefix+'*'+postfix
    tags = command(['git', '--git-dir='+repod, 'tag', '-l', filter]).split()
    itags = [] # the integer part of tags
    for tag in tags:
        try:
            if branch:
                num = int(tag[len(tag_prefix):-len(postfix)])
            else:
                num = int(tag[len(tag_prefix):].split('-')[0])
        except ValueError:
            continue
        itags.append(num)
    return sorted(itags)[-1] if tags else 0

def allocate_tag_number():
    """Work out next tag number"""
    return find_highest_tag_number(options.repository_base+'/'+
                                   options.inspection_repository+'.git')+1

def set_tag(tag, repod, revision):
    """apply tag to revision on repod"""
    try:
        command(['git', '--git-dir='+repod, 'tag', '-m', tag, tag, revision])
    except CalledProcessError:
        print >> stderr, 'ERROR: git tag failed'
        exit(3)

    if not options.server:
        tag_file = repod+'/refs/tags/'+tag
        check_output(['chown', '--reference='+repod, tag_file])
        # chown the object we just created
        # TODO: can we get git to tell us the object path to remove
        # the nasty assumption of the layout of .git here?
        taghash = file(tag_file, 'r').read().strip()
        check_output(['chown', '--reference='+repod,
                      repod+'/objects/'+taghash[:2]])
        check_output(['chown', '--reference='+repod,
                      repod+'/objects/'+taghash[:2]+'/'+taghash[2:]])

def parse_lines(text):
    """Split into lines, strip out comments and trailing/leading white space,
    drop blank lines and return a list"""
    content = []

    for line in text.split('\n'):
        line2 = line[:line.find('#')] if line.find('#') != -1 else line
        text = line2.strip()
        if text == '':
            continue
        content.append(text)
    return content

def parse_repositories(text, format, context):
    """Parse a repositories.txt file or exit. Context is for error messages."""
    if format == 'txt':
        content = parse_lines(text)
        if len(content) < 2:
            print >> stderr, 'ERROR: not enough in repositories.txt', context,
            print >> stderr, 'need at least',
            print >> stderr, 'a default branch and a single repository'
            exit(1)

        work = [options.inspection_repository] + [x for x in content[1:] if 
                                    x.split()[0] != options.inspection_repository]
        return {'fallback':content[0], 
                'repositories':[{'name':name} for name in content[1:]]}
    assert format == 'json'
    return loads(text)

def get_repolist(branch):
    """Return default branch and a list of repositories for branch or exit"""
    try:
        repos, extn = get_repositories(branch)
    except CalledProcessError:
        repos, extn  = get_repositories('master')
    return parse_repositories(repos, extn, 'on '+branch)


def obtain_head(repod, branch, defbranch):
    """Work out the head of branch in repod. 
    If the branch does not exist try defbranch."""
    try:
        return 'target '+branch, get_head(branch, repod)
    except CalledProcessError:
        pass
    try:
        return 'fallback '+defbranch, get_head(defbranch, repod)
    except CalledProcessError:
        print >> stderr, repod, 'has neither', branch, 'nor', defbranch
        exit(6)

def get_latest_tag(branch, tag_format):
    """Find the latest tag on branch"""
    repod = options.repository_base+'/'+options.inspection_repository+'.git'
    highest = find_highest_tag_number(repod, branch)
    return tag_format % (tag_prefix, highest, branch)

def handle_branch(branch, tag_format):
    """Work on branch"""
    if options.verbose:
        print >> stderr, 'working on branch', branch
    heads = []
    untagged = set()
    record = get_repolist(branch)
    if options.dump_json:
        with open(options.dump_json, 'w') as fout:
            dump(record, fout, indent=4)
    latest_tag = get_latest_tag(branch, tag_format)
    if latest_tag is None:
        print >> stderr, 'WARNING: no tag found on', branch, 'in', \
            options.inspection_repository
    else:
        print >> stderr, 'latest tag starting %s on %s is %s' % (
            args[0], branch, latest_tag)
        
    for repo in record['repositories']:
        if repo.get('type', 'git') != 'git':
            continue
        if repo.get('skip'): 
            continue
        repod = options.repository_base+'/'+repo['name']+'.git'
        branchdes, headrev = obtain_head(repod, branch, record['fallback'])
        heads.append((repod, headrev))
        try:
            out = command(['git', '--git-dir='+repod, 'rev-parse', '-q',
                           '--verify', latest_tag+'^{commit}'])
        except CalledProcessError:
            # this can happen if do_tag is killed so we don't fail
            # or if the repository is new, so we don't even warn
            latest_tag_is_head = False
        else:
            latest_tag_rev = out.strip()
            latest_tag_is_head = latest_tag_rev == headrev
        if latest_tag_is_head:
            excontext = ' '+latest_tag
        else:
            excontext = ' UNTAGGED'
            untagged.add(repo['name'])

        if options.verbose:
            print >> stderr, '%50s using %15s is %s%s' % (
                repo['name'], branchdes, headrev, excontext)

        if not options.tag and not latest_tag_is_head:
            # once we have found one untagged repository there
            # is no need to scan the others
            break

    if len(untagged) == 0:
        if options.tag and not options.force:
            print >> stderr, 'ERROR: no need to tag', branch
            print >> stderr, '  use -f to tag anyway'
            exit(9)
    else:
        if not options.tag:
            print branch

    if options.tag:
        tagnum = allocate_tag_number()
        tag = tag_format % (tag_prefix, tagnum, branch)
        print tagnum
        for repod, revision in heads:
            set_tag(tag, repod, revision)

def main():
    """make tag"""
    read_options()
    umask(0022)

    branches = list(options.branch)
    if options.branches_file:
        branches += parse_lines(file(options.branches_file, 'r').read())
    if branches == []:
        print >> stderr, 'ERROR: specify at least one branch with -b or -l'
        exit(5)
    if len(args) != 1:
        print >> stderr, 'ERROR: specify exactly one tag prefix as an argument'
        exit(7)
    global tag_prefix
    tag_prefix = args[0]
    for branch in branches:
        handle_branch(branch, options.tag_format)

if __name__ == '__main__':
    main()
