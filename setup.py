from distutils.core import setup
import py2exe
import sys
sys.path.append('src')

opts = {
	'py2exe': {
		'dist_dir'		: 'bin',
		'optimize'		: 2,
		'bundle_files'	: 1,
	}
}

setup( 	console = [	{ 'script': 'src/p4shelf.py', 'icon_resources': [(0, 'icon.ico')] },
					{ 'script': 'src/p4revert.py', 'icon_resources': [(0, 'icon.ico')] },
					{ 'script': 'src/p4branch.py', 'icon_resources': [(0, 'icon.ico')] },
					{ 'script': 'src/p4offlinesync.py', 'icon_resources': [(0, 'icon.ico')] } ], 
		options = opts,
		zipfile = None)
