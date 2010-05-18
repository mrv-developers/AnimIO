# -*- coding: utf-8 -*-
"""All kinds of utility methods and classes that are used in more than one modules """
import networkx as nx
from collections import deque as Deque
import weakref
import inspect
import itertools
from interface import iDuplicatable

import logging
log = logging.getLogger("mrv.maya.ui.util")

__docformat__ = "restructuredtext"
__all__ = ("decodeString", "decodeStringOrList", "capitalize", "uncapitalize", 
	"pythonIndex", "copyClsMembers", "packageClasses", "iterNetworkxGraph", 
           "Call", "CallAdv", "WeakInstFunction", "Event", "EventSender", 
           "InterfaceMaster", "Singleton", "CallOnDeletion", 
           "DAGTree", "PipeSeparatedFile", "MetaCopyClsMembers", "And", "Or") 
           

def decodeString( valuestr ):
	""" :return: int,float or str from string valuestr - a string that encodes a
		numeric value or a string
	
	:raise TypeError: if the type could not be determined"""
	# put this check here intentionally - want to allow
	if not isinstance( valuestr, basestring ):
		raise TypeError( "Invalid value type: only int, long, float and str are allowed", valuestr )

	types = ( long, float )
	for numtype in types:
		try:
			val = numtype( valuestr )

			# truncated value ?
			if val != float( valuestr ):
				continue

			return val
		except ( ValueError,TypeError ):
			continue
	# END for each numeric type

	# its just a string and not a numeric type
	return valuestr

def decodeStringOrList( valuestrOrList ):
	"""
	:return: as `decodeString`, but returns a list of appropriate values if
		the input argument is a list or tuple type"""
	if isinstance( valuestrOrList , ( list, tuple ) ):
		return [ decodeString( valuestr ) for valuestr in valuestrOrList ]

	return decodeString( valuestrOrList )

def capitalize(s):
	""":return: s with first letter capitalized"""
	return s[0].upper() + s[1:]

def uncapitalize(s, preserveAcronymns=False):
	""":return: ``s`` with first letter lower case
	:param preserveAcronymns: enabled ensures that 'NTSC' does not become 'nTSC'
	:note: from pymel
	"""
	try:
		if preserveAcronymns and s[0:2].isupper():
			return s
	except IndexError: pass

	return s[0].lower() + s[1:]

def pythonIndex( index, length ):
	"""Compute the actual index based on the given index and array length, thus
	-1 will result in the last array element's index"""
	if index > -1: return index
	return length + index			# yes, length be better 1 or more ;)

def copyClsMembers( sourcecls, destcls, overwritePrefix = None, forbiddenMembers = list(), copyNamespaceGlobally=None):
	"""Copy the members or sourcecls to destcls while ignoring member names in forbiddenMembers
	It will only copy mebers of this class, not its base classes
	
	:param sourcecls: class whose members should be copied
	:param destcls: class to receive members from sourcecls
	:param overwritePrefix: if None, existing members on destcls will not be overwritten, if string,
		the original method will be stored in a name like prefix+originalname ( allowing you to access the
		original method lateron )
	:param copyNamespaceGlobally: if not None, the variable contains the name of the namespace as string 
		whose methods should also be copied into the global namespace, possibly overwriting existing ones.
		For instance, 'nsmethod' will be available as obj.nsmethod and as obj.method if the namespace value was 'ns.
		The forbiddenMembers list is applied to the original as well as the global name
	:note: this can be useful if you cannot inherit from a class directly because you would get
		method resolution order problems
	:note: see also the `MetaCopyClsMembers` meta class"""
	for orig_name,member in sourcecls.__dict__.iteritems():
		names = [orig_name]
		if copyNamespaceGlobally is not None and orig_name.startswith(copyNamespaceGlobally):
			names.append(orig_name[len(copyNamespaceGlobally):])	# truncate namespace
		# END handle namespace removal
		
		for name in names:
			if name in forbiddenMembers:
				continue
			try:
				# store original - overwritten members must still be able to access it
				if hasattr( destcls, name ):
					if not overwritePrefix:
						continue
					morig = getattr( destcls, name )
					type.__setattr__( destcls, overwritePrefix+name, morig )
				type.__setattr__( destcls, name, member )
			except TypeError:
				pass
		# END for each name
	# END for each memebr in sourcecls

def packageClasses( importBase, packageFile, predicate = lambda x: True ):
	"""
	:return: all classes of modules of the given package file that additionally
		match given predicate
	:param importBase: longest import base path whose submodules contain the classes to import
	:param packageFile: the filepath to the package, as given in your __file__ variables
	:param predicate: receives the class and returns True if it is a class you are looking for"""
	from glob import glob
	import os

	packageDir = os.path.dirname( packageFile )

	# get all submodules
	basenameNoExt = lambda n: os.path.splitext( os.path.split( n )[1] )[0]
	pymodules = itertools.chain( glob( os.path.join( packageDir, "*.py" ) ), glob( os.path.join( packageDir, "*.pyc" ) ) ) 
	pymodules = [ basenameNoExt( m ) for m in pymodules
							if not os.path.basename( m ).startswith( '_' ) ]

	outclasses = []
	classAndCustom = lambda x: inspect.isclass( x ) and predicate( x )
	for modulename in pymodules:
		modobj = __import__( "%s.%s" % ( importBase, modulename ), globals(), locals(), [''] )
		for name,obj in inspect.getmembers( modobj, predicate = classAndCustom ):
			outclasses.append( obj )
	# import the modules
	return outclasses

def iterNetworkxGraph( graph, startItem, direction = 0, prune = lambda i,g: False,
					   stop = lambda i,g: False, depth = -1, branch_first=True,
					   visit_once = True, ignore_startitem=1 ):
	""":return: iterator yielding pairs of depth, item 
	:param direction: specifies search direction, either :
		0 = items being successors of startItem
		1 = items being predecessors of startItem
	:param prune: return True if item d,i in graph g should be pruned from result.
		d is the depth of item i
	:param stop: return True if item d,i in graph g, d is the depth of item i
		stop the search in that direction. It will not be returned.
	:param depth: define at which level the iteration should not go deeper
		if -1, there is no limit
		if 0, you would only get startitem.
		i.e. if 1, you would only get the startitem and the first level of predessessors/successors
	:param branch_first: if True, items will be returned branch first, otherwise depth first
	:param visit_once: if True, items will only be returned once, although they might be encountered
		several times
	:param ignore_startitem: if True, the startItem will be ignored and automatically pruned from
		the result
	:note: this is an adjusted version of `dge.iterShells`"""
	visited = set()
	stack = Deque()
	stack.append( ( 0 , startItem ) )		# startitem is always depth level 0

	def addToStack( stack, lst, branch_first, dpth ):
		if branch_first:
			reviter = ( ( dpth , lst[i] ) for i in range( len( lst )-1,-1,-1) )
			stack.extendleft( reviter )
		else:
			stack.extend( ( dpth,item ) for item in lst )
	# END addToStack local method

	# adjust function to define direction
	directionfunc = graph.successors
	if direction == 1:
		directionfunc = graph.predecessors

	while stack:
		d, item = stack.pop()			# depth of item, item

		if item in visited:
			continue

		if visit_once:
			visited.add( item )

		oitem = (d, item)
		if stop( oitem, graph ):
			continue

		skipStartItem = ignore_startitem and ( item == startItem )
		if not skipStartItem and not prune( oitem, graph ):
			yield oitem

		# only continue to next level if this is appropriate !
		nd = d + 1
		if depth > -1 and nd > depth:
			continue

		addToStack( stack, directionfunc( item ), branch_first, nd )
	# END for each item on work stack



class Call( object ):
	"""Call object encapsulating any code, thus providing a simple facade for it
	:note: derive from it if a more complex call is required"""
	__slots__ = ( "func", "args", "kwargs" )
	
	def __init__( self, func, *args,**kwargs ):
		"""Initialize object with function to call once this object is called"""
		self.func = func
		self.args = args
		self.kwargs = kwargs

	def __call__( self, *args, **kwargs ):
		"""Execute the stored function on call
		:note: having ``args`` and ``kwargs`` set makes it more versatile"""
		return self.func( *self.args, **self.kwargs )


class CallAdv( Call ):
	"""Advanced call class providing additional options:
	
	merge_args: 
		if True, default True, incoming arguments will be prepended before the static ones
	merge_kwargs: 
		if True, default True, incoming kwargs will be merged into the static ones """
	__slots__ = ( "merge_args", "merge_kwargs" )
	
	def __init__( self, func, *args, **kwargs ):
		self.merge_args = kwargs.pop( "merge_args", True )
		self.merge_kwargs = kwargs.pop( "merge_kwargs", True )

		super( CallAdv, self ).__init__( func, *args, **kwargs )

	def __call__( self, *inargs, **inkwargs ):
		"""Call with merge support"""
		args = self.args
		if self.merge_args:
			args = list( inargs )
			args.extend( self.args )

		if self.merge_kwargs:
			self.kwargs.update( inkwargs )

		return self.func( *args, **self.kwargs )


class WeakInstFunction( object ):
	"""Create a proper weak instance to an instance function by weakly binding
	the instance, not the bound function object.
	When called, the weakreferenced instance pointer will be retrieved, if possible,
	to finally make the call. If it could not be retrieved, the call
	will do nothing."""
	__slots__ = ( "_weakinst", "_clsfunc" )

	def __init__( self, instancefunction ):
		self._weakinst = weakref.ref( instancefunction.im_self )
		self._clsfunc = instancefunction.im_func

	def __eq__(self, other):
		return hash(self) == hash(other)

	def __hash__(self):
		return hash((self._clsfunc,  self._weakinst()))

	def __call__( self, *args, **kwargs ):
		"""
		:raise LookupError: if the instance referred to by the instance method
			does not exist anymore"""
		inst = self._weakinst()
		if inst is None:	# went out of scope
			raise LookupError( "Instance for call to %s has been deleted as it is weakly bound" % self._clsfunc.__name__ )

		return self._clsfunc( inst, *args, **kwargs )


class Event( object ):
	"""Descriptor allowing to easily setup callbacks for classes derived from
	EventSender"""
	_inst_event_attr = '__events__'	# dict with event -> set() relation
	
	#{ Configuration
	# if true, functions will be weak-referenced - its useful if you use instance
	# variables as callbacks
	use_weakref = True

	# if True, callback handlers throwing an exception will immediately be
	# removed from the callback list
	remove_on_error = False
	
	
	# If not None, this value overrides the corresponding value on the EventSender class
	sender_as_argument = None
	#} END configuration

	# internally used to keep track of the current sender. Is None if no event
	# is being fired
	_curSender = None

	def __init__( self, **kwargs ):
		"""
		:param kwargs:
			 * weak: if True, default class configuration use_weakref, weak
				references will be created for event handlers, if False it will be strong
				references
			 * remove_failed: if True, defailt False, failed callback handlers
			 	will be removed silently"""
		self.use_weakref = kwargs.get( "weak", self.__class__.use_weakref )
		self.remove_on_error = kwargs.get( "remove_failed", self.__class__.remove_on_error )
		self.sender_as_argument = kwargs.get("sender_as_argument", self.__class__.sender_as_argument)
		self._last_inst_ref = None

	def _func_to_key( self, eventfunc ):
		"""
		:return: an eventfunction suitable to be used as key in our instance
			event set"""
		if self.use_weakref:
			if inspect.ismethod( eventfunc ):
				eventfunc = WeakInstFunction( eventfunc )
			else:
				eventfunc = weakref.ref( eventfunc )
			# END instance function special handling
		# END if use weak ref
		return eventfunc

	def _key_to_func( self, eventkey ):
		""":return: event function from the given eventkey as stored in our events set.
		:note: this is required as the event might be weakreffed or not"""
		if self.use_weakref:
			if isinstance( eventkey, WeakInstFunction ):
				return eventkey
			else:
				return eventkey()
			# END instance method handling
		# END weak ref handling
		return eventkey

	def _get_last_instance(self):
		""":return: The last instance that retrieved us"""
		if self._last_inst_ref is None or self._last_inst_ref() is None:
			raise TypeError("Cannot send events through class descriptor")
		return self._last_inst_ref()

	def __set__( self, inst, eventfunc ):
		"""Set a new event to our object"""
		self._getFunctionSet(inst).add( self._func_to_key( eventfunc ) )

	def __get__( self, inst, cls = None ):
		"""Always return self, but keep the instance in case
		we someone wants to send an event."""
		if inst is not None:
			inst = weakref.ref(inst)
		# END handle instance
		self._last_inst_ref = inst  
		return self
		
	def _getFunctionSet(self, inst):
		""":return: function set of the given instance containing functions of our event"""
		if not hasattr( inst, self._inst_event_attr ):
			setattr( inst, self._inst_event_attr, dict() )
		# END initialize set
		
		ed = getattr( inst, self._inst_event_attr )
		try:
			return ed[self]
		except KeyError:
			return ed.setdefault(self, set())
		# END handle self -> set relation
	#{ Interface
		
	def send( self, *args, **kwargs ):
		"""Send our event using the given args
		
		:note: if an event listener is weak referenced and goes out of scope
		:note: will catch all event exceptions trown by the methods called
		:return: False if at least one event call threw an exception, true otherwise"""
		inst = self._get_last_instance()
		callbackset = self._getFunctionSet( inst )
		success = True
		failed_callbacks = list()
		
		sas = inst.sender_as_argument
		if self.sender_as_argument is not None:
			sas = self.sender_as_argument
		# END event override
		
		# keep the sender
		Event._curSender = inst
		
		for function in callbackset:
			try:
				func = self._key_to_func( function )
				if func is None:
					log.warn("Listener for callback of %s was not available anymore" % self)
					failed_callbacks.append( function )
					continue
				# END handle no-func

				try:
					if sas:
						func( inst, *args, **kwargs )
					else:
						func( *args, **kwargs )
				except LookupError, e:
					# thrown if self in instance methods went out of scope
					if inst.reraise_on_error:
						raise 
					log.error(str( e ))
					failed_callbacks.append( function )
				# END sendder as argument
			except Exception, e :
				if self.remove_on_error:
					failed_callbacks.append( function )
				
				if inst.reraise_on_error:
					raise 
				
				log.error(str( e ))
				success = False
		# END for each registered event

		# remove failed listeners
		for function in failed_callbacks:
			callbackset.remove( function )

		Event._curSender = None
		return success

	# Alias, to make event sending even easier
	__call__ = send

	def remove( self, eventfunc ):
		"""remove the given function from this event
		:note: will not raise if eventfunc does not exist"""
		inst = self._get_last_instance()
		eventfunc = self._func_to_key( eventfunc )
		try:
			self._getFunctionSet( inst ).remove( eventfunc )
		except KeyError:
			pass

	def duplicate( self ):
		inst = self.__class__( "" )
		inst._name = self._name	
		inst.use_weakref = self.use_weakref
		inst.remove_on_error = self.remove_on_error
		inst.sender_as_argument = self.sender_as_argument
		return inst
		
	#} END interface 

# END event class

class EventSender( object ):
	"""Base class for all classes that want to provide a common callback interface
	to supply event information to clients.
	
	**Usage**:
	Derive from this class and define your callbacks like:
	
		>>> event = Event( )
		>>> # Call it using
		>>> self.event.send( [*args][,**kwargs]] )

		>>> # Users register using
		>>> yourinstance.event = callable

		>>> # and deregister using
		>>> yourinstance.event.remove( callable )

	:note: if use_weakref is True, we will weakref the eventfunction, and deal
		properly with instance methods which would go out of scope immediatly otherwise

	:note: using weak-references to ensure one does not keep objects alive,
		see `Event.use_weakref`"""
	__slots__ = tuple()
	
	#{ Configuration
	# if True, the sender, thus self of an instance of this class, will be put
	# as first arguments to functions when called for a specific event
	sender_as_argument = False
	
	# if True, exceptions thrown when sending events will be reraised immediately
	# and may stop execution of the event sender as well
	reraise_on_error = False
	#} END configuration

	@classmethod
	def listEventNames( cls ):
		""":return: list of event ids that exist on our class"""
		return [ name for name,member in inspect.getmembers( cls, lambda m: isinstance( m, Event ) ) ]

	def clearAllEvents(self):
		"""Remove all event receivers for all events registered in this instance.
		
		:note: This usually doesn't need to be called directly, but might be useful 
			in conjunction with other system that do not release your strongly bound 
			instance"""
		# call remove once for each registered method to properly deregister them
		for en in self.listEventNames():
			event = getattr(self, en)
			for key in event._getFunctionSet(self).copy():
				event.remove(event._key_to_func(key))
			# END for each function key
		# END for each event whose methods are to clear 
		
	def sender(self):
		""":return: instance which sent the event you are currently processing
		:raise ValueError: if no event is currently in progress"""
		if Event._curSender is None:
			raise ValueError("Cannot return sender as no event is being sent")
		return Event._curSender
	

class InterfaceMaster( iDuplicatable ):
	"""Base class making the derived class an interface provider, allowing interfaces
	to be set, queried and used including build-in use"""
	__slots__ = ( "_idict", )
	#{ Configuration
	im_provide_on_instance = True			 # if true, interfaces are available directly through the class using descriptors
	#} END configuration

	#{ Helper Classes
	class InterfaceDescriptor( object ):
		"""Descriptor handing out interfaces from our interface dict
		They allow access to interfaces directly through the InterfaceMaster without calling
		extra functions"""

		def __init__( self, interfacename ):
			self.iname = interfacename			# keep name of our interface

		def __get__( self, inst, cls = None ):
			# allow our instance to be manipulated if accessed through the class
			if inst is None:
				return self

			try:
				return inst.interface( self.iname )
			except KeyError:
				raise AttributeError( "Interface %s does not exist" % self.iname )

		def __set__( self, value ):
			raise ValueError( "Cannot set interfaces through the instance - use the setInterface method instead" )


	class _InterfaceHandler( object ):
		"""Utility class passing all calls to the stored InterfaceBase, updating the
		internal caller-id"""
		def __init__( self, ibase ):
			self.__ibase = ibase
			self.__callerid = ibase._num_callers
			ibase._num_callers += 1

			ibase._current_caller_id = self.__callerid		# assure the callback finds the right one
			ibase.givenToCaller( )

		def __getattr__( self, attr ):
			self.__ibase._current_caller_id = self.__callerid 	# set our caller
			return getattr( self.__ibase, attr )

		def __del__( self ):
			self.__ibase.aboutToRemoveFromCaller( )
			self.__ibase._num_callers -= 1
			self.__ibase._current_caller_id = -1


	class InterfaceBase( object ):
		"""If your interface class is derived from this base, you get access to
		access to call to the number of your current caller.
		
		:note: You can register an InterfaceBase with several InterfaceMasters and
			share the caller count respectively"""
		__slots__ = ( "_current_caller_id", "_num_callers" )
		def __init__( self ):
			self._current_caller_id	 = -1 # id of the caller currently operating on us
			self._num_callers = 0		# the amount of possible callers, ids range from 0 to (num_callers-1)

		def numCallers( self ):
			""":return: number possible callers"""
			return self._num_callers

		def callerId( self ):
			"""Return the number of the caller that called your interface method
			
			:note: the return value of this method is undefined if called if the
				method has been called by someone not being an official caller ( like yourself )"""
			return self._current_caller_id

		def givenToCaller( self ):
			"""Called once our interface has been given to a new caller.
			The caller has not made a call yet, but its id can be queried"""
			pass

		def aboutToRemoveFromCaller( self ):
			"""Called once our interface is about to be removed from the current
			caller - you will not receive a call from it anymore """
			pass

	#} END helper classes

	#{ Object Overrides
	def __init__( self ):
		"""Initialize the interface base with some tracking variables"""
		self._idict = dict()			# keep interfacename->interfaceinstance relations

	#} END object overrides

	def copyFrom( self, other, *args, **kwargs ):
		"""Copy all interface from other to self, use they duplciate method if
		possibly """
		for ifname, ifinst in other._idict.iteritems():
			myinst = ifinst
			if hasattr( ifinst, "duplicate" ):
				myinst = ifinst.duplicate( )

			self.setInterface( ifname, myinst )
		# END for each interface in other


	#{ Interface
	def setInterface( self, interfaceName, interfaceInstance ):
		"""Set the given interfaceInstance to be handed out once an interface
		with interfaceName is requested from the provider base
		
		:param interfaceName: should start with i..., i.e. names would be iInterface
			The name can be used to refer to the interface later on
		:param interfaceInstance: instance to be handed out once an interface with the
			given name is requested by the InterfaceMaster or None
			if None, the interface will effectively be deleted
		:raise ValueError: if given InterfaceBase has a master already """
		if interfaceInstance is None:			# delete interface ?
			# delete from dict
			try:
				del( self._idict[ interfaceName ] )
			except KeyError:
				pass

			# delete class descriptor
			if self.im_provide_on_instance:
				try:
					delattr( self.__class__, interfaceName )
				except AttributeError:
					pass
			# END del on class

		# END interface deleting
		else:
			self._idict[ interfaceName ] = interfaceInstance

			# set on class ?
			if self.im_provide_on_instance:
				setattr( self.__class__, interfaceName, self.InterfaceDescriptor( interfaceName ) )

		# provide class variables ?

	def interface( self, interfaceName ):
		""":return: an interface registered with interfaceName
		:raise ValueError: if no such interface exists"""
		try:
			iinst = self._idict[ interfaceName ]

			# return wrapper if we can, otherwise just
			if isinstance( iinst, self.InterfaceBase ):
				return self._InterfaceHandler( iinst )
			else:
				return iinst
		except KeyError:
			raise ValueError( "Interface %s does not exist" % interfaceName )

	def listInterfaces( self ):
		""":return: list of names indicating interfaces available at our InterfaceMaster"""
		return self._idict.keys()

	#} END interface


class Singleton(object) :
	""" Singleton classes can be derived from this class,
		you can derive from other classes as long as Singleton comes first (and class doesn't override __new__ ) """
	def __new__(cls, *p, **k):
		if not '_the_instance' in cls.__dict__:
			cls._the_instance = super(Singleton, cls).__new__(cls)
		return cls._the_instance


class CallOnDeletion( object ):
	"""Call the given callable object once this object is being deleted
	Its usefull if you want to assure certain code to run once the parent scope
	of this object looses focus"""
	__slots__ = "callableobj"
	def __init__( self, callableobj ):
		self.callableobj = callableobj

	def __del__( self ):
		if self.callableobj is not None:
			self.callableobj( )


class DAGTree( nx.DiGraph ):
	"""Adds utility functions to DirectedTree allowing to handle a directed tree like a dag
	:note: currently this tree does not support instancing
	:todo: add instancing support"""

	def children( self, n ):
		""" :return: list of children of given node n """
		return list( self.children_iter( n ) )

	def children_iter( self, n ):
		""" :return: iterator with children of given node n"""
		return ( e[1] for e in self.out_edges_iter( n ) )

	def parent( self, n ):
		""":return: parent of node n
		:note: currently there is only one parent, as instancing is not supported yet"""
		for parent in  self.predecessors_iter( n ):
			return parent
		return None

	def parent_iter( self, n ):
		""":return: iterator returning all parents of node n"""
		while True:
			p = self.parent( n )
			if p is None:
				raise StopIteration( )
			yield p
			n = p

	def get_root( self, startnode = None ):
		""":return: the root node of this dag tree
		:param startnode: if None, the first node will be used to get the root from
			( good for single rooted dags ), otherwise this node will be used to get the root from
			- thus it must exist in the dag tree"""
		if startnode is None:
			startnode = self.nodes_iter().next()

		root = None
		for parent in self.parent_iter( startnode ):
			root = parent

		return root
		
	def to_hierarchy_file(self, root, output_path):
		"""Write ourselves in hierarchy file format to the given output_path.
		
		:param root: The root of the written file, nodes above it will not be serialized.
		:note: Directories are expected to exist
		:raise ValueError: If an node's string representation contains a newline or 
			starts with a tab
		:note: works best with strings as nodes, which may not contain newlines"""
		fp = open(output_path, "wb")
		for depth, item in iterNetworkxGraph(self, root, branch_first=False, ignore_startitem=False):
			itemstr = str(item)
			if itemstr.startswith("\t") or "\n" in itemstr:
				raise ValueError("Item %r contained characters unsupported by the hierarchy file format")
			# END handle serialization
			fp.write("%s%s\n" % ("\t"*depth, itemstr))
		# END for each item
		fp.close()


class PipeSeparatedFile( object ):
	"""Read and write simple pipe separated files.

	The number of column must remain the same per line
	**Format**:
	
		val11 | val2 | valn
		...
	"""
	kSeparator = '|'
	__slots__ = ( "_fileobj", "_columncount", "_formatstr" )

	def __init__( self, fileobj ):
		"""Initialize the instance
		
		:param fileobj: fileobject where new lines will be written to or read from
			It must already be opened for reading and/or writing respectively"""
		self._fileobj = fileobj
		self._columncount = None

	def beginReading( self ):
		"""Start reading the file"""

	def readColumnLine( self ):
		"""Generator reading one line after another, returning the stripped columns
		
		:return: tuple of stripped column strings
		:raise ValueError: if the column count changes between the lines"""
		for line in self._fileobj:
			if not len( line.strip() ):
				continue

			tokens = [ item.strip() for item in line.split( self.kSeparator ) ]
			if not self._columncount:
				self._columncount = len( tokens )

			if self._columncount != len( tokens ):
				raise ValueError( "Columncount changed between successive lines" )

			yield tuple( tokens )
		# END for each line

	def beginWriting( self, columnSizes ):
		"""intiialize the writing process
		
		:param columnSizes: list of ints defining the size in characters for each column you plan to feed
		:note: When done writing, you have to close the file object yourself ( there is no endWriting method here )"""
		columnTokens = [ "%%-%is" % csize for csize in columnSizes ]
		self._formatstr = ( ( self.kSeparator + " " ).join( columnTokens ) ) + "\n"

	def writeTokens( self, tokens ):
		"""Write the list of tokens to the file accordingly
		
		:param tokens: one token per column that you want to write
		:raise TypeError: If column count changed between successive calls"""
		self._fileobj.write( self._formatstr % tokens )


class MetaCopyClsMembers( type ):
	"""Meta class copying members from given classes onto the type to be created
	it will read the following attributes from the class dict:
	``forbiddenMembers``, ``overwritePrefix``, ``__virtual_bases__``

	The virtual bases are a tuple of base classes whose members you whish to receive
	For information on these members, check the docs of `copyClsMembers`"""
	def __new__( metacls, name, bases, clsdict ):
		forbiddenMembers = clsdict.get( 'forbiddenMembers', [] )
		overwritePrefix = clsdict.get( 'overwritePrefix', None )
		vbases = clsdict.get( '__virtual_bases__', [] )

		for sourcecls in vbases:
			for name,member in sourcecls.__dict__.iteritems():
				if name in forbiddenMembers:
					continue

				# store original - overwritten members must still be able to access it
				if name in clsdict:
					if not overwritePrefix:
						continue
					morig = clsdict[ name ]
					clsdict[ overwritePrefix+name ] = morig
				clsdict[ name ] = member
			# END for each sourcecls member
		# END for each sourcecls in bases

		return super( MetaCopyClsMembers, metacls ).__new__( metacls, name, bases, clsdict )


#{ Predicates

# general boolean
class And( object ):
	"""For use with python's filter method, simulates logical AND
	Usage: filter( And( f1,f2,fn ), sequence )"""
	__slots__ = "functions"
	def __init__( self, *args ):
		"""args must contain the filter methods to be AND'ed
		To append functions after creation, simply access the 'functions' attribute
		directly as a list"""
		self.functions = list( args )

	def __call__( self, *args, **kwargs ):
		"""Called during filter function, return true if all functions return true"""
		val = True
		for func in self.functions:
			val = val and func( *args, **kwargs )
			if not val:
				return val
		# END for each function
		return val


class Or( object ):
	"""For use with python's filter method, simulates logical OR
	Usage: filter( Or( f1,f2,fn ), sequence ) """
	__slots__ = "functions"
	def __init__( self, *args ):
		"""args must contain the filter methods to be AND'ed"""
		self.functions = args

	def __call__( self, *args, **kwargs ):
		"""Called during filter function, return true if all functions return true"""
		val = False
		for func in self.functions:
			val = val or func( *args, **kwargs )
			if val:
				return val
		# END for each function
		return val

#} END predicates
