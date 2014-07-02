to create buildbot:

as user buildbot:

cd ~
git clone git://git.xci-test.com/infrastructure/build-machines.git
ln -s build-machines/buildmaster/README.txt .
buildbot create-slave buildmaster
cd buildmaster
ln -s ../build-machines/buildmaster/Makefile .
ln -s ../build-machines/buildmaster/buildbot2.cfg master.cfg
buildbot start ~/buildmaster



