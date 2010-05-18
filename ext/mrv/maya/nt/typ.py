# -*- coding: utf-8 -*-
"""
Houses the MetaClass able to setup new types to work within the system. This can 
be considered the heart of the node wrapping engine, but it plays together with 
the implementation in the `base` module.
"""
__docformat__ = "restructuredtext"

from mrv.maya.util import MetaClassCreator
from mrv.maya.util import MEnumeration
import mrv.maya as mrvmaya
import mrv.maya.mdb as mdb
from mrv.util import uncapitalize, capitalize


import maya.OpenMaya as api

from new import instancemethod
import logging
log = logging.getLogger("mrv.maya.nt.typ")

__all__ = ("MetaClassCreatorNodes", )

#{ Caches
_nodesdict = None					# to be set during initialization
nodeTypeTree = None
nodeTypeToMfnClsMap = dict()		# allows to see the most specialized compatible mfn cls for a given node type
#} END caches

#{Globals
targetModule = None				# must be set in intialization to tell this class where to put newly created classes
mfnclsattr = '_mfncls'
mfndbattr = '_mfndb'
apiobjattr = '_apiobj'
getattrorigname = '__getattr_orig'
codegen = None		# python code generator, to be set during initialization
#} END globals


#{ Metaclasses
class MetaClassCreatorNodes( MetaClassCreator ):
	"""Builds the base hierarchy for the given classname based on our typetree
	:todo: build classes with slots only as members are pretermined"""
	
	@classmethod
	def _fetchMfnDB( cls, newcls, mfncls, **kwargs ):
		"""Return the mfndb for the given mfncls as existing on newcls. 
		If it does not yet exist, it will be created and attached first
		
		:param kwargs: passed to MMemberMap initializer"""
		try:
			return newcls.__dict__[ mfndbattr ]
		except KeyError:
			mfndbpath = mdb.mfnDBPath(mfncls.__name__)
			try:
				mfndb = mdb.MMemberMap(mfndbpath, **kwargs)
			except IOError:
				print IOError("Could not create MFnDB for file at %s" % mfndbpath)
				raise
			# END handle mmap reading
			type.__setattr__( newcls, mfndbattr, mfndb )
			return mfndb
		# END mfndb handling

	@classmethod
	def _wrapStaticMembers( cls, newcls, mfncls ):
		"""Find static mfnmethods - if these are available, initialize the 
		mfn database for the given function set ( ``mfncls`` ) and create properly 
		wrapped methods. 
		Additionally check for enumerations, and generate the respective enumeration
		instances
		:note: As all types are initialized on startup, the staticmethods check 
			will load in quite a few function sets databases as many will have static 
			methods. There is no real way around it, but one could introduce 'packs'
			to bundle these together and load them only once. Probably the performance
			hit is not noticeable, but lets just say that I am aware of it
		:note: Currently method aliases are not implemented for statics !"""
		fstatic, finst = mdb.extractMFnFunctions(mfncls)
		hasEnum = mdb.hasMEnumeration(mfncls)
		if not fstatic and not hasEnum:
			return
			
		mfndb = cls._fetchMfnDB(newcls, mfncls, parse_enums=hasEnum)
		if fstatic:
			mfnname = mfncls.__name__
			for fs in fstatic:
				fn = fs.__name__
				if fn.startswith(mfnname):
					fn = fn[len(mfnname)+1:]	# cut MFnName_methodName
				# END handle name prefix
				
				static_function = cls._wrapMfnFunc(newcls, mfncls, fn, mfndb)
				type.__setattr__(newcls, fn, staticmethod(static_function))
			# END for each static method
		# END handle static functions
		
		
		if hasEnum:
			for ed in mfndb.enums:
				type.__setattr__(newcls, ed.name, MEnumeration.create(ed, mfncls))
			# END for each enum desriptor
		# END handle enumerations
		
		
	@classmethod
	def _wrapMfnFunc( cls, newcls, mfncls, funcname, mfndb, addFlags=0 ):
		"""Create a function that makes a Node natively use its associated Maya
		function set on calls.

		The created function will use the api object of the instance of the call to initialize
		a function set of type mfncls and execute the function in question.

		The method mutation database allows to adjust the way a method is being wrapped
		
		:param mfncls: Maya function set class from which to take the functions
		:param funcname: name of the function set function to be wrapped.
		:param mfndb: `mdb.MMemberMap` 
		:param addFlags: If set, these flags define how the method will be generated.
		:raise KeyError: if the given function does not exist in mfncls
		:note: if the called function starts with _api_*, a special accellerated method
			will be returned and created allowing direct access to the mfn instance method.
			This is unsafe if the same api object is being renamed. Also it will only be faster if
			the same method is actually called multiple times. It can be great for speed sensitive code
			where where the same method(s) are called repeatedly on the same set of objects
		:return:  wrapped function or None if it was deleted"""
		flags = mfndb.flags|addFlags
		funcname_orig = funcname	# store the original for later use

		# rewrite the function name to use the actual one
		if funcname.startswith( "_api_" ):
			flags |= mdb.PythonMFnCodeGenerator.kDirectCall
			funcname = funcname[ len( "_api_" ) : ]
		# END is special api function is requested
		mfnfuncname = funcname		# method could be remapped - if so we need to lookup the real name

		
		method_descriptor = None
		# adjust function according to DB
		try:
			mfnfuncname, method_descriptor = mfndb.methodByName( funcname )
			# delete function ?
			if method_descriptor.flag == mdb.MMemberMap.kDelete:
				return None
		except KeyError:
			pass # could just be working
		# END if entry available
	
		if method_descriptor is None:
			method_descriptor = mdb.MMethodDescriptor()
		# END assure method descriptor is set
		
		# access it directly from the class, ignoring inheritance. If the class
		# would have overridden the function, we would get it. If it does not do that, 
		# we will end up with the first superclass implementing it. 
		# This is what we want as more specialized Function sets will do more checks
		# hence will be slower to create. Also in case of geometry, the python api 
		# is a real bitch with empty shapes on which it does not want to operate at all
		# as opposed to behaviour of the API.
		mfnfunc = mfncls.__dict__[ mfnfuncname ]			# will just raise on error
		if isinstance(mfnfunc, staticmethod):
			flags |= mdb.PythonMFnCodeGenerator.kIsStatic
			
			# convert static method to real method
			mfnfunc = type.__getattribute__(mfncls, mfnfuncname)
		# END handle 
		
		# finish compile flags
		if api.MFnDagNode in mfncls.mro():
			flags |= mdb.PythonMFnCodeGenerator.kIsDagNode
		if api.MObject in newcls.mro():
			flags |= mdb.PythonMFnCodeGenerator.kIsMObject
		
		# could be cached, but we need to wait until the dict is initialized, 
		# TODO: To be done in __init__ together with the nodedict
		newfunc = codegen.generateMFnClsMethodWrapperMethod(funcname_orig, funcname, mfncls, mfnfunc, method_descriptor, flags)
		
		if not flags & mdb.PythonMFnCodeGenerator.kIsStatic: 
			newfunc.__name__ = funcname			# rename the method
		# END handle renames
		return newfunc


	@classmethod
	def _wrapLazyGetAttr( thiscls, newcls ):
		""" Attach the lazy getattr wrapper to newcls """
		# keep the original getattr
		if hasattr( newcls, '__getattr__' ):
			getattrorig =  newcls.__dict__.get( '__getattr__', None )
			if getattrorig:
				getattrorig.__name__ = getattrorigname
				setattr( newcls, getattrorigname, getattrorig )

		# CREATE GET ATTR CUSTOM FUNC
		# called if the given attribute is not available in class
		def meta_getattr_lazy( self, attr ):
			actualcls = None										# the class finally used to store located functions

			# MFN ATTRTIBUTE HANDLING
			############################
			# check all bases for and their mfncls for a suitable function
			newclsfunc = newinstfunc = None							# try to fill these
			for basecls in newcls.mro():
				if not hasattr( basecls, mfnclsattr ):			# could be object too or user defined cls
					continue

				mfncls = getattr( basecls, mfnclsattr )
				if not mfncls:
					continue

				# get function as well as its possibly changed name
				try:
					mfndb = thiscls._fetchMfnDB(basecls, mfncls)
					newclsfunc = thiscls._wrapMfnFunc( newcls, mfncls, attr, mfndb )
					if not newclsfunc: # Function %s has been deleted - ignore
						continue
				except KeyError:  		# function not available in this mfn - ignore
					continue
				newinstfunc = instancemethod( newclsfunc, self, basecls )	# create the respective instance method !
				actualcls = basecls
				break					# stop here - we found it
			# END for each basecls ( searching for mfn func )

			# STORE MFN FUNC ( if available )
			# store the new function on instance level !
			# ... and on class level
			if newclsfunc:
				# assure we do not call overwridden functions
				object.__setattr__( self, attr, newinstfunc )
				type.__setattr__( actualcls, attr, newclsfunc )		# setattr would do too, but its more dramatic this way :)
				return newinstfunc
			# END newclsfunc exists

			# ORIGINAL ATTRIBUTE HANDLING
			###############################
			# still no funcion ? Continue with non-mfn search routine )
			# try to find orignal getattrs in our base classes - if we have overwritten
			# them we find them under a backup attribute, otherwise we check the name of the
			# original method for our lazy tag ( we never want to call our own counterpart on a
			# base class
			getattrorigfunc = None
			for basecls in newcls.mro():
				if hasattr( basecls, getattrorigname ):
					getattrorigfunc = getattr( basecls, getattrorigname )
					break
				# END orig getattr method check

				# check if the getattr function itself is us or not
				if hasattr( basecls, '__getattr__' ):
					getattrfunc = getattr( basecls, '__getattr__' )
					if getattrfunc.func_name != "meta_getattr_lazy":
						getattrorigfunc = getattrfunc
						break
				# END default getattr method check
			# END for each base ( searching for getattr_orig or nonoverwritten getattr )

			if not getattrorigfunc:
				raise AttributeError( "Could not find mfn function for attribute '%s'" % attr )

			# pass on the call - if this method produces an output, its responsible for caching
			# it in the instance dict
			return getattrorigfunc( self, attr )
			# EMD orig getattr handling
		# END getattr_lazy func definition

		# STORE LAZY GETATTR
		# identification !
		setattr( newcls, "__getattr__", meta_getattr_lazy )


	def __new__( metacls, name, bases, clsdict ):
		""" Called to create the class with name """
		# will be used later
		def func_nameToTree( name ):
			# first check whether an uncapitalized name is known, if not, check 
			# the capitalized version ( for special cases ), finalyl return
			# the uncapitalized version which is the default
			name = uncapitalize(name)
			if nodeTypeTree.has_node(name):
				return name
				
			capname = capitalize(name)
			if nodeTypeTree.has_node(capname):
				return capname
			
			return name
		# END utility

		# ATTACH MFNCLS
		#################
		# ask our NodeType to MfnSet database and attach it to the cls dict
		# ( if not yet there ). By convention, there is only one mfn per class
		mfncls = None
		needs_static_method_initialization = False
		if not clsdict.has_key( mfnclsattr ):
			treeNodeTypeName = func_nameToTree( name )
			if nodeTypeToMfnClsMap.has_key( treeNodeTypeName ):
				mfncls = nodeTypeToMfnClsMap[ treeNodeTypeName ]
				clsdict[ mfnclsattr ] = mfncls
				
				# attach static mfn methods directly.
				needs_static_method_initialization = True
			# END attach mfncls to type
		else:
			mfncls = clsdict[ mfnclsattr ]

		# do not store any mfn if there is none set - this would override mfns of
		# base classes although the super class is compatible to it
		if mfncls:
			clsdict[ mfnclsattr ] = mfncls			# we have at least a None mfn
		clsdict[ apiobjattr ] = None			# always have an api obj


		# CREATE CLS
		#################
		newcls = super( MetaClassCreatorNodes, metacls ).__new__( nodeTypeTree, targetModule,
																metacls, name, bases, clsdict,
																nameToTreeFunc = func_nameToTree )


		# LAZY MFN WRAPPING
		#####################
		# Functions from mfn should be wrapped on demand to the respective classes as they
		# should be generated only when used
		# Wrap the existing __getattr__ method in an own one linking mfn methods if possible
		# Additionally, precreate static methods
		if mfncls:
			metacls._wrapLazyGetAttr( newcls )
			
			if needs_static_method_initialization:
				metacls._wrapStaticMembers(newcls, mfncls)
		# END if mfncls defined


		return newcls

	# END __new__

#} END metaclasses


#{ Utilities

def prefetchMFnMethods():
	"""Fetch and install all mfn methods on all types supporting a function set.
	This should only be done to help interactive mode, but makes absolutely no 
	sense in the default mode of operation when everything is produced on demand.
	
	:note: Attaches docstrings as well
	:return: integer representing the number of generated methods"""
	log.info("Prefetching all MFnMethods")
	
	num_fetched = 0
	for typename, mfncls in nodeTypeToMfnClsMap.iteritems():
		try:
			nodetype = _nodesdict[capitalize(typename)]
		except KeyError:
			log.debug("MFn methods for %s exists, but type was not found in nt" % typename)
			continue
		# END handle type exceptions
		
		mfnname = mfncls.__name__
		mfndb = MetaClassCreatorNodes._fetchMfnDB(nodetype, mfncls)
		fstatic, finst = mdb.extractMFnFunctions(mfncls)
		
		def set_method_if_possible(cls, fn, f):
			if not hasattr(cls, fn):
				type.__setattr__(cls, fn, f)
			# END overwrite protection
		# END utility 
		
		for f in finst:
			fn = f.__name__
			if fn.startswith(mfnname):
				fn = fn[len(mfnname)+1:]
			# END handle prefixed names
			
			fna = fn		# alias for method 
			try:
				origname, entry = mfndb.methodByName(fn)
				fna = entry.newname
			except KeyError:
				pass
			# END get alias metadata
			
			fwrapped = MetaClassCreatorNodes._wrapMfnFunc(nodetype, mfncls, fn, mfndb, mdb.PythonMFnCodeGenerator.kWithDocs)
			
			# could have been deleted
			if fwrapped is None:
				continue
			
			set_method_if_possible(nodetype, fn, fwrapped)
			if fna != fn:
				set_method_if_possible(nodetype, fna, fwrapped)
			# END handle aliases
			
			num_fetched += 1
		# END for each instance function
	# END for each type/mfncls pair
	
	return num_fetched
	
	

#} END utilities

#{ Initialization

def _addCustomType( targetmoduledict, parentclsname, newclsname,
				   	metaclass=MetaClassCreatorNodes, **kwargs ):
	"""Add a custom type to the system such that a node with the given type will
	automatically be wrapped with the corresponding class name
	
	:param targetmoduledict: the module's dict to which standin classes are supposed to be added
	:param parentclsname: the name of the parent node type - if your new class
		has several parents, you have to add the new types beginning at the first exsiting parent
		as written in the maya/cache/nodeHierarchy.html file
	:param newclsname: the new name of your class - it must exist targetmodule
	:param metaclass: meta class object to be called to modify your type upon creation
		It will not be called if the class already exist in targetModule. Its recommended to derive it
		from the metaclass given as default value.
	:raise KeyError: if the parentclsname does not exist"""
	# add new type into the type hierarchy #
	parentclsname = uncapitalize( parentclsname )
	newclsname = uncapitalize( newclsname )
	nodeTypeTree.add_edge( parentclsname, newclsname )

	# create wrapper ( in case newclsname does not yet exist in target module )
	mrvmaya.initWrappers( targetmoduledict, [ newclsname ], metaclass, **kwargs )
	
	
def _removeCustomType( targetmoduledict, customTypeName ):
	"""Remove the given typename from the given target module's dictionary as 
	well as from internal caches
	
	:note: does nothing if the type does not exist
	:param targetmoduledict: dict of your module to remove the type from
	:param customTypeName: name of the type to be removed, its expected
		to be capitalized"""
	try:
		del(targetmoduledict[customTypeName])
	except KeyError:
		pass
	# END remove from dictionary
	
	customTypeName = uncapitalize(customTypeName)
	if nodeTypeTree.has_node(customTypeName):
		nodeTypeTree.remove_node(customTypeName)
	# END remove from type tree

def _addCustomTypeFromDagtree( targetmoduledict, dagtree, metaclass=MetaClassCreatorNodes,
							  	force_creation=False, **kwargs ):
	"""As `_addCustomType`, but allows to enter the type relations using a
	`mrv.util.DAGTree` instead of individual names. Thus multiple edges can be added at once
	
	:note: special care is being taken to make force_creation work - first all the standind classes
		are needed, then we can create them - just iterating the nodes in undefined order will not work
		as a parent node might not be created yet
	:note: node names in dagtree must be uncapitalized"""
	# add edges - have to start at root
	rootnode = dagtree.get_root()
	def recurseOutEdges( node ):		# postorder
		for child in dagtree.children_iter( node ):
			yield (node,child)
			for edge in recurseOutEdges( child ):	# step down the hierarchy
				yield edge

	nodeTypeTree.add_edges_from( recurseOutEdges( rootnode ) )
	mrvmaya.initWrappers( targetmoduledict, dagtree.nodes_iter(), metaclass, force_creation = force_creation, **kwargs )

def initTypeNameToMfnClsMap( ):
	"""Fill the cache map supplying additional information about the MFNClass to use
	when creating the classes"""
	global nodeTypeToMfnClsMap
	nodeTypeToMfnClsMap = mdb.createTypeNameToMfnClsMap()

def initNodeHierarchy( ):
	"""Initialize the global tree of types, providing a hierarchical relationship between 
	the node typename strings"""
	global nodeTypeTree
	nodeTypeTree = mdb.createDagNodeHierarchy()

def initWrappers( targetmoduledict ):
	"""Create Standin Classes that will delay the creation of the actual class till
	the first instance is requested
	
	:param targetmoduledict: the module's dictionary (globals()) to which to put the wrappers"""
	global nodeTypeTree
	mrvmaya.initWrappers( targetmoduledict, nodeTypeTree.nodes_iter(), MetaClassCreatorNodes )

#} END initialization
