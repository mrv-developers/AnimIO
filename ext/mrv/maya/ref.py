# -*- coding: utf-8 -*-
"""
Allows convenient access and handling of references in an object oriented manner
"""
__docformat__ = "restructuredtext"

from mrv.path import Path
from mrv.util import And
from mrv.exc import MRVError
from mrv.maya.ns import Namespace, _isRootOf
from mrv.maya.util import noneToList
from mrv.interface import iDagItem
import undo
import maya.cmds as cmds
import maya.OpenMaya as api
from itertools import ifilter

__all__ = ("createReference", "listReferences", "FileReference", "FileReferenceError")

#{ Exceptions
class FileReferenceError( MRVError ):
	pass

#}


#{ Utilities 

def createReference( *args, **kwargs ):
	"""create a new reference, see `FileReference.create` for more information"""
	return FileReference.create(*args, **kwargs)

def listReferences( *args, **kwargs ):
	"""List intermediate references of in the scene, see `FileReference.ls` for 
	more information"""
	return FileReference.ls( *args, **kwargs )

#} END utilities 


class FileReference( iDagItem ):
	"""Represents a Maya file reference
	
	:note: do not cache these instances but get a fresh one when you have to work with it
	:note: as FileReference is also a iDagItem, all the respective methods, especially for
		parent/child iteration and query can be used as well"""
	editTypes = [	'setAttr','addAttr','deleteAttr','connectAttr','disconnectAttr','parent' ]
	_sep = '/'					# iDagItem configuration
	__slots__ = '_refnode'

	@classmethod
	def _splitCopyNumber( cls, path ):
		""":return: ( path, copynumber ), copynumber is at least 0 """
		lbraceindex = path.rfind( '{' )
		if lbraceindex == -1:
			return (path, 0)
		# END handle no brace found
		
		return (path[:lbraceindex], int(path[lbraceindex+1:-1]))

	#{ Object Overrides
	def __init__( self, filepath = None, refnode = None ):
		if refnode:
			self._refnode = str(refnode)
		elif filepath:
			self._refnode = cmds.referenceQuery( filepath, rfn=1 )
		else:
			raise ValueError( "Specify either filepath or refnode to initialize the instance from" )
		# END handle input

	def __eq__( self, other ):
		"""Special treatment for other filereferences"""
		# need equal copy numbers as well as equal paths - the refnode encapsulates all this
		if isinstance( other, FileReference ):
			return self._refnode == other._refnode

		return self.path() == other

	def __ne__( self, other ):
		return not self.__eq__( other )

	def __hash__(self):
		return hash(self.path(copynumber=1))

	def __str__(self):
		return str(self.path())
		
	def __repr__(self):
		return "FileReference(%s)" % str(self.path(copynumber=1))

	#} END object overrides

	#{ Reference Adjustments 
	@classmethod
	def create( cls, filepath, namespace=None, load = True, **kwargs ):
		"""Create a reference with the given namespace
		
		:param filepath: path describing the reference file location
		:param namespace: if None, a unique namespace will be generated for you
			The namespace will contain all referenced objects.
		:param load: if True, the reference will be created in loaded state, other
			wise its loading is deferred
		:param kwargs: passed to file command
		:raise ValueError: if the namespace does already exist
		:raise RuntimeError: if the reference could not be created"""
		filepath = Path( cls._splitCopyNumber( filepath )[0] )

		def nsfunc( base, i ):
			if not i: return base
			return "%s%i" % ( base,i )

		ns = namespace
		if not ns:										# assure unique namespace
			nsbasename = filepath.stripext().basename()
			ns = Namespace.findUnique( nsbasename, incrementFunc = nsfunc )
		else:
			ns = Namespace( ns )		# assure we have a namespace object

		ns = ns.relativeTo( Namespace( Namespace.rootpath ) )
		if ns.exists():
			raise ValueError( "Namespace %s for %s does already exist" % (ns,filepath) )

		# assure we keep the current namespace
		prevns = Namespace.current()
		
		# removing duplicate **kwargs
		kwargs.pop('ns', None)
		kwargs.pop('reference', kwargs.pop('r', None))
		kwargs.pop('deferReference', kwargs.pop('dr', None))
		try:
			createdRefpath = cmds.file( filepath, ns=str(ns),r=1,dr=not load, **kwargs )
		finally:
			prevns.setCurrent( )
		# END assure we keep the namespace

		return FileReference( createdRefpath )
		
	@undo.notundoable
	def remove( self, **kwargs ):
		""" Remove the given reference from the scene
		
		:note: assures that no namespaces of that reference are left, remaining objects
			will be moved into the root namespace. This way the namespaces will not be left as waste.
			This fails if there are referenced objects in the subnamespace - we currently 
			ignore that issue as the main reference removal worked at that point.
		:note: kwargs passed to namespace.delete """
		ns = self.namespace( )
		cmds.file( self.path( copynumber=1 ), rr=1 )
		try:
			ns.delete( **kwargs )
		except RuntimeError:
			pass

	@undo.notundoable
	def replace( self, filepath ):
		"""Replace this reference with filepath
		
		:param filepath: the path to the file to replace this reference with
			Reference instances will be handled as well.
		:return: self"""
		filepath = (isinstance(filepath, type(self)) and filepath.path()) or filepath
		filepath = self._splitCopyNumber( filepath )[0]
		cmds.file( filepath, lr=self._refnode )
		return self

	@undo.notundoable
	def importRef( self, depth=0 ):
		"""Import the reference until the given depth is reached
		
		:param depth:
			 - x<1: import all references and subreferences
			 - x: import until level x is reached, 0 imports just self such that
			 	all its children are on the same level as self was before import
		:return: list of FileReference objects that are now in the root namespace - this
			  list could be empty if all subreferences are fully imported"""
		def importRecursive( reference, curdepth, maxdepth ):
			# load ref
			reference.setLoaded( True )
			children = reference.children()
			cmds.file( reference.path(copynumber=1), importReference=1 )

			if curdepth == maxdepth:
				return children

			outsubrefs = []
			for childref in children:
				outsubrefs.extend( importRecursive( childref, curdepth+1, maxdepth ) )

			return outsubrefs
		# END importRecursive

		return importRecursive( self, 0, depth )

	# } END reference adjustments

	#{ Listing

	@classmethod
	def fromPaths( cls, paths, **kwargs ):
		"""Find the reference for each path in paths. If you provide the path X
		2 times, but you only have one reference to X, the return value will be 
		[ FileReference(X), None ] as there are less references than provided paths.
		
		:param paths: a list of paths or references whose references in the scene 
			should be returned. In case a reference is found, its plain path will be 
			used instead.
		:param kwargs: all supported by `ls` to yield the base set of references
			we will use to match the paths with. Additionally, you may specify:
			
			 * ignore_extension: 
			 	if True, default False, the extension will be ignored
				during the search, only the actual base name will matter.
				This way, an MA file will be matched with an MB file. 
				The references returned will still have their extension original extension.
			
		:return: list( FileReference|None, ... )
			if a filereference was found for given occurrence of Path, it will be returned
			at index of the current path in the input paths, otherwise it is None.
		:note: zip( paths, result ) to get a corresponding tuple list associating each input path
			with the located reference"""
		if not isinstance( paths, (list,tuple) ) or hasattr( paths, 'next' ):
			raise TypeError( "paths must be tuple, was %s" % type( paths ) )

		ignore_ext = kwargs.pop( "ignore_extension", False )
		refs = cls.ls( **kwargs )

		# build dict for fast lookup
		# It will keep each reference
		lut = dict()
		pathscp = [ (isinstance(p, cls) and p.path()) or Path(p) for p in paths ]
		
		conv = lambda f: f
		if ignore_ext:
			conv = lambda f: f.expandvars().splitext()[0]
		# END ignore extension converter
		
		def countTuple( filepath, lut ):
			count = lut.get( filepath, 0 )
			lut[ filepath ] = count + 1
			return ( filepath , count )
		# END utility
		
		clut = dict()
		for ref in refs:
			lut[ countTuple(conv(ref.path()), clut) ] = ref			# keys have no ext
		# END for each ref to put into lut
		
		clut.clear()
		for i,path in enumerate( pathscp ):
			pathscp[i] = countTuple(conv(path), clut)
		# END for each path to prepare
		
		outlist = list()
		for path in pathscp:
			ref_or_none = lut.get( path, None )
			outlist.append( ref_or_none )
			# no need to delete the keys as they have to be unique anyway
		# END for each path to find
		return outlist

	@classmethod
	def ls( cls, rootReference = "", predicate = lambda x: True):
		"""list all references in the scene or under the given root
		
		:param rootReference: if not empty, the references below it will be returned.
			Otherwise all scene references will be listed.
			May be string, Path or FileReference
		:param predicate: method returning true for each valid file reference object that 
			should be part of the return value.
		:return: list of `FileReference` s objects"""
		if isinstance(rootReference, cls):
			rootReference = rootReference.path(copynumber=1)
		# END handle non-string type
		out = list()
		for reffile in cmds.file( str( rootReference ), q=1, r=1 ):
			refinst = FileReference( filepath = reffile )
			if predicate( refinst ):
				out.append( refinst )
		# END for each reference file
		return out

	@classmethod
	def lsDeep( cls, predicate = lambda x: True, **kwargs ):
		"""Return all references recursively
		
		:param kwargs: support for arguments as in `ls`, hence you can use the 
			rootReference flag to restrict the set of returned FileReferences."""
		kwargs['predicate'] = predicate
		refs = cls.ls( **kwargs )
		out = refs
		for ref in refs:
			out.extend(ref.childrenDeep(order=cls.kOrder_BreadthFirst, predicate=predicate))
		return out

	#} listing
	
	#{ Nodes Query
	def iterNodes( self, *args, **kwargs):
		"""Creates iterator over nodes in this reference
		
		:param args: MFn.kType filter ids to be used to pre-filter all nodes.
			If you know what you are looking for, setting this can greatly improve 
			performance !
		:param kwargs: additional kwargs will be passed to either `iterDagNodes`
			or `iterDgNodes` ( dag = False ). The following additional kwargs may
			be specified:
			
			 * asNode: 
			 	if True, default True, return wrapped Nodes, if False MDagPaths
			 	or MObjects will be returned
			 	
			 * dag: 
			 	if True, default False, return dag nodes only. Otherwise return dependency nodes 
			 	as well. Enables assemblies and assembilesInReference.
			 	
			 * assemblies: 
			 	if True, return only dagNodes with no parent. Needs dag and 
			 	is mutually exclusive with assembilesInReference.
			 	
			 * assembliesInReference: 
			 	if True, return only dag nodes that have no
				parent in their own reference. They may have a parent not coming from their
				reference though. This flag has a big negative performance impact and requires dag.
				
			 * predicate: 
			 	if function returns True for Node|MObject|MDagPath n, n will be yielded.
			 	Defaults to return True for all.
		:raise ValueError: if incompatible arguments have been given"""
		import nt
		
		rns = self.namespace()
		rnsrela = rns.toRelative()+':'
		asNode = kwargs.get('asNode', True)
		predicate = kwargs.get('predicate', lambda n: True)
		kwargs['asNode'] = False	# we will do it
		
		dag = kwargs.pop('dag', False)
		assemblies = kwargs.pop('assemblies', False)
		assembliesInReference = kwargs.pop('assembliesInReference', False)
		
		
		if ( assemblies or assembliesInReference ) and not dag:
			raise ValueError("Cannot list assemblies of any kind if dag is not specified")
		
		if assemblies and assembliesInReference:
			raise ValueError("assemblies and assembilesInReference are mutually exclusive")
		
		# CONSTRUCT PREDICATE
		iter_type = None
		pred = None
		if dag:
			# cache functions for 10% more performance
			mfndag = api.MFnDagNode()
			mfndagSetObject = mfndag.setObject
			mfndagParentNamespace = mfndag.parentNamespace
			MDagPath = api.MDagPath
			mdppop = MDagPath.pop
			mdplen = MDagPath.length
			
			def check_dag_ns(n):
				mfndagSetObject(n)
				if not _isRootOf(rnsrela, mfndagParentNamespace()):
					return False
				# END first namespace check
				
				# assemblies have no parents
				if assemblies: 
					nc = MDagPath(n)
					mdppop(nc, 1)
					if mdplen(nc) != 0:
						return False
					# END check length
				elif assembliesInReference:
					nc = MDagPath(n)
					mdppop(nc, 1)
					if mdplen(nc) != 0:
						# check whether parent is in a different namespace
						mfndagSetObject(n)
						if _isRootOf(rnsrela, mfndagParentNamespace()):
							return False
						# END check parent rns
					# END check length
				# END handle assemblies
				return True
			# END filter
			
			pred = check_dag_ns
			iter_type = nt.it.iterDagNodes
		else:
			mfndep = api.MFnDependencyNode()
			mfndepSetObject = mfndep.setObject
			mfndepParentNamespace = mfndep.parentNamespace
			
			def check_ns(n):
				mfndepSetObject(n)
				if not _isRootOf(rnsrela, mfndepParentNamespace()):
					return False
				# END first namespace check
				return True
			# END filter
			
			pred = check_ns
			iter_type = nt.it.iterDgNodes
		# END handle dag/dg mode predicate
		
		kwargs['predicate'] = pred
		
		# have to iterate it manually in order to get the toNode conversion right
		NodeFromObj = nt.NodeFromObj
		for n in iter_type(*args, **kwargs):
			if asNode:
				n = NodeFromObj(n)
			if predicate(n):
				yield n
		# END for each node in iteartion
	#} nodes query

	#{ Edit
	@undo.notundoable
	def cleanup( self, unresolvedEdits = True, editTypes = editTypes ):
		"""remove unresolved edits or all edits on this reference
		
		:param unresolvedEdits: if True, only dangling connections will be removed,
			if False, all reference edits will be removed - the reference will be unloaded for beforehand.
			The loading state of the reference will stay unchanged after the operation.
		:param editTypes: list of edit types to remove during cleanup
		:return: self"""
		wasloaded = self.isLoaded()
		if not unresolvedEdits:
			self.setLoaded(False)

		for etype in editTypes:
			cmds.file( cr=self._refnode, editCommand=etype )

		if not unresolvedEdits:
			self.setLoaded(wasloaded)
			
		return self

	@undo.notundoable
	def setLocked( self, state ):
		"""Set the reference to be locked or unlocked
		
		:param state: if True, the reference is locked , if False its unlocked and
			can be altered
		:return: self"""
		if self.isLocked( ) == state:
			return

		# unload ref
		wasloaded = self.isLoaded()
		self.setLoaded(False)

		# set locked
		cmds.setAttr( self._refnode+".locked", state )

		# reset the loading state
		self.setLoaded(wasloaded)
		
		return self

	@undo.notundoable
	def setLoaded( self, state ):
		"""set the reference loaded or unloaded
		
		:param state: True = unload reference, True = load reference 
		:return: self"""

		if state == self.isLoaded( ):			# already desired state
			return

		if state:
			cmds.file( loadReference=self._refnode )
		else:
			cmds.file( unloadReference=self._refnode )

		return self

	@undo.notundoable
	def setNamespace( self, namespace ):
		"""set the reference to use the given namespace
		
		:param namespace: Namespace instance or name of the short namespace
		:raise RuntimeError: if namespace already exists or if reference is not root
		:return: self"""
		shortname = namespace
		if isinstance( namespace, Namespace ):
			shortname = namespace.basename( )

		# set the namespace
		cmds.file( self.path(copynumber=1), e=1, ns=shortname )
		
		return self

	#}END edit

	def parent( self ):
		""":return: the parent reference of this instance or None if we are root"""
		parentrfn = cmds.referenceQuery( self._refnode, rfn=1, p=1 )
		if not parentrfn:
			return None
		return FileReference( refnode = parentrfn )

	def children( self , predicate = lambda x: True ):
		""" :return: all intermediate child references of this instance """
		return self.ls( rootReference = self, predicate = predicate )

	#{ Query
	def exists( self ):
		""":return: True if our file reference exists in maya"""
		try:
			self.path(copynumber=1)
		except RuntimeError:
			return False
		else:
			return True

	def isLocked( self ):
		""":return: True if reference is locked"""
		return cmds.getAttr( self._refnode + ".locked" )

	def isLoaded( self ):
		""":return: True if the reference is loaded"""
		return cmds.file( rfn=self._refnode, q=1, dr=1 ) == False

	def copynumber( self ):
		""":return: the references copy number - starting at 0 for the first reference
		:note: we do not cache the copy number as mayas internal numbering can change on
			when references change - the only stable thing is the reference node name"""
		return self._splitCopyNumber( self.path(copynumber=1) )[1]

	def namespace( self ):
		""":return: namespace object of the full namespace holding all objects in this reference"""
		fullpath = self.path(copynumber=1)
		refspace = cmds.file( fullpath, q=1, ns=1 )
		parentspace = cmds.file( fullpath, q=1, pns=1 )[0]		# returns lists, although its always just one string
		if parentspace:
			parentspace += ":"
		# END handle parent namespace
		return Namespace( ":" + parentspace + refspace )

	def path( self, copynumber=False, unresolved = False ):
		""":return: Path object with the path containing the reference's data
		:param copynumber: If True, the returned path will include the copy number.
			As it will be a path object, it might not be fully usable in that state
		:param unresolved: see `ls`
		:note: we always query it from maya as our numbers change if some other
			reference is being removed and cannot be trusted"""
		path_str = cmds.referenceQuery( self._refnode, f=1, un=unresolved )
		if not copynumber:
			path_str = self._splitCopyNumber( path_str )[0]
		# END handle copy number
		return Path(path_str)

	def referenceNode( self ):
		""":return: wrapped reference node managing this reference"""
		import mrv.maya.nt as nt
		return nt.NodeFromStr( self._refnode )

	#}END query methods


