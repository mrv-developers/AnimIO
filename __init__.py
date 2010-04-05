# -*- coding: utf-8 -*-

import os
import sys
import glob 

#{ Configuration 

# the minimum version of MRV that you require to work properly - usually the 
# version you used during development, its worth testing older versions though to 
# be more compatible 
mrv_min_version = (1, 0, 0)

# the name of your tool or program
tool_name = "AnimIO"

#} END configuration

#{ Initialization

def _get_ext_path():
	""":return: path containing our external packages"""
	return os.path.join(os.path.dirname(__file__), 'ext')

def _setup_ext_path():
	"""Put our external directory into the path to allow contained packages to be found"""
	sys.path.insert(0, _get_ext_path())
	
def _assure_mayarv():
	"""Assure we have access to mayarv , bark nicely if this is not the case"""
	
	# if we have non-mrv submodules, definitely add ext to the path.
	module_dirs = glob.glob(_get_ext_path() + "/*")
	if len(module_dirs) > 1 or (len(module_dirs) == 1 and not module_dirs[0].endswith('mrv')):
		_setup_ext_path()
	# END setup externals 
	
	try:
		import mrv
	except ImportError:
		# its not installed by default, try to use it as external
		_setup_ext_path()
		try:
			import mrv
		except ImportError:
			raise ImportError("could not import mrv, please make sure it exists in your PYTHONPATH")
		# END exception handling, 2nd attempt
	# END exception handling - try import mrv
	
	
	# CHECK MRV VERSION
	###################
	# check the version
	mmajor, mminor, mmicro = mrv_min_version
	major, minor, micro = mrv.version_info[:3]
	if major < mmajor or minor < mminor or micro < mmicro:
		raise EnvironmentError( "%s requires MRV version %i.%i.%i or higher, got %i.%i.%i instead" % ((tool_name, ) + mrv_min_version + mrv.version_info[:3]))   
	# END verify MRV version
	

#} END initilization

_assure_mayarv()

# import basic modules
from lib import *
from ui import *