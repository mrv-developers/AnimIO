# -*- coding: utf-8 -*-
""" Inialize the mrv.maya sub-system and startup maya as completely as possible or configured """
import os, sys
import mrv
from mrv import init_modules
from mrv.util import capitalize, DAGTree, PipeSeparatedFile
from mrv.exc import MRVError
from mrv.path import Path

from itertools import chain
import logging
log = logging.getLogger("mrv.maya")

# initialize globals
if not hasattr( sys,"_dataTypeIdToTrackingDictMap" ):
	sys._dataTypeIdToTrackingDictMap = dict()			 # DataTypeId : tracking dict


__all__ = ("registerPluginDataTrackingDict", )

############################
#### COMMON   			####
##########################

#{ Common

def registerPluginDataTrackingDict( dataTypeID, trackingDict ):
	"""Using the given dataTypeID and tracking dict, nt.PluginData can return
	self pointers belonging to an MPxPluginData instance as returned by MFnPluginData.
	Call this method to register your PluginData information to the mrv system.
	Afterwards you can extract the self pointer using plug.masData().data()"""
	sys._dataTypeIdToTrackingDictMap[ dataTypeID.id() ] = trackingDict

#} End Common


#{ Init new maya version
def initializeNewMayaRelease( ):
	"""This method should be called once a new maya release is encountered. It will
	initialize and update the database as well as possible, and give instructions 
	on what to do next.
	
	:note: Will not run if any user setup is performed as we need a clean maya 
	without any plugins loaded.
	:raise EnvironmentError: if the current maya version has already been initialized
	or if the user setup was executed"""
	if int(os.environ.get('MRV_STANDALONE_AUTOLOAD_PLUGINS', 0)) or \
		int(os.environ.get('MRV_STANDALONE_RUN_USER_SETUP', 0)):
		raise EnvironmentError("Cannot operate if custom user setup was performed")
	# END check environments
	
	import env
	import mdb

	nodeshf = mdb.nodeHierarchyFile()
	app_version = env.appVersion()[0]
	if nodeshf.isfile():
		raise EnvironmentError("Maya version %g already initialized as hierarchy file at %s does already exist" % (app_version, nodeshf))
	# END assure we are not already initialized
	
	# UPDATE MFN DB FILES
	#####################
	# Get all MFn function sets and put in their new versions as well as files
	mdb.writeMfnDBCacheFiles()
	
	# UPDATE NODE HIERARCHY FILE
	############################
	# create all node types, one by one, and query their hierarchy relationship.
	# From that info, generate a dagtree which is written to the hierarchy file.
	# NOTE: for now we just copy the old one
	dagTree, typeToMFnList = mdb.generateNodeHierarchy()
	dagTree.to_hierarchy_file('_root_', mdb.nodeHierarchyFile())
	
	# UPDATE MFN ASSOCIATIONS
	#########################
	fp = open(mdb.cacheFilePath('nodeTypeToMfnCls', 'map'), 'wb')
	mla = reduce(max, (len(t[0]) for t in typeToMFnList))
	mlb = reduce(max, (len(t[1]) for t in typeToMFnList))
	
	psf = PipeSeparatedFile(fp)
	psf.beginWriting((mla, mlb))
	for token in typeToMFnList:
		psf.writeTokens(token)
	# END for each line to write
	fp.close()
	
	
	# PROVIDE INFO	TO THE USER
	############################
	print >> sys.stderr, "1. git status might reveals new MFnFunction sets as untracked files - check the new methods and possibly define aliases (or delete them wiht 'x')"
	print >> sys.stderr, "2. Check the 'whats new' part of the maya docs for important API changes and possibly incorporate them into the code"
	print >> sys.stderr, "3. run 'tmrv %g' and fix possibly breaking tests or the code being tested" % app_version
	print >> sys.stderr, "4. run 'tmrvr' to assure all maya versions are still working - ideally on all platforms."
	print >> sys.stderr, "5. run the UI tests and assure that they don't fail"
	print >> sys.stderr, "6. Commit and push your changes - you are done"

#} END init new maya version


#{ Internal Utilities
def dag_tree_from_tuple_list( tuplelist ):
	""":return: DagTree from list of tuples [ (level,name),...], where level specifies
	the level of items in the dag.
	:note: there needs to be only one root node which should be first in the list
	:return: `DagTree` item allowing to easily query the hierarchy """
	tree = None
	lastparent = None
	lastchild = None
	lastlevel = 0

	for no,item in enumerate( tuplelist ):
		level, name = item

		if level == 0:
			if tree != None:
				raise MRVError( "DAG tree must currently be rooted - thus there must only be one root node, found another: " + name )
			else:
				tree = DAGTree(  )		# create root
				tree.add_node( name )
				lastparent = name
				lastchild = name
				continue

		direction = level - lastlevel
		if direction > 1:
			raise MRVError( "Can only change by one down the dag, changed by %i in item %s" % ( direction, str( item ) ) )

		lastlevel = level
		if direction == 0:
			pass
		elif direction == 1 :
			lastparent = lastchild
		elif direction == -1:
			lastparent = tree.parent( lastparent )
		elif direction < -1:		# we go many parents back, find the parent at level
			lastparent = list( tree.parent_iter( lastparent ) )[ -level ]

		tree.add_edge( lastparent, name )
		lastchild = name
	# END for each line in hiearchy map

	return tree

def tuple_list_from_file( filepath ):
	"""Create a tuple hierarchy list from the file at the given path
	:return: tuple list suitable for dag_tree_from_tuple_list"""
	lines = Path( filepath ).lines( retain = False )

	hierarchytuples = list()
	# PARSE THE FILE INTO A TUPLE LIST
	for no,line in enumerate( lines ):
		item = ( line.count( '\t' ), line.lstrip( '\t' ) )
		hierarchytuples.append( item )

	return hierarchytuples

def initWrappers( mdict, types, metacreatorcls, force_creation = False ):
	""" Create standin classes that will create the actual class once creation is
	requested.
	:param mdict: module dictionary object from which the latter classes will be imported from, 
	can be obtained using ``globals()`` in the module
	:param types: iterable containing the names of classnames ( they will be capitalized
	as classes must begin with a capital letter )"""
	from mrv.maya.util import StandinClass

	# create dummy class that will generate the class once it is first being instatiated
	standin_instances = list()
	for uitype in types:
		clsname = capitalize( uitype )

		# do not overwrite hand-made classes
		if clsname in mdict:
			continue

		standin = StandinClass( clsname, metacreatorcls )
		mdict[ clsname ] = standin

		if force_creation:
			standin_instances.append(standin)
	# END for each uitype
	
	# delay forced creation as there may be hierarchical relations between 
	# the types
	for standin in standin_instances:
		standin.createCls( )

def move_vars_to_environ( ):
	"""Move the maya vars as set in the shell into the os.environ to make them available to python"""
	import maya.cmds as cmds
	import subprocess
	envcmd = "env"

	if cmds.about( nt=1 ):
		envcmd = "set"

	p = subprocess.Popen( envcmd, shell=True, stdout=subprocess.PIPE )

	for line in p.stdout:
		try:
			var,value = line.split("=", 1)
		except:
			continue
		else:
			os.environ[ var ] = value.strip()
		# END try to split line
	# END for each line from process' stdout 
#} END internal utilities



############################
#### INITIALIZATION   ####
#########################

#{ Initialization
def init_system( ):
	"""
	Check if we are suited to import the maya namespace and try to set it
	up such we can use the maya standalone package.
	If running within maya or whith maya py, this is true, otherwise we have to
	use the MAYA_LOCATION to get this to work.
	"""
	# RUNNING WITHIN MAYA ? Then we have everything
	# if being launched in mayapy, we need initialization though !
	binBaseName = os.path.split( sys.executable )[1].split( '.' )[0]
	if binBaseName[0:4].lower() == 'maya' and binBaseName[0:6].lower() != 'mayapy':
		return


	# try to setup the paths to maya accordingly
	locvar = 'MAYA_LOCATION'
	if not os.environ.has_key( locvar ):
		raise EnvironmentError( locvar + " was not set - it must point to the maya installation directory" )

	# EXTRACT VERSION INFORMATION IF POSSIBLE
	##########################################
	mayalocation = os.path.realpath(os.environ[locvar])
	splitpos = -1

	# OS X special case
	if mayalocation.endswith( "Contents" ):
		splitpos = -3

	mayabasename = mayalocation.split( os.sep )[ splitpos ]

	# currently unused
	bits = 32
	if mayabasename.endswith( '64' ):
		bits = 64

	mayabasename = mayabasename.replace( "-x64", "" )	# could be mayaxxxx-x64
	mayaversion = mayabasename[4:]				# could be without version, like "maya"
	fmayaversion = float(mayaversion)


	# PYTHON COMPATABILITY CHECK
	##############################
	pymayaversion = sys.version_info[0:2]
	if len( mayaversion ):
		pyminor = pymayaversion[1]

		if mayaversion not in [ '8.5', '2008', '2009', '2010', '2011' ]:
			raise EnvironmentError( "Requires Maya 8.5 or higher for python support, found " + mayaversion + ", or maya version is not implemented" )

		if  ( mayaversion == "8.5" and pyminor != 4 ) or \
			( mayaversion == "2008" and pyminor != 5 ) or \
			( mayaversion == "2009" and pyminor != 5 ) or \
			( mayaversion == "2010" and pyminor != 6 ) or \
			( mayaversion == "2011" and pyminor != 6 ):
			raise EnvironmentError( "Maya " + mayaversion + " python interpreter requirements not met" )
		# END check python version
	# END check maya version



	# FINALLY INIALIZE MAYA TO TO MAKE USE OF MAYA STANDALONE
	###########################################################
	if os.name == "nt":
		osspecific = os.path.join("Python", "lib")
	else:
		pyversionstr = str( pymayaversion[0] ) + "." + str( pymayaversion[1] )
		osspecific = os.path.join("lib", "python" + pyversionstr, "site-packages")
		
	mayapylibpath = os.path.join( mayalocation, osspecific, "site-packages" )
	sys.path.append( mayapylibpath )
	

	# CHECK AND FIX SYSPATH
	########################
	# to be very sure: If for some reason we have our own root package
	# in the path, remove it as we would most likely import our own maya
	# This appears to happen if mrv is installed as site-package btw.
	packagename = mrv.__name__
	for path in sys.path[:]:
		if path.endswith("/"+packagename) or path.endswith("\\"+packagename):
			sys.path.remove(path)
		# END if it is an invalid path
	# END for each sys path

	# although this was already done, do it again :). Its required if mrv is installed
	# natively
	mrv._remove_empty_syspath_entries()

	try:
		import maya
	except Exception, e:
		print "Paths in sys.path: "
		for p in sys.path: print "%r" % p
		raise EnvironmentError( "Failed to import maya - check this script or assure LD_LIBRARY path is set accordingly: " + str( e ) )
	# END handle import


	# FINALLY STARTUP MAYA
	########################
	# This will also set all default path environment variables and read the
	# maya environment file
	try:
		import maya.standalone
		maya.standalone.initialize()
	except:
		log.debug("Paths in sys.path: ")
		for p in sys.path: log.debug("%r" % p)
		if 'maya' in locals():
			log.info("Imported maya module is located at: %r" % maya.__file__)
		log.error("ERROR: Failed initialize maya")
		raise
	# END handle maya standalone initialization


	# COPY ENV VARS
	###############
	# NOTE: this might have to be redone in your own package dependent on when
	# we are called - might be too early here
	# This also handles the Maya.env variables
	if fmayaversion < 2009:
		move_vars_to_environ( )

	# FINISHED
	return

# END INIT SYSTEM

def init_user_prefs( ):
	"""intiialize the user preferences according to the set configuration variables"""
	try:
		init_mel = int(os.environ.get('MRV_STANDALONE_INIT_OPTIONVARS', 0))
		run_user_setup = int(os.environ.get('MRV_STANDALONE_RUN_USER_SETUP', 0))
		autoload_plugins = int(os.environ.get('MRV_STANDALONE_AUTOLOAD_PLUGINS', 0))
	except ValueError, e:
		log.warn("Invalid value for MRV configuration variable: %s" % str(e).split(':', 1)[-1])
	# END safe access to variables
	
	def source_file_safely(script):
		try:
			maya.mel.eval('source "%s"' % script)  
		except RuntimeError, e:
			log.error(str(e) + "- ignored")
		# END exception handling
	# END utility 
	
	if not (init_mel|run_user_setup|autoload_plugins):
		return
	
	import maya.cmds as cmds
	prefsdir = Path(cmds.internalVar(userPrefDir=1))
	
	if not prefsdir.isdir():
		log.warn("User Preferences directory did not exist: %s" % prefsdir)
		return
	# END check for existence
	
	# source actual MEL scripts
	sources = list()
	if init_mel:
		sources.append("createPreferencesOptVars.mel")
		sources.append("createGlobalOptVars.mel")
		sources.append(prefsdir + "/userPrefs.mel")
	# END option vars 
	
	if autoload_plugins:
		sources.append(prefsdir + "/pluginPrefs.mel")
	# END autoload plugins
	
	# run scripts we collected
	import maya.mel
	for scriptpath in sources:
		if os.path.isabs(scriptpath) and not os.path.isfile(scriptpath):
			log.warn("Couldn't source %s as it did not exist" % scriptpath)
		# END check whether absolute paths are available
		
		source_file_safely(scriptpath)
	# END for each script path 
	
	if run_user_setup:
		# mel
		source_file_safely("userSetup.mel")
		
		# userSetup.py gets executed by maya
	# END run user setup
	

def init_singletons( ):
	""" Initialize singleton classes and attach them direclty to our module"""
	global Scene
	global Mel

	import scene
	Scene = scene.Scene()

	import util
	Mel = util.Mel()


def init_standard_output( ):
	"""Assure that logging can print to stdout and stderr which get overwritten
	by special maya versions which lack the 'flush' method"""
	
	class PassOnOrDummy(object):
		def __init__(self, obj):
			self.obj = obj
		
		def does_nothing(self, *args, **kwargs):
			return
		
		def __getattr__(self, attr):
			try:
				return getattr(self.obj, attr)
			except AttributeError:
				return self.does_nothing
			# END handle object retrieval
	# END utility class
	
	for channame in ('stdout', 'stderr'):
		chan = getattr(sys, channame)
		if hasattr(chan, 'flush'):
			continue
		# END skip channels that would work
		
		# patch the curently established channel
		fixedchan = PassOnOrDummy(chan)
		setattr(sys, channame, fixedchan)
		
		# find all loggers so far and patch up their logging objects
		for l in chain((logging.root, ), logging.root.manager.loggerDict.values()):
			if not isinstance(l, logging.Logger):
				continue
			# END skip placeholders
			for handler in l.handlers:
				if isinstance(handler, logging.StreamHandler) and handler.stream is chan:
					handler.stream = fixedchan
				# END if stream needs fixing
			# END for each handler
		# END for each logger
	# END for each channel
	

#} Initialization

if 'init_done' not in locals():
	init_done = False


if not init_done:
	# assure we do not run several times
	init_system()
	init_standard_output()
	init_modules(__file__, "mrv.maya")
	init_singletons()
	
	# this serves as a reentrance check in case userSetup is importing us again
	init_done = True
	init_user_prefs()


