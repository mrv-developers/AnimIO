# -*- coding: utf-8 -*-
"""
Contains different multi-purpose iterators allowing to conveniently walk the dg and
dag.
"""
__docformat__ = "restructuredtext"

import maya.OpenMaya as api
import maya.cmds as cmds
from maya.OpenMaya import MDagPath, MObject
from base import Node, DagNode, NodeFromObj, Component

__all__ = ("dgIterator", "dagIterator", "graphIterator", "selectionListIterator", 
           "iterDgNodes", "iterDagNodes", "iterGraph", "iterSelectionList")

def _argsToFilter( args ):
	"""convert the MFnTypes in args list to the respective typeFilter"""
	typeFilter = api.MIteratorType( )
	if args:
		if len(args) == 1 :
			typeFilter.setFilterType ( args[0] )
		else :
			# annoying argument conversion for Maya API non standard C types
			scriptUtil = api.MScriptUtil()
			typeIntM = api.MIntArray()
			scriptUtil.createIntArrayFromList( args,  typeIntM )
			typeFilter.setFilterList( typeIntM )
		# we will iterate on dependancy nodes, not dagPaths or plugs
		typeFilter.setObjectType( api.MIteratorType.kMObject )
	# create iterator with (possibly empty) typeFilter
	return typeFilter


#{ Iterator Creators

def dgIterator( *args, **kwargs ):
	"""
	:return: MItDependencyNodes configured according to args - see docs at
		`iterDgNodes`.
	:note: use this method if you want to use more advanced features of the iterator"""
	typeFilter = _argsToFilter( args )
	iterObj = api.MItDependencyNodes( typeFilter )
	return iterObj

def dagIterator( *args, **kwargs ):
	"""
	:return: MItDagIterator configured according to args - see docs at
		`iterDagNodes`.
	:note: use this method if you want to use more advanced features of the iterator"""
	depth = kwargs.get('depth', True)
	underworld = kwargs.get('underworld', False)
	root = kwargs.get('root', None )
	typeFilter = _argsToFilter( args )

	# SETUP TYPE FILTER - reset needs to work with root
	if root is not None:
		if isinstance( root, (MDagPath, DagNode) ):
			typeFilter.setObjectType( api.MIteratorType.kMDagPathObject )
		else :
			typeFilter.setObjectType( api.MIteratorType.kMObject )

	# create iterator with (possibly empty) filter list and flags
	if depth :
		traversal = api.MItDag.kDepthFirst
	else :
		traversal =	 api.MItDag.kBreadthFirst

	iterObj = api.MItDag( typeFilter, traversal )

	# set start object
	if root is not None :
		startObj = startPath = None
		if isinstance( root, MDagPath):
			startPath = root
		elif isinstance( root, DagNode ):
			startPath = root.dagPath()
		elif isinstance( root, Node ):
			startObj = root.object()
		else:
			startObj = root
		# END handle obj type
		iterObj.reset( typeFilter, startObj, startPath, traversal )
	# END if root is set

	if underworld :
		iterObj.traverseUnderWorld( True )
	else :
		iterObj.traverseUnderWorld( False )


	return iterObj
	

def graphIterator( nodeOrPlug, *args, **kwargs ):
	"""
	:return: MItDependencyGraph configured according to args - see docs at
		`iterGraph`.
	:note: use this method if you want to use more advanced features of the iterator
	:raise RuntimeError: if the filter types does not allow any nodes to be returned.
		This is a bug in that sense as it should just return nothing. It also shows that
		maya pre-parses the result and then just iterates over a list with the iterator in
		question"""
	startObj = startPlug = None

	if isinstance( nodeOrPlug, api.MPlug ):
		startPlug = nodeOrPlug
		startObj = MObject()
	elif isinstance( nodeOrPlug, Node ):
		startObj = nodeOrPlug.object()
		startPlug = nullplugarray[0]
	else:
		startObj = nodeOrPlug
		startPlug = nullplugarray[0]
	# END traversal root

	inputPlugs = kwargs.get('input', False)
	breadth = kwargs.get('breadth', False)
	plug = kwargs.get('plug', False)
	prune = kwargs.get('prune', False)
	typeFilter = _argsToFilter( args )

	if startPlug is not None :
		typeFilter.setObjectType( api.MIteratorType.kMPlugObject )
	else :
		typeFilter.setObjectType( api.MIteratorType.kMObject )
	# END handle object type

	direction = api.MItDependencyGraph.kDownstream
	if inputPlugs :
		direction = api.MItDependencyGraph.kUpstream

	traversal =	 api.MItDependencyGraph.kDepthFirst
	if breadth :
		traversal = api.MItDependencyGraph.kBreadthFirst

	level = api.MItDependencyGraph.kNodeLevel
	if plug :
		level = api.MItDependencyGraph.kPlugLevel

	iterObj = api.MItDependencyGraph( startObj, startPlug, typeFilter, direction, traversal, level )

	iterObj.disablePruningOnFilter()
	if prune :
		iterObj.enablePruningOnFilter()

	return iterObj
	

def selectionListIterator( sellist, **kwargs ):
	"""
	:return: iterator suitable to iterate given selection list - for more info see
		`iterSelectionList`"""
	filtertype = kwargs.get( "filterType", api.MFn.kInvalid )
	iterator = api.MItSelectionList( sellist, filtertype )
	return iterator
	
#} END iterator creators 


def iterDgNodes( *args, **kwargs ):
	""" Iterator on MObjects or Nodes of the specified api.MFn types
	
	:param args: type as found in MFn.k... to optionally restrict the set of nodes the iterator operates upon.
		All nodes of a type included in the args will be iterated on.
		args is empty, all nodes of the scene will be iterated on which may include DAG nodes as well.
	:param kwargs:
		 * asNode: 
		 	if True, default True, the returned value will be wrapped as node
		 * predicate: 
		 	returns True for every iteration element that may be returned by the iteration,
			default : lambda x: True"""
	iterator = dgIterator( *args, **kwargs )
	predicate = kwargs.get( "predicate", lambda x: True )
	asNode = kwargs.get( "asNode", True )
	
	isDone = iterator.isDone
	thisNode = iterator.thisNode
	next = iterator.next
	
	while not isDone() :
		node = thisNode()
		if asNode:
			node = NodeFromObj( node )
		if predicate( node ):
			yield node
		next()
	# END for each obj in iteration

# Iterators on dag nodes hierarchies using MItDag (ie listRelatives)
def iterDagNodes( *args, **kwargs ):
	""" Iterate over the hierarchy under a root dag node, if root is None, will iterate on whole Maya scene
	If a list of types is provided, then only nodes of these types will be returned,
	if no type is provided all dag nodes under the root will be iterated on.
	Types are specified as Maya API types being a member of api.MFn
	The following keywords will affect order and behavior of traversal:

	:param kwargs:
		 * dagpath:
		 	if True, default True, MDagPaths will be returned
			If False, MObjects will be returned - it will return each object only once in case they
			occour in multiple paths.
		 * depth: 
		 	if True, default True, Nodes will be returned as a depth first traversal of the hierarchy tree
			if False as a post-order (breadth first)
		 * underworld: 
		 	if True, default False, traversal will include a shape's underworld 
			(dag object parented to the shape), if False the underworld will not be traversed,
		 * asNode: 
		 	if True, default True, the returned item will be wrapped into a Node
		 * root: 
			MObject or MDagPath or Node of the object you would like to start iteration on, or None to
			start on the scene root. The root node will also be returned by the iteration !
			Please note that if an MObject is given, it needs to be an instanced DAG node to have an effect.
		 * predicate: 
		 	method returning True if passed in iteration element can be yielded
			default: lambda x: True"""

	# Must define dPath in loop or the iterator will yield
	# them as several references to the same object (thus with the same value each time)
	# instances must not be returned multiple times
	# could use a dict but it requires "obj1 is obj2" and not only "obj1 == obj2" to return true to
	iterator = dagIterator( *args, **kwargs )
	isDone = iterator.isDone
	next = iterator.next
	
	dagpath = kwargs.get('dagpath', True)
	asNode = kwargs.get('asNode', True )
	predicate = kwargs.get('predicate', lambda x: True )
	
	if dagpath:
		getPath = iterator.getPath
		while not isDone( ) :
			rval = MDagPath( )
			getPath( rval )
			if asNode:
				rval = NodeFromObj( rval )
			if predicate( rval ):
				yield rval
			
			next()
		# END while not is done
	# END if using dag paths
	else:
		# NOTE: sets don't work here, as more than == comparison is required
		instanceset = list()
		currentItem = iterator.currentItem
		isInstanced = iterator.isInstanced
		
		while not isDone() :
			rval = currentItem()
			if isInstanced( True ):
				if rval not in instanceset:
					instanceset.append( rval )
				else:
					next()
					continue
				# END if object not yet returned
			# END handle instances
			
			if asNode:
				rval = NodeFromObj(rval)
			if predicate( rval ):
				yield rval
			
			next()
		# END while not is done
	# END if using mobjects

def iterGraph( nodeOrPlug, *args, **kwargs ):
	""" Iterate Dependency Graph (DG) Nodes or Plugs starting at a specified root Node or Plug.
	The iteration _includes_ the root node or plug.
	The following keywords will affect order and behavior of traversal:
	
	:param nodeOrPlug: Node, MObject or MPlug to start the iteration at
	:param args: list of MFn node types
		If a list of types is provided, only nodes of these types will be returned,
		if no type is provided all connected nodes will be iterated on.
	:param kwargs:
		 * input: 
		 	if True connections will be followed from destination to source,
			if False from source to destination
			default is False (downstream)
		 * breadth: 
		 	if True nodes will be returned as a breadth first traversal of the connection graph,
			if False as a preorder (depth first)
			default is False (depth first)
		 * plug: 
		 	if True traversal will be at plug level (no plug will be traversed more than once),
			if False at node level (no node will be traversed more than once),
			default is False (node level)
		 * prune: 
		 	if True, the iteration will stop on nodes that do not fit the types list,
			if False these nodes will be traversed but not returned
			default is False (do not prune)
		 * asNode: 
		 	if True, default True, and if the iteration is on node level, 
			Nodes ( wrapped MObjects ) will be returned
			If False, MObjects will be returned
		 * predicate: 
		 	method returning True if passed in iteration element can be yielded
			default: lambda x: True
	:return: Iterator yielding MObject, Node or Plug depending on the configuration flags, first yielded item is 
		always the root node or plug."""
	try:
		iterator = graphIterator( nodeOrPlug, *args, **kwargs )
	except RuntimeError:
		# may raise if iteration would yield no results
		raise StopIteration()

	retrievePlugs = not iterator.atNodeLevel( )
	asNode = kwargs.get( "asNode", True )
	predicate = kwargs.get( 'predicate', lambda x: True )

	isDone = iterator.isDone
	next = iterator.next
	thisPlug = iterator.thisPlug
	currentItem = iterator.currentItem

	# iterates and yields MObjects
	rval = None
	# if node filters are used, it easily threw NULL Object returned errors
	# just because the iteration is depleted - catching this now
	try:
		while not isDone():
			if retrievePlugs:
				rval = thisPlug()
			else:
				rval = currentItem()
				if asNode:
					rval = NodeFromObj( rval )
				# END handle asNode
			# END if return on node level
			
			if predicate( rval ):
				yield rval
	
			next()
		# END of iteration
	except RuntimeError:
		raise StopIteration()
	# END handle possible iteration error


nullplugarray = api.MPlugArray()
nullplugarray.setLength( 1 )
def iterSelectionList( sellist, filterType = api.MFn.kInvalid, predicate = lambda x: True,
					  	asNode = True, handlePlugs = True, handleComponents = False ):
	"""Iterate the given selection list
	
	:param sellist: MSelectionList to iterate
	:param filterType: MFnType id acting as simple type filter to ignore all objects which do not
		have the given object type
	:param asNode: if True, returned MObjects or DagPaths will be wrapped as Node, compoents will be
		wrapped as Component. 
		Otherwise they will be returned as MObjects and MDagPaths respectively.
	:param handlePlugs: if True, plugs can be part of the selection list and will be returned. This
		implicitly means that the selection list will be iterated without an iterator, and MFnType filters
		will be slower as it is implemented in python. If components are enabled, the tuple returned will be
		( Plug, MObject() )
	:param predicate: method returninng True if passed in iteration element can be yielded
		default: lambda x: True
	:param handleComponents: if True, possibly selected components of dagNodes will be returned
		as well. This forces the return value into tuple(Node, Component)
	:return: Node or Plug on each iteration step
		If handleComponents is True, for each Object, a tuple will be returned as tuple( Node, Component ) where
		component is NullObject ( MObject ) if the whole object is on the list.
		If the original object was a plug, it will be in the tuples first slot, whereas the component 
		will be a NullObject"""
	kNullObj = MObject()
	if handlePlugs:
		# version compatibility - maya 8.5 still defines a plug ptr class that maya 2005 lacks
		plug_types = api.MPlug
		if cmds.about( v=1 ).startswith( "8.5" ):
			plug_types = ( api.MPlug, api.MPlugPtr )

		# SELECTION LIST MODE
		kInvalid = api.MFn.kInvalid
		getDagPath = sellist.getDagPath
		getPlug = sellist.getPlug
		getDependNode = sellist.getDependNode
		for i in xrange( sellist.length() ):
			# DAG PATH
			rval = None
			component = kNullObj
			try:
				rval = MDagPath( )
				if handleComponents:
					component = MObject()
					getDagPath( i, rval, component )
					if asNode and not component.isNull():
						component = Component( component )
					# END handle asNode
				else:
					getDagPath( i, rval )
				# END handle components in DagPaths
			except RuntimeError:
				# TRY PLUG - first as the object could be returned as well if called
				# for DependNode
				try:
					rval = nullplugarray[0]
					getPlug( i, rval )
					# try to access the attribute - if it is not really a plug, it will
					# fail and throw - for some reason maya can put just the depend node into
					# a plug
					rval.attribute()
				except RuntimeError:
				# TRY DG NODE
					rval = MObject( )
					getDependNode( i, rval )
				# END its not an MObject
			# END handle dagnodes/plugs/dg nodes

			# should have rval now
			if isinstance( rval, plug_types ):
				# apply filter
				if filterType != kInvalid and rval.node().apiType() != filterType:
					continue
					# END apply filter type
			else:
				if filterType != kInvalid:
					# must be MDagPath or MObject
					if rval.apiType() != filterType:
						continue
				# END filter handling
				
				if asNode:
					rval = NodeFromObj( rval )
			# END plug handling
			
			if handleComponents:
				rval = ( rval, component )
			
			if predicate( rval ):
				yield rval
		# END for each element
	else:
		# ITERATOR MODE
		# the code above can handle it all, this one might be faster though 
		iterator = selectionListIterator( sellist, filterType = filterType )
		kDagSelectionItem = api.MItSelectionList.kDagSelectionItem
		kDNselectionItem = api.MItSelectionList.kDNselectionItem
		rval = None
		
		isDone = iterator.isDone
		itemType = iterator.itemType
		getDagPath = iterator.getDagPath
		getDependNode = iterator.getDependNode
		next = iterator.next
		while not isDone():
			# try dag object
			component = kNullObj
			itemtype = itemType( )
			if itemtype == kDagSelectionItem:
				rval = MDagPath( )
				if handleComponents:
					component = MObject( )
					getDagPath( rval, component )
					if asNode and not component.isNull():
						component = Component( component )
					# END handle component conversion
				else:
					getDagPath( rval )
				# END handle components
			else:
				rval = MObject()
				getDependNode( rval )
			# END handle item type
			
			if asNode:
				rval = NodeFromObj( rval )
			# END handle as node
			
			if handleComponents:
				rval = ( rval, component )
			# END handle component
				
			if predicate( rval ):
				yield rval
			
			next()
		# END while not done

