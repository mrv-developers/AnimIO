# -*- coding: utf-8 -*-
"""
Initialize mrv system assisting development, debugging and maintenance

	- install general `decorator` into __builtin__ namespace
"""
import __builtin__
import logging
import logging.config
log = logging.getLogger("mrv")

__all__ = ("init_modules", )


import os, sys
from path import Path


#{ Common
def init_modules( filepath, moduleprefix, recurse=False, self_module = None):
	""" Call '__initialize' functions in submodules of module at filepath if they exist
	These functions should setup the module to be ready for work, its a callback informing
	the submodules that the super module is being requested. They return a True value if
	the initialization was performed, or a False one if they weren't for some reason.
	Throw to indicate error.
	:param filepath: your module module.__file__ value
	:param moduleprefix: prefix like "super.yourmodule." leading to the submodules from
	an available system include path
	:param recurse: if True, method will recursively initialize submodules
	:param self_module: if not None, it must be the module that called this function.
	It will be given to the __initialize functions as first arguments allowing 
	them to operate on functions of their own module - importing their own 
	module is not yet possible as it is in the course of being intialized itself.
	The module will be given only to intermediate submodules in case recurse is True.
	:note: in this moment, all submodules will be 'pulled' in"""
	moduledir = Path( filepath  ).parent()
	moduleitems = moduledir.listdir( )
	moduleitems.sort()					# assure we have the same order on every system
	extensions = ( ".py", ".pyc", ".pyo" )
	initialized_modules = set()
	
	if not moduleprefix.endswith( "." ):
		moduleprefix += "."

	# import each module
	for path in moduleitems:

		# SUB-PACKAGE ?
		if path.isdir( ):
			if not recurse:
				continue

			packageinitfile = None
			for ext in extensions:
				testpackageinitfile = path / "__init__%s" % ext
				if testpackageinitfile.exists():
					packageinitfile = testpackageinitfile
					break
				# END if packageinit file exists
			# END for each possible extension
			
			# skip non-existing ones
			if not packageinitfile:
				continue
			
			init_modules( packageinitfile, moduleprefix + path.basename(), recurse=True )
			continue
		# END path handling

		if path.ext() not in extensions:
			continue

		modulename = path.namebase()
		if modulename.startswith( "_" ) or modulename.startswith( "." ) or modulename in ('all', 'mdb'):
			continue

		fullModuleName = moduleprefix + modulename
		if fullModuleName in initialized_modules:
			continue
		# END prevent duplicate initialization due to different endings
		initialized_modules.add(fullModuleName)
		module = __import__( fullModuleName , globals(), locals(), [ modulename ] )

		# call init
		args = ( self_module and [ self_module ] ) or tuple()
		if hasattr( module, "__initialize" ):
			res = module.__initialize( *args )
			if res:
				log.info("Initialized " + module.__name__)
			# EMD handle result
	# END for each file or dir


#} END common

#{ Initialization

def _remove_empty_syspath_entries():
	"""fix sys.path: if there are empty entries and our cwd is the mrvroot
	we will be in trouble as we try to import our own 'maya' module which 
	will not provide the original maya packages of course
	
	:note: only for internal use - code was moved into a method as it needs 
		to be called again from maya.__init__"""
	while '' in sys.path:
		sys.path.remove('')
	# END while we have whitespace

def _init_syspath( ):
	""" Initialize the path such that additional modules can be found"""
	import site
	mrvroot = mrvroot = os.path.dirname( __file__ )
	
	_remove_empty_syspath_entries()
	
	# process additional site-packackes
	# The startup script may add additional site-package paths, but if these
	# are non-default, they will not be handled which leads to an incomplete 
	# environment. Hence we process them.
	# Fortunately, the function handles multiple initializations gracefully
	for syspath in sys.path[:]:
		if syspath.endswith('site-packages'):
			site.addsitedir(syspath, set(sys.path))
		# END found site-packages path
	# END for each path to possibly initialize
	
	if sys.platform == 'darwin':
		# in order to have a chance to get the setuptools going, 
		# add the default python library to the path.
		sys.path.append("/System/Library/Frameworks/Python.framework/Versions/%s/Extras/lib/python"%sys.version[:3])
	# END desperate hack
	
	# get external base
	extbase = os.path.join( mrvroot, "ext" )

	# pyparsing
	pyparsing = os.path.join( extbase, "pyparsing", "src" )

	# pydot
	pydot = os.path.join( extbase, "pydot" )

	# networkx
	networkxpath = os.path.join( extbase, "networkx" )

	# add all to the path
	sys.path.append( pyparsing )
	sys.path.append( pydot )
	sys.path.append( networkxpath )


# end __init_syspath


def _init_configProvider( ):
	""" Install the configuration provider system

	This allows values and settings to be stored in a convenient way. """
	pass

def _init_internationalization( ):
	"""Install internationalization module

	Using the default python gettext module, internationalization compatibility
	can be garantueed.

	Will map the '_' function to translate enclosed strings """
	import gettext
	gettext.install( "mrv" )


def _init_logging( ):
	""" Initialize the default mrv logging interface

	The logging interface unifies the way messages for the end user are handled
	and assure a flexible message handling.
	
	:note: will not raise even if the logging module could not be setup
	
	:note: in the current implementation, it is based on the default python logging
		package"""
	logcfgfile = os.environ.get('MRV_LOGGING_INI', None)
	if logcfgfile is None:
		return
		
	try:
		logcfgfile = Path(logcfgfile).expand_or_raise()
		logging.config.fileConfig(logcfgfile)
	except Exception, e:
		print "Failed to apply logging configuration at %s with error: %s" % (logcfgfile, str(e))
	else:
		log.debug("Initialized logging configuration from file at %s" % logcfgfile)
	# END exception handling
	


def _init_python( ):
	"""
	Assure that certain python classes have the least possible amount of compatablity
	so that we can work with them
	"""
	

#} END initialization

# INITIALIZE
#############
_init_syspath( )
_init_configProvider( )
_init_internationalization( )
_init_logging( )
_init_python( )