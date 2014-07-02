#
# Copyright (c) 2011 Citrix Systems, Inc.
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

#print "test"
import re
from twisted.python import log as logging
from buildbot.steps.shell import ShellCommand
#from twisted.python import components
from buildbot.status.web import waterfall
from buildbot.status.web.base import IBox
from buildbot.status import builder
from buildbot.process.buildstep import LogLineObserver


class XcBBShellCommand(ShellCommand):
    problem_re = re.compile(r'^\[\d+:\d+:\d+\.\d+\]: (WARNING:|ERROR:|\|)')
    def __init__(self, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.addLogObserver('stdio', XcLogLineObserver(self))

    def createSummary(self, log):
        ShellCommand.createSummary(self, log)
        problems = []
        for line in log.getText().split("\n"):
            if self.problem_re.match(line):
                problems.append(line)
        if problems:
            self.addCompleteLog('bb problems', "\n".join(problems))

#    def describe(self, done=False):
#        description = ShellCommand.describe(self, done)
#        bb_current_task = self.original.getStatistic('bb_current_task')
#        bb_task_number = self.original.getStatistic('bb_task_number')
#        if bb_current_task != None and bb_task_number != None:
#            description.append("BB task: %d/%d" % (bb_current_task, bb_task_number))
#        else:
#            description.append("No info about BB tasks")



class XcLogLineObserver(LogLineObserver):
    task_re = re.compile(r'''^\[(?P<time>\d+:\d+:\d+\.\d+)\]: NOTE: Running task (?P<bb_current_task>\d+) of (?P<bb_task_number>\d+) \(ID: \d+, (?P<bbname>.*), (?P<taskstep>.*)\)$''')
    def __init__(self, buildstep):
        LogLineObserver.__init__(self)
        self.buildstep = buildstep
    def outLineReceived(self, line):
        match = self.task_re.match(line)
        if not match:
            return
        values = match.groupdict()
        bb_current_task = int(values['bb_current_task'])
        bb_task_number = int(values['bb_task_number'])
        self.buildstep.step_status.setStatistic('bb_current_task', bb_current_task)
        self.buildstep.step_status.setStatistic('bb_task_number', bb_task_number)

    


class XcStepBox(waterfall.StepBox):
    def getBox(self, req):
        box = waterfall.StepBox.getBox(self, req)
        bb_current_task = self.original.getStatistic('bb_current_task')
        bb_task_number = self.original.getStatistic('bb_task_number')
        if bb_current_task != None and bb_task_number != None:
            box.text += '<br /><span style="color: black">BB tasks: %d/%d</span>' % (bb_current_task, bb_task_number)
        #else:
        #    box.text += '<span style="color: black">No info about BB tasks</span>'
        return box

# to use XcStepBox place in config file:
#from twisted.python import components
#from buildbot.status.builder import BuildStepStatus
#from buildbot.status.web.base import IBox
#components.ALLOW_DUPLICATES = True # haaack!
#components.registerAdapter(XcStepBox, BuildStepStatus, IBox)
#components.ALLOW_DUPLICATES = False


from buildbot.status import base
from zope.interface import implements
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY 
from twisted.internet import utils
from twisted.internet.utils import getProcessValue

class XcShellBuildResultNoitifer(base.StatusReceiverMultiService):
    compare_attrs = [ "builder_name", "command" ]
    result_dict = { SUCCESS: "SUCCESS", WARNINGS: "WARNINGS", FAILURE: "FAILURE", 
                    SKIPPED: "SKIPPED", EXCEPTION: "EXCEPTION", RETRY:"RETRY" }
    def __init__(self, builder_name, command):
        self.builder_name = builder_name
        self.command = command
        self.watched = []
        base.StatusReceiverMultiService.__init__(self)

    def exec_command(self, command):
        def print_result(val):
            logging.msg("%s: Command %s exited with value of %d" % (str(self), str(command), val))
        cmd = command[0]
        ret = getProcessValue(cmd, command[1:]);
        ret.addCallback(print_result)
        
    def buildFinished(self, builderName, build, results):
        if builderName != self.builder_name:
            logging.msg("%s: Invoked with builder I don't know about" % str(self))
            return # 
        result_text = self.translate_result(results)
        logging.msg("%s: build finished with %s result" % (str(self), result_text))
        self.exec_command([self.command, result_text])

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.setup()

    def setup(self):
        self.master_status = self.parent.getStatus()
        self.master_status.subscribe(self)

    def builderAdded(self, name, builder):
        if name != self.builder_name:
            return None # we don't care
        self.watched.append(builder)
        return self # subscribe to this builder

    def disownServiceParent(self):
        self.master_status.unsubscribe(self)
        for w in self.watched:
            w.unsubscribe(self)
        return base.StatusReceiverMultiService.disownServiceParent(self)

    def translate_result(self, result):
        return self.result_dict.get(result, "UNKNOWN")


class Logwrap:
    def __init__(self, text):
        self.text = text
    def getText(self):
        return self.text

if __name__ == "__main__":
    import sys
    text = open(sys.argv[1]).read()
    wrap = Logwrap(text)
    xc = XcBBShellCommand(name="CopyConfig", description="test", command=["echo" , "test"], haltOnFailure=True)
    xc.createSummary(wrap)
