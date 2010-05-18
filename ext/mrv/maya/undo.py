# -*- coding: utf-8 -*-
"""
Contains the undo engine allowing to adjust the scene with api commands while
providing full undo and redo support.

Features
--------
 - modify dag or dg using the undo-enabled DG and DAG modifiers
 - modify values using Nodes and their plugs ( as the plugs are overridden
   to store undo information )

Limitations
-----------

 - You cannot mix mel and API proprely unless you use an MDGModifier.commandToExecute
 
 - Calling operations that flush the undo queue from within an undoable method
   causes the internal python undo stack not to be flushed, leaving dangling objects
   that might crash maya once they are undon.
  
  - WORKAROUND: Mark these methods with @notundoable and assure they are not
    called by an undoable method
    
 - calling MFn methods on a node usually means that undo is not supported for it.

Configuration
-------------
To globally disable the undo queue using cmds.undo will disable tracking of opeartions, but will
still call the mel command.

Disable the 'undoable' decorator effectively remove the surrounding mel script calls
by setting the ``MRV_UNDO_ENABLED`` environment variable to 0 ( default 1 ). 
Additionally it will turn off the maya undo queue as a convenience.

If the mrv undo queue is disabled, MPlugs will not store undo information anymore
and do not incur any overhead.

Implementing an undoable method
-------------------------------
   - decorate with @undoable
   - minimize probability that your operation will fail before creating an operation ( for efficiency )
   - only use operation's doIt() method to apply your changes
   - if you raise, you should not have created an undo operation
"""
__docformat__ = "restructuredtext"

import sys
import os

__all__ = ("undoable", "forceundoable", "notundoable", "StartUndo", "endUndo", "undoAndClear", 
           "UndoRecorder", "Operation", "GenericOperation", "GenericOperationStack", "DGModifier", 
           "DagModifier")

_undo_enabled_envvar = "MRV_UNDO_ENABLED"
_should_initialize_plugin = int(os.environ.get(_undo_enabled_envvar, True))

#{ Initialization

def __initialize():
	""" Assure our plugin is loaded - called during module intialization
	
	:note: will only load the plugin if the undo system is not disabled"""
	pluginpath = os.path.splitext( __file__ )[0] + ".py"
	if _should_initialize_plugin and not cmds.pluginInfo( pluginpath, q=1, loaded=1 ):
		cmds.loadPlugin( pluginpath )

	# assure our decorator is available !
	import __builtin__
	setattr( __builtin__, 'undoable', undoable )
	setattr( __builtin__, 'notundoable', notundoable )
	setattr( __builtin__, 'forceundoable', forceundoable )
	
	return _should_initialize_plugin



#} END initialization


#{ Undo Plugin
# when we are here, these have been imported already
import maya.OpenMaya as api
import maya.cmds as cmds
import maya.mel as mel

# cache
isUndoing = api.MGlobal.isUndoing
undoInfo = cmds.undoInfo


# Use sys as general placeholder that will only exist once !
# Global vars do not really maintain their values as modules get reinitialized
# quite often it seems
if not hasattr( sys, "_maya_stack_depth" ):
	sys._maya_stack_depth = 0
	sys._maya_stack = []

_maya_undo_enabled = int(os.environ.get(_undo_enabled_envvar, True))

if not _maya_undo_enabled:
	undoInfo(swf=0)

# command - only generate code if we are to initialize undo
# mpx takes .3 s to load and we can just safe that time
if _should_initialize_plugin:
	import maya.OpenMayaMPx as mpx
	class UndoCmd( mpx.MPxCommand ):
		kCmdName = "storeAPIUndo"
		fId = "-id"
	
		def __init__(self):
			mpx.MPxCommand.__init__(self)
			self._operations = None
	
		#{ Command Methods
		def doIt(self,argList):
			"""Store out undo information on maya's undo stack"""
			# if we reach the starting level, we can actually store the undo buffer
			# and allow us to be placed on the undo queue
			if sys._maya_stack_depth == 0:
				self._operations = sys._maya_stack
				sys._maya_stack = list()					# clear the operations list
				return
			# END if stack 0
	
	
			# still here ?
			msg = "storeAPIUndo may only be called by the top-level function"
			self.displayError( msg )
			raise RuntimeError( msg )
	
		def redoIt( self ):
			"""Called on once a redo is requested"""
			if not self._operations:
				return
	
			for op in self._operations:
				op.doIt( )
	
		def undoIt( self ):
			"""Called once undo is requested"""
			if not self._operations:
				return
	
			# run in reversed order !
			for op in reversed(self._operations):
				op.undoIt()
	
		def isUndoable( self ):
			"""
			:return: True if we are undoable - it depends on the state of our
				undo stack
			:note: we are always undoable as doIt is called first and stores operations"""
			return self._operations is not None
	
		# END command methods
	
		@staticmethod
		def creator():
			return mpx.asMPxPtr( UndoCmd() )
	
	
		# Syntax creator
		@staticmethod
		def createSyntax( ):
			syntax = api.MSyntax()
	
			# id - just for information and debugging
			syntax.addFlag( UndoCmd.fId, "-callInfo", syntax.kString )
	
			syntax.enableEdit( )
	
			return syntax
	
	
	def initializePlugin(mobject):
		mplugin = mpx.MFnPlugin(mobject)
		mplugin.registerCommand( UndoCmd.kCmdName, UndoCmd.creator, UndoCmd.createSyntax )
	
	# Uninitialize the script plug-in
	def uninitializePlugin(mobject):
		mplugin = mpx.MFnPlugin(mobject)
		mplugin.deregisterCommand( UndoCmd.kCmdName )
# END if plugin should be initialized

#} END plugin


#{ Utilities

def _incrStack( ):
	"""Indicate that a new method level was reached"""
	sys._maya_stack_depth += 1

def _decrStack( name = "unnamed" ):
	"""Indicate that a method level was exitted - and cause the
	undo queue to be stored on the command if appropriate
	We try to call the command only if needed"""
	sys._maya_stack_depth -= 1

	# store our stack on the undo queue
	if sys._maya_stack_depth == 0:
		mel.eval( "storeAPIUndo -id \""+name+"\"" )


def undoable( func ):
	"""Decorator wrapping func so that it will start undo when it begins and end undo
	when it ends. It assures that only toplevel undoable functions will actually produce
	an undo event
	To mark a function undoable, decorate it:
	
	>>> @undoable
	>>> def func( ):
	>>> 	pass
	
	:note: Using decorated functions appears to be only FASTER  than implementing it
		manually, thus using these is will greatly improve code readability
	:note: if you use undoable functions, you should mark yourself undoable too - otherwise the
		functions you call will create individual undo steps
	:note: if the undo queue is disabled, the decorator does nothing"""
	if not _maya_undo_enabled:
		return func

	name = "unnamed"
	if hasattr( func, "__name__" ):
		name = func.__name__

	def undoableDecoratorWrapFunc( *args, **kwargs ):
		"""This is the long version of the method as it is slightly faster than
		simply using the StartUndo helper"""
		_incrStack( )
		try:
			return func( *args, **kwargs )
		finally:
			_decrStack( name )
		# END try finally
	# END wrapFunc

	undoableDecoratorWrapFunc.__name__ = name
	return undoableDecoratorWrapFunc

def forceundoable( func ):
	"""As undoable, but will enable the undo queue if it is currently disabled. It will 
	forcibly enable maya's undo queue.
	
	:note: can only be employed reasonably if used in conjunction with `undoAndClear`
		as it will restore the old state of the undoqueue afterwards, which might be off, thus
		rendering attempts to undo impossible"""
	undoable_func = undoable( func )
	def forcedUndo( *args, **kwargs ):
		disable = False
		if not undoInfo( q=1, st=1 ):
			disable = True
			undoInfo( swf=1 )
		# END undo info handling
		try:
			return undoable_func( *args, **kwargs )
		finally:
			if disable:
				undoInfo( swf=0 )
		# END exception handling
	# END forced undo function
	return forcedUndo

def notundoable( func ):
	"""Decorator wrapping a function into a muteUndo call, thus all undoable operations
	called from this method will not enter the UndoRecorder and thus pollute it.
	
	:note: use it if your method cannot support undo, butcalls undoable operations itself
	:note: all functions using a notundoable should be notundoable themselves
	:note: does nothing if the undo queue is globally disabled"""
	if not _maya_undo_enabled:
		return func
	
	def notundoableDecoratorWrapFunc( *args, **kwargs ):
		"""This is the long version of the method as it is slightly faster than
		simply using the StartUndo helper"""
		prevstate = undoInfo( q=1, st=1 )
		undoInfo( swf = 0 )
		try:
			return func( *args, **kwargs )
		finally:
			undoInfo( swf = prevstate )
		# END exception handling
	# END wrapFunc

	if hasattr( func, "__name__" ):
		notundoableDecoratorWrapFunc.__name__ = func.__name__

	return notundoableDecoratorWrapFunc


class MuteUndo( object ):
	"""Instantiate this class to disable the maya undo queue - on deletion, the
	previous state will be restored
	
	:note: useful if you want to save the undo overhead involved in an operation,
		but assure that the previous state is always being reset"""
	__slots__ = ( "prevstate", )
	def __init__( self ):
		self.prevstate = cmds.undoInfo( q=1, st=1 )
		cmds.undoInfo( swf = 0 )

	def __del__( self ):
		cmds.undoInfo( swf = self.prevstate )


class StartUndo( object ):
	"""Utility class that will push the undo stack on __init__ and pop it on __del__
	
	:note: Prefer the undoable decorator over this one as they are easier to use and FASTER !
	:note: use this class to assure that you pop undo when your method exists"""
	__slots__ = ( "id", )
	def __init__( self, id = None ):
		self.id = id
		_incrStack( )

	def __del__( self ):
		if self.id:
			_decrStack( self.id )
		else:
			_decrStack( )


def startUndo( ):
	"""Call before you start undoable operations
	
	:note: prefer the @undoable decorator"""
	_incrStack()

def endUndo( ):
	"""Call before your function with undoable operations ends
	
	:note: prefer the @undoable decorator"""
	_decrStack()

def undoAndClear( ):
	"""Undo all operations on the undo stack and clear it afterwards. The respective
	undo command will do nothing once undo, but would undo all future operations.
	The state of the undoqueue is well defined afterwards, but callers may stop functioning
	if their changes have been undone.
	
	:note: can be used if you need control over undo in very specific operations and in
		a well defined context"""
	operations = sys._maya_stack
	sys._maya_stack = list()

	# run in reversed order !
	for op in reversed(operations):
		op.undoIt()


class UndoRecorder( object ):
	"""Utility class allowing to undo and redo operations on the python command 
	stack so far to be undone and redone separately and independently of maya's 
	undo queue.
	
	It can be used to define sections that need to be undone afterwards, for example
	to reset a scene to its original state after it was prepared for export.
	
	Use the `startRecording` method to record all future undoable operations 
	onto the stack. `stopRecording` will finalize the operation, allowing 
	the `undo` and `redo` methods to be used.
	
	If you never call startRecording, the instance does not do anything.
	If you call startRecording and stopRecording but do not call `undo`, it 
	will integrate itself transparently with the default undo queue.
	
	:note: as opposed to `undoAndClear`, this utility may be used even if the 
		user is not at the very beginning of an undoable operation.
	:note: If this utility is used incorrectly, the undo queue will be in an 
		inconsistent state which may crash maya or cause unexpected behaviour
	:note: You may not interleave the start/stop recording areas of different 
		instances which could happen easily in recursive calls."""
	__slots__ = ("_orig_stack", "_recorded_commands", "_undoable_helper", "_undo_called")
	
	# prevents recursive access
	_is_recording = False
	_disable_undo = False 
	
	def __init__(self):
		self._orig_stack = None
		self._recorded_commands = None
		self._undoable_helper = None
		self._undo_called =False
	
	def __del__(self):
		try:
			self.stopRecording()
		except AssertionError:
			# invalid isntances shouldn't bark
			pass
		# END exception handling
		
	#{ Interface 
	
	def startRecording(self):
		"""Start recording all future undoable commands onto this stack.
		The previous stack will be safed and restored once this class gets destroyed
		or once `stopRecording` gets called.
		
		:note: this method may only be called once, subsequent calls have no effect
		:note: This will forcibly enable the undo queue if required until 
			stopRecording is called."""
		if self._orig_stack is not None:
			return
			
		if self._is_recording:
			raise AssertionError("Another instance already started recording")
			
		# force undo enabled
		if not undoInfo( q=1, st=1 ):
			self.__class__._disable_undo = True
			cmds.undoInfo( swf=1 )
		# END undo info handling
		
		self._undoable_helper = StartUndo()			# assures we have a stack
		
		self.__class__._is_recording = True
		self._orig_stack = sys._maya_stack
		sys._maya_stack = list()			# will record future commands 
		
		# put ourselves on the previous undo queue which allows us to integrate 
		# with the original undo stack if that is required
		self._orig_stack.append(self)
		
	def stopRecording(self):
		"""Stop recording of undoable comamnds and restore the previous command stack.
		The instance is now ready to undo and redo the recorded commands
		
		:note: this method may only be called once, subsequent calls have no effect"""
		if self._recorded_commands is not None:
			return
		
		try:
			if not self._is_recording:
				raise AssertionError("startRecording was not called")
				
			if self._orig_stack is None:
				raise AssertionError("startRecording was not called on this instance, but on another one")
			
			self.__class__._is_recording = False
			self._recorded_commands = sys._maya_stack
			sys._maya_stack = self._orig_stack
			
			# restore previous undo queue state
			if self._disable_undo:
				self.__class__._disable_undo = False
				cmds.undoInfo( swf=0 )
			# END handle undo
		finally:
			# tigger deletion
			self._undoable_helper = None
		# END assure we finish our undo
		
		
	def undo(self):
		"""Undo all stored operations
		
		:note: Must be called at the right time, otherwise the undo queue is in an 
			inconsistent state.
		:note: If this method is never being called, the undo-stack will undo itself
			as part of mayas undo queue, and thus behaves transparently
		:raise AssertionError: if called before `stopRecording` as called"""
		if self._recorded_commands is None:
			raise AssertionError("Undo called before stopRecording")
			
		for op in reversed(self._recorded_commands):
			op.undoIt()
		# END for each operation to undo
		self._undo_called = True
		
	def redo(self):
		"""Redo all stored operations after they have been undone
		:raise AssertionError: if called before `stopRecording`"""
		if self._recorded_commands is None:
			raise AssertionError("Redo called before stopRecording")
			
		for op in self._recorded_commands:
			op.doIt()
		# END for each operation to redo
		
		# this reverts the effect of the undo
		self._undo_called = False
		
	#} END interface 
	
	#{ Internal
	def doIt( self ):
		"""Called only if the user didn't call undo"""
		if self._undo_called or not self._recorded_commands:
			return
			
		# we have not been called, and now the user hits redo on the whole 
		# operation 
		for op in self._recorded_commands:
			op.doIt()
		# END for each operation

	def undoIt( self ):
		"""called only if the user didnt call undo"""
		if self._undo_called or not self._recorded_commands:
			return
			
		# we have not be undone, hence we are part of the default undo queue
		for op in reversed(self._recorded_commands):
			op.undoIt()
		# END for each operation
	#} END internal
	
#} END utilities



#{ Operations

class Operation( object ):
	"""Simple command class as base for all operations
	All undoable/redoable operation must support it
	
	:note: only operations may be placed on the undo stack !"""
	__slots__ = tuple()
	
	def __init__( self ):
		"""Operations will always be placed on the undo queue if undo is available
		This happens automatically upon creation
		
		:note: assure subclasses call the superclass init !"""
		if _maya_undo_enabled and not isUndoing() and undoInfo( q=1, st=1 ):
			# sanity check !
			if sys._maya_stack_depth < 1:
				raise AssertionError( "Undo-Stack was %i, but must be at least 1 before operations can be put - check your code !" % sys._maya_stack_depth )
			# END sanity check
			sys._maya_stack.append( self )
		# END if not undoing and undo is enabled
	def doIt( self ):
		"""Do whatever you do"""
		raise NotImplementedError

	def undoIt( self ):
		"""Undo whatever you did"""
		raise NotImplementedError


class GenericOperation( Operation ):
	"""Simple oeration allowing to use a generic doit and untoit call to be accessed
	using the operation interface.
	
	In other words: If you do not want to derive from operation just because you would like
	to have your own custom (  but simple ) do it and undo it methods, you would just
	use this all-in-one operation"""

	__slots__ = (  "_dofunc", "_doargs", "_dokwargs", "_doitfailed",
					"_undofunc", "_undoargs", "_undokwargs" )

	def __init__( self ):
		"""intiialize our variables"""
		Operation.__init__( self )
		self._dofunc = None
		self._doargs = None
		self._dokwargs = None
		self._doitfailed = False	# keep track whether we may actually undo something

		self._undofunc = None
		self._undoargs = None
		self._undokwargs = None

	def setDoitCmd( self, func, *args, **kwargs ):
		"""Add the doit call to our instance"""
		self._dofunc = func
		self._doargs = args
		self._dokwargs = kwargs

	def setUndoitCmd( self, func, *args, **kwargs ):
			"""Add the undoit call to our instance"""
			self._undofunc = func
			self._undoargs = args
			self._undokwargs = kwargs

	def doIt( self ):
		"""Execute the doit command
		
		:return: result of the doit command"""
		try:
			return self._dofunc( *self._doargs, **self._dokwargs )
		except:
			self._doitfailed = True

	def undoIt( self ):
		"""Execute undoit if doit did not fail"""
		if self._doitfailed:
			return

		self._undofunc( *self._undoargs, **self._undokwargs )



class GenericOperationStack( Operation ):
	"""Operation able to undo generic callable commands ( one or multiple ). It would be used
	whenever a simple generic operatino is not sufficient
	
	In your api command, create a GenericOperationStack operation instance, add your (mel) commands
	that should be executed in a row as Call. To apply them, call doIt once ( and only once ! ).
	You can have only one command stored, or many if they should be executed in a row.
	The vital part is that with each do command, you supply an undo command.
	This way your operations can be undone and redone once undo / redo is requested
	
	:note: this class works well with `mrv.util.Call`
	:note: to execute the calls added, you must call `doIt` or `addCmdAndCall` - otherwise
		the undoqueue might brake if exceptions occour !
	:note: your calls may use MEL commands safely as the undo-queue will be torn off during execution
	:note: Undocommand will be applied in reversed order automatically"""

	__slots__ = ( "_docmds", "_undocmds", "_undocmds_tmp" )

	def __init__( self ):
		"""intiialize our variables"""
		Operation.__init__( self )
		self._docmds = list()				# list of Calls
		self._undocmds = list()				# will store reversed list !
		self._undocmds_tmp = list()			# keeps undo until their do was verified !


	def doIt( self ):
		"""Call all doIt commands stored in our instance after temporarily disabling the undo queue"""
		prevstate = undoInfo( q=1, st=1 )
		undoInfo( swf=False )

		try:
			if self._undocmds_tmp:
				# verify each doit command before we shedule undo
				# if it raies, we will not schedule the respective command for undo
				for i,call in enumerate( self._docmds ):
					try:
						call()
					except:
						# forget about this and all following commands and reraise
						del( self._docmds[i:] )
						self._undocmds_tmp = None		# next time we only execute the cmds that worked ( and will undo only them )
						raise
					else:
						self._undocmds.insert( 0, self._undocmds_tmp[i] )	# push front
				# END for each call
				self._undocmds_tmp = None			# free memory
			else:
				for call in self._docmds:
					call()
				# END for each do calll
			# END if undo cmds have been verified
		finally:
			undoInfo( swf=prevstate )

	def undoIt( self ):
		"""Call all undoIt commands stored in our instance after temporarily disabling the undo queue"""
		# NOTE: the undo list is already reversed !
		prevstate = undoInfo( q=1, st=1 )
		undoInfo( swf=False )

		# sanity check
		try:
			if self._undocmds_tmp:
				raise AssertionError( "Tmp undo commands queue was not None on first undo call - this means doit has not been called before - check your code!" )

			for call in self._undocmds:
				call()
		finally:
			undoInfo( swf=prevstate )

	def addCmd( self, doCall, undoCall ):
		"""Add a command to the queue for later application
		
		:param doCall: instance supporting __call__ interface, called on doIt
		:param undoCall: instance supporting __call__ interface, called on undoIt"""

		self._docmds.append( doCall )		# push
		self._undocmds_tmp.append( undoCall )

	def addCmdAndCall( self, doCall, undoCall ):
		"""Add commands to the queue and execute it right away - either always use
		this way to add your commands or the `addCmd` method, never mix them !
		
		:return: return value of the doCall
		:note: use this method if you need the return value of the doCall right away"""
		prevstate = undoInfo( q=1, st=1 )
		undoInfo( swf=False )

		rval = doCall()
		self._docmds.append( doCall )
		self._undocmds.insert( 0, undoCall )

		undoInfo( swf=prevstate )
		return rval


class DGModifier( Operation ):
	"""Undo-aware DG Modifier - using it will automatically put it onto the API undo queue
	
	:note: You MUST call doIt() before once you have instantiated an instance, even though you
		have nothing on it. This requiredment is related to the undo queue mechanism
	:note: May NOT derive directly from dg modifier!"""
	__slots__ = ( "_modifier", )
	_modifier_class_ = api.MDGModifier		# do be overridden by subclasses

	def __init__( self ):
		"""Initialize our base classes explicitly"""
		Operation.__init__( self )
		self._modifier = self._modifier_class_( )

	def __getattr__( self , attr ):
		"""Always return the attribute of the dg modifier - it is fully compatible
		to our operation interface"""
		return getattr( self._modifier, attr )

	def doIt( self ):
		"""Override from Operation"""
		return self._modifier.doIt()

	def undoIt( self ):
		"""Override from Operation"""
		return self._modifier.undoIt()


class DagModifier( DGModifier ):
	"""undo-aware DAG modifier, copying all extra functions from DGModifier"""
	__slots__ = tuple()
	_modifier_class_ = api.MDagModifier
	

#} END operations


