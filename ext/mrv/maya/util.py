# -*- coding: utf-8 -*-
"""All kinds of utility methods and classes that are used in more than one modules """
__docformat__ = "restructuredtext"

import maya.mel as mm
import maya.cmds as cmds
import maya.OpenMaya as api
import mrv.util as util
from mrv.util import capitalize,uncapitalize
import networkx.exception as networkxexc

import weakref

__all__ = ("noneToList", "isIterable", "pythonToMel", "makeEditOrQueryMethod", 
           "queryMethod", "editMethod", "propertyQE", "Mel", "OptionVarDict", 
           "optionvars", "StandinClass", "MetaClassCreator", "CallbackEventBase", 
           "MEnumeration")

#{ Utility Functions
def noneToList( res ):
	""":return: list instead of None"""
	if res is None:
		return []
	return res
	
def isIterable( obj ):
	return hasattr(obj,'__iter__') and not isinstance(obj,basestring)

def pythonToMel(arg):
	if isinstance(arg,basestring):
		return u'"%s"' % cmds.encodeString(arg)
	elif isIterable(arg):
		return u'{%s}' % ','.join( map( pythonToMel, arg) )
	return unicode(arg)
#} END utility functions


#{ MEL Function Wrappers

def makeEditOrQueryMethod( inCmd, flag, isEdit=False, methodName=None ):
	"""Create a function calling inFunc with an edit or query flag set.
	
	:note: THIS CODE HAS BEEN DUPLICATED TO `mrv.maya.ui.util` !
	:param inCmd: maya command to call
	:param flag: name of the query or edit flag
	:param isEdit: If not False, the method returned will be an edit function
	:param methodName: the name of the method returned, defaults to inCmd name  """

	func = None
	if isEdit:
		def editFunc(self, val, **kwargs):
			kwargs[ 'edit' ] = True
			kwargs[ flag ] = val
			return inCmd( self, **kwargs )

		func = editFunc
	# END if edit
	else:
		def queryFunc(self, **kwargs):
			kwargs[ 'query' ] = True
			kwargs[ flag ] = True
			return inCmd( self, **kwargs )

		func = queryFunc
	# END if query

	if not methodName:
		methodName = flag
	func.__name__ = methodName

	return func

def queryMethod( inCmd, flag, methodName = None ):
	""" Shorthand query version of makeEditOrQueryMethod """
	return makeEditOrQueryMethod( inCmd, flag, isEdit=False, methodName=methodName )

def editMethod( inCmd, flag, methodName = None ):
	""" Shorthand edit version of makeEditOrQueryMethod """
	return makeEditOrQueryMethod( inCmd, flag, isEdit=True, methodName=methodName )

def propertyQE( inCmd, flag, methodName = None ):
	""" Shorthand for simple query and edit properties """
	editFunc = editMethod( inCmd, flag, methodName = methodName )
	queryFunc = queryMethod( inCmd, flag, methodName = methodName )
	return property( queryFunc, editFunc )

#} END mel function wrappers


#{ Utitliy Classes

class Mel(util.Singleton):
	"""This class is a necessity for calling mel scripts from python. It allows scripts to be called
	in a cleaner fashion, by automatically formatting python arguments into a string
	which is executed via maya.mel.eval().

	:note: originated from pymel, added customizations  """

	def __getattr__(self, command):
		"""Only for instances of this class - call methods directly as if they where
		attributes """
		if command.startswith('__') and command.endswith('__'):
			return self.__dict__[command]
		def _call(*args):

			strArgs = map( pythonToMel, args)

			cmd = '%s(%s)' % ( command, ','.join( strArgs ) )
			try:
				return mm.eval(cmd)
			except RuntimeError, msg:
				info = self.whatIs( command )
				if info.startswith( 'Presumed Mel procedure'):
					raise NameError, 'Unknown Mel procedure'
				raise RuntimeError, msg

		return _call

	@staticmethod
	def call( command, *args ):
		""" Call a mel script , very simpilar to Mel.myscript( args )
		
		:todo: more docs """
		strArgs = map( pythonToMel, args)

		cmd = '%s(%s)' % ( command, ','.join( strArgs ) )

		try:
			return mm.eval(cmd)
		except RuntimeError, msg:
			info = Mel.call( "whatIs", command )
			if info.startswith( 'Presumed Mel procedure'):
				raise NameError, ( 'Unknown Mel procedure: ' + cmd )
			raise RuntimeError, msg

	@staticmethod
	def mprint(*args):
		"""mel print command in case the python print command doesn't cut it. i have noticed that python print does not appear
		in certain output, such as the rush render-queue manager."""
		mm.eval( r"""print (%s);""" % pythonToMel( ' '.join( map( str, args))) + '\n' )

	@staticmethod
	def eval( command ):
		""" same as maya.mel eval """
		return mm.eval( command )

	@staticmethod
	def _melprint( cmd, msg ):
		mm.eval( """%s %s""" % ( cmd, pythonToMel( msg ) ) )

	error = staticmethod( lambda *args: Mel._melprint( "error", *args ) )
	trace = staticmethod( lambda *args: Mel._melprint( "trace", *args ) )
	info = staticmethod( lambda *args: Mel._melprint( "print", *args ) )


class OptionVarDict( util.Singleton ):
	"""	 A singleton dictionary-like class for accessing and modifying optionVars.
	
	:note: Idea and base Implementation from PyMel, modified to adapt to mrv """
	class OptionVarList(tuple):
		def __new__( cls, key, val ):
			"""modify constructor to work with tuple"""
			newinstpreinit = tuple.__new__( cls, val )
			newinstpreinit.key = key
			return newinstpreinit

		def appendVar( self, val ):
			""" values appended to the OptionVarList with this method will be 
			added to the Maya optionVar at the key denoted by self.key. """
			if isinstance( val, basestring):
				return cmds.optionVar( stringValueAppend=[self.key,unicode(val)] )
			if isinstance( val, (bool,int) ):
				return cmds.optionVar( intValueAppend=[self.key,int(val)] )
			if isinstance( val, float):
				return cmds.optionVar( floatValueAppend=[self.key,val] )


	def __contains__(self, key):
		return cmds.optionVar( exists=key )

	def __getitem__(self, key):
		if key not in self:
			raise KeyError("OptionVar named %s did not exist" % key)
		# END raise if k not in d
		
		val = cmds.optionVar( q=key )
		if isinstance(val, list):
			val = self.OptionVarList( key, val )
		return val

	def __setitem__(self,key,val):
		if isinstance( val, basestring):
			return cmds.optionVar( stringValue=[key,unicode(val)] )
		if isinstance( val, (int,bool)):
			return cmds.optionVar( intValue=[key,int(val)] )
		if isinstance( val, float):
			return cmds.optionVar( floatValue=[key,val] )

		if isinstance( val, (list,tuple) ):
			if len(val) == 0:
				return cmds.optionVar( clearArray=key )

			if isinstance( val[0], basestring):
				cmds.optionVar( stringValue=[key,unicode(val[0])] ) # force to this datatype
				for elem in val[1:]:
					cmds.optionVar( stringValueAppend=[key,unicode(elem)] )
				return

			if isinstance( val[0], (int,bool)):
				cmds.optionVar(	 intValue=[key,int(val[0])] ) # force to this datatype
				for elem in val[1:]:
					cmds.optionVar( intValueAppend=[key,int(elem)] )
				return

			if isinstance( val[0], float):
				cmds.optionVar( floatValue=[key,val[0]] ) # force to this datatype
				for elem in val[1:]:
					cmds.optionVar( floatValueAppend=[key,float(elem)] )
				return

		raise TypeError, 'unsupported datatype: strings, ints, float, lists, and their subclasses are supported'

	def __delitem__( self, key ):
		"""Delete the optionvar identified by key"""
		cmds.optionVar( rm = str( key ) )

	def keys(self):
		return cmds.optionVar( list=True )

	def iterkeys( self ):
		""":return: iterator to option var names"""
		return iter( self.keys() )

	def itervalues( self ):
		""":return: iterator to optionvar values"""
		for key in self.iterkeys():
			yield self[ key ]

	def iteritems( self ):
		""":return: iterators to tuple of key,value pairs"""
		for key in self.iterkeys():
			yield ( key, self[ key ] )

	def get(self, key, default=None):
		if self.has_key(key):
			return self[key]
		else:
			return default

	def has_key(self, key):
		return cmds.optionVar( exists=key )

	def pop(self, key):
		val = self[ key ]
		del( self[ key ] )
		return val


# use it as singleton
optionvars = OptionVarDict()

#} END utility classes


#{ API Utilities Classes

class StandinClass( object ):
	""" Simple Function Object allowing to embed the name of the type as well as
	the metaclass object supposed to create the actual class. It mus be able to completely
	create the given class.
	
	:note: Use it at placeholder for classes that are to be created on first call, without
		vasting large amounts of memory if one wants to precreate them."""
	__slots__ = ( "clsname", "classcreator", "_createdClass" )
	
	def __init__( self, classname, classcreator=type ):
		self.clsname = classname
		self.classcreator = classcreator
		self._createdClass = None

	def createCls( self ):
		""" Create the class of type self.clsname using our classcreator - can only be called once !
		
		:return : the newly created class"""
		if self._createdClass is None:
			self._createdClass = self.classcreator( self.clsname, tuple(), {} )

		return self._createdClass

	def __call__( self, *args, **kwargs ):
		newcls = self.createCls( )
		return newcls( *args, **kwargs )


class MetaClassCreator( type ):
	""" Builds the base hierarchy for the given classname based on our
	typetree """

	def __new__( 	dagtree, module, metacls, name, bases, clsdict,
					nameToTreeFunc=uncapitalize, treeToNameFunc=capitalize ):
		"""Create a new class from hierarchy information found in dagtree and
		put it into the module if it not yet exists
		
		:param dagtree: `mrv.util.DAGTree` instance with hierarchy information
		:param module: the module instance to which to add the new classes to
		:param nameToTreeFunc: convert the class name to a name suitable for dagTree look-up
		:param treeToNameFunc: convert a value from the dag tree into a valid class name ( used for parent lookup )"""
		# recreate the hierarchy of classes leading to the current type
		nameForTree = nameToTreeFunc( name )
		parentname = None
		try:
			parentname = dagtree.parent( nameForTree )
		except networkxexc.NetworkXError:
			# we can handle and thus ignore key errors, mostly created by subclass
			# of our wrapped classes
			pass
		# END parent name handling

		parentcls = None

		# ASSURE PARENTS
		#####################
		# Parent classes must be available in advance
		if parentname is not None:
			parentclsname = treeToNameFunc( parentname )
			parentcls = module.__dict__[ parentclsname ]
			if isinstance( parentcls, StandinClass ):
				parentcls = parentcls.createCls( )
		# END if parent cls name defined

		# could be a user-defined class coming with some parents already - thus assure
		# that the auto-parent is not already in there
		# NOTE: bases is sometimes filled with types, sometimes with classes
		if parentcls and not ( parentcls in bases or isinstance( parentcls, bases ) ):
			bases += ( parentcls, )

		# create the class
		newcls = super( MetaClassCreator, metacls ).__new__( metacls, str( name ), bases, clsdict )

		# change the module - otherwise it will get our module
		newcls.__module__ = module.__name__

		# replace the dummy class in the module
		module.__dict__[ name ] = newcls



		return newcls

class CallbackEventBase( util.Event ):
	"""Allows the mapping of MMessage callbacks to mrv's event sender system.
	This event will register a new message once the first event receiver registers
	itself. Once the last event receiver deregisters, the message will be deregistered in 
	maya as well.
	
	Derived types have to implement the `_getRegisterFunction`
	
	:note: Its important that you care about deregistering your event to make sure the maya event can 
		be deregistered. Its worth knowing that the eventSender in question is strongly 
		bound to his callback event, so it cannot be deleted while the event is active."""

	#{ Utility Classes
	class CBStorageFunction(object):
		__slots__ = '_callbackID'
		def __init__(self, callbackID=None):
			self.setCallbackID(callbackID)
		
		def setCallbackID(self, callbackID):
			self._callbackID = callbackID
		
		def callbackID(self):
			return self._callbackID
		
		def removeCallback(self):
			if self._callbackID:
				api.MMessage.removeCallback(self._callbackID)
				# prevent memory leak message if possible
				if hasattr(self._callbackID, 'disown'):
					self._callbackID.disown()
				self._callbackID = None
			# END 
		
		def __call__(self, *args, **kwargs):
			return self._callbackID
	#} END utility classes

	def __init__( self, eventId, **kwargs ):
		"""Initialize our instance with the callbackID we are to represent."""
		super( CallbackEventBase, self ).__init__( **kwargs )
		self._eventID = eventId
		
	#{ Subclass Implementation Needed
	def _getRegisterFunction(self, eventID):
		"""
		:return: MMessage::register* compatible callback function which can be 
			used to register the given eventID"""
		raise NotImplementedError("To be implemented in subclass")

	#} END subclass implementation needed

	#{ CallbackID handling
	def _storeCallbackID(self, inst, callbackID):
		"""Store the given callbackID in the event sender instance. 
		We do that by registering it as function for the given instance which
		
		:return: the callback ID on call"""
		storage = self._getCallbackIDStorage(inst, create=True)
		storage.setCallbackID(callbackID)
		
	def _getCallbackIDStorage(self, inst, create=False):
		"""
		:return: Callback storage function if it exists or None
		:param create: if True, the storage will be created if needed, hence 
			you will always receive a valid storage"""
		functions = self._getFunctionSet(inst)
		storage_functions = [ cb for cb in functions if isinstance(cb, self.CBStorageFunction) ]
		if not storage_functions:
			if not create:
				return None
			
			sf = self.CBStorageFunction()
			functions.add(sf)
			return sf
		# END handle storage does not exists
		
		assert len(storage_functions) == 1, "Expecting only one storage function, found %i" % len(storage_functions)
		return storage_functions[0]
		
	def _getCallbackID(self, inst):
		""":return: stored callback ID or None"""
		storage = self._getCallbackIDStorage(inst)
		if storage is None:
			return None
		return storage.callbackID()
		
	#} END handle callback ID

	
	def send( self, inst, *args, **kwargs ):
		"""Sets our instance prior to calling the super class
		
		:note: must not be called manually"""
		# fake the instance
		self._last_inst_ref = weakref.ref(inst)
		super(CallbackEventBase, self).send(*args, **kwargs)

	def __set__(  self, inst, eventfunc ):
		eventset = self._getFunctionSet( inst )

		# REGISTER MCALLBACK IF THIS IS THE FIRST EVENTRECEIVER
		if not eventset:
			reg_method = self._getRegisterFunction(self._eventID)
			
			dyncall = lambda *args, **kwargs: self.send(inst, *args, **kwargs)
			callbackID = reg_method(self._eventID, dyncall)
			self._storeCallbackID(inst, callbackID)
		# END create event

		super( CallbackEventBase, self ).__set__( inst, eventfunc )
		
	def remove(self, eventfunc):
		"""Also removes our callback if the last receiver is gone"""
		super(CallbackEventBase, self).remove(eventfunc)
		inst = self._get_last_instance()
		functions = self._getFunctionSet( inst )
		
		# if there is only one item left, this should be our storage function
		if len(functions) == 1:
			cbstorage = iter(functions).next()
			assert isinstance(cbstorage, self.CBStorageFunction)
			
			cbstorage.removeCallback()
			functions.remove(cbstorage)
		# END dergister event
		
		
class MEnumeration(tuple):
	"""Simple enumeration class which allows access to its enumeration using 
	getattr access. 
	As it is a tuple as well, one can access the enumeration values in the right sequencial
	order"""
	def __new__(cls, sequence, name=''):
		inst = super(MEnumeration, cls).__new__(cls, sequence)
		inst.name = name
		return inst
		
	def __str__(self):
		return self.name
	
	def __repr__(self):
		return "MEnumeration(%s)" % self.name
	
	#{ Interface
	
	def nameByValue(self, value):
		""":return: name string with the given integer value
		:param value: integer value of this enumeration
		:raise ValueError: if value is not in the enumeration"""
		for n,v in self.__dict__.items():
			if not n.startswith('k') or not isinstance(v, int):
				continue
				
			if v == value:
				return n
			# END if value matches
		# END for each item in our dict
		raise ValueError("Value %i not in enumeration" % value)
		
	#} END interface
	
	@classmethod
	def create( cls, ed, mfncls ):
		"""
		:return: new instance of this type as initialized from the EnumDescriptor ed and 
			the mfncls
		"""
		emembers = list()		# temporary
		
		# get the values in the right sequence
		try:
			for em in ed:
				ev = getattr(mfncls, em)
				emembers.append(ev)
			# END for each enumeration member
		except AttributeError:
			# happens in 2008+ as they have ifdeffed items that we pick up, 
			# but which are somewhat inoffical
			pass
		# END exception handling
		
		enum = cls(emembers, name=ed.name)
		
		# assign each member by name
		try:
			for em in ed:
				ev = getattr(mfncls, em)
				setattr(enum, em, ev)
			# END for each enumeration member
		except AttributeError:
			pass
		# END exception handlign
		
		return enum
	
#} END api utility classes
