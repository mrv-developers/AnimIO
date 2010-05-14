# -*- coding: utf-8 -*-
import os
import sys
import glob 

#{ Initialization

def _get_ext_path():
	""":return: path containing our external packages"""
	return os.path.join(os.path.dirname(__file__), 'ext')

def _setup_ext_path():
	"""Put our external directory into the path to allow contained packages to be found"""
	sys.path.insert(0, _get_ext_path())
	
def _assure_mrv_is_available():
	"""Assure we have access to mrv 
	:raise ImportError: if mrv is not available or does not have a compatible version"""
	import info
	
	# if we have non-mrv submodules, definitely add ext to the path.
	module_dirs = glob.glob(_get_ext_path() + "/*")
	if len(module_dirs) > 1 or (len(module_dirs) == 1 and not module_dirs[0].endswith('mrv')):
		_setup_ext_path()
	# END setup externals 
	
	try:
		import mrv.info as mrvinfo
	except ImportError:
		# its not installed by default, try to use it as external
		_setup_ext_path()
		try:
			import mrv.info as mrvinfo
		except ImportError:
			raise ImportError("could not import mrv, please make sure it exists in your PYTHONPATH")
		# END exception handling, 2nd attempt
	# END exception handling - try import mrv
	
	
	# CHECK MRV VERSION
	###################
	# check the version
	mmajor, mminor, mmicro = info.mrv_min_version
	major, minor, micro = mrvinfo.version[:3]
	if major < mmajor or minor < mminor or micro < mmicro:
		raise EnvironmentError( "%s requires MRV version %i.%i.%i or higher, got %i.%i.%i instead" % ((project_name, ) + info.mrv_min_version + mrvinfo.version[:3]))   
	# END verify MRV version
	

#} END initilization

_assure_mrv_is_available()