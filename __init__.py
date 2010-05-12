# -*- coding: utf-8 -*-
import os
import sys
import glob 

#{ Configuration 
# The configuration provided here is used by the template to learn more about 
# your particular project. Additionally it is used during distribution


# the minimum version of MRV that you require to work properly - usually the 
# version you used during development, its worth testing older versions though to 
# be more compatible 
mrv_min_version = (1, 0, 0)		# ( major, minor, micro )

# Information about the version of your tool
#               major, minor, micro, releaselevel, serial
version_info = (1,     0,     0,     'Preview',        0)

# the name of your tool or program
project_name = "AnimIO"

# Author Name
author = "Martin Freitag & Sebastian Thiel"

# Authors Email
author_email = ''

# url of the project's main web presence
url = 'http://gitorious.org/animio'

# A short description of your project
description = 'Convenient Animation Export and Import'

# License Identification String
license = "BSD License"

# Additional Keyword Arguments to be passed to distutils.core.setup
# This should include the 'classifiers' keyword which is important to pipy
setup_kwargs = dict()

#} END configuration

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
		raise EnvironmentError( "%s requires MRV version %i.%i.%i or higher, got %i.%i.%i instead" % ((project_name, ) + mrv_min_version + mrv.version_info[:3]))   
	# END verify MRV version
	

#} END initilization

_assure_mrv_is_available()