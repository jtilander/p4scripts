#!/usr/bin/env python
#
# This script allows you to "shelf" your current work in the repository and 
# then restore your client to the exact state afterwards.
#
# This script might not handle all corner cases, so to ensure that you can 
# always recover files, this script stores the actual data as complete copies 
# in a zip file that you can extract yourself as well.
#
# p4shelf.py Jim Tilander 2008
#
# This tool is released "as is" with no guarantees to function nor warranty of any
# sort. Use it at your own risk. Read more about it (including license) at
# http://www.tilander.org/aurora
#
#
# History:
#
# 2008-01-26: Initial release.
# 2008-01-28: Added improved parsing for comments.
# 2008-01-31: Fixed an bug when backing up files that actually were opened for add.
#
#
#
# TODO: Instead of the convoluted way to figure out what you have, use the "tag" command in p4 instead ?
#
import sys
import os
import marshal
import logging
import getopt
import time
import zipfile
import string
import re

VERBOSE = 0
FAKEIT  = 1
DESCRIPTION_FILENAME = '___p4shelf_information___.txt'
COMMON_FLAGS = ''

VERSION = 'v0.1'
HELP = """

p4shelf %s (c) 2008 Jim Tilander. A tool to ease the minds of paranoid programmers.

Usage: p4shelf [options] <filename>

Valid options:
    -c <client>     : perforce client spec
    -p <port>       : perforce port
    -u <user>       : perforce user
    -z              : create shelf (default is extract)
    -q              : quiet
    -v              : verbose
    -h              : help
    -y              : actually do work (default is to show only)
    -m              : set comment
    -s <changelist> : only archive specified changelist
    -f              : use exact filename for compression
    -d              : open head revision and ignore the source revision for extract operations
    -o              : overwrite target file, always
    -r              : use client relative paths instead of depot absolute paths (useful for moving files from different clients)
""" % VERSION

def p4( command, commonFlags = '' ):
	if commonFlags == '':
		commonFlags = COMMON_FLAGS
	commandline = 'p4 %s -G %s' % (commonFlags, command)
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

def getClientName():
	entries = p4( 'info' )
	return entries[0]['clientName'].strip()

def calcRevisionDiff(changefiles, havefiles):
	logging.debug( 'Traversing %d changelist files against %d have files' % (len(changefiles), len(havefiles)) )
	logging.debug( 'Removing revision duplicates (%d entries)' % len(havefiles) )
	base = dict( changefiles )
	diffs = []
	for name, rev in havefiles:
		try:
			baserev = base[name]
			if baserev != rev:
				diffs.append((name,rev))
			del base[name]
		except KeyError:
			diffs.append((name,rev))
	
	for name, rev in base.iteritems():
		diffs.append((name,0))
	
	return diffs

def findFileRevisions():
	clientname = getClientName()
	logging.debug( 'Searching for the files on the client "%s"' % clientname )
	
	lastchange = int(p4( 'changes -m 1 //%s/...#have' % clientname )[0]['change'])
	logging.debug( 'Last synced changelist was #%d' % lastchange )
	
	logging.debug( 'Listing file revisions from changelist #%d' % lastchange )
	changefiles = [ (x['depotFile'], int(x['rev'])) for x in p4('files //%s/...@%d' % (clientname,lastchange)) ]
	
	logging.debug( 'Listing file revisions on actual client' )
	havefiles = [ (x['depotFile'], int(x['rev'])) for x in p4('files //%s/...#have' % clientname) ]
	
	revdiffs = calcRevisionDiff(changefiles, havefiles)
	return lastchange, revdiffs

def collectOpenedFiles(changelist, useClientRelativePaths):
	result = []
	
	changestring = ''
	if 0 != changelist:
		changestring = ' -c %d ' % changelist
	
	for entry in p4( 'opened %s' % changestring ):
		if useClientRelativePaths:
			filename = entry['clientFile']
		else:
			filename = entry['depotFile']
		result.append( (filename, int(entry['rev']), entry['action']) )
	return result

def depotNameToLocal( depotname ):
	results = p4( 'fstat "%s"' % depotname )
	return results[0]['clientFile']

def depotWhere( depotname ):
	result = p4( 'where "%s"' % depotname )[0]
	return result['path']

def depotNameToLocalClient( rootDir, depotName ):
	size = len(rootDir.strip())
	result = depotName[size:]
	if result[0] == '\\':
		return result[1:]
	return result
	
def toClientRelative( sourceClientName, depotname ):
	# replace the name //sourceClientName/ with //ourclientname/
	myClientName = getClientName()
	result = re.sub( '//%s/' % sourceClientName, '//%s/' % myClientName, depotname )
	return result
	
def findSourceDepotName( depotName ):
	result = p4( 'fstat -Or "%s"' % depotName )[0]
	
	try:
		sourceName = result['resolveBaseFile0']
		sourceRev = int(result['resolveBaseRev0'])
		try:
			sourceRev = int(result['resolveEndFromRev0'])
		except KeyError:
			pass
		return '%s#%d' % (sourceName, sourceRev)
	except KeyError:
		return ''
	
def clientRoot():
	client = getClientName()
	return p4( 'client -o' )[0]['Root'].strip()

def createFilename(filename):
	timestring = time.strftime( '%Y-%m-%d_%H-%M' )
	name, ext = os.path.splitext(filename)
	
	if '' == ext:
		ext = '.zip'
	
	result = '%s_%s%s' % (name, timestring, ext)
	logging.info( 'Target filename is %s' % result )
	return result

def createDescription(basechangelist, difffiles, changedfiles, comment, useClientRelativePaths):
	description = ''

	description += 'TIME: %s\n' % time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
	if useClientRelativePaths:
		description += 'CLIENT: %s\n' % getClientName()
	
	if '' != comment:
		description += 'INFO: """%s"""\n' % comment
	
	if 0 != basechangelist:
		description += 'BASE: %3d\n\n' % basechangelist
	
	for name, revision in difffiles:
		desc = 'DRFT: %3d "%s"\n' % (revision, name)
		description += desc
		
	description += '\n\n'
	
	rootDir = clientRoot()
	for name, revision, action in changedfiles:
		sourcePath = ''
		if action in ['branch', 'add', 'integrate', 'edit']:
			sourcePath = findSourceDepotName(name)
		
		choppedName = depotNameToLocalClient(rootDir, depotNameToLocal(name))
		desc = 'OPEN: %3d %s "%s" "%s" "%s"\n' % (revision, action, name, sourcePath, choppedName)
		description += desc
	
	return description
	
def parseDescriptions(data):
	descriptions = string.split(data, '\n')
	descriptions = map( string.strip, descriptions )
	descriptions = filter( len, descriptions )
	
	baseChange = 0
	driftFiles = []
	openedFiles = []
	comment = ''
	time = ''
	sourceClientName = ''
	
	timeRe = re.compile( '^TIME: (.*)' )
	commentRe = re.compile( '^INFO: """(.*)"""', re.MULTILINE + re.DOTALL )
	baseRe = re.compile('^BASE:\s+(\d+)')
	driftRe = re.compile('^DRFT:\s+(\d+)\s+"(.+)"')
	openRe = re.compile('^OPEN:\s+(\d+)\s+([a-z]+)\s+"(.+)"\s+"(.*)"\s+"(.+)"')
	clientRe = re.compile( '^CLIENT: ([^\s]+)' )
	
	m = commentRe.search(data)
	if m:
		comment = m.group(1).strip()
		logging.info( 'Comment = %s' % comment )

	for description in descriptions:
		m = timeRe.match(description)
		if m:
			time = m.group(1)
			logging.info( 'Archive time = %s' % time )
			continue
			
		m = baseRe.match(description)
		if m:
			baseChange = int(m.group(1))
			logging.info( 'sync //...@%d' % baseChange )
			continue
		
		m = driftRe.match(description)
		if m:
			revision = int(m.group(1))
			name = m.group(2)
			logging.info( 'sync %s#%d' % (name, revision) )
			driftFiles.append((revision,name))
			continue
		
		m = clientRe.match(description)
		if m:
			sourceClientName = m.group(1)
		
		m = openRe.match(description)
		if m:
			revision = int(m.group(1))
			action = m.group(2)
			name = m.group(3)
			sourcePath = m.group(4)
			chopped = m.group(5)
			
			# Now we need to transform both the name and the sourcepath into client relative files.
			if len(sourceClientName):
				name = toClientRelative(sourceClientName, name)
				sourcePath = toClientRelative(sourceClientName, sourcePath)

			if len(sourcePath):
				logging.info( '%s on %s#%d from %s' % (action, name, revision, sourcePath) )
			else:
				logging.info( '%s on %s#%d' % (action, name, revision) )

			openedFiles.append((revision, action, name, sourcePath, chopped))
			continue
			
	return baseChange, driftFiles, openedFiles, comment, time
	
	
def unpack(archive, chopped, depotName):
	if FAKEIT:
		return
	data = archive.read(chopped.replace('\\', '/'))
	
	# Some users like to map their depot a little whacky, so we need to lookup the proper name
	# on this client mapping.
	clientFile = depotWhere(depotName)
	stream = open( clientFile, 'wb' )
	stream.write(data)
	stream.close()
	
def doExtract(filename):
	archive = zipfile.ZipFile(filename, 'r')
	baseChange, driftFiles, openedFiles, comment, archiveTime = parseDescriptions( archive.read(DESCRIPTION_FILENAME) )
	
	# First sync to the base changelist
	syncOptions = ''
	if FAKEIT: syncOptions = '-n'
	if baseChange != 0:
		p4( 'sync %s //...@%d' % (syncOptions, baseChange) )
	
	# Take care of all the exceptions
	for revision, name in driftFiles:
		p4( 'sync %s "%s#%d"' % (syncOptions, name, revision) )
	
	rootDir = clientRoot()
	for revision, action, name, sourcePath, chopped in openedFiles:
		p4( 'sync %s "%s#%d"' % (syncOptions, name, revision) )
		if len(sourcePath):
			if action == 'branch':
				p4( 'integrate %s "%s" "%s"' % (syncOptions, sourcePath, name) )
			if action in ['add', 'edit']:
				p4( 'integrate %s "%s" "%s"' % (syncOptions, sourcePath, name) )
				p4( 'resolve %s -at "%s"' % (syncOptions, name) )
				p4( 'edit %s "%s"' % (syncOptions, name) )
				unpack(archive, chopped, name)
		else:
			if action == 'edit':
				p4( 'edit %s "%s"' % (syncOptions, name) )
				unpack(archive, chopped, name)
			if action == 'add':
				unpack(archive, chopped, name)
				p4( 'add %s "%s"' % (syncOptions, name) )
			if action == 'delete':
				p4( 'delete %s "%s"' % (syncOptions, name) )
	
	return 0

def doCompress(filename, changelist, comment, overwriteTarget, useClientRelativePaths):
	basechangelist, difffiles = (0, [])
	changedfiles = collectOpenedFiles(changelist, useClientRelativePaths)	

	description = createDescription(basechangelist, difffiles, changedfiles, comment, useClientRelativePaths)

	baseChange, driftFiles, openedFiles, comment, archiveTime = parseDescriptions( description )

	if FAKEIT:
		return 0

	if os.path.exists(filename) and not overwriteTarget:
		logging.error( 'Refusing to overwrite existing file %s (give -o to override)' % filename )
		return 1

	archive = zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED)
	archive.writestr(DESCRIPTION_FILENAME, description)

	for revision, action, name, sourcePath, chopped in openedFiles:
		if action == 'delete':
			continue
		archiveName = chopped
		localName = depotNameToLocal(name)
		archive.write(localName, archiveName.replace('\\', '/'))
		
	archive.close()
	return 0

def main( argv ):
	try:
		opts, args = getopt.getopt( argv, 's:m:c:u:p:yqvczhfdor' )
	except getopt.GetoptError:
		print HELP
		return 1
	
	verbose		= 1
	extract		= 1
	fakeit		= 1
	comment		= ''
	changelist  = 0
	exactFileName = 0
	openHeadRevision = 0
	overwriteTarget = 0
	useClientRelativePaths = 0
	global COMMON_FLAGS
	COMMON_FLAGS = ''
	
	for o,a in opts:
		if '-v' == o:
			verbose = 1
		if '-h' == o:
			print HELP
			return 1
		if '-z' == o:
			extract = 0
		if '-q' == o:
			verbose = 0
		if '-y' == o:
			fakeit = 0
		if '-c' == o:
			COMMON_FLAGS += ' -c %s ' % a
		if '-u' == o:
			COMMON_FLAGS += ' -u %s ' % a
		if '-p' == o:
			COMMON_FLAGS += ' -p %s ' % a
		if '-m' == o:
			comment = a
		if '-s' == o:
			changelist = int(a)
		if '-f' == o:
			exactFileName = 1
		if '-d' == o:
			openHeadRevision = 1
		if '-o' == o:
			overwriteTarget = 1
		if '-r' == o:
			useClientRelativePaths = 1
	if len(args) != 1:
		print 'No filename given!'
		print HELP
		return 1
	filename = args[0]

	global VERBOSE
	global FAKEIT
	VERBOSE = verbose
	FAKEIT = fakeit

	if verbose:
		logging.basicConfig( level=logging.DEBUG, format='%(asctime)s %(levelname)-7s: %(message)s' )
	else:
		logging.basicConfig( level=logging.INFO, format=os.path.basename(sys.argv[0]) + ': %(message)s' )

	if fakeit: logging.info( 'Fake mode, no actions will be taken' )

	if extract:
		return doExtract(filename)
	else:
		if 0 != changelist and comment == '':
			result = p4('change -o %d' % changelist)[0]
			comment = result['Description'].rstrip()
		if not exactFileName:
			filename = createFilename(filename)
		return doCompress(filename, changelist, comment, overwriteTarget, useClientRelativePaths)

if __name__ == '__main__':
	sys.exit( main(sys.argv[1:] ) )
