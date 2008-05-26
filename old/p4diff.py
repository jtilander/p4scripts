#!/usr/bin/python
# (c) 2006 Jim Tilander
import sys
import os
import string
import re
import base64
import zlib

P4EXE = 'p4'
NEWFILEPATTERN = re.compile( r'==== ([^#]+)#([\d]+) - (.+) ====(.*)$' )
MARKER = '================'
USAGE = """Usage: p4diff <outputfile> [options]

Produces input to p4patch

Options:
    -z    - compress output with zlib
    -h    - display this help

(c) 2006 Jim Tilander
"""

class Diff:
    def __init__(self):
        self.p4path = ""
        self.localpath = ""
        self.revision = 0
        self.binary = False
        self.data = ""

    def __str__(self):
        return "p4path= %s\nlocal= %s\nrev = %d\nbin = %s\ndata = %s\n" % (self.p4path, self.localpath, self.revision, self.binary, self.data)

    def asString(self):
        s = "%s\n%s\n" % (self.p4path, self.revision)
        if self.binary:
            s += "bin\n"
        else:
            s += "text\n"
        s += self.data + '\n'
        return s

class DiffFileParser:
    def __init__(self, match):
        self.lines = []
        self.perforcePath = match.group(1)
        self.revision = match.group(2)
        self.localPath = match.group(3)
        try:
            self.flags = match.group(4)
        except IndexError:
            self.flags = ""

    def parse(self):
        diff = Diff()
        diff.p4path = self.perforcePath
        diff.localpath = self.localPath
        diff.revision = int(self.revision)
        #if self.flags == "":
        #    # Assume text mode
        #    diff.binary = False
        #    diff.data = string.join(self.lines,'\n')
        #else:
        #    We're in binary mode
        diff.binary = True
        diff.data = file( self.localPath, 'rb' ).read()
        diff.data = string.rstrip(base64.standard_b64encode(diff.data))
        return diff

def executeCommand( cmd ):
    """
    Executes any perforce command and then returns the results in a list
    of lines.
    Returns: (p4 exit code, list of lines)
    """
    stream = os.popen( 'p4 ' + cmd )
    lines = stream.readlines()
    lines = map(string.rstrip, lines)
    code = stream.close()
    return code, lines

def parseCompleteDiff( lines ):
    """
        Steps through all the output lines from p4 diff -du
        and parses each file in turn and put them into a list of results.
    """
    foundFile = False
    fileParser = None
    results = []
    for i, line in enumerate(lines):
        m = NEWFILEPATTERN.match(line)
        if not m:
            if fileParser:
                fileParser.lines.append(line)
            continue
        if fileParser:
            results.append( fileParser.parse() )
        fileParser = DiffFileParser(m)
    if fileParser:
        results.append( fileParser.parse() )
    return results

def makStringFromresults(results):
    if len(results) == 0:
        return ""
    message = MARKER + '\n' + string.join( map(lambda x: x.asString(), results), MARKER + '\n' ) + MARKER
    return message

def main(args):
    if len(args) < 2 or args[1] == '-h':
        print USAGE
        return 0
    
    outputname = args[1]
    
    code, lines = executeCommand('diff -du')
    if None != code:
        print 'Failed to run diff -du'
        return 1
    results = parseCompleteDiff(lines)
    if len(results) == 0:
        print 'No diffs found'
        return 1
    message = makStringFromresults(results)
    
    if len(args) > 2 and args[2] == '-z':
        message = zlib.compress(message,9)

    file(outputname,'wb').write(message)
    print 'wrote', outputname
    return 0

if __name__ == '__main__':
    sys.exit( main(sys.argv) )
