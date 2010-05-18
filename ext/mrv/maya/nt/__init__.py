# -*- coding: utf-8 -*-
"""
All classes required to wrap maya nodes in an object oriented manner into python objects
and allow easy handling of them.

These python classes wrap the API representations of their respective nodes - most general
commands will be natively working on them.

These classes follow the node hierarchy as supplied by the maya api.

Optionally: Attribute access is as easy as using properties like:

	>>> node.translateX

:note: it is important not to cache these as the underlying obejcts my change over time.
	For long-term storage, use handles instead.

Default maya commands will require them to be used as strings instead.
"""
__docformat__ = "restructuredtext"

import mrv.maya as mrvmaya
import typ
_thismodule = __import__( "mrv.maya.nt", globals(), locals(), ['nt'] )
from mrv.path import Path
from mrv.util import capitalize
import mrv.maya.env as env
import mrv.maya.util as mrvmayautil
from mrv import init_modules

import maya.cmds as cmds
import maya.OpenMaya as api

import sys
import os
import logging

# May not use all as it will receive all submodules 
# __all__

#{ Globals

pluginDB = None

#} END globals

#{ Common

def addCustomType( newcls, parentClsName=None, **kwargs ):
	""" Add a custom class to this module - it will be handled like a native type
	
	:param newcls: new class object if metaclass is None, otherwise string name of the
		type name to be created by your metaclass
	:param parentClsName: if metaclass is set, the parentclass name ( of a class existing
		in the nodeTypeTree ( see /maya/cache/nodeHierarchy.html )
		Otherwise, if unset, the parentclassname will be extracted from the newcls object
	:param kwargs:
		 * force_creation: 
				if True, default False, the class type will be created immediately. This
				can be useful if you wish to use the type for comparison, possibly before it is first being
				queried by the system. The latter case would bind the StandinClass instead of the actual type.
	:raise KeyError: if the parentClsName does not exist"""
	newclsname = newcls
	newclsobj = None
	parentname = parentClsName
	if not isinstance( newcls, basestring ):
		newclsname = newcls.__name__
		newclsobj = newcls
		if not parentClsName:
			parentname = newcls.__bases__[0].__name__

	# add to hierarchy tree
	typ._addCustomType( globals(), parentname, newclsname, **kwargs )

	# add the class to our module if required
	if newclsobj:
		setattr( _thismodule, newclsname, newclsobj )
		
def removeCustomType( customType ):
	"""Removes the given type from this module as well as from the type hierarchy.
	This makes it unavailble to MRV
	
	:param customType: either string identifying the type's name or the type itself
	:note: does nothing if the type does not exist"""
	if not isinstance(customType, basestring):
		customType = customType.__name__
	typ._removeCustomType(globals(), customType)
	
def addCustomTypeFromFile( hierarchyfile, **kwargs ):
	"""Add a custom classes as defined by the given tab separated file.
	Call addCustomClasses afterwards to register your own base classes to the system
	This will be required to assure your own base classes will be used instead of auto-generated
	stand-in classes
	
	:param hierarchyfile: Filepath to file modeling the class hierarchy using tab-indentation.
		The root node has no indentation, whereas each child node adds one indentation level using 
		tabs.
	:param kwargs:
		 * force_creation: see `addCustomType`
	:note: all attributes of `addCustomType` are supported
	:note: there must be exactly one root type
	:return: iterator providing all class names that have been added"""
	dagtree = mrvmaya._dagTreeFromTupleList( mrvmaya._tupleListFromFile( hierarchyfile ) )
	typ._addCustomTypeFromDagtree( globals(), dagtree, **kwargs )
	return ( capitalize( nodetype ) for nodetype in dagtree.nodes_iter() )

def addCustomClasses( clsobjlist ):
	"""Add the given classes to the nodes module, making them available to the sytem
	
	:note: first the class hierarchy need to be updated using addCustomTypeFromFile.
		This must appen before your additional classes are parsed to assure our metaclass creator will not
		be called before it knows the class hierarchy ( and where to actually put your type ).
	
	:param clsobjlist: list of class objects whose names are mentioned in the dagtree"""
	# add the classes
	for cls in clsobjlist:
		setattr( _thismodule, cls.__name__, cls )
	# END for each class to add

def forceClassCreation( typeNameList ):
	"""Create the types from standin classes from the given typeName iterable.
	The typenames must be upper case
	
	:return: List of type instances ( the classes ) that have been created"""
	outclslist = list()
	standincls = mrvmayautil.StandinClass
	for typename in typeNameList:
		typeCls = getattr( _thismodule, typename )
		if isinstance( typeCls, standincls ):
			outclslist.append( typeCls.createCls() )
	# END for each typename
	return outclslist

def enforcePersistence( ):
	"""Call this method to ensure that the persistance plugin is loaded and available.
	This should by used by plugins which require persitence features but want to 
	be sure it is not disabled on the target system"""
	import mrv.maya.nt.storage as storage
	import mrv.maya.nt.persistence as persistence
	
	os.environ[persistence.persistence_enabled_envvar] = "1"
	reload(persistence)
	reload(storage)
	persistence.__initialize( _thismodule )

#} END common utilities

#{ Initialization 

def _init_package( ):
	"""Do the main initialization of this package"""
	import mrv.maya.mdb as mdb
	typ.targetModule = _thismodule			# init metaclass with our module
	typ._nodesdict = globals()
	typ.initNodeHierarchy( )
	typ.initTypeNameToMfnClsMap( )
	typ.initWrappers( globals() )
	
	# code generator needs an initialized nodes dict to work
	typ.codegen = mdb.PythonMFnCodeGenerator(typ._nodesdict)

	# initialize base module with our global namespace dict
	import base
	base._nodesdict = globals()

	# must come last as typ needs full initialization first
	import apipatch
	apipatch.init_applyPatches( )
	
	# initialize modules
	init_modules( __file__, "mrv.maya.nt", self_module = _thismodule )


def _force_type_creation():
	"""Enforce the creation of all types - must be called once all custom types 
	were imported"""
	standincls = mrvmayautil.StandinClass
	for cls in _thismodule.__dict__.itervalues():
		if isinstance( cls, standincls ):
			cls.createCls()
		# END create type 
	# END for each stored type
	
	
def _init_plugin_db():
	"""Find loaded plugins and provide dummies for their types - this assures iteration 
	will not stop on these types for instance"""
	global pluginDB
	pluginDB = PluginDB()
	
#} END initialization

#{ Utility Classes

class PluginDB(dict):
	"""Simple container keeping information about the loaded plugins, namely the node
	types they register.
	
	As PyMel code has shown, we cannot rely on pluginLoaded and unloaded callbacks, which 
	is why we just listen to plugin changed events, and figure out the differences ourselves.
	
	Currently we are only interested in the registered node types, which is why we 
	are on ``mrv.maya.nt`` level, not on ``mrv.maya`` level
	"""
	__slots__ = 'log'
	
	def __init__(self):
		"""Upon initialization, we will parse the currently loaded plugins and 
		register them. Additionally we register our event to stay in the loop 
		if anything changes."""
		self.log = logging.getLogger('mrv.maya.nt.%s' % type(self).__name__)
		# yes, we need a string here, yes, its mel
		# UPDATE: In maya 2011, a method is alright !
		melstr = 'python("import mrv.maya.nt; mrv.maya.nt.pluginDB.plugin_registry_changed()")'
		if env.appVersion()[0] < 2011.0:
			cmds.pluginInfo(changedCommand=melstr)
		else:
			# Okay, if we do this, maya crashes during shutdown, which is why we 
			# use mel then ... nice work, Autodesk ;)
			# cmds.pluginInfo(changedCommand=self.plugin_registry_changed)
			mrvmaya.Mel.eval('pluginInfo -changedCommand "%s"' % melstr.replace('"', '\\"'))
		# END install callback
		self.plugin_registry_changed()

	def plugin_registry_changed(self, *args):
		"""Called by maya to indicate something has changed. 
		We will diff the returned plugin information with our own database 
		to determine which plugin was added or removed, to make the appropriate 
		calls"""
		self.log.debug("registry changed")
		
		loaded_plugins = set(cmds.pluginInfo(q=1, listPlugins=1) or list())
		our_plugins = set(self.keys())
		
		# plugins loaded 
		for pn in loaded_plugins - our_plugins:
			self.plugin_loaded(pn)
			
		# plugins unloded
		for pn in our_plugins - loaded_plugins:
			self.plugin_unloaded(pn)
		
	def plugin_loaded(self, pluginName):
		"""Retrieve plugin information from a plugin named ``pluginName``, which is 
		assumed to be loaded.
		Currently the nodetypes found are added to the node-type tree to make them available.
		The plugin author is free to add specialized types to the tree afterwards, overwriting 
		the default ones.
		
		We loosely determine the inheritance by differentiating them into types suggested
		by MFn::kPlugin<Name>Node"""
		import base		# needs late import, TODO: reorganize modules
		
		self.log.debug("plugin '%s' loaded" % pluginName)
		
		type_names = cmds.pluginInfo(pluginName, q=1, dependNode=1) or list()
		self[pluginName] = type_names
		
		# register types in the system if possible
		dgmod = api.MDGModifier()
		dagmod = api.MDagModifier()
		transobj = None
		
		nt = globals()
		for tn in type_names:
			tnc = capitalize(tn)
			if tnc in nt:
				self.log.debug("Skipped type %s as it did already exist in module" % tnc)
				continue
			# END skip existing node types ( probably user created )
			
			# get the type id- first try depend node, then dag node. Never actually
			# create the nodes in the scene, created MObjects will be discarded
			# once the modifiers go out of scope
			apitype = None
			try:
				apitype = dgmod.createNode(tn).apiType()
			except RuntimeError:
				try:
					# most plugin dag nodes require a transform to be created
					# We create a dummy for the dagmod, otherwise it would create
					# it for us and return the parent transform instead, which 
					# has no child officially yet as its not part of the dag
					# ( so we cannot query the child from there ).
					if transobj is None:
						transobj = dagmod.createNode("transform")
					# END assure we have parent 
					
					apitype = dagmod.createNode(tn, transobj).apiType()
				except RuntimeError:
					self.log.error("Failed to retrieve apitype of node type %s - skipped" % tnc)
					continue
				# END dag exception handling
			# END dg exception handling 
			
			parentclsname = base._plugin_type_to_node_type_name.get(apitype, 'Unknown')
			typ._addCustomType( nt, parentclsname, tnc, force_creation=True )
		# END for each type to handle

	def plugin_unloaded(self, pluginName):
		"""Remove all node types registered by pluginName unless they have been 
		registered by a third party. We cannot assume that they listen to these events, 
		hence we just keep the record as it will not harm.
		
		In any way, we will remove any record of the plugin from our db"""
		self.log.debug("plugin '%s' unloaded" % pluginName)
		
		# clear our record
		installed_type_names = self[pluginName]
		del(self[pluginName])
		
		# deregister types if possible
		nt = globals()
		for tn in installed_type_names:
			tnc = capitalize(tn)
			
			try:
				node_type = nt[tnc]
			except KeyError:
				# wasnt registered anymore ? 
				self.log.warn("Type %s of unloaded plugin %s was already de-registered in mrv type system - skipped" % (tnc, pluginName)) 
				continue
			# END handle exception
			
			# remove the type only if it was one of our unknown default types
			parentclsname = node_type.__base__.__name__
			if not parentclsname.startswith('Unknown'):
				continue
			# END skip custom nodes
			
			typ._removeCustomType(nt, tnc)
		# END for each typename
		
		

#} END utilty classes



if 'init_done' not in locals():
	init_done = False

if not init_done:

	_init_package( )


	# overwrite dummy node bases with hand-implemented ones
	from base import *
	from geometry import *
	from set import *
	from anim import *
	from it import *
	from storage import *
	
	# fix set
	import __builtin__
	set = __builtin__.set
	
	# import additional classes required in this module
	from mrv.maya.ns import Namespace
	
	# Setup all actual types - this makes the use much easier
	_force_type_creation()
	_init_plugin_db()

init_done = True
