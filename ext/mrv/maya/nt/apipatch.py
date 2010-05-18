# -*- coding: utf-8 -*-
"""
Contains patch classes that are altering their respective api classes

The classes here are rather verbose and used as patch-template which can be
handled correctly by epydoc, and whose method will be used to patch the respective
api classes.

As they are usually derived from the class they patch , they could also be used directly

:note: **never import classes directly in here**, import the module instead, thus
	**not**: thisImportedClass **but**: module.thisImportedClass !
"""
__docformat__ = "restructuredtext"

import base
import mrv.maya.undo as undo
import mrv.util as util
from mrv.interface import iDagItem

import maya.OpenMaya as api
import maya.cmds as cmds

import inspect
import itertools
import it
import os

# Doesnt need all as it is just a utility package containing patches that are applies
# to API classes
# __all__ 

def init_applyPatches( ):
	"""Called by package __init__ method to finally apply the patch according to
	the template classes
	Template classes must derive from the to-be-patched api class first, and can derive
	from helper classes providing basic patch methods.
	Helper classes must derive from Abstract to indicate their purpose

	If a class has an _applyPatch method, it will be called and not additional. If
	it returns True, the class members will be applied as usual, if False the method will stop

	:note: overwritten api methods will be renamed to _api_methodname
	:note: currently this method works not recursively"""
	module = __import__( "mrv.maya.nt.apipatch", globals(), locals(), ['apipatch'] )
	classes = [ v for v in globals().values() if inspect.isclass(v) ]
	forbiddenMembers = [ '__module__','_applyPatch','__dict__','__weakref__','__doc__' ]
	apply_globally = int(os.environ.get('MRV_APIPATCH_APPLY_GLOBALLY', 0))
	
	ns = None
	if apply_globally:
		ns = 'm'
	# END configure namespace mode
	
	
	for cls in classes:
		# use the main class as well as all following base
		# the first base is always the main maya type that is patched - we skip it
		templateclasses = [ cls ]
		templateclasses.extend( cls.__bases__[ 1: ] )

		# assure that the actual class rules over methods from lower base classes
		# by applying them last
		templateclasses.reverse()

		# skip abstract classes ?
		if cls is Abstract or cls.__bases__[0] is Abstract:
			continue

		apicls = cls.__bases__[0]

		# SPECIAL CALL INTERFACE ?
		# If so, call and let the class do the rest
		if hasattr( cls, "_applyPatch" ):
			if not cls._applyPatch(  ):
				continue

		for tplcls in templateclasses:
			util.copyClsMembers( tplcls, apicls, overwritePrefix="_api_",
										forbiddenMembers = forbiddenMembers, 
										copyNamespaceGlobally=ns)
		# END for each template class
	# END for each cls of this module
	pass


class Abstract:
	"""Class flagging that subclasses should be abstract and are only to be used
	as superclass """
	pass


#{ Primitive Types
class TimeDistanceAngleBase( Abstract ):
	"""Base patch class for all indicated classes
	
	:note: idea for patches from pymel"""
	def __str__( self ): return str(float(self))
	def __int__( self ): return int(float(self))
	
	# in Maya 2010, these classes have an as_units method allowing 
	# it to be used in python without the use of getattr
	if hasattr(api.MTime, 'asUnits'):
		def __float__( self ): return self.asUnits(self.uiUnit())
	else:
		def __float__( self ): return getattr(self, 'as')(self.uiUnit())
	# END conditional implementation
	def __repr__(self): return '%s(%s)' % ( self.__class__.__name__, float(self) )


class MTime( api.MTime, TimeDistanceAngleBase ) :
	pass

class MDistance( api.MDistance, TimeDistanceAngleBase ) :
	pass

class MAngle( api.MAngle, TimeDistanceAngleBase ) :
	pass


# patch some Maya api classes that miss __iter__ to make them iterable / convertible to list
class PatchIterablePrimitives( Abstract ):
	""":note: Classes derived from this base should not be used directly"""
	@classmethod
	def _applyPatch( cls ):
		"""Read per-class values from self and create appropriate methods and
		set them as well
		
		:note: idea from pymel"""
		def __len__(self):
			""" Number of components in Maya api iterable """
			return self._length
		# END __len__
		type.__setattr__( cls.__bases__[0], '__len__', __len__ )

		def __iter__(self):
			""" Iterates on all components of a Maya base iterable """
			for i in range( self._length ) :
				yield self.__getitem__( i )
		# END __iter__
		type.__setattr__( cls.__bases__[0], '__iter__', __iter__)

		def __str__( self ):
			return "[ %s ]" % " ".join( str( f ) for f in self )
		# END __str__

		type.__setattr__( cls.__bases__[0], '__str__', __str__)
		
		def __repr__( self ):
			return "%s([ %s ])" % (type(self).__name__, " ".join( str( f ) for f in self ))
		# END __str__

		type.__setattr__( cls.__bases__[0], '__repr__', __repr__)

		# allow the class members to be used ( required as we are using them )
		return True

class PatchMatrix( Abstract, PatchIterablePrimitives ):
	"""Only for matrices"""
	@classmethod
	def _applyPatch( cls ):
		"""Special version for matrices"""
		PatchIterablePrimitives._applyPatch.im_func( cls )
		def __iter__(self):
			""" Iterates on all 4 rows of a Maya api MMatrix """
			for r in range( self._length ) :
				row = self.__getitem__( r )
				yield [ self.scriptutil( row, c ) for c in range( self._length ) ]
		# END __iter__
		type.__setattr__( cls.__bases__[0], '__iter__', __iter__ )


		def __str__( self ):
			return "\n".join( str( v ) for v in self )
		# END __str__

		type.__setattr__( cls.__bases__[0], '__str__', __str__)

		return True



class MVector( api.MVector, PatchIterablePrimitives ):
	_length =3

class MFloatVector( api.MFloatVector, PatchIterablePrimitives ):
	_length =3

class MPoint( api.MPoint, PatchIterablePrimitives ):
	_length =4

class MFloatPoint( api.MFloatPoint, PatchIterablePrimitives ):
	_length =4

class MColor( api.MColor, PatchIterablePrimitives ):
	_length =4

class MQuaternion( api.MQuaternion, PatchIterablePrimitives ):
	_length =4

class MEulerRotation( api.MEulerRotation, PatchIterablePrimitives ):
	_length =4

class MMatrix( api.MMatrix, PatchMatrix ):
	_length =4
	scriptutil = api.MScriptUtil.getDoubleArrayItem

class MFloatMatrix( api.MFloatMatrix, PatchMatrix ):
	_length =4
	scriptutil = api.MScriptUtil.getFloatArrayItem

class MTransformationMatrix( api.MTransformationMatrix, PatchMatrix ):
	_length =4

	@classmethod
	def _applyPatch( cls ):
		"""Special version for matrices"""
		PatchMatrix._applyPatch.im_func( cls )
		def __iter__(self):
			""" Iterates on all 4 rows of a Maya api MMatrix """
			return self.asMatrix().__iter__()
		# END __iter__
		type.__setattr__( cls.__bases__[0], '__iter__', __iter__ )
		return True

	def mgetScale( self , space = api.MSpace.kTransform ):
		ms = api.MScriptUtil()
		ms.createFromDouble( 1.0, 1.0, 1.0 )
		p = ms.asDoublePtr()
		self.getScale( p, space );
		return MVector( *( ms.getDoubleArrayItem (p, i) for i in range(3) ) )

	def msetScale( self, value, space = api.MSpace.kTransform ):
		ms = api.MScriptUtil()
		ms.createFromDouble( *value )
		p = ms.asDoublePtr()
		self.setScale ( p, space )

	def getTranslation( self, space = api.MSpace.kTransform ):
		"""This patch is fully compatible to the default method"""
		return self._api_getTranslation( space )

	def setTranslation( self, vector, space = api.MSpace.kTransform ):
		"""This patch is fully compatible to the default method"""
		return self._api_setTranslation( vector, space )

#} END primitve types

#{ Basic Types

def _mplug_createUndoSetFunc( dataTypeId, getattroverride = None ):
	"""Create a function setting a value with undo support
	
	:param dataTypeId: string naming the datatype, like "Bool" - capitalization is
		important
	:note: if undo is globally disabled, we will resolve to implementing a faster
		function instead as we do not store the previous value.
	:note: to use the orinal method without undo, use api.MPlug.setX(your_plug, value)"""
	# this binds the original setattr and getattr, not the patched one
	getattrfunc = getattroverride
	if not getattrfunc:
		getattrfunc = getattr( api.MPlug, "as"+dataTypeId )
	setattrfunc = getattr( api.MPlug, "set"+dataTypeId )

	# YES, WE DUPLICATE CODE FOR SPEED
	####################################
	# Create actual functions
	finalWrappedSetAttr = None
	if dataTypeId == "MObject":
		def wrappedSetAttr( self, data ):
			# asMObject can fail instead of returning a null object !
			try:
				curdata = getattrfunc( self )
			except RuntimeError:
				curdata = api.MObject()
			op = undo.GenericOperation( )

			op.setDoitCmd( setattrfunc, self, data )
			op.setUndoitCmd( setattrfunc, self, curdata )

			op.doIt()
		# END wrapped method
		finalWrappedSetAttr = wrappedSetAttr
	else:
		def wrappedSetAttr( self, data ):
			# asMObject can fail instead of returning a null object !
			curdata = getattrfunc( self )
			op = undo.GenericOperation( )

			op.setDoitCmd( setattrfunc, self, data )
			op.setUndoitCmd( setattrfunc, self, curdata )

			op.doIt()
		# END wrappedSetAttr method
		finalWrappedSetAttr = wrappedSetAttr
	# END MObject special case

	# did undoable do anything ? If not, its disabled and we return the original
	wrappedUndoableSetAttr = undoable( finalWrappedSetAttr )
	if wrappedUndoableSetAttr is finalWrappedSetAttr:
		return setattrfunc
	# END return original 

	return wrappedUndoableSetAttr


class MPlug( api.MPlug ):
	"""Patch applying mrv specific functionality to the MPlug. These methods will be
	available through methods with the 'm' prefix.
	
	Other methods are overridden to allow more pythonic usage of the MPlug class
	if and only if it is not specific to mrv.
	
	Additionally it provides aliases for all MPlug methods that are getters, but 
	don't start with a 'get'.
	
	:note: Theoretically the MPlug would satisfy the 'iDagItem' interface, but due 
		to the method prefixes, it could not work here as it calls un-prefixed methods only."""

	pa = api.MPlugArray( )		# the only way to get a null plug for use
	pa.setLength( 1 )

	#{ Overridden Methods

	def __len__( self ):
		"""
		:return: number of physical elements in the array, but only if they are 
			not connected. If in doubt, run evaluateNumElements beforehand"""
		if not self.isArray( ): return 0
		return self.numElements( )

	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield self.elementByPhysicalIndex(i)
	
	__str__ = api.MPlug.name

	def __repr__( self ):
		""":return: our class representation"""
		return "MPlug(%s)" % self.name()

	def __eq__( self, other ):
		"""Compare plugs,handle elements correctly"""
		if not api.MPlug._api___eq__( self, other ):
			return False

		# see whether elements are right - both must be elements if one is
		if self.isElement():
			return self.logicalIndex( ) == other.logicalIndex()

		return True

	def __ne__( self, other ):
		return not( self.__eq__( other ) )

	#} Overridden Methods

	#{ Plug Hierarchy Query
	def mparent( self ):
		""":return: parent of this plug or None
		:note: for array plugs, this is the array, for child plugs the actual parent """
		p = None
		if self.isChild():
			p = self.parent()
		elif self.isElement():
			p = self.array()

		if p.isNull( ):	# sanity check - not all
			return None
		return p

	def mchildren( self , predicate = lambda x: True):
		""":return: list of intermediate child plugs, [ plug1 , plug2 ]
		:param predicate: return True to include x in result"""
		outchildren = []
		if self.isCompound():
			nc = self.numChildren()
			for c in xrange( nc ):
				child = self.child( c )
				if predicate( child ):
					outchildren.append( child )
			# END FOR EACH CHILD
		# END if is compound

		return outchildren

	def mchildByName( self, childname ):
		""":return: MPlug with the given childname
		:raise AttributeError: if no child plug of the appropriate name could be found
		:raise TypeError: self is not a compound plug"""
		if not self.isCompound( ):
			raise TypeError( "Plug %s is not a compound plug" % self )
		# END if is compound
		
		nc = self.numChildren( )
		for c in xrange( nc ):
			child = self.child( c )
			if (	child.partialName( ).split('.')[-1] == childname or
					child.partialName( 0, 0, 0, 0, 0, 1 ).split('.')[-1] == childname ):
				return child
			# END if it is the child we look for
		# END FOR EACH CHILD
		raise AttributeError( "Plug %s has no child plug called %s" % ( self, childname ) )

	def msubPlugs( self , predicate = lambda x: True):
		"""
		:return: list of intermediate sub-plugs that are either child plugs or element plugs.
			Returned list will be empty for leaf-level plugs
		:param predicate: return True to include x in result
		:note: use this function recursively for easy deep traversal of all
			combinations of array and compound plugs"""
		if self.isCompound( ):
			outchildren = []
			nc = self.numChildren( )
			for c in xrange( nc ):
				child = self.child( c )
				if predicate( child ):
					outchildren.append( child )
			# END FOR EACH CHILD
			return outchildren
		elif self.isArray( ):
			return [ elm for elm in self ]

		# we have no sub plugs
		return []

	#} END hierarcy query

	#{ Attributes ( Edit )

	def _mhandleAttrSet( self, state, getfunc, setfunc ):
		"""Generic attribute handling"""
		op = undo.GenericOperation()
		op.setDoitCmd( setfunc, state )
		op.setUndoitCmd( setfunc, getfunc( ) )
		op.doIt()

	@undoable
	def msetLocked( self, state ):
		"""If True, the plug's value may not be changed anymore"""
		self._mhandleAttrSet( state, self.isLocked, self.setLocked )

	@undoable
	def msetKeyable( self, state ):
		"""if True, the plug may be set using animation curves"""
		self._mhandleAttrSet( state, self.isKeyable, self.setKeyable )

	@undoable
	def msetCaching( self, state ):
		"""if True, the plug's value will be cached, preventing unnecessary computations"""
		self._mhandleAttrSet( state, self.isCachingFlagSet, self.setCaching )

	@undoable
	def msetChannelBox( self, state ):
		"""if True, the plug will be visible in the channelbox, even though it might not
		be keyable or viceversa """
		self._mhandleAttrSet( state, self.isChannelBoxFlagSet, self.setChannelBox )

	#} END attributes edit


	#{ Connections ( Edit )

	@classmethod
	@undoable
	def mconnectMultiToMulti(self, iter_source_destination, force=False):
		"""Connect multiple source plugs to the same amount of detsination plugs.
		
		:note: This method provides the most efficient way to connect a large known 
			amount of plugs to each other
		:param iter_source_destination: Iterator yielding pairs of source and destination plugs to connect
		:param force: If True, existing input connections on the destination side will 
			be broken automatically. Otherwise the whole operation will fail if one 
			connection could not be made.
		:note: Both iterators need to yield the same total amount of plugs
		:note: In the current implementation, performance will be hurt if force 
			is specified as each destination has to be checked for a connection in advance"""
		mod = undo.DGModifier( )
		for source, dest in iter_source_destination:
			if force:
				destinputplug = dest.minput()
				if not destinputplug.isNull():
					if source == destinputplug:
						continue
					# END skip this plug if it is already connected
					mod.disconnect(destinputplug, dest)
				# END destination is connected
			# END handle force
			mod.connect(source, dest)
		# END for each source, dest pair
		mod.doIt()
		return mod
		

	@undoable
	def mconnectTo( self, destplug, force=True ):
		"""Connect this plug to the right hand side plug
		
		:param destplug: the plug to which to connect this plug to.
		:param force: if True, the connection will be created even if another connection
			has to be broken to achieve that.
			If False, the connection will fail if destplug is already connected to another plug
		:return: destplug allowing chained connections a.connectTo(b).connectTo(c)
		:raise RuntimeError: If destination is already connected and force = False"""
		mod = undo.DGModifier( )

		# is destination already input-connected ? - disconnect it if required
		# Optimization: We only care if force is specified. It will fail otherwise
		if force:
			destinputplug = destplug.minput()
			if not destinputplug.isNull():
				# handle possibly connected plugs
				if self == destinputplug:		# is it us already ?
					return destplug
	
				# disconnect
				mod.disconnect( destinputplug, destplug )
				# END disconnect existing
			# END destination is connected
		# END force mode
		mod.connect( self, destplug )	# finally do the connection
		
		try:
			mod.doIt( )
		except RuntimeError:
			raise RuntimeError("Failed to connect %s to %s as destination is already connected or incompatible" % (self, destplug))
		# END connection failed handling
		return destplug

	@undoable
	def mconnectToArray( self, arrayplug, force = True, exclusive_connection = False ):
		"""Connect self an element of the given arrayplug.
		
		:param arrayplug: the array plug to which you want to connect to
		:param force: if True, the connection will be created even if another connection
			has to be broken to achieve that.
		:param exclusive_connection: if True and destplug is an array, the plug will only be connected
			to an array element if it is not yet connected
		:return: newly created element plug or the existing one"""
		# ARRAY PLUG HANDLING
		######################
		if arrayplug.isArray( ):
			if exclusive_connection:
				arrayplug.evaluateNumElements( )
				for delm in arrayplug:
					if self == delm.minput():
						return delm
					# END if self == elm plug
				# END for each elemnt in destplug
			# END if exclusive array connection

			# connect the next free plug
			return self.mconnectTo( arrayplug.mnextLogicalPlug( ), force = force )
		# END Array handling
		raise AssertionError( "Given plug %r was not an array plug" % arrayplug )

	@undoable
	def mdisconnect( self ):
		"""Completely disconnect all inputs and outputs of this plug. The plug will not 
		be connected anymore.
		
		:return: self, allowing chained commands"""
		self.mdisconnectInput()
		self.mdisconnectOutputs()
		return self

	@undoable
	def mdisconnectInput( self ):
		"""Disconnect the input connection if one exists
		
		:return: self, allowing chained commands"""
		inputplug = self.minput()
		if inputplug.isNull():
			return self

		mod = undo.DGModifier( )
		mod.disconnect( inputplug, self )
		mod.doIt()
		return self

	@undoable
	def mdisconnectOutputs( self ):
		"""Disconnect all outgoing connections if they exist
		
		:return: self, allowing chained commands"""
		outputplugs = self.moutputs()
		if not len( outputplugs ):
			return self

		mod = undo.DGModifier()
		for destplug in outputplugs:
			mod.disconnect( self, destplug )
		mod.doIt()
		return self

	@undoable
	def mdisconnectFrom( self, other ):
		"""Disconnect this plug from other plug if they are connected
		
		:param other: MPlug that will be disconnected from this plug
		:return: other plug allowing to chain disconnections"""
		try:
			mod = undo.DGModifier( )
			mod.disconnect( self, other )
			mod.doIt()
		except RuntimeError:
			pass
		return other

	@undoable
	def mdisconnectNode( self, other ):
		"""Disconnect this plug from the given node if they are connected
		
		:param other: Node that will be completely disconnected from this plug"""
		for p in self.moutputs():
			if p.mwrappedNode() == other:
				self.mdisconnectFrom(p)
		# END for each plug in output

	#} END connections edit


	#{ Connections ( Query )
	@staticmethod
	def mhaveConnection( lhsplug, rhsplug ):
		""":return: True if lhsplug and rhs plug are connected - the direction does not matter
		:note: equals lhsplug & rhsplug"""
		return lhsplug.misConnectedTo( rhsplug ) or rhsplug.misConnectedTo( lhsplug )

	def misConnectedTo( self, destplug ):
		""":return: True if this plug is connected to destination plug ( in that order )
		:note: return true for self.misConnectedTo(destplug) but false for destplug.misConnectedTo(self)
		:note: use the mhaveConnection method whether both plugs have a connection no matter which direction
		:note: use `misConnected` to find out whether this plug is connected at all"""
		return destplug in self.moutputs()

	def moutputs( self ):
		""":return: MPlugArray with all plugs having this plug as source
		:todo: should the method be smarter and deal nicer with complex array or compound plugs ?"""
		outputs = api.MPlugArray()
		self.connectedTo( outputs, False, True )
		return outputs

	def moutput( self ):
		"""
		:return: first plug that has this plug as source of a connection, or null plug 
			if no such plug exists.
		:note: convenience method"""
		outputs = self.moutputs()
		if len( outputs ) == 0:
			return self.pa[0]
		return outputs[0]

	def minput( self ):
		"""
		:return: plug being the source of a connection to this plug or a null plug
			if no such plug exists"""
		inputs = api.MPlugArray()
		self.connectedTo( inputs, True, False )

		noInputs = len( inputs )
		if noInputs == 0:
			# TODO: find a better way to get a MPlugPtr type that can properly be tested for isNull
			return self.pa[0]
		elif noInputs == 1:
			return inputs[0]

		# must have more than one input - can this ever be ?
		raise ValueError( "Plug %s has more than one input plug - check how that can be" % self )

	def minputs( self ):
		"""Special handler returning the input plugs of array elements
		
		:return: list of plugs connected to the elements of this arrayplug
		:note: if self is not an array, a list with 1 or 0 plugs will be returned"""
		out = list()
		if self.isArray():
			self.evaluateNumElements()
			for elm in self:
				elminput = elm.minput()
				if elminput.isNull():
					continue
				out.append( elminput )
			# END for each elm plug in sets
		else:
			inplug = self.minput()
			if not inplug.isNull():
				out.append( inplug )
		# END array handling
		return out
		
	def miterGraph( self, *args, **kwargs ):
		"""
		:return: graph iterator with self as root, args and kwargs are passed to `it.iterGraph`.
			Plugs are returned by default, but this can be specified explicitly using 
			the plug=True kwarg"""
		import it
		kwargs['plug'] = kwargs.get('plug', True)
		return it.iterGraph(self, *args, **kwargs)
		
	def miterInputGraph( self, *args, **kwargs ):
		"""
		:return: iterator over the graph starting at this plug in input(upstream) direction.
			Plugs will be returned by default
		:note: see `it.iterGraph` for valid args and kwargs"""
		kwargs['input'] = True
		return self.miterGraph(*args, **kwargs)
		
	def miterOutputGraph( self, *args, **kwargs ):
		"""
		:return: iterator over the graph starting at this plug in output(downstream) direction.
			Plugs will be returned by default
		:note: see `it.iterGraph` for valid args and kwargs"""
		kwargs['input'] = False
		return self.miterGraph(*args, **kwargs)

	def mconnections( self ):
		""":return: tuple with input and outputs ( inputPlug, outputPlugs )"""
		return ( self.minput( ), self.moutputs( ) )

	#} END connections query

	#{ Affects Query
	def mdependencyInfo( self, by=False ):
		""":return: list of plugs on this node that this plug affects or is being affected by
		:param by: if false, affected attributplugs will be returned, otherwise the attributeplugs affecting this one
		:note: you can also use the `base.DependNode.dependencyInfo` method on the node itself if plugs are not
			required - this will also be faster
		:note: have to use MEL :("""
		ownnode = self.mwrappedNode()
		attrs = cmds.affects( self.mwrappedAttribute().name() , ownnode.name(), by=by ) or list()
		outplugs = list()
		depfn = api.MFnDependencyNode( ownnode.object() )

		for attr in attrs:
			outplugs.append( depfn.findPlug( attr ) )
		return outplugs

	def maffects( self ):
		""":return: list of plugs affected by this one"""
		return self.mdependencyInfo( by = False )

	def maffected( self ):
		""":return: list of plugs affecting this one"""
		return self.mdependencyInfo( by = True )

	#} END affects query

	#{ General Query
	def mnextLogicalIndex( self ):
		""":return: index of logical indexed plug that does not yet exist
		:note: as this method does a thorough search, it is relatively slow
			compared to a simple numPlugs + 1 algorithm
		:note: only makes sense for array plugs"""
		indices = api.MIntArray()
		self.getExistingArrayAttributeIndices( indices )

		logicalIndex = 0
		numIndices = indices.length()

		# do a proper search
		if numIndices == 1:
			logicalIndex =  indices[0] + 1	# just increment the first one
		else:
			# assume indices are SORTED, smallest first
			for i in xrange( numIndices - 1 ):
				if indices[i+1] - indices[i] > 1:
					logicalIndex = indices[i] + 1 	# at least one free slot here
					break
				else:
					logicalIndex = indices[i+1] + 1	# be always one larger than the last one
			# END for each logical index
		# END if more than one indices exist
		return logicalIndex

	def mnextLogicalPlug( self ):
		""":return: plug at newly created logical index
		:note: only valid for array plugs"""
		return self.elementByLogicalIndex(self.mnextLogicalIndex())

	def mwrappedAttribute( self ):
		""":return: Attribute instance of our underlying attribute"""
		return base.Attribute(self.attribute())

	def mwrappedNode( self ):
		"""
		:return: wrapped Node of the plugs node
		:note: instance information gets lost this way, the respective instance 
			can be re-retrieved using the instance information on this instanced 
			attribute, if this is an instanced attribute"""
		return base.NodeFromObj(self.node())

	def masData( self, *args, **kwargs ):
		""":return: our data Mobject wrapped in `base.Data`
		:note: args and kwagrs have to be provided as MDGContext.fsNormal
			does not exist in maya 8.5, so we have to hide that fact."""
		return base.Data(self.asMObject(*args, **kwargs))
		
	def mfullyQualifiedName( self ):
		"""
		:return: string returning the absolute and fully qualified name of the
			plug. It might take longer to evaluate but is safe to use if you want to 
			convert the resulting string back to the actual plug"""
		return self.partialName(1, 1, 1, 0, 1, 1)
		
	#} END query


	#{ Set Data with Undo

	# wrap the methods
	msetBool = _mplug_createUndoSetFunc( "Bool" )
	msetChar = _mplug_createUndoSetFunc( "Char" )
	msetShort = _mplug_createUndoSetFunc( "Short" )
	msetInt = _mplug_createUndoSetFunc( "Int" )
	msetFloat = _mplug_createUndoSetFunc( "Float" )
	msetDouble = _mplug_createUndoSetFunc( "Double" )
	msetString = _mplug_createUndoSetFunc( "String" )
	msetMAngle = _mplug_createUndoSetFunc( "MAngle" )
	msetMDistance = _mplug_createUndoSetFunc( "MDistance" )
	msetMTime = _mplug_createUndoSetFunc( "MTime" )
	msetMObject = _mplug_createUndoSetFunc( "MObject" )

	#} END set data

	#{ Name Remapping
	mctf = lambda self,other: self.mconnectTo( other, force=True )
	mct = lambda self,other: self.mconnectTo( other, force=False )
	mict = misConnectedTo
	mhc = lambda lhs,rhs: MPlug.mhaveConnection( lhs, rhs )
	mdc = mdisconnectFrom
	mwn = mwrappedNode
	mwa = mwrappedAttribute
	#} END name remapping


# SETUP DEBUG MODE ?
if int(os.environ.get('MRV_DEBUG_MPLUG_SETX', 0)):
	def __getattribute__(self, attr):
		"""Get attribute for MPlug which will raise if a setX method is used.
		This could cause undo bugs that you'd better catch before they hit the user"""
		if attr.startswith('set'):
			raise AssertionError("%s method called on MPlug - this causes undo-issues if it happens unintended" % attr)
		return api.MPlug._api___getattribute__(self, attr)
	# END method override
	
	# will be transferred onto api.MPlug when the patches are auto-applied.
	MPlug.__getattribute__ = __getattribute__
# END setup debug mode


#} END basic types


#{ Arrays

class ArrayBase( Abstract ):
	""" Base class for all maya arrays to easily fix them
	
	:note: set _apicls class variable to your api base class """

	def __len__( self ):
		return self._apicls.length( self )

	def __setitem__ ( self, index, item ):
		""":note: does not work as it expects a pointer type - probably a bug"""
		return self.set( item, index )
		
	@classmethod
	def mfromMultiple(cls, *args):
		""":return: Array created from the given elements"""
		ia = cls()
		ia.setLength(len(args))
		
		ci = 0
		for elm in args:
			ia[ci] = elm
			ci += 1
		# END for each index
		
		return ia
		
	@classmethod
	def mfromIter(cls, iter):
		""":return: Array created from elements yielded by iter
		:note: this one is less efficient than `mfromList` as the final length 
			of the array is not predetermined"""
		ia = cls()
		append = ia.append
		for index in iter:
			append(index)
		return ia
	
	@classmethod
	def mfromList(cls, list):
		""":return: Array created from the given list of elements"""
		ia = cls()
		ia.setLength(len(list))
		
		ci = 0
		set = ia.set
		for elm in list:
			set(elm, ci)
			ci += 1
		# END for each item
		
		return ia


_plugarray_getitem = api.MPlugArray.__getitem__
_objectarray_getitem = api.MObjectArray.__getitem__
_colorarray_getitem = api.MColorArray.__getitem__
_pointarray_getitem = api.MPointArray.__getitem__
_floatpointarray_getitem = api.MFloatPointArray.__getitem__
_doublearray_getitem = api.MDoubleArray.__getitem__
_floatarray_getitem = api.MFloatArray.__getitem__
_floatvectorarray_getitem = api.MFloatVectorArray.__getitem__
_vectorarray_getitem = api.MVectorArray.__getitem__
class MPlugArray( api.MPlugArray, ArrayBase ):
	""" Wrap MPlugArray to make it compatible to pythonic contructs
	
	:note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MPlugArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield api.MPlug(_plugarray_getitem( self,  i ))
	
	def __getitem__ ( self, index ):
		"""Copy the MPlugs we return to assure their ref count gets incremented"""
		return api.MPlug(_plugarray_getitem( self,  index ))
	

class MObjectArray( api.MObjectArray, ArrayBase ):
	""" Wrap MObject to make it compatible to pythonic contructs.
	
	:note: This array also fixes an inherent issue that comes into play when 
		MObjects are returned using __getitem__, as the reference count does not natively
		get incremented, and the MObjects will be obsolete once the parent-array goes out 
		of scope
	:note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MObjectArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield api.MObject(_objectarray_getitem( self,  i ))
	
	def __getitem__ ( self, index ):
		"""Copy the MObjects we return to assure their ref count gets incremented"""
		return api.MObject(_objectarray_getitem( self,  index ))


class MColorArray( api.MColorArray, ArrayBase ):
	""" Wrap MColor to make it compatible to pythonic contructs.
	
	:note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MColorArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield _colorarray_getitem( self,  i )
	

class MPointArray( api.MPointArray, ArrayBase ):
	""" Wrap MPoint to make it compatible to pythonic contructs.
	
	:note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MPointArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield _pointarray_getitem( self,  i )


class MFloatVectorArray( api.MFloatVectorArray, ArrayBase ):
	""" Wrap MFloatVector to make it compatible to pythonic contructs.
	
	:note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MFloatVectorArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield _floatvectorarray_getitem( self,  i )
			

class MVectorArray( api.MVectorArray, ArrayBase ):
	""":note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MVectorArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield _vectorarray_getitem( self,  i )


class MFloatPointArray( api.MFloatPointArray, ArrayBase ):
	""" Wrap MFloatPoint to make it compatible to pythonic contructs.
	
	:note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MFloatPointArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield _floatpointarray_getitem( self,  i )


class MDoubleArray( api.MDoubleArray, ArrayBase ):
	""":note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MDoubleArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield _doublearray_getitem( self,  i )
			
			
class MFloatArray( api.MFloatArray, ArrayBase ):
	""":note: for performance reasons, we do not provide negative index support"""
	_apicls = api.MFloatArray
	
	def __iter__( self ):
		""":return: iterator object"""
		for i in xrange(len(self)):
			yield _floatarray_getitem( self,  i )
			

class MIntArray( api.MIntArray, ArrayBase ):
	"""Attach additional creator functions"""
	_apicls = api.MIntArray
	
	@classmethod
	def mfromRange(cls, i, j):
		""":return: An MIntArray initialized with integers ranging from i to j
		:param i: first integer of the returned array
		:param j: last integer of returned array will have the value j-1"""
		if j < i:
			raise ValueError("j < i violated")
		if j < 0 or i < 0:
			raise ValueError("negative ranges are not supported")
		
		ia = api.MIntArray()
		l = j - i
		ia.setLength(l)
		
		# wouldn't it be great to have a real for loop now ?
		ci = 0
		set = ia.set
		for i in xrange(i, j):
			set(i, ci)
			ci += 1
		# END for each integer
		
		# this is slightly slower
		#for ci, i in enumerate(xrange(i, j)):
		#	ia[ci] = i
		# END for each index/value pair
		
		return ia


class MSelectionList( api.MSelectionList, ArrayBase ):
	_apicls = api.MSelectionList
	
	def mhasItem( self, rhs ):
		""":return: True if we contain rhs
		:note: As we check for Nodes as well as MayaAPI objects, we are possibly slow"""
		if isinstance(rhs, base.DagNode):
			return self.hasItem(rhs.dagPath())
		elif isinstance(rhs, base.DependNode):
			return self.hasItem(rhs.object())
		else:
			return self.hasItem(rhs)
		# END handle input type
	
	@staticmethod
	def mfromStrings( iter_strings, **kwargs ):
		""":return: MSelectionList initialized from the given iterable of strings
		:param kwargs: passed to `base.toSelectionListFromNames`"""
		return base.toSelectionListFromNames(iter_strings, **kwargs)
		
	@staticmethod
	def mfromList( iter_items, **kwargs ):
		"""
		:return: MSelectionList as initialized from the given iterable of Nodes, 
			MObjects, MDagPaths, MPlugs or strings
		:param kwargs: passed to `base.toSelectionList`"""
		return base.toSelectionList(iter_items, **kwargs)
		
	# We need to override the respective method on the base class as it wouldnt work
	mfromIter = mfromList
	
	@staticmethod
	def mfromMultiple( *args, **kwargs ):
		"""Alternative form of `mfromList` as args can be passed in."""
		return MSelectionList.mfromList(args, **kwargs)
	
	@staticmethod
	def mfromComponentList( iter_components, **kwargs ):
		"""
		:return: MSelectionList as initialized from the given list of tuple( DagNode, Component ), 
			Component can be a filled Component object or null MObject
		:param kwargs: passed to `base.toComponentSelectionList`"""
		return base.toComponentSelectionList(iter_components, **kwargs)
		
	def mtoList( self, *args, **kwargs ):
		""":return: list with the contents of this MSelectionList
		:note: all args and kwargs passed to `it.iterSelectionList`"""
		return list(self.mtoIter(*args, **kwargs))
		
	def mtoIter( self, *args, **kwargs ):
		""":return: iterator yielding of Nodes and MPlugs stored in this given selection list
		:note: all args and kwargs are passed to `it.iterSelectionList`"""
		return it.iterSelectionList( self, *args, **kwargs )
		
	def miterComponents( self, **kwargs ):
		"""
		:return: Iterator yielding node, component pairs, component is guaranteed 
			to carry a component, implying that this iterator applies a filter
		:param kwargs: passed on to `it.iterSelectionList`"""
		kwargs['handleComponents'] = True
		pred = lambda pair: not pair[1].isNull()
		kwargs['predicate'] = pred
		return it.iterSelectionList( self, **kwargs )
		
	def miterPlugs( self, **kwargs ):
		""":return: Iterator yielding all plugs on this selection list.
		:param kwargs: passed on to `it.iterSelectionList`"""
		kwargs['handlePlugs'] = True
		pred = lambda n: isinstance(n, api.MPlug)
		kwargs['predicate'] = pred
		return it.iterSelectionList( self, **kwargs )
		
	
class MeshIteratorBase( Abstract ):
	"""Provides common functionality for all MItMesh classes"""
	
	def __iter__(self):
		""":return: Iterator yielding self for each item in the iteration
		:note: the iteration will be reset before beginning it
		:note: extract the information you are interested in yourself"""
		self.reset()
		next = self.next
		if hasattr(self, 'count'):
			for i in xrange(self.count()):
				yield self
				next()
			# END for each item 
		else:
			isDone = self.isDone
			while not isDone():
				yield self
				next()
			# END while we have items
		# END handle optimized iteration, saving function calls
	
class MItMeshVertex( api.MItMeshVertex, MeshIteratorBase ):
	pass

class MItMeshEdge( api.MItMeshEdge, MeshIteratorBase ):
	pass

class MItMeshPolygon( api.MItMeshPolygon, MeshIteratorBase ):
	pass

class MItMeshFaceVertex( api.MItMeshFaceVertex, MeshIteratorBase ):
	pass
#}

