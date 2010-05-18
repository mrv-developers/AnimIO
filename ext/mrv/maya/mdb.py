# -*- coding: utf-8 -*-
"""
Provides classes and functions operating on the MayaAPI class database

:note: This module must not be auto-initialized as it assumes its parent package to 
	be present already
:note: The implementation is considered internal and may change any time unless stated
	otherwise.
"""
__docformat__ = "restructuredtext"

from mrv.path import Path
from mrv.util import PipeSeparatedFile
import mrv.maya.env as env
import mrv.maya as mrvmaya

import maya.cmds as cmds
import maya.OpenMaya as api

import UserDict
import inspect
import re
from cStringIO import StringIO
import string
import sys
import os

import logging
log = logging.getLogger("mrv.maya.mdb")

__all__ = ("createDagNodeHierarchy", "createTypeNameToMfnClsMap", "apiModules", 
           "mfnDBPath", "cacheFilePath", "writeMfnDBCacheFiles", 
           "extractMFnFunctions", "PythonMFnCodeGenerator", "MMemberMap", 
           "MMethodDescriptor" )

#{ Initialization 

def nodeHierarchyFile():
	""":return: Path to the node hierarchy file of the currently active maya version"""
	return cacheFilePath( "nodeHierarchy", "hf", use_version = 1 )

def createDagNodeHierarchy( ):
	""" Parse the nodes hierarchy file and return a `DAGTree` with its data
	:return: `DAGTree`"""
	mfile = nodeHierarchyFile()
	return mrvmaya.dag_tree_from_tuple_list( mrvmaya.tuple_list_from_file( mfile ) )

def createTypeNameToMfnClsMap( ):
	"""Parse a file associating node type names with the best compatible MFn function 
	set and return a dictionary with the data
	
	:return: dict(((nodeTypeNameStr : api.MFnCls), ...)) dictionary with nodetypeName
		MFn class mapping"""
	typenameToClsMap = dict()
	
	cfile = cacheFilePath( "nodeTypeToMfnCls", "map" )
	fobj = open( cfile, 'r' )
	pf = PipeSeparatedFile( fobj )

	version = pf.beginReading( )	 # don't care about version
	for nodeTypeName, mfnTypeName in pf.readColumnLine( ):
		found = False
		for apimod in apiModules():
			try:
				typenameToClsMap[ nodeTypeName ] = getattr( apimod, mfnTypeName )
				found = True
				break				# it worked, there is only one matching class
			except AttributeError:
				pass
		# END for each api module
		if not found:
			log.debug("Couldn't find mfn class named %s" % mfnTypeName)
	# END for each type/mfnclass pair
	fobj.close()
	
	return typenameToClsMap
	
#} END initialization


#{ Utilities 

def apiModules():
	""":return: tuple of api modules containing MayaAPI classes
	:note: This takes a moment to load as it will import many api modules. Delay 
		the call as much as possible"""
	import maya.OpenMaya as api
	import maya.OpenMayaAnim as apianim
	import maya.OpenMayaUI	as apiui
	import maya.OpenMayaRender	as apirender
	import maya.OpenMayaFX as apifx
	
	return (api, apianim, apiui, apirender, apifx)

def mfnDBPath( mfnclsname ):
	"""Generate a path to a database file containing mfn wrapping information"""
	return Path(cacheFilePath("mfndb/"+ mfnclsname, '', use_version=False)[:-1])	# cut the '.'
	
def headerPath( apiname ):
	"""
	:return: Path to file containing the c++ header of the given apiclass' name.
		The file will not be verified, hence it may be inaccessible
	:param apiname: string name, like 'MFnBase'
	:raise ValueError: if MAYA_LOCATION is not set"""
	p = Path("$MAYA_LOCATION").expand_or_raise().realpath()
	if sys.platform == 'darwin':
		p = p.parent().parent() / "devkit"
	# END handle platform dependency
	return p / ("include/maya/%s.h" % apiname)

def cacheFilePath( filename, ext, use_version = False ):
	"""Return path to cache file from which you would initialize data structures
	
	:param use_version: if true, the maya version will be appended to the filename  """
	mfile = Path( __file__ ).parent()
	version = ""
	if use_version:
		version = cmds.about( version=1 ).split( " " )[0]
	# END use version
	return mfile / ( "cache/%s%s.%s" % ( filename, version, ext ) )

def extractMFnFunctions(mfncls):
	"""Extract callables from mfncls, sorted into static methods and instance methods
	:return: tuple(list(callable_staticmethod, ...), list(callable_instancemethod, ...))"""
	mfnfuncs = list()
	staticmfnfuncs = list()
	mfnname = mfncls.__name__
	for fn, f in mfncls.__dict__.iteritems():
		if fn.startswith('_') or fn.endswith(mfnname) or not inspect.isroutine(f):
			continue
		# END skip non-routines
		
		if isinstance(f, staticmethod):
			# convert static methods into callable methods by fetching them officially
			staticmfnfuncs.append(getattr(mfncls, fn))
		else:
			mfnfuncs.append(f)
		# END handle static methods 
	# END for each function in mfncls dict
	
	return (staticmfnfuncs, mfnfuncs)

def hasMEnumeration(mfncls):
	""":return: True if the given mfncls has at least one enumeration"""
	for n in mfncls.__dict__.keys():
		if n.startswith('k') and n[1] in string.ascii_uppercase:	# a single k would kill us ... 
			return True
	# END for each dict name
	return False

def writeMfnDBCacheFiles(  ):
	"""Create a simple Memberlist of available mfn classes and their members
	to allow a simple human-editable way of adjusting which methods will be added
	to the Nodes.
	
	:note: currently writes information about all known api modules"""
	for apimod in apiModules():
		mfnclsnames = [ clsname for clsname in dir( apimod ) if clsname.startswith( "MFn" ) ]
		for mfnname in mfnclsnames:
			mfncls = getattr( apimod, mfnname )
			if not inspect.isclass(mfncls):
				continue
			# END assure we don't get methods, like MFnName_deallocateFlag
			mfnfile = mfnDBPath( mfnname )
			

			mfnfuncs = list()
			fstatic, finst = extractMFnFunctions(mfncls)
			mfnfuncs.extend(fstatic)
			mfnfuncs.extend(finst)
			
			if not mfnfuncs:
				continue
			
			db = MMemberMap()
			if mfnfile.exists():
				db = MMemberMap( mfnfile )

			# assure folder exists
			folder = mfnfile.dirname()
			if not folder.isdir(): folder.makedirs()


			# write data - simple set the keys, use default flags
			for func in mfnfuncs:
				# it could be prefixed with the function set name - remove the prefix
				# This happens in maya2008 + and may introduce plenty of new methods
				fname = func.__name__
				if fname.startswith(mfnname):
					fname = fname[len(mfnname)+1:]	# cut MFnName_(function)
				# END handle prefix
				
				db.createEntry(fname)
			# END for each function to add

			# finally write the change db
			db.writeToFile( mfnfile )
		# END for each api class
	# END for each api module

def _createTmpNode(nodetype):
	"""Return tuple(mobject, modifier) for the nodetype or raise RuntimeError
	doIt has not yet been called on the modifier, hence the mobject is temporary"""
	try:
		mod = api.MDGModifier()
		obj = mod.createNode(nodetype)
		return (obj, mod)
	except RuntimeError:
		mod = api.MDagModifier()
		tmpparent = mod.createNode("transform")
		obj = mod.createNode(nodetype, tmpparent)
		return (obj, mod)
	# END exception handling
# END utility

def _iterAllNodeTypes( ):
	"""Returns iterator which yield tuple(nodeTypeName, MObject, modifier) triplets
	of nodeTypes, with an MObjects instance of it, created with the given modifier, 
	one for each node type available to maya.
	
	:note: skips manipulators as they tend to crash maya on creation ( perhaps its only
		one which does that, but its not that important )"""
	for nodetype in sorted(cmds.ls(nodeTypes=1)):
		# evil crashers
		if 'Manip' in nodetype or nodetype.startswith('manip'):
			continue
		# END skip manipulators
		try:
			obj, mod = _createTmpNode(nodetype) 
			yield nodetype, obj, mod
		except RuntimeError:
			log.warn("Could not create '%s'" % nodetype)
			continue
		# END create dg/dag node exception handling

def generateNodeHierarchy( ):
	"""Generate the node-hierarchy for the current version based on all node types 
	which can be created in maya.
	
	:return: tuple(DAGTree, typeToMFnClsNameList)
	
		* DAGTree representing the type hierarchy
		* list represents typeName to MFnClassName associations
		 
	:note: should only be run as part of the upgrade process to prepare MRV for  a
		new maya release. Otherwise the nodetype tree will be read from a cache"""
	from mrv.util import DAGTree
	from mrv.util import uncapitalize, capitalize
	from mrv.maya.util import MEnumeration
	
	# init DagTree
	root = "_root_" 
	depnode = 'dependNode'
	depnode_list = [depnode]
	noderoottype = 'node'
	dagTree = DAGTree()
	dagTree.add_edge(root, noderoottype)
	dagTree.add_edge(noderoottype, depnode)
	
	apiTypeToNodeTypeMap = dict()		# apiTypeStr -> nodeTypeName
	mfnTypes = set()					# apiTypeStr of mfns used by NodeTypes
	sl = list()							# string list
	
	
	mfndep = api.MFnDependencyNode()
	def getInheritanceAndUndo(obj, modifier):
		"""Takes a prepared modifier ( doIt not yet called ) and the previously created object, 
		returning the inheritance of the obj which was retrieved before undoing
		its creation"""
		modifier.doIt()
		mfndep.setObject(obj)
		inheritance = cmds.nodeType(mfndep.name(), i=1)
		modifier.undoIt()
		return inheritance
	# END utility
	
	
	# CREATE ALL NODE TYPES
	#######################
	# query the inheritance afterwards
	for nodetype, obj, mod in _iterAllNodeTypes():
		inheritance = getInheritanceAndUndo(obj, mod)
		
		if not inheritance:
			log.error("Failed on type %s" % nodetype)
			continue
		# END handle unusual case
		
		# filter bases
		for parent, child in zip(depnode_list + inheritance[:-1], inheritance):
			dagTree.add_edge(parent, child)
		# END for each edge to add
		
		# retrieve all compatible MFnTypes - these refer to apiTypes which are 
		# also used by Nodes. Currently we have only the type of the node, fortunately, 
		# it will match very well with the MFnType, by just prepending MFn.
		# As some MFn are in other modules, we will search em all ... later
		apiTypeToNodeTypeMap[obj.apiTypeStr()] = nodetype
		
		api.MGlobal.getFunctionSetList(obj, sl)
		for mfnType in sl:
			mfnTypes.add(mfnType)
	# END for each node type
	
	# INSERT SPECIAL TYPES
	######################
	# used by the type system if it cannot classify a node at all
	dagTree.add_edge(depnode, 'unknown')
	
	# can be iterated using the DagIterator, and it should at least be a dag node, 
	# not unknown. The groundPlane is actually a special object that users shouldn't
	# touch directly
	dagTree.add_edge('transform', 'groundPlane')
	
	# although we don't handle manips directly, we must still support them if it
	# is a plugin manipulator
	dagTree.add_edge('transform', 'manipContainer')
	
	
	
	# INSERT PLUGIN TYPES
	######################
	for edge in (	(depnode, 'DependNode'),
					('shape', 'Shape'), 
					('locator', 'LocatorNode'), 
					('spring', 'SpringNode'), 
					('transform', 'TransformNode'), 
					('manipContainer', 'ManipContainer'), 
					('dynBase', 'EmitterNode'), 
					('field', 'FieldNode'), 
					('objectSet', 'ObjectSet'), 
					('geometryFilter', 'DeformerNode'), 
					(depnode, 'HwShaderNode'), 
					('ikSolver', 'IkSolver'), 
					(depnode, 'ImagePlaneNode'), 
					(depnode, 'ParticleAttributeMapperNode')	):
		dagTree.add_edge(edge[0], 'unknownPlugin'+edge[1])
	# END for each plugin edge to add
	
	
	
	# BULD TYPE-TO-MFN MAP
	######################
	# Prepare data to be put into a type separated file, it associates 
	# a nodeType or nodeApiType with the respecitve MFnClass name
	typeToMFn = set()		# list((typeName, MFnClsName), ...)
	
	# add default associations - some are not picked up due to name mismatches
	typeToMFn.add((noderoottype, 'MFn'))
	typeToMFn.add((depnode, 'MFnDependencyNode'))
	typeToMFn.add(('dagContainer', 'MFnContainerNode'))
	
	abstractMFns = ('MFnBase', )		# MFns which cannot be instantiated ans should be ignored
	failedMFnTypes = list()			# list of types we could not yet associate
	
	modsapi = apiModules()
	for mfnApiType in mfnTypes:
		mfnNodePseudoType = uncapitalize(mfnApiType[1:])	# # kSomething -> something
		nodeType = apiTypeToNodeTypeMap.get(mfnApiType, mfnNodePseudoType)
		
		# MFnSets follow their kMFnType names, but when we try to associate it with 
		# the actual nodeType . Sometimes, they follow the actual nodeType, so we 
		# have to use this one as well
		found = False
		for nt, mfnNameCandidate in ( (mfnNodePseudoType, "MFn%s" % capitalize(mfnApiType[1:])), 
									   (nodeType, "MFn%s" % capitalize(nodeType)) ):
			# ignore abstract ones
			if mfnNameCandidate in abstractMFns:
				continue
			
			for modapi in modsapi:
				if hasattr(modapi, mfnNameCandidate):
					found = True
					
					# prefer a real nodetype if we have one - it will default
					# to the pseudotype
					typeToMFn.add((nodeType, mfnNameCandidate))
					break
				# END module with given name exists
			# END for each api module
			
			if found:
				break
		# END for each nodeType/mfnNamecandidate
		
		# still not found ? Keep it, but only if there is a nodetype 
		# associated with it
		if not found and mfnApiType in apiTypeToNodeTypeMap:
			failedMFnTypes.append(mfnApiType)
		# END keep a record
	# END for each mfnType
	
	
	
	# DATA, COMPONENTS, ATTRIBUTES
	###############################
	# get inheritance of Data, Component and Attribute types
	def unMFn(name):
		return uncapitalize(name[3:])
	# END remove MFn in front of MFnSomething strings
	
	for mfnsuffix in ("data", "component", "attribute"):
		mfnsuffixcap = capitalize(mfnsuffix)
		mfnnames = list()
		for modapi in modsapi:
			mfnnames.extend( n for n in dir(modapi) if n.endswith(mfnsuffixcap) )
		# END for each api module to get information from
		
		dagTree.add_edge(root, mfnsuffix)
		
		mfnsuffix_root = [ mfnsuffix ]
		for mfnname in mfnnames:
			for modapi in modsapi:
				try:
					mfncls = getattr(modapi, mfnname)
				except AttributeError:
					continue
				# END handle multi-modules
				
				# skip classes which are just named like the super type, but 
				# don't actually inherit it
				if "MFn%s" % mfnsuffixcap not in ( p.__name__ for p in mfncls.mro() ):
					continue
				
				# add type->MFn association
				typeToMFn.add((unMFn(mfnname), mfnname))
				
				# cut object and MFnBase
				# from the names, cut the MFn and uncaptialize it: MFnData -> data
				pclsnames = [ unMFn(p.__name__) for p in list(reversed(mfncls.mro()))[2:] ]
				for parent, child in zip(pclsnames[:-1], pclsnames[1:]):
					dagTree.add_edge(parent, child)
				# END for each mfn child to add
				
				break
			# END for each api module
		# END for each name
	# END for each mfnsuffix
	
	
	# HANDLE FAILED MFN-ASSOCITAIONS
	################################
	# lets take some very special care !
	if failedMFnTypes:
		# Here we handle cases which don't follow any naming conventions really
		# Hence we have to instantiate an object of the failed type, then 
		# we instantiate all the remaining functions sets to see which one fits.
		# If the required one has the requested type, we have a match. 
		# If we have no type match, its still a valid MFn - If we haven't seen it 
		# yet, its probably a base MFn whose kType string allows deduction of the 
		# actual abtract node type which we will use instead.
		associatedMFns = ( t[1] for t in typeToMFn )
		allMFnSetNames = list()
		for modapi in modsapi:
			allMFnSetNames.extend( n for n in dir(modapi) if n.startswith('MFn') and 
															not n.endswith('Ptr') and 
															not '_' in n and 		# skip 'special' ones
															not 'Manip' in n )		# skip everything about Manipulators
		# END get all MFn names
		
		# find MFnClasses for each candidate name
		candidateMFnNames = (set(allMFnSetNames) - set(associatedMFns)) - set(abstractMFns)
		candidateMFns = list()
		for cn in list(candidateMFnNames):
			for modapi in modsapi:
				try:
					mfncls = getattr(modapi, cn)
					# ignore them if they don't derive from MFnBase
					if not hasattr(mfncls, "type"):
						log.debug("Skipped MFn %s as it didn't derive from MFnBase" % mfncls)
						candidateMFnNames.discard(cn)
						continue
					# END skip mfn
					candidateMFns.append(mfncls)
					break
				except AttributeError:
					continue
			# END for each api module
		# END for each candidate name
		
		succeededMFnNames = set()
		
		
		# PRUNE REMAINING MFNs
		# prune out all MFnClasses that can be constructed without an actual object
		enumMembers = MEnumDescriptor('Type')
		enumMembers.extend( m for m in dir(api.MFn) if m.startswith('k') )
		mfntypes = MEnumeration.create(enumMembers, api.MFn)
		
		for mfncls in candidateMFns[:]:
			try:
				mfninst = mfncls()
				if mfntypes.nameByValue(mfninst.type()) in failedMFnTypes:
					continue
				# END keep actually missing MFns
				candidateMFns.remove(mfncls)
				candidateMFnNames.remove(mfncls.__name__)
			except RuntimeError:
				continue
		# END for each possible MFn to prune
		
		# at this point, we have about 500 api types with no MFn, but only 
		# about 10 function sets, 
		# Now ... we  brute-force test our way through all of these to find 
		# matching ones ... argh
		derivedMatches = list()		# keeps tuple(kTypeStr, mfnname) of matches of derived types
		perfectMatches = list()		# keeps mfnnames of perfect matches
		for failedApiTypeStr in failedMFnTypes:
			nodeType = apiTypeToNodeTypeMap[failedApiTypeStr]
			obj, mod = _createTmpNode(nodeType)
			
			removeThisMFn = None
			for mfncls in candidateMFns:
				try:
					mfninst = mfncls(obj)
				except RuntimeError:
					continue
				# END handle incompatability
				
				apiTypeStr = mfntypes.nameByValue(mfninst.type())
				
				if apiTypeStr not in failedMFnTypes:
					removeThisMFn = mfncls
					break
				# END remove MFns that no one wants
				
				if apiTypeStr == failedApiTypeStr:
					mfnname = mfncls.__name__
					typeToMFn.add((nodeType, mfnname))
					perfectMatches.append(mfnname)
					removeThisMFn = mfncls
					break
				# END perfect match 
				
				# its matching, but its not perfectly suited for our node type
				# We keep it, and will map it later if we don't find a better match
				derivedMatches.append((apiTypeStr, mfncls.__name__))
			# END for each mfncls
			
			if removeThisMFn is not None:
				succeededMFnNames.add(removeThisMFn.__name__)
				candidateMFns.remove(removeThisMFn)
			# END remove matched MFn
			
			if not candidateMFns:
				break
			# END abort search if there is nothing left 
		# END for each failed type
		
		# HANDLE DERIVED MFns
		# prune out all derived mfs which have found a perfect match in the meanwhile
		# the rest will be added to the list
		for apiTypeStr, mfnname in filter(lambda t: t not in perfectMatches, derivedMatches):
			typeToMFn.add((apiTypeToNodeTypeMap[apiTypeStr], mfnname))
			succeededMFnNames.add(mfnname)
		# END for each apiTypeStr left ot add
		
		
		# LAST MANUAL WORK
		##################
		# SubDees, if created empty, cannot be attached to their function set
		# Hence we don't see the match, but ... we know its there, so we add it
		# ourselves
		for nodeType, mfnname in (('subdiv', 'MFnSubd'), ):
			typeToMFn.add((nodeType, mfnname))
			succeededMFnNames.add(mfnname)
		# END for each manually added type
		
		
		for mfnname in candidateMFnNames - succeededMFnNames:
			log.warn("Could not associate MFn: %s" % mfnname)
		# END provide some info
	# END special treatment
	return (dagTree, sorted(typeToMFn, key=lambda t: t[0]))

#} END functions 


#{ Code Generators 

class MFnCodeGeneratorBase(object):
	"""Define the interface and common utility methods to generate a string defining 
	code for a given MFnMethod according to the meta data provided by an `MMethodDescriptor`.
	
	Once instantiated, it can create any number of methods"""
	__slots__ = 'module_dict'
	def __init__(self, module_dict):
		"""Intialize this instance"""
		self.module_dict = module_dict
	
	#{ Utilities
	def _toRvalFunc( self, funcname ):
		""":return: None or a function which receives the return value of our actual mfn function"""
		if not isinstance( funcname, basestring ):
			return funcname
		if funcname == 'None': return None
		
		try:
			return self.module_dict[funcname]
		except KeyError:
			raise ValueError("'%s' does not exist in code generator's dictionary" % funcname )
	#} END utilities
	
	
	#{ Interface 
	def generateMFnClsMethodWrapper(self, source_method_name, target_method_name, mfn_fun_name, method_descriptor, flags=0):
		"""
		:return: string containing the code for the wrapper method as configured by the 
			method descriptor
		:param source_method_name: Original name of the method - this is the name under which 
			it was requested.
		:param target_method_name: Name of the method in the returned code string
		:param mfn_fun_name: original name of the MFn function
		:param method_descriptor: instance of `MMethodDescriptor`
		:param flags: bit flags providing additional information, depending on the actual 
			implementation. Unsupported flags are ignored."""
		raise NotImplementedError("To be implemented in SubClass")
	#} END interfacec
	

class PythonMFnCodeGenerator(MFnCodeGeneratorBase):
	"""Specialization to generate python code
	
	**Flags**:
	
	 * kDirectCall:
	 	If set, the call return the actual mfn method in the best case, which is 
	 	a call as direct as it gets. A possibly negative side-effect would be that
	 	it the MFnMethod caches the function set and actual MObject/MDagPath, which 
	 	can be dangerous if held too long
	 	
	 * kIsMObject:
	 	If set, the type we create the method for is not derived from Node, but 
	 	from MObject. This hint is required in order to generate correct calling code.
	 	
	 * kIsDagNode:
	 	If set, the type we create the method for is derived from DagNode
	 	
	 * kIsStatic:
	 	If set, the method to be wrapped is considered static, no self is needed, nor
	 	any object.
	 	NOTE: This flag is likely to be removed as it should be part of the method_descriptor, 
	 	for now though it does not provide that information so we pass it in.
	 	
	 * kWithDocs:
	 	If set, a doc string will be generated the method. In future, this information
	 	will come from the method descriptor. Please note that docs should only be attaced
	 	in interactive modes, otherwise its a waste of memory.
	 
	"""
	# IMPORTANT: If these change, update docs above, and test.maya.test_mdb and test.maya.performance.test_mdb !
	kDirectCall, \
	kIsMObject, \
	kIsDagNode, \
	kIsStatic, \
	kWithDocs = [ 1<<i for i in range(5) ] 
	
	def generateMFnClsMethodWrapper(self, source_method_name, target_method_name, mfn_fun_name, method_descriptor, flags=0):
		"""Generates code as python string which can be used to compile a function. It assumes the following 
		globals to be existing once evaluated: mfncls, mfn_fun, [rvalfunc]
		Currently supports the following data within method_descriptor:
		
		 * method_descriptor.rvalfunc
		 
		as well as all flags except kIsStatic.
		:raise ValueError: if flags are incompatible with each other
		"""
		if flags & self.kIsMObject and flags & self.kIsDagNode:
			raise ValueError("kIsMObject and kIsDagNode are mutually exclusive")
		# END handle flags
		
		
		sio = StringIO()
		
		rvalfunname = ''
		if method_descriptor.rvalfunc != 'None':
			rvalfunname = method_descriptor.rvalfunc
		
		sio.write("def %s(self, *args, **kwargs):\n" % target_method_name)
		
	
		# mfn function call
		mfnset = "mfncls(self"
		if flags & self.kIsDagNode:
			mfnset += ".dagPath()"
		elif not flags & self.kIsMObject:
			mfnset += ".object()"
		mfnset += ")"
		
		if flags & self.kDirectCall:
			curline = "\tmfninstfunc = %s.%s\n" % (mfnset, mfn_fun_name)
			sio.write(curline)
			
			if rvalfunname:
				sio.write("\tmfninstfunc = lambda *args, **kwargs: rvalfun(mfninstfunc(*args, **kwargs))\n")
			# END handle rvalfunc name
			sio.write("\tself.%s = mfninstfunc\n" % source_method_name)
			sio.write("\treturn mfninstfunc(*args, **kwargs)")
		else:
			curline = "mfn_fun(%s, *args, **kwargs)" % mfnset
			if rvalfunname:
				curline = "rvalfunc(%s)" % curline
			sio.write("\treturn %s" % curline)
		# END handle direct call
		
		return sio.getvalue()
	
	#{ Interface
	
	def generateMFnClsMethodWrapperMethod(self, source_method_name, target_method_name, mfncls, mfn_fun, method_descriptor, flags=0):
		""":return: python function suitable to be installed on a class
		:param mfncls: MFnFunction set class from which the method was retrieved.
		:param mfn_fun: function as retrieved from the function set's dict. Its a bare function.
		:note: For all other args, see `MFnCodeGeneratorBase.generateMFnClsMethodWrapper`"""
		rvalfunc = self._toRvalFunc(method_descriptor.rvalfunc)
		mfnfuncname = mfn_fun.__name__
		
		# handle MFnName_function
		if mfnfuncname.startswith(mfncls.__name__):
			mfnfuncname = mfnfuncname[len(mfncls.__name__)+1:]
			
		new_method = None
		if flags & self.kIsStatic:
			# use the function directly
			rvalfun = self._toRvalFunc(method_descriptor.rvalfunc)
			if rvalfun is None:
				new_method = mfn_fun
			else:
				fun = lambda *args, **kwargs: rvalfun(mfn_fun(*args, **kwargs))
				fun.__name__ = target_method_name
				new_method = fun
			# END 
		else:
			# get the compiled code
			codestr = self.generateMFnClsMethodWrapper(source_method_name, target_method_name, mfnfuncname, method_descriptor, flags)
			code = compile(codestr, "mrv/%s" % (mfncls.__name__+".py"), "exec")	# this operation is expensive !
			
			# get the function into our local dict, globals are our locals
			eval(code, locals())
			
			new_method = locals()[target_method_name]
		# END handle static methods
		
		if flags & self.kWithDocs:
			if hasattr(new_method, 'func_doc'):
				new_method.func_doc = "%s.%s" % (mfncls.__name__, mfnfuncname)
		# END attach generated doc string
		
		return new_method
	
	#} END interface
	
#} END code generators

#{ Parsers

class CppHeaderParser(object):
	"""Simplistic regex based parser which will extract information from the file
	it was initialized with.
	
	For now its so simple that there is no more than one method"""
	reEnums = re.compile( r"""^\s+ enum \s+ (?P<name>\w+) \s* \{                 # enum EnumName
                               (?P<members>[\(\)/\w\s,\-+="'\.\#!<\*\\]+)     # match whitespace or newlines
                               \}[ \t]*;[ \t]*$                                 # closing brace""", 
							  re.MULTILINE|re.VERBOSE)
	
	reEnumMembers = re.compile( """
	                           [\t ]{2,}                                        # assure we don't get something within the comment
								(k\w+)[ ]*                                       # find kSomething
								(?:=[ ]*[\w]+[ ]*)?                              # optionally find initializer = int|other_enum_member
								""", re.VERBOSE)
	
	@classmethod
	def parseAndExtract(cls, header_filepath, parse_enums=True):
		"""Parse the given header file and return the parsed information
		
		:param header_filepath: Path pointing to the given header file. Its currently
			assumed to be 7 bit ascii
		:param parse_enums: If True, enumerations will be parsed from the file. If 
			False, the enumeration tuple in the return value will be empty.
		:note: Currently we can only parse non-anonymous enumerations !
		:return: tuple(tuple(MEnumDescriptor, ...), )"""
		enum_list = list()
		
		# ENUMERATIONS
		##############
		# read everything, but skip the license text when matching
		if parse_enums:
			read_method = header_filepath.bytes
			# on windows, we have \r\n newlines, which are automatically 
			# converted to \n by the .text method. This might be a bit slower, 
			# so we only do it on windows
			if os.name == 'nt':
				read_method = header_filepath.text
			# END handle newline sequence
			
			header = read_method()
			for enummatch in cls.reEnums.finditer(header, 2188):
				ed = MEnumDescriptor(enummatch.group('name'))
				
				# parse all occurrences of kSomething, including the initializer
				members = enummatch.group('members')
				assert members
				for memmatch in cls.reEnumMembers.finditer(members):
					ed.append(memmatch.group(1))
				# END for each member to add
				
				enum_list.append(ed)
			# END for each match
		# END if enums should be parsed
		
		# METHODS 
		#########
		# TODO:
		
		return (tuple(enum_list), )
	
#} END parsers 
	
	
#{ Database
	
class MMethodDescriptor(object):
	"""Contains meta-information about a given method according to data read from 
	the MFnDatabase"""
	__slots__ = ("flag", "rvalfunc", "newname")
	
	def __init__( self, flag='', rvalfunc = None, newname="" ):
		self.flag = flag
		self.rvalfunc = rvalfunc
		self.newname = newname


class MEnumDescriptor(list):
	"""Is an ordered list of enumeration names without its values, together
	with the name of the enumeration type"""
	__slots__ = "name"
	def __init__(self, name):
		self.name = name
		

class MMemberMap( UserDict.UserDict ):
	"""Simple accessor for MFnDatabase access
	Direct access like db[funcname] returns an entry object with all values
	
	**Globals**:
	The __globals__ entry in MFn db files allows to pass additional options.
	Currently there are no supported flags"""
	__slots__ = ("flags", "enums")
	kDelete = 'x'

	def __init__( self, filepath = None, parse_enums=False ):
		"""intiialize self from a file if not None
		
		:param parse_enums: if True, enumerations will be parsed. Save time by specifying
			False in case you know that there are no enumerations"""
		UserDict.UserDict.__init__( self )

		self._filepath = filepath
		if filepath:
			self._initFromFile( filepath )
			
		# initialize globals
		self.flags = 0
		ge = self.get('__global__', None)
		if ge is not None:
			# currently we know none
			pass
		# END fetch info
		
		# INITIALIZE PARSED DATA
		self.enums = tuple()
		if parse_enums:
			self.enums, = CppHeaderParser.parseAndExtract(headerPath(filepath.namebase()))
		# END if enumerations should be parsed

	def __str__( self ):
		return "MMemberMap(%s)" % self._filepath


	def _initFromFile( self, filepath ):
		"""Initialize the database with values from the given file
		
		:note: the file must have been written using the `writeToFile` method"""
		self.clear()
		fobj = open( filepath, 'r' )

		pf = PipeSeparatedFile( fobj )
		pf.beginReading( )
		
		# get the entries
		for tokens in pf.readColumnLine( ):
			key = tokens[ 1 ]
			self[ key ] = MMethodDescriptor( flag=tokens[0], rvalfunc=tokens[2], newname=tokens[3] )
		# END for each token in read column line

	def writeToFile( self, filepath ):
		"""Write our database contents to the given file"""
		klist = self.keys()
		klist.sort()

		fobj = open( filepath, 'w' )
		pf = PipeSeparatedFile( fobj )
		pf.beginWriting( ( 4,40,20,40 ) )

		for key in klist:							# write entries
			e = self[ key ]
			pf.writeTokens( ( e.flag, key,e.rvalfunc, e.newname ) )
		# end for each key

		fobj.close()

	def methodByName( self, funcname ):
		"""
		:return: Tuple( mfnfuncname, entry )
			original mfnclass function name paired with the
			db entry containing more information
		:raise KeyError: if no such function exists"""
		try:
			return ( funcname, self[ funcname ] )
		except KeyError:
			for mfnfuncname,entry in self.iteritems():
				if entry.newname == funcname:
					return ( mfnfuncname, entry )
			# END for each item

		raise KeyError( "Function named '%s' did not exist in db" % funcname )

	def createEntry( self, funcname ):
		""" Create an entry for the given function, or return the existing one
		
		:return: Entry object for funcname"""
		return self.setdefault( funcname, MMethodDescriptor() )

	def mfnFunc( self, funcname ):
		""":return: mfn functionname corresponding to the ( possibly renamed ) funcname """
		return self.methodByName( funcname )[0]
		
#} END database

