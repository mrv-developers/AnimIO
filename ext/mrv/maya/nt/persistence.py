# -*- coding: utf-8 -*-
"""generic python style persitance plugin
This module contains a storage interface able to easily handle python-style
data within maya scenes. 
"""
__docformat__ = "restructuredtext"

import os
import sys
import cPickle
import cStringIO
import binascii
import logging
log = logging.getLogger('mrv.maya.nt.persistence')

import maya.OpenMaya as api
import maya.OpenMayaMPx as mpx

persistence_enabled_envvar = "MRV_PERSISTENCE_ENABLED"
_should_initialize_plugin = int(os.environ.get(persistence_enabled_envvar, False))


__all__ = ('persistence_enabled_envvar', 'PyPickleData', 'createStorageAttribute')

#{ Initialization

def __initialize( nodes_module ):
	"""Assure our plugin is loaded - called during module intialization.
	Its a tough time to run, it feels more like bootstrapping as we initialize
	ourselves although the system is not quite there yet."""
	import maya.cmds as cmds	# late import
	pluginpath = os.path.splitext( __file__ )[0] + ".py"
	
	if _should_initialize_plugin and not cmds.pluginInfo( pluginpath, q=1, loaded=1 ):
		cmds.loadPlugin( pluginpath )
	return _should_initialize_plugin

#} END initialization

#{ Storage Plugin

# GLOBAL PERSITENCE TRACKING DICT
# assure we only have it once
if not hasattr( sys, "_maya_pyPickleData_trackingDict" ):
	sys._maya_pyPickleData_trackingDict = dict()


# NOTE: We do not prevent the code to be executed if we are not to load as, 
# at this point, openMayaAnim has been initialized already which in fact 
# loads OpenMayaMPx that we would try to delay. 

def createStorageAttribute( dataType ):
	""" This method creates an Attribute in a configuration suitable to be used
	with the ``StorageBase`` interface. 
	
	:note: this allows your own plugin node to receive storage compatibility
	:param dataType: the type of the typed attribute - either MTypeID or MFnData enumeration
		An MTypeID must point to a valid and already registered plugin data.
		In order for the ``StorageBase`` interface to work, it must by ``PyPickleData.kPluginDataId``. 
	:return: attribute api object of its master compound attribute"""
	tAttr = api.MFnTypedAttribute()
	mAttr = api.MFnMessageAttribute()
	cAttr = api.MFnCompoundAttribute()
	nAttr = api.MFnNumericAttribute()

	aData = cAttr.create( "data", "dta" )					# connect to instance transforms
	if True:
		dataID = tAttr.create( "dataId", "id", api.MFnData.kString )

		typeInfo = nAttr.create( "dataType", "type", api.MFnNumericData.kInt )	# can be used for additional type info

		typedData = tAttr.create( "value", "dval", dataType )

		# even though its a child attribute, we cannot use 'message' as it is already
		# taken on the DependNode
		messageData = mAttr.create( "mmessage", "dmsg" )
		mAttr.setArray( True )


		cAttr.addChild( dataID )
		cAttr.addChild( typeInfo )
		cAttr.addChild( typedData )
		cAttr.addChild( messageData )

	# END COMPOUND ATTRIBUTE
	cAttr.setArray( True )

	# copy attribute, just to be sure we don't loose the object when cAttr goes out
	# of scope
	return api.MObject(aData)

class StoragePluginNode( mpx.MPxNode ):
	""" Base Class defining the storage node data interfaces  """

	# The ID used here has been assigned by the autodesk support and is globally unique !
	kPluginNodeTypeName = "storageNode"
	kPluginNodeId = api.MTypeId( 0x0010D134 )

	aData = api.MObject()

	def __init__( self ):
		return mpx.MPxNode.__init__( self )

	@staticmethod
	def creator( ):
		return mpx.asMPxPtr( StoragePluginNode() )

def initStoragePluginNodeAttrs( ):
	"""Called to initialize the attributes of the storage node"""
	StoragePluginNode.aData = createStorageAttribute( PyPickleData.kPluginDataId )
	StoragePluginNode.addAttribute( StoragePluginNode.aData )

class PyPickleData( mpx.MPxData ):
	"""Allows to access a pickled data object natively within a maya file.
	In ascii mode, the pickle will be encoded into string data, in binary mode
	the cPickle will be taken in its original value.

	To get the respective dict-references back, we use a tracking dict as proposed
	by the API Docs

	:note: This datatype is copies the data by reference which is why maya always calls
		the copy constructor, even if you retrieve a const data reference, where this would not be
		required actually. This is fine for most uses
	:note: as the datatype is reference based, undo is currently not supported ( or does not
		work as it is expected to do"""

	# The ID used here has been assigned by the autodesk support and is globally unique !
	kPluginDataId = api.MTypeId( 0x0010D135 )
	kDataName = "PickleData"

	def __init__(self):
		mpx.MPxData.__init__( self )
		self.__data = dict()
		sys._maya_pyPickleData_trackingDict[ mpx.asHashable( self ) ] = self.__data

	def __del__( self ):
		"""Remove ourselves from the dictionary to prevent flooding
		
		:note: we can be called even if maya is already unloaded or shutting down"""
		if mpx.asHashable is not None:
			del( sys._maya_pyPickleData_trackingDict[ mpx.asHashable( self ) ] )
		# call super just to be on the safe side in future, currently it appears
		# not to be required
		try:
			super( PyPickleData, self ).__del__( )
		except AttributeError:
			# Maya 2008 and following do not require this anymore as they
			# do not have a del method implemented apparently
			pass

	def _writeToStream( self, ostream, asBinary ):
		"""Write our data binary or ascii respectively"""
		sout = cStringIO.StringIO()
		try:
			cPickle.dump( self.__data, sout, protocol=2 )
		except cPickle.PicklingError, e:
			log.error( str( e ) )
			return
		# END pickle error handling

		if not asBinary:
			api.MStreamUtils.writeChar( ostream, '"', asBinary )

		# assure number of bytes is a multiple of 4
		if asBinary:
			for c in range( sout.tell() % 4 ):
				sout.write( chr( 0 ) )		# 0 bytes

		# NOTE: even binaries will be encoded as this circumvents the 0 byte which terminates the
		# char byte stream ... can't help it but writing individual bytes
		# TODO: improve this if it turns out to be too slow
		api.MStreamUtils.writeCharBuffer( ostream, binascii.b2a_base64( sout.getvalue() ).strip(), asBinary )

		if not asBinary:
			api.MStreamUtils.writeChar( ostream, '"', asBinary )

	def writeBinary(self, out):
		"""cPickle to cStringIO, write in 4 byte packs using ScriptUtil"""
		self._writeToStream( out, True )

	def readBinary(self, inStream, numBytesToRead ):
		"""Read in 4 byte packs to cStringIO, unpickle from there
		
		:note: this method is more complicated than it needs be since asCharPtr does not work !
			It returns a string of a single char ... which is not the same :) !
		:note: YES, this is a CUMBERSOME way to deal with bytes ... terrible, thanks maya :), thanks python"""
		sio = cStringIO.StringIO( )
		scriptutil = api.MScriptUtil( )
		scriptutil.createFromInt( 0 )
		intptr = scriptutil.asIntPtr()

		# require multiple of 4 !
		if numBytesToRead % 4 != 0:
			raise AssertionError( "Require multiple of for for number of bytes to be read, but is %i" % numBytesToRead )

		bitmask = 255								# mask the lower 8 bit
		shiftlist = [ 0, 8, 16, 24 ]				# used to shift bits by respective values
		for i in xrange( numBytesToRead  / 4 ):
			api.MStreamUtils.readInt( inStream, intptr, True )
			intval = scriptutil.getInt( intptr )

			# convert to chars - endianess should be taken care of by python
			for shift in shiftlist:
				sio.write( chr( ( intval >> shift ) & bitmask ) )
			# END for each byte
		# END for all 4 bytes to read

		self.__data = cPickle.loads( binascii.a2b_base64( sio.getvalue() ) )
		sys._maya_pyPickleData_trackingDict[ mpx.asHashable( self ) ] = self.__data

	def writeASCII(self, out):
		"""cPickle to cStringIO, encode with base64 encoding"""
		self._writeToStream( out, False )

	def readASCII(self, args, lastParsedElement ):
		"""Read base64 element and decode to cStringIO, then unpickle"""
		parsedIndex = api.MScriptUtil.getUint( lastParsedElement )
		base64encodedstring = args.asString( parsedIndex )
		self.__data = cPickle.loads( binascii.a2b_base64( base64encodedstring ) )

		parsedIndex += 1
		api.MScriptUtil.setUint(lastParsedElement,parsedIndex)	# proceed the index

		# update tracking dict
		sys._maya_pyPickleData_trackingDict[ mpx.asHashable( self ) ] = self.__data

	def copy( self, other ):
		"""Copy other into self - allows copy pointers as maya copies the data each
		time you retrieve it"""
		otherdata = sys._maya_pyPickleData_trackingDict[ mpx.asHashable( other ) ]
		self.__data = otherdata
		sys._maya_pyPickleData_trackingDict[ mpx.asHashable( self ) ] = self.__data

	@staticmethod
	def creator( ):
		return mpx.asMPxPtr( PyPickleData() )

	def typeId( self ):
		return self.kPluginDataId

	def name( self ):
		return self.kDataName


def initializePlugin(mobject):
	import mrv.maya as mrv

	mplugin = mpx.MFnPlugin( mobject )
	mplugin.registerData( PyPickleData.kDataName, PyPickleData.kPluginDataId, PyPickleData.creator )
	mplugin.registerNode( 	StoragePluginNode.kPluginNodeTypeName, StoragePluginNode.kPluginNodeId, StoragePluginNode.creator, initStoragePluginNodeAttrs, mpx.MPxNode.kDependNode )
	
	# register plugin data in the respective class
	mrv.registerPluginDataTrackingDict( PyPickleData.kPluginDataId, sys._maya_pyPickleData_trackingDict )

def uninitializePlugin( mobject ):
	mplugin = mpx.MFnPlugin( mobject )
	mplugin.deregisterData( PyPickleData.kPluginDataId )
	mplugin.deregisterNode( StoragePluginNode.kPluginNodeId )
	
#} END plugin

