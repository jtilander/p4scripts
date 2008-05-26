#!/usr/bin/python
#
# Simple python script that tries to sync up with a repository after an offline session 
# with perforce. Read more about this on Perforce's technote:
#
# http://www.perforce.com/perforce/technotes/note002.html
#
#
# This script was downloaded from http://www.tilander.org/aurora
#
# (c) 2006 Jim Tilander
import sys, os, marshal

# Assume that we're on win32 or a UNIX compatible system.
if "win32" == sys.platform:
	FINDCOMMAND = "dir /b /s /a-d"
else:
	FINDCOMMAND = "find . -type f -print"

def doPerforceCommand( command ):
	""" Returns the error code and entries as a tuple."""
	stream = os.popen( command, 'rb' )
	entries = []
	try:
		while True:
			entry = marshal.load(stream)
			entries.append(entry)
	except EOFError:
		pass
	
	code = stream.close()
	return code, entries

def processOutput(results, showDryRun):
	""" Ignores the info codes and prints only the stat actions."""
	for result in results:
		code = result['code']
		if 'info' == code:
			continue
		
		if 'stat' == code:
			would = ""
			if showDryRun:
				would = "Would "
			print '%s%s %s' % (would,result['action'], result['clientFile'])
			continue
		
		print "Unknown dict entry: %s" % str(result)

def main( argv ):
	""" 
		Main function, parses the already stripped argv. 
		Will return a positive number upon failure, zero upon success.
		Hardcoded DOS style find command.
	"""
	dryRunFlag = ''
	if len(argv) > 0 and "-n" == argv[0]:
		dryRunFlag = '-n'
	
	commands = [ "p4 diff -sd ... | p4 -G -x - delete %s",
				 "p4 diff -se ... | p4 -G -x - edit %s",
				 FINDCOMMAND + " | p4 -G -x - add %s" ]
	
	for i, command in enumerate(commands):
		code, result = doPerforceCommand( command % dryRunFlag)
		processOutput(result, len(dryRunFlag) > 0)
		if code:
			print 'Failed to run command "%s"' % (command%dryRunFlag)
			return i

	return 0
	
if __name__ == '__main__':
	sys.exit( main(sys.argv[1:]) )
