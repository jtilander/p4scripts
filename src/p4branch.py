#!/usr/bin/env python
#
# p4branch.py Jim Tilander 2008 http://www.tilander.org/aurora
#
# This scripts allows you to branch your current clientspec to another location 
# in perforce and keep your work! Yay! It basically follows the instructions here
# http://kb.perforce.com/UserTasks/CodelinesAndBranching/BranchingWorkInProgress
# and it also uses the p4shelf.py module I wrote. 
#
# This tool is released "as is" with no guarantees to function nor warranty of any
# sort. Use it at your own risk. Read more about it (including license) at
# http://www.tilander.org/aurora
#
# Seriously !!! While this script tries to be "safe", and I've labored to be correct,
# I can't possibly imagine all the whacky ways people use perforce, so this script might
# not work for you. At all. Please be very careful while doing on the fly branches, so that
# you don't loose your work. It would suck. I know, I've been there.
#
import os,sys,marshal
import logging
import p4shelf
import re	
import getopt

def unhookfiles():
	""" 
		Reverts all the files in the clientspec, but keeps the local data around unchanged
	"""
	for entry in p4shelf.p4('opened'):
		depotFile = entry['depotFile']
		logging.debug( 'reverting %s from the client' % (depotFile) )
		p4shelf.p4( 'revert -k "%s"' % depotFile )

def checkClientspec(clientname):
	# Check if this is a multiline clientspec, then abort!
	views = 0
	for entry in p4shelf.p4( 'client -o' ):
		for key in entry.keys():
			if key.lower().startswith('view'):
				views = views + 1
	return views == 1

def getClientName(clientname):
	return p4shelf.p4( 'client -o', '-c %s' % clientname)[0]['Client']

def clientspaceSwitch(clientname, newClientPath):
	"""
		Replaces the depot portion of the clientspec with the new path given. Note that just the
		very first line gets the substitution here so it really only works with single line
		clientspecs.
	"""
	clientspec = os.popen( 'p4 -c %s client -o' % clientname, 'rt' ).read()
	newclient = re.sub( '(//.+) //', '%s //' % newClientPath, clientspec )
	os.popen('p4 -c %s client -i' % clientname, 'wt' ).write(newclient)

def branchCurrentView(clientname, newPath):
	"""
		This branches whatever you have synced to in your current view (but not any changes you have)
		to another location, without actually copying any files from the server. Branching in perforce is
		really a server side operation (it doesn't even copy files) so we don't need to pull down files from
		the server.
		
		It does that by cloning this clientspec and then rewriting the view to match the new location and
		then submitting it.
	"""
	# Figure out what our base path is
	view = p4shelf.p4( 'client -o' )[0]['View0']
	depotPath = re.search( '(//.+)\s+//', view).group(1)
	
	# Create a new client (or rewrite the one there) to hold the view we try to integrate into...
	newclient = clientname + '_Tmp'
	clientspec = os.popen( 'p4 -c %s client -o' % clientname, 'rt' ).read()
	newspec = re.sub( '(//.+) //', '%s //' % newPath, clientspec )
	newspec = newspec.replace( getClientName(clientname), newclient )
	os.popen('p4 -c %s client -i' % newclient, 'wt' ).write(newspec)

	# Now switch personality to the new client, integrate this client's files and then submit them into the new branch.
	p4shelf.p4( 'integ -v %s@%s %s' % (depotPath, clientname, newPath), '-c %s' % newclient)
	p4shelf.p4( 'submit -d "On the fly branching from clientspec %s"' % clientname, '-c %s' % newclient)
	
	# Delete the temporary client when we're done
	p4shelf.p4( 'client -d %s' % newclient )

def doit(clientname, newClientPath, doBranching):
	# First check if we can actually have a chance to replace the clientspec...
	if not checkClientspec(clientname):
		logging.error( 'Only support single line clientspecs.' )
		return 1
	
	# First find out the clientspec's root.
	rootDirectory = p4shelf.p4( "client -o" )[0]['Root']
	logging.info( 'My root directory is %s' % rootDirectory )
	
	# Check if we can backup the root directory later on (really paranoid)
	counter = 0
	backupDirectory = '%s%08d.bak' % (rootDirectory, counter)
	while os.path.isfile(backupDirectory) or os.path.isdir(backupDirectory):
		counter = counter + 1
		backupDirectory = '%s%08d.bak' % (rootDirectory, counter)
		
	
	# If we've requested on the fly branching, then do it at the very beginning, since this can go wrong, and
	# if it does, then we want to stop really early...
	if doBranching:
		try:
			logging.info( 'Branching client files into new location %s' % newClientPath )
			branchCurrentView(clientname, newClientPath)
		except IOError, e:
			logging.exception(e)
			print '\n\n\n'
			logging.error( 'Failed to create target branch (perhaps it already exists?), aborting...' )
			return 1
	
	# This is the temporary .zip file that we will squirrel away the current state of the workspace.
	tempfilename = os.path.join( os.environ['TEMP'], 'p4migrate.zip' )
	
	# Shelf all the work.
	logging.info('Saving currently opened files on this client (going to restore them later at the new location) to %s' % tempfilename)
	p4shelf.main( ['-r', '-f', '-z', '-y', '-o', '-c', clientname, tempfilename] )
	
	try:
		# Backup this directory (just move it to another location)
		logging.info('Backing up the current clientspec %s -> %s' % (rootDirectory, backupDirectory))
		os.rename( rootDirectory, backupDirectory )
	except WindowsError, e:
		logging.error( 'There is already a backup directory %s, abort.' % backupDirectory )
		return 1

	# Fools perforce into thinking that we have no opened files on this client
	logging.info( 'Reverting files from local client (but they are already shelved at %s' % tempfilename)
	unhookfiles()
	
	# Tell perforce that we don't have any revisions of any files on this machine.
	p4shelf.p4( "sync -k //...#none" )
	
	# Change the clientspec
	logging.info( 'Switching current clientspec to the fresh branch' )
	clientspaceSwitch(clientname, newClientPath)
	
	# Create new root
	os.mkdir( rootDirectory )
	
	# Sync to the new data
	logging.info( 'Syncing to the new branch...' )
	p4shelf.p4( "sync //...#head" )
	
	# Unshelf the work
	logging.info( 'Restoring work from old clientspec...' )
	p4shelf.main( ['-r', '-d', '-y', '-c', clientname, tempfilename] )
		
	# Magic! We're back at the same state as before the switch!
	return 0
	
def main( argv ):
	"""
p4branch [options] <clientname> <new location in depot>

Options:		

	-v		verbose
	-s		switch only, don't branch files first

Example new locations must be written in perforce depot format, e.g.

	p4branch myclient  //depot/alpha1/...

2008 Jim Tilander (http://www.tilander.org/aurora)
	"""
	try:
		opts, args = getopt.getopt( argv, 'vsh' )
	except getopt.GetoptError:
		print 'Error parsing arguments'
		print main.__doc__
		return 1

	verbose = 0
	doBranching = 1
	for o,a in opts:
		if '-v' == o:
			verbose = 1
		if '-h' == o:
			print HELP
			return 1
		if '-s' == o:
			doBranching = 0

	if len(args) != 2:
		print 'You must give both a clientspec and a target branch path'
		print main.__doc__
		return 1
	
	clientname = args[0]
	newClientPath = args[1]
	if verbose:
		logging.basicConfig( level=logging.DEBUG, format='%(asctime)s %(levelname)-7s: %(message)s' )
	else:
		logging.basicConfig( level=logging.INFO, format=os.path.basename(sys.argv[0]) + ': %(message)s' )

	return doit(clientname, newClientPath, doBranching)

if __name__ == '__main__':
	sys.exit( main(sys.argv[1:] ) )
