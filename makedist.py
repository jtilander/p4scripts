import os
import glob
import zipfile
import sys

def main(argv):
	
	if len(argv) != 1:
		print 'Usage: makedist <zipfilename>'
		return 1
	
	filename = argv[0]
	
	archive = zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED)
	
	candidates = glob.glob('bin/*.exe') + glob.glob('bin/*.dll') + glob.glob('src/*.py')
	
	for name in candidates:
		archive.write(name)
		
	archive.close()
	
	return 0

if __name__ == '__main__':
	sys.exit( main(sys.argv[1:]) )
	