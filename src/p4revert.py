#!/usr/bin/env python
# 
# Reverts a specified changelist in perforce.
# Add it to the perforce p4win tool as a contex sensitive tool.
#
# Import the following to your p4win client:
#
# --- cut ---
# P4Win Tools File from jt
# >>Imported from jt				0	0	0	1	0	1
# >>RevertChangelist	p4revert.py	-c $c -p $p -u $u %c		1	0	1	0	0	1	0		1
# --- cut ---
#
# Jim Tilander (2007)
# Downloaded off http://www.tilander.org/aurora
#
# Improvements made by Matt Zimmer. Graceously contributed with the permission of Intuit.
#    - Changed default from overwrite to require manual resolve if later
#      edits made to a file (you want to roll 28 back to 27 but there is a 29
#      in the depot).
#    - Added force flag to force overwrite (27 would overwrite 29 in the above
#      scenario).
#
#
#

import os
import sys
import getopt
import marshal
import logging

P4_PORT_AND_USER = ' '

def p4( command ):
	"""
		Run a perforce command line instance and marshal the 
		result as a list of dictionaries.
	"""
	commandline = 'p4 %s -G %s' % (P4_PORT_AND_USER, command)
	logging.debug( '%s' % commandline )
	stream = os.popen( commandline, 'rb' )
	entries = []
	try:
		while 1:
			entry = marshal.load(stream)
			entries.append(entry)
	except EOFError:
		pass
	code = stream.close()
	if None != code:
		raise IOError( "Failed to execute %s: %d" % (commandline, int(code)) )
	return entries

def deleteFile(name):
	"""
		Deletes the file from the repository.
	"""
	p4( 'delete "%s"' % name )

def backRevision(name, revision, force):
	"""
		Given a file and a revision number, tries to go back 
		one revision in time.
	"""
	targetRevision = revision - 1
	headAction = p4( 'fstat "%s#%d"' % (name, targetRevision))[0]['headAction']

	if 'delete' == headAction:
		if laterRevisionExists(name, revision) and not force:
			logging.warn("%s has new edits since this change list was submitted. Skipping automated delete; You must delete manually." % (name))
		else:
			deleteFile(name)
	else:
		syncDoActionAndResolve(name, "edit", int(revision), force)

def laterRevisionExists(name, revision):
	headRevision = p4( 'fstat "%s"' % (name))[0]['headRev']
	return int(headRevision) > revision
	

def recoverFile(name, revision, force):
	"""
		Adds a deleted file back to the repository.
	"""
	syncDoActionAndResolve(name, "add", int(revision), force)

def syncDoActionAndResolve(name, action, revision, force):
	p4( 'sync "%s#%d"' % (name, revision -1) )
	p4( '%s "%s"' % (action, name) )
	p4( 'sync "%s"' % name )

	headRevision = int(p4( 'fstat "%s"' % (name))[0]['headRev'])
	logging.debug("revision = %d" % (revision))
	logging.debug("headRevision = %d" % (headRevision))

	if laterRevisionExists(name, revision) and not force:
		logging.warn("%s has new edits since this change list was submitted. Skipping automated resolve; You must resolve manually." % (name))
	else:
		p4( 'resolve -ay "%s"' % name )


def revertChangelist( changelistNumber, force ):
	"""
		Steps through the whole changelist file by file and looks at 
		the last action taken and then tries to go back one step.
	"""
	logging.debug( 'Trying to revert the changelist %d' % changelistNumber )
	description = p4( 'describe -s %d' % changelistNumber )[0]
	infos = []
	counter = 0
	try:
		while 1:
			name = description[ 'depotFile%d' % counter ]
			action = description[ 'action%d' % counter ]
			revision = int(description[ 'rev%d' % counter ])
			infos.append( (name, action, revision) )
			counter += 1
	except KeyError:
		pass
	
	for name, action, revision in infos:
		logging.debug( 'Processing %s#%d' % (name, revision) )
		if 'add' == action:
			deleteFile(name)
		if 'edit' == action:
			backRevision(name, revision, force)
		if 'delete' == action:
			recoverFile(name, revision, force)
		if 'branch' == action or 'integrate' == action:
			if 1 == revision:
				deleteFile(name)
			else:
				backRevision(name, revision, force)
	

def main(argv):
	"""
		Usage: p4revert.py [options] <changelist>

			Options:
				-v              : verbose
				-f              : force
				-c client       : perforce client
				-p port         : perforce port
				-u user         : perforce user
	"""
	try:
		options, arguments = getopt.getopt(argv, 'c:p:u:vf')
	except getopt.GetoptError:
		print 'Error parsing arguments'
		print main.__doc__
		return 1

	# Default tweakable values for the options.
	verbose = False
	force = False
	client = ''
	port = ''
	user = ''
	
	# Loop through all the options
	for o,a in options:
		if '-v' == o:
			verbose = True
		if '-c' == o:
			client = a
		if '-p' == o:
			port = a
		if '-u' == o:
			user = a
		if '-f' == o:
			force = True
	
	if len(arguments) != 1:
		print 'Must give one changelist number'
		print main.__doc__
		return 1
	
	try:
		changelistNumber = int(arguments[0])
	except ValueError:
		print 'Changelist number must be a number!'
		print main.__doc__
		return 1
	
	global P4_PORT_AND_USER
	if len(client):
		P4_PORT_AND_USER += ' -c %s ' % client
	if len(port):
		P4_PORT_AND_USER += ' -p %s ' % port
	if len(user):
		P4_PORT_AND_USER += ' -u %s ' % user
	
	# At this point we're all done with the options! Now to the real code.
	if verbose:
		logging.basicConfig( 
			level=logging.DEBUG, 
			format='%(asctime)s %(levelname)-7s: %(message)s' )
	else:
		logging.basicConfig( 
			level=logging.INFO, format='%(message)s' )

	revertChangelist( changelistNumber, force )
	logging.info( 'Revert of %d done.' % changelistNumber )
	results = p4 ( "resolve -n" )
	for result in results:
		code = result['code']
		if code == 'stat':
			logging.warning("%s must be resolved." % (result['fromFile']))
		elif code == 'error':
			logging.info("Change list reverted and files are ready for submit.")
	return 0
	
if __name__ == '__main__':
	# This is just the main stub trick that makes the script act like a regular
	# unix application. We return 1 for errors and 0 for success.
	sys.exit( main(sys.argv[1:]) )
