#! /bin/bash
#
# Copyright (c) 2010 Citrix Systems, Inc.
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

# This script is checked out onto the build machines to run the xenclient build.
# Options include :-
# -b <branch>   ( build branch <branch> ) 
# -x 		( Don't build the xmitter even if it is configured in the config ) 

set -x

# Debian has an annoying umask if not running from a login type shell
umask 022

# Lets make sure we have a (mostly) sane path.
PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
export PATH



echo "======================================" 
echo "Starting component build for build ID ${id}"
echo "Path: `pwd`"
echo "======================================"

"./build-scripts/do_build.sh" -S $@
exit $?
