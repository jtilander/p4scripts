#!/usr/bin/python
# (c) 2006 Jim Tilander
import os, sys, string, re, base64, time, zlib

MARKER = '================'
HELP = """Usage: p4patch <patchfile>

Takes output from p4diff

(c)2006 Jim Tilander
"""

def execute(cmd):
    stream = os.popen( cmd )
    output = stream.read()
    code = stream.close()
    return code, output

def openForEdit(p4path, revision):
    code = execute( 'p4 sync %s#%s' % (p4path, revision) )
    code = execute( 'p4 edit %s' % p4path )
    return code

def findLocalPath(p4path):
    stream = os.popen( 'p4 where %s' % p4path )
    lines = stream.readlines()
    code = stream.close()
    if code:
        return ""
    pattern = re.compile(r'.* ([^ ]+)$')
    m = pattern.match( lines[0] )
    if not m:
        return ""
    return string.strip(m.group(1))

def patchTextFile( localFile, data ):
    # TODO: Read the patch and apply it.
    return False

def patchBinaryFile( localFile, data ):
    stream = file( localFile, "wb" )
    msg = base64.standard_b64decode(string.join(data))
    stream.write( msg )
    return True

def parseSingleFile( p4path, revision, bintext, data ):
    openForEdit(p4path, revision)
    localPath = findLocalPath(p4path)
    if bintext == 'text':
        patchTextFile(localPath, data)
    else:
        patchBinaryFile( localPath, data )

def parseFile(stream):
    data = stream.read()
    try:
        data = zlib.decompress(data)
    except zlib.error, e:
        print "Not a zlib file: %s" % str(e)
    lines = string.split( data, '\n' )
    lines = map(string.rstrip, lines)
    while len(lines) > 3:
        marker = lines[0]
        p4path = lines[1]
        revision = lines[2]
        bintext = lines[3]
        i = 4
        while MARKER != lines[i]:
            i += 1
        data = lines[4:i]
        parseSingleFile( p4path, revision, bintext, data )
        lines = lines[i:]

def main(args):
    if len(args) != 2:
        print HELP
        return -1
    
    #stream = sys.stdin
    stream = file(args[1],'rb')
    sys.exit( parseFile(stream) )

if __name__ == '__main__':
    sys.exit( main(sys.argv) )
