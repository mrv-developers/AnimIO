# -*- coding: utf-8 -*-
"""Contains an implementation for the Persistence plugin for easy access within 
mrv and derived nodes.
"""
__docformat__ = "restructuredtext"

import os
from persistence import PyPickleData
import maya.OpenMaya as api

import mrv.maya.undo as undo
from mrv.util import iDuplicatable

from base import Node, DependNode, Data, createNode, delete
from set import ObjectSet

import copy

__all__ = ( "StorageBase", "StorageNode" )

#{ Storage Access

class StorageBase( iDuplicatable ):
	"""A storage node contains a set of attributes allowing it to store
	python data and objects being stored in a pickled format upon file save.
	Additionally you can store connections.
	Nodes used with this interface must be compatible to the following attribute scheme.
	To create that scheme, use `createStorageAttribute`

	**Attribute Setup**::
	
		( shortname ( description ) [ data type ] )
		dta ( data )[ multi compound ]
			id ( data id )[ string ]
			type ( data type ) [ int ]	# for your own use, store bitflags to specify attribute
			dval ( data value ) [ python pickle ]
			dmsg ( data message )[ multi message ]

	**Configuration**::
	
		attrprefix: will prefix every attribute during attr set and get - this allows
			several clients to access the same storage base ( on the same node for example )
			It acts like a namespace
		mayaNode: the maya node holding the actual attributes

	:note: A mrv node should derive from this class to allow easy attribute access of its
		own compatible attributes - its designed for flexiblity
	:note: attribute accepts on the generic attribute should be set by a plugin node when it
		creates its attributes
	:todo: should self._node be stored as weakref ?"""
	kValue, kMessage, kStorage = range( 3 )
	_partitionIdAttr = "bda_storagePartition"

	class PyPickleValue( object ):
		"""Wrapper object prividing native access to the wrapped python pickle object
		and to the corresponding value plug, providing utlity methods for easier handling"""
		__slots__ = ( '_plug', '_pydata', '_isReferenced', '_updateCalled' )

		def __init__( self, valueplug, pythondata ):
			"""value plug contains the plugin data in pythondata"""
			object.__setattr__( self, '_plug', valueplug )
			object.__setattr__( self, '_pydata', pythondata )
			object.__setattr__( self, '_isReferenced', valueplug.mwrappedNode( ).isReferenced( ) )
			object.__setattr__( self, '_updateCalled', False )

		def __len__( self ):
			return len( self._pydata )

		def __iter__( self ):
			return iter( self._pydata )

		def __getattr__( self, attr ):
			return getattr( self._pydata, attr )

		def __setattr__( self, attr, val ):
			try:
				object.__setattr__( self, attr, val )
			except AttributeError:
				self._pydata[ attr ] = val


		def __getitem__( self, key ):
			return self._pydata[ key ]

		def __setitem__( self, key, value ):
			self._pydata[ key ] = value
			if self._isReferenced:
				self.valueChanged()		# assure we make it into the reference , but only if we change

		def valueChanged( self ):
			"""Will be called automatically if the underlying value changed if
			the node of the underlying plug is referenced
			
			:note: this method will only be called once during the lifetime of this object if it changes,
				as its enough to trigger reference to write the value if it changes once.
				Getting and setting data is expensive as there is a tracking dict in the background
				being spawned with internally created copies."""
			if self._updateCalled:
				return
			self._plug.msetMObject( self._plug.asMObject() )
			self._updateCalled = True
	# END class pypickle value



	#{ Overridden Methods
	def __init__( self, attrprefix = "", mayaNode = None ):
		"""Allows customization of this base to modify its behaviour
		
		:note: see more information on the input attributes in the class description"""
		# now one can derive from us and override __setattr__
		object.__init__( self )
		self._attrprefix = attrprefix
		self._node = mayaNode
		if not mayaNode:
			if not isinstance( self, Node ):
				raise TypeError( "StorageNode's derived class must be an instance of type %r if mayaNode is not given" % Node )
			self._node = self
		# END no maya node given handling

	#} END overridden methods

	#( iDuplicatable
	def createInstance( self, *args, **kwargs ):
		"""Create a new instance with our type"""
		return self.__class__( self._attrprefix, self._node )

	def copyFrom( self, other, *args, **kwargs ):
		"""Copy all values from other to ourselves
		
		:param kwargs:
			 * shallow:
			 	if True, default False, only a shallow copy will
				be made. If False, a deep copy will be made
		:note: only does so if the attribute prefixes actually match ( which should be
			the case if we get here, checking for it anyway
		:note: as pickle data always copies by reference to be efficient, we have to explicitly
			create new data to assure we really copy it
		:todo: copy connections to our messages as well, make it an option at least"""
		if self.attributePrefix() != other.attributePrefix():
			raise AssertionError( "Attribute prefixes between self and other did not match" )

		shallow = kwargs.pop( "shallow", False )
		for dataid in other.dataIDs():
			othervalplug = other.storagePlug( dataid, plugType = self.kValue, autoCreate = False )
			ownvalplug = self.storagePlug( dataid, plugType = self.kValue, autoCreate = True )

			self._clearData( ownvalplug )

			if shallow:
				ownvalplug.msetMObject( othervalplug.asMObject() )
			else:
				owndict = self.pythonDataFromPlug( ownvalplug )
				otherdict = other.pythonDataFromPlug( othervalplug )

				# copy each value
				for key in otherdict:
					val = otherdict[ key ]
					if isinstance( val, iDuplicatable ):
						owndict[ key ] = val.duplicate( )
					else:
						# try deep copy, use shallow copy on error
						try:
							owndict[ key ] = copy.deepcopy( val )
						except copy.Error:
							owndict[ key ] = val
					# END copy operation
				# END for each key to deep copy
			# END shallow/deep copy
		# END for each dataid

	#) END iDuplicatable

	def __makePlug( self, dataID ):
		"""Find an empty logical plug index and return the newly created
		logical plug with given dataID"""
		elementPlug = self._node.dta.mnextLogicalPlug( )
		elementPlug.mchildByName('id').msetString( dataID )
		return elementPlug

	#{ Edit
	
	def makePlug( self, dataID ):
		"""Create a plug that can be retrieved using the given dataID
		
		:param dataID: string identifier
		:return: the created master plug, containing subplugs dval and dmsg
			for generic data and  message connections respectively """
		actualID = self._attrprefix + dataID
		existingPlug = self.findStoragePlug( dataID )
		if existingPlug is not None:
			return existingPlug

		# otherwise create it - find a free logical index - do a proper search
		return self.__makePlug( actualID )

	def _clearData( self, valueplug ):
		"""Safely clear the data in valueplug - its undoable"""
		# NOTE: took special handling out - it shuld be done in the api-patch
		# for an MPlug
		plugindataobj = api.MFnPluginData( ).create( PyPickleData.kPluginDataId )
		valueplug.msetMObject( plugindataobj )

	@undoable
	def clearAllData( self ):
		"""empty the whole storage, creating new python storage data to assure
		nothing is still referenced
		
		:note: use this method if you want to make sure your node
			is empty after it has been duplicated ( would usually be done in the
			postContructor"""
		for compoundplug in self._node.dta:
			self._clearData( compoundplug.mchildByName('dval') )
		# END for each element in data compound

	@undoable
	def clearData( self, dataID ):
		"""Clear all data stored in the given dataID"""
		try:
			valueplug = self.storagePlug( dataID, plugType=self.kValue, autoCreate = False )
		except AttributeError:
			return
		else:
			self._clearData( valueplug )
		# ELSE attr exists and clearage is required

	#} END edit


	#{ Query Plugs
	def findStoragePlug( self, dataID ):
		""":return: compound plug with given dataID or None"""
		actualID = self._attrprefix + dataID
		for compoundplug in self._node.dta:
			if compoundplug.mchildByName('id').asString( ) == actualID:
				return compoundplug
		# END for each elemnt ( in search for mathching dataID )
		return None

	def dataIDs( self ):
		""":return: list of all dataids available in the storage node
		:note: respects attribute prefix, and will only see ids with matching prefix.
			The prefix itself is transparent and will not bre returned"""
		outids = list()
		for compoundplug in self._node.dta:
			did = compoundplug.mchildByName('id').asString( )
			if did and did.startswith( self._attrprefix ):
				outids.append( did[ len( self._attrprefix ) : ] )
			# END if is valid id
		# END for each compound plug element
		return outids

	def storagePlug( self, dataID, plugType = None, autoCreate=False ):
		"""
		:return: plug of the given type, either as tuple of two plugs or the plug
			specified by plugType
		:param dataID: the name of the plug to be returned
		:param plugType:
			StorageBase.kMessage: return message array plug only
			StorageBase.kValue: return python pickle array plug only
			StorageBase.kStorage: return the storage plug itself containing message and the value plug
			None: return ( picklePlug , messagePlug )
		:param autoCreate: if True, a plug with the given dataID will be created if it does not
			yet exist
		:raise AttributeError: if a plug with dataID does not exist and default value is None
		:raise TypeError: if  plugtype unknown """
		matchedplug = self.findStoragePlug( dataID )
		if matchedplug is None:
			if autoCreate:
				actualID = self._attrprefix + dataID
				matchedplug = self.__makePlug( actualID )
			else:
				raise AttributeError( "Plug with id %s not found on %r" % ( dataID, self._node ) )
		# END matched plug not found handling

		# return the result
		if plugType is None:
			return ( matchedplug.mchildByName('dval'), matchedplug.mchildByName('dmsg') )
		elif plugType == StorageBase.kStorage:
			return matchedplug
		elif plugType == StorageBase.kValue:
			return matchedplug.mchildByName('dval')
		elif plugType == StorageBase.kMessage:
			return matchedplug.mchildByName('dmsg')
		else:
			raise TypeError( "Invalid plugType value: %s" % plugType )

	#} END query plugs


	#{ Query Data
	def pythonData( self, dataID, **kwargs ):
		""":return: PyPickleVal object at the given index ( it can be modified natively )
		:param dataID: id of of the data to retrieve
		:param kwargs:
			 * index: 
			 	element number of the plug to retrieve, or -1 to get a new plug.
				Plugs will always be created, the given index specifies a logical plug index
			 * Additionally all arguments supported by `storagePlug`
		""" 
		storagePlug = self.storagePlug( dataID, plugType = StorageBase.kStorage, **kwargs )
		valplug = storagePlug.mchildByName('dval')
		return self.pythonDataFromPlug( valplug )


	@classmethod
	def pythonDataFromPlug( cls, valplug ):
		"""Exract the python data using the given plug directly
		
		:param valplug: data value plug containing the plugin data
		:return: PyPickleData object allowing data access"""

		# initialize data if required
		# if the data is null, we do not get a kNullObject, but an exception - fair enough ...
		try:
			plugindata = valplug.masData()
		except RuntimeError:
			# set value
			plugindataobj = api.MFnPluginData( ).create( PyPickleData.kPluginDataId )

			# data gets copied here - re-retrieve data
			valplug.msetMObject( plugindataobj ) # use original version only - no undo support
			plugindata = Data( plugindataobj )

		# exstract the data
		#return plugindata.data()
		return StorageBase.PyPickleValue( valplug, plugindata.data( ) )

	#} END query Data

	#{ Set Handling
	def objectSet( self, dataID, setIndex, autoCreate = True ):
		"""Get an object set identified with setIndex at the given dataId
		
		:param dataID: id identifying the storage plug on this node
		:param setIndex: logical index at which the set will be connected to our message plug array
		:param autoCreate: if True, a set will be created if it does not yet exist
		:raises ValueError: if a set does not exist at setIndex and autoCreate is False
		:raises AttributeError: if the plug did not exist ( and autocreate is False )
		:note: method is implicitly undoable if autoCreate is True, this also means that you cannot
			explicitly undo this operation as you do not know if undo has been queued or not
		:note: newly created sets will automatically use partitions if one of the sets does"""
		mp = self.storagePlug( dataID, self.kMessage, autoCreate = autoCreate )
		# array plug having our sets
		setplug = mp.elementByLogicalIndex( setIndex )
		inputplug = setplug.minput()
		if inputplug.isNull():
			if not autoCreate:
				raise AttributeError( "Set at %s[%i] did not exist on %r" % ( self._attrprefix + dataID, setIndex, self ) )
			su = undo.StartUndo()			# make the following operations atomic
			objset = createNode( dataID + "Set", "objectSet", forceNewLeaf = True )
			inputplug = objset.message
			inputplug.mconnectTo(setplug)

			# hook it up to the partition
			if self.partition( dataID ):
				self.setPartition( dataID, True )
		# END create set as needed


		# return actual object set
		return inputplug.mwrappedNode()

	@undoable
	def deleteObjectSet( self, dataID, setIndex ):
		"""Delete the object set identified by setIndex
		
		:note: the method is implicitly undoable
		:note: use this method to delete your sets instead of manual deletion as it will automatically
			remove the managed partition in case the last set is being deleted"""
		try:
			objset = self.objectSet( dataID, setIndex, autoCreate = False )
		except ( ValueError, AttributeError ):
			# did not exist, its fine
			return
		else:
			# if this is the last set, remove the partition as well
			if len( self.setsByID( dataID ) ) == 1:
				self.setPartition( dataID, False )

			delete( objset )
		# END obj set handling

	def setsByID( self, dataID ):
		""":return: all object sets stored under the given dataID"""
		mp = self.storagePlug( dataID, self.kMessage, autoCreate = False )
		allnodes = [ p.mwrappedNode() for p in mp.minputs() ]
		return [ n for n in allnodes if isinstance( n, ObjectSet ) ]


	@undoable
	def setPartition( self, dataID, state ):
		"""Make all sets in dataID use a partition or not
		
		:param dataID: id identifying the storage plug
		:param state: if True, a partition will be used, if False, it will be disabled
		:note: this method makes sure that all sets are hooked up to the partition
		:raise ValueError: If we did not have a single set to which to add to the partition
		:raise AttributeError: If the dataID has never had sets
		:return: if state is True, the name of the possibly created ( or existing ) partition"""
		sets = self.setsByID( dataID )
		partition = self.partition( dataID )

		if state:
			if partition is None:
				if not sets:
					raise ValueError("Cannot create partition as data %r did not have any connected sets" % dataID)
				# END check sets exist
				# create partition
				partition = createNode( "storagePartition", "partition", forceNewLeaf=True )

				tattr = api.MFnTypedAttribute( )
				attr = tattr.create( self._partitionIdAttr, "pid", api.MFnData.kString )
				partition.addAttribute( attr )
			# END create partition

			# make sure all sets are members of our partition
			partition.addSets( sets )
			return partition
		else:
			if partition:
				# delete partition
				# have to clear partition as, for some reason, or own node will be killed as well !
				partition.clear()
				delete( partition )
		# END state check


	def partition( self, dataID ):
		"""
		:return: partition Node attached to the sets at dataID or None if state
			is disabled"""
		sets = self.setsByID( dataID )

		# get the dominant partition
		partitions = []
		for s in sets:
			partitions.extend( s.partitions() )

		for p in partitions:
			if hasattr( p, self._partitionIdAttr ):
				return p
		# END for each partition

		# nothing found, there is no partition yet
		return None

	#} END set handling

	# Query General

	def storageNode( self ):
		""":return: Node actually being used as storage"""
		return self._node

	def setStorageNode( self, node ):
		"""Set ourselves to use the given storage compatible node
		
		:note: use this if the path of our instance has changed - otherwise
			trying to access functions will fail as the path of our node might be invalid"""
		self._node = node

	def attributePrefix( self ):
		""":return: our attribute prefix
		:note: it is read-only to assure we will never 'forget' about our data"""
		return self._attrprefix

	# END query general


class StorageNode( DependNode, StorageBase ):
	"""This node can be used as pythonic and easy-to-access value container - it could
	be connected to your node, and queried for values actually being queried on your node.
	As value container, it can easily be replaced by another one, or keep different sets of information
	
	:note: the storage node can only use generic attributes and recover them properly during scene reload
		if the configuration of the generic attributes have been setup properly - they are unique only per
		node type, not per instance of the node type.
		Thus it is recommened to use the storage node attribute base on your own custom type that setsup the
		generic attributes as it requires during plugin load"""

	#{ Overrriden Methods
	def __init__( self, *args ):
		"""initialize bases properly"""
		DependNode.__init__( self )
		StorageBase.__init__( self )


	#} END overridden methods

#} END storage access
