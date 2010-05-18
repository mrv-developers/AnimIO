# -*- coding: utf-8 -*-
"""Contains a simple but yet powerful dependency graph engine allowing computations
to be organized more efficiently.
"""
__docformat__ = "restructuredtext"

import networkx as nx
from collections import deque
import inspect
import weakref
import itertools
from util import iDuplicatable

__all__ = ("ConnectionError", "PlugIncompatible", "PlugAlreadyConnected", "AccessError",
           "NotWritableError", "NotReadableError", "MissingDefaultValueError", "ComputeError", 
           "ComputeFailed", "ComputeFailed", "PlugUnhandled", 
           "iterShells", "Attribute", "iPlug", "plug", "Graph", "NodeBase")

#####################
## EXCEPTIONS ######
###################
#{ Exceptions

class ConnectionError( Exception ):
	"""Exception base for all plug related errors"""

class PlugIncompatible( ConnectionError, TypeError ):
	"""Thrown whenever plugs are not compatible with each other during connection"""

class PlugAlreadyConnected( ConnectionError ):
	"""Thrown if one tries to connect a plug to otherplug when otherplug is already connected"""

class AccessError( Exception ):
	"""Base class for all errors indicating invalid access"""

class NotWritableError( AccessError ):
	"""Thrown if a non-writable plug is being written to"""

class NotReadableError( AccessError ):
	"""Thrown if a non-readable attribute is being read"""

class MissingDefaultValueError( AccessError ):
	"""Thrown if a default value is missing for input attributes that are not connected"""

class ComputeError( Exception ):
	"""Thrown if the computation done by a plug failed by an unknown exception
	It will be passed on in the exception"""

class ComputeFailed( ComputeError ):
	"""Raised by the derived class computing a value if the computational goal
	cannot be achieved ( anymore )"""

class PlugUnhandled( ComputeError ):
	"""Raised if a plug was not handled by the node's compute method"""

#} END exceptions



#####################
## Iterators  ######
###################
#{ Iterators
def iterShells( rootPlugShell, stopAt = lambda x: False, prune = lambda x: False,
			   direction = "up", visit_once = False, branch_first = False ):
	"""Iterator starting at rootPlugShell going "up"stream ( input ) or "down"stream ( output )
	breadth first over plugs, applying filter functions as defined.
	
	:param rootPlugShell: shell at which to start the traversal. The root plug will be returned as well
	:param stopAt: if function returns true for given PlugShell, iteration will not proceed
		at that point ( possibly continuing at other spots ). Function will always be called, even
		if the shell would be pruned as well. The shell serving as stop marker will not be returned
	:param prune: if function returns true for given PlugShell, the shell will not be returned
		but iteration continues.
	:param direction: traversal direction
			"up" upstream, in direction of inputs of plugs
			"down" downstream, in direction of outputs of plugs
	:param visit_once: if True, plugs will only be returned once, even though they are
	:param branch_first: if True, individual branches will be travelled first ( thuse the node will be left quickly following the datastream ).
			If False, the plugs on the ndoe will be returned first before proceeding to the next node
			encountered several times as several noodes are connected to them in some way. """
	visited = set()
	stack = deque()
	stack.append( rootPlugShell )

	def addToStack( node, stack, lst, branch_first ):
		if branch_first:
			stack.extend( node.toShell( plug ) for plug in lst )
		else:
			reviter = ( node.toShell( lst[i] ) for i in range( len( lst )-1,-1,-1) )
			stack.extendleft( reviter )
	# END addToStack local method

	def addOutputToStack( stack, lst, branch_first ):
		if branch_first:
			stack.extend( lst )
		else:
			stack.extendleft( reversed( lst[:] ) )
	# END addOutputToStack local method

	while stack:
		shell = stack.pop()
		if shell in visited:
			continue

		if visit_once:
			visited.add( shell )

		if stopAt( shell ):
			continue

		if not prune( shell ):
			yield shell

		if direction == 'up':
			# I-N-O
			addToStack( shell.node, stack, shell.plug.affectedBy(), branch_first )
			# END if provides output

			# O<-I
			ishell = shell.input( )
			if ishell:
				if branch_first:
					stack.append( ishell )
				else:
					stack.appendleft( ishell )
			# END has input connection
		# END upstream
		else:
			# I-N-O and I->O
			# could also be connected - follow them
			if branch_first:
				# fist the outputs, then the internals ( this ends up with the same effect )
				addToStack( shell.node, stack, shell.plug.affected(), branch_first )
				addOutputToStack( stack, shell.outputs(), branch_first )
			else:
				addOutputToStack( stack, shell.outputs(), branch_first )
				addToStack( shell.node, stack, shell.plug.affected(), branch_first )
		# END downstream
	# END for each shell on work stack

#} END iterators


#####################
## Classes    ######
###################


#{ END Plugs and Attributes

class Attribute( object ):
	"""Simple class defining the type of a plug and several flags that
	affect it. Additionally it can determine how well suited another attribute is

	**Flags**:
		exact_type: if True, derived classes of our typecls are not considered to be a valid type.
		i.e: basestring could be stored in a str attr if exact type is false - its less than we need, but
		still something.
		Putting a str into a basestring attribute will always work though, as it would be more than we need
		readonly: if True, the attribute's plug cannot be written to. Read-only attributes can be used
		as storage that the user can read, but not write.
		You can write read-only plugs by directly setting its cache - this of course - is only
		for the node itself, but will never be done by the framework
	
	**computable**:
		Nodes are automatically computable if they are affected by another plug.
		If this is not the case, they are marked input only and are not computed.
		If this flag is true, even unaffeted plugs are computable.
		Plugs that affect something are automatically input plugs and will not be computed.
		If the plug does not affect anything and this flag is False, they are seen as input plugs
		anyway.
	
		The system does not allow plugs to be input and output plugs at the same time, thus your compute
		cannot be triggered by your own compute
				
		cls: if True, the plug requires classes to be set ( instances of 'type' ) , but no instances of these classes
		uncached: if False, computed values may be cached, otherwise they will always be recomputed.
		unconnectable: if True, the node cannot be the destination of a connection
		check_passing_values: check each value as it flows through a connection - usually compatability is only checked
		on connection and once values are set, but not if they flow through an existing connection
	
	**Default Values**:
		Although default values can be simple primitives are classes, a callable is specifically supported.
		It allows you to get a callback whenever a default value is required.
		The same result could be achieved by connected the plug in question, but dynamic defaults are a quick
		way to achive that.
		Your returned value will be type-checked against the required type if check_passing_values is set."""
	kNo, kGood, kPerfect = 0, 127, 255				# specify how good attributes fit together
	exact_type, readonly, computable, cls, uncached, unconnectable,check_passing_values = ( 1, 2, 4, 8, 16, 32, 64 )

	def __init__( self, typeClass, flags, default = None ):
		self.typecls = typeClass
		self.flags = flags			# used for bitflags describing mode
		self._default = default

		# check default value for compatability !
		if default is not None:
			if not hasattr( default, '__call__' ) and self.compatabilityRate( default ) == 0:
				raise TypeError( "Default value %r is not compatible with this attribute" % default )
		# END default type check

	def _getClassRating( self, cls, exact_type ):
		""" compute class rating
		
		:return: rating based on value being a class and compare.
				0 means there is no type compatability, 255 matches comparecls, or linearly 
				less if is just part of the mro of value
		"""
		if not isinstance( cls, type ):
			return 0

		mro = self.typecls.mro()
		mro.reverse()

		if not cls in mro:
			# if we are in the classes mr, then we can perfectly store the class
			# as it is more than we need
			if not exact_type and self.typecls in cls.mro():
				return self.kPerfect
			return 0
		# END simple mro checking

		if len( mro ) == 1:
			return self.kPerfect

		rate = ( float( mro.index( cls ) ) / float( len( mro ) - 1 ) ) * self.kPerfect

		if exact_type and rate != self.kPerfect:		# exact type check
			return 0

		return rate

	#{ Interface

	def affinity( self, otherattr ):
		"""Compute affinity for otherattr.
		
		:return: 
			rating from 0 to 255 defining how good the attribtues match each
			other in general - how good can we store values of otherattr ? 
			Thus this comparison is directed.

		:note: for checking connections, use `connectionAffinity`"""
		# see whether our class flags match
		if self.flags & self.cls != otherattr.flags & self.cls:
			return 0

		# DEFAULT VALUE CHECK
		#######################
		# see whether we destination can handle our default value - if not
		# just go for a class comparison
		rate = self.kNo
		try:
			defvalue = otherattr.default()
			rate = self.compatabilityRate( defvalue )
		except (MissingDefaultValueError,TypeError):
			rate = self._getClassRating( otherattr.typecls, self.flags & self.exact_type )
		# finally check how good our types match

		return rate

	def connectionAffinity( self, destinationattr ):
		"""Compute connection affinity for given destination attribute
		
		:return: 
			rating from 0 to 255 defining the quality of the connection to
			otherplug. an affinity of 0 mean connection is not possible, 255 mean the connection
			is perfectly suited.
			The connection is a directed one from self -> otherplug """
		if destinationattr.flags & self.unconnectable:		# destination must be connectable
			return 0

		# how good can the destination attr deal with us ?
		return destinationattr.affinity( self )

	def compatabilityRate( self, value ):
		"""Compute value's compatability rate
		
		:return: value between 0 and 255, 0 means no compatability, 255 a perfect match. 
			if larger than 0, the plug can hold the value ( assumed the flags are set correctly ). """
		if isinstance( value, type ):
			# do we need a class ?
			if not self.flags & self.cls:
				return 0		# its a class

			# check compatability
			return self._getClassRating( value, self.flags & self.exact_type )
		# END is class type
		else:
			if not self.flags & self.cls:
				return self._getClassRating( value.__class__, self.flags & self.exact_type )
		# END is instance type

		return 0

	def default( self ):
		""":return: default value stored for this attribute, or raise
		:note: handles dynamic defaults, so you should not directly access the default member variable
		:raise MissingDefaultValueError: if attribute does not have a default value
		:raise TypeError: if value returned by dynamic attribute has incorrect type"""
		if self._default is None:
			raise MissingDefaultValueError( "Attribute %r has no default value" % self )

		# DYNAMIC ATTRIBUTES
		######################
		if hasattr( self._default, '__call__' ):
			default = self._default()
			if self.flags & self.check_passing_values and self.compatabilityRate( default ) == 0:
				raise TypeError( "Dynamic default value had incorrect type: %s" % type( default ) )
			return default
		# END dynamic default handling

		# normal static default
		return self._default


	#} END interface



class iPlug( object ):
	"""Defines an interface allowing to compare compatabilies according to types.

	Plugs can either be input plugs or output plugs - output plugs affect no other
	plug on a node, but are affected by 0 or more plugs .

	By convention, a plug has a name - that name must also be the name of the
	member attribute that stores the plag. Plugs, possibly different instances of it,
	need to be re-retrieved on freshly duplicated nodes to allow graph duplication to
	be done properly

	:note: if your plug class supports the ``setName`` method, a metaclass will
		adjust the name of your plug to match the name it has in the parent class
	"""
	kNo,kGood,kPerfect = ( 0, 127, 255 )

	#{ Base Implementation
	def __str__( self ):
		return self.name()

	#} END base implementation


	#{ Interface
	def name( self ):
		""":return: name of the plug ( the name that identifies it on the node"""
		raise NotImplementedError( "Implement this in subclass" )

	def affects( self, otherplug ):
		"""Set an affects relation ship between this plug and otherplug, saying
		that this plug affects otherplug."""
		raise NotImplementedError( "Implement this in subclass" )

	def affected( self ):
		""":return: tuple containing affected plugs ( plugs that are affected by our value )"""
		raise NotImplementedError( "Implement this in subclass" )

	def affectedBy( self ):
		""":return: tuple containing plugs that affect us ( plugs affecting our value )"""
		raise NotImplementedError( "Implement this in subclass" )

	def providesOutput( self ):
		""":return: True if this is an output plug that can trigger computations"""
		raise NotImplementedError( "Implement this in subclass" )
                                                                                                  
	def providesInput( self ):
		""":return: True if this is an input plug that will never cause computations"""
		raise NotImplementedError( "Implement this in subclass" )

	#} END interface


class plug( iPlug ):
	"""Defines an interface allowing to compare compatabilies according to types.

	Plugs are implemented as descriptors, thus they will be defined on node class
	level, and all static information will remain static

	As descriptors, they are defined statically on the class, and some additional information
	such as connectivity, is stored on the respective class instance. These special methods
	are handled using `NodeBase` class

	Plugs are implemented as descriptors as all type information can be kept per class,
	whereas only connection information changes per node instance.

	Plugs can either be input plugs or output plugs - output plugs affect no other
	plug on a node, but are affected by 0 or more plugs

	:note: class is lowercase as it is used as descriptor ( acting more like a function )
	"""
	kNo,kGood,kPerfect = ( 0, 127, 255 )

	#{ Overridden object methods
	def __init__( self, attribute ):
		"""Intialize the plug with a distinctive name"""
		self._name = None
		self.attr = attribute
		self._affects = list()			# list of plugs that are affected by us
		self._affectedBy = list()		# keeps record of all plugs that affect us

	#} END object overridden methods

	#{ Value access

	def __get__( self, obj, cls=None ):
		"""A value has been requested - return our plugshell that brings together
		both, the object and the static plug"""
		# in class mode we return ourselves for access
		if obj is not None:
			return obj.toShell( self )

		# class attributes just return the descriptor itself for direct access
		return self


	#def __set__( self, obj, value ):
		"""We do not use a set method, allowing to override our descriptor through
		actual plug instances in the instance dict. Once deleted, we shine through again"""
		# raise AssertionError( "To set this value, use the node.plug.set( value ) syntax" )
		# obj.toShell( self ).set( value )

	#} value access


	def name( self ):
		""":return: name of plug"""
		return self._name

	def setName( self, name ):
		"""Set the name of this plug - can be set only once"""
		if not self._name:
			self._name = name
		else:
			raise ValueError( "The name of the plug can only be set once" )

	def affects( self, otherplug ):
		"""Set an affects relation ship between this plug and otherplug, saying
		that this plug affects otherplug."""
		if otherplug not in self._affects:
			self._affects.append( otherplug )

		if self not in otherplug._affectedBy:
			otherplug._affectedBy.append( self )

	def affected( self ):
		""":return: tuple containing affected plugs ( plugs that are affected by our value )"""
		return tuple( self._affects )

	def affectedBy( self ):
		""":return: tuple containing plugs that affect us ( plugs affecting our value )"""
		return tuple( self._affectedBy )

	def providesOutput( self ):
		""":return: True if this is an output plug that can trigger computations"""
		return bool( len( self.affectedBy() ) != 0 or self.attr.flags & Attribute.computable )

	def providesInput( self ):
		""":return: True if this is an input plug that will never cause computations"""
		#return len( self._affects ) != 0 and not self.providesOutput( )
		return not self.providesOutput() # previous version did not recognize storage plugs as input


#} END plugs and attributes


class _PlugShell( tuple ):
	"""Handles per-node-instance plug connection setup and storage. As plugs are
	descriptors and thus an instance of the class, per-node-instance information needs
	special treatment.
	This class is being returned whenever the descriptors get and set methods are called,
	it contains information about the node and the plug being involved, allowing to track
	connection info directly using the node dict

	This allows plugs to be connected, and information to flow through the dependency graph.
	Plugs never act alone since they always belong to a parent node that will be asked for
	value computations if the value is not yet cached.
	:note: Do not instantiate this class youself, it must be created by the node as different
	node types can use different versions of this shell"""

	#{ Object Overrides

	def __new__( cls, *args ):
		return tuple.__new__( cls, args )

	def __getattr__( self, attr ):
		"""Allow easy attribute access while staying memory efficient"""
		if attr == 'node':
			return self[0]
		if attr == 'plug':
			return self[1]

		# let it raise the typical error
		return super( _PlugShell, self ).__getattribute__( attr )

	def __repr__ ( self ):
		return "%s.%s" % ( self.node, self.plug )

	def __str__( self ):
		return repr( self )

	#} END object overrides


	#{ Values

	def get( self, mode = None ):
		""":return: value of the plug
		:param mode: optional arbitary value specifying the mode of the get attempt"""
		if self.hasCache( ):
			return self.cache( )

		# Output plugs compute values
		if self.plug.providesOutput( ):
			# otherwise compute the value
			try:
				result = self.node.compute( self.plug, mode )
			except ComputeError,e:
				raise ComputeError( "%s->%s" % ( repr( self ), str( e ) ) )
			except Exception:		# except all - this is an unknown excetion - just pass it on, keeping the origin
				raise

			if result is None:
				raise AssertionError( "Plug %s returned None - check your node implementation" % ( str( self ) ) )
			# END result check

			# try to cache computed values
			self.setCache( result )
			return result
		# END plug provides output
		elif self.plug.providesInput( ):	# has to be separately checked
			# check for connection
			inputshell = self.input()
			if not inputshell:
				# check for default value
				try:
					return self.plug.attr.default()
				except ( TypeError, MissingDefaultValueError ),e:
					raise MissingDefaultValueError( "Plug %r failed to getrieve its default value and is not connected" % repr( self ), e )
			# END if we have no input

			# query the connected plug for the value
			value = inputshell.get( mode )
			if self.plug.attr.flags & Attribute.check_passing_values:
				if not self.plug.attr.compatabilityRate( value ):
					raise TypeError( "Value coming from input %s is not compatible with %s" % ( str( inputshell ), str( self ) ) )

			return value
		# END plug provides input

		raise AssertionError( "Plug %s did not provide any output or input!" % repr( self ) )



	def set( self, value, ignore_connection = False ):
		"""Set the given value to be used in our plug
		:param ignore_connection: if True, the plug can be destination of a connection and
		will still get its value set - usually it would be overwritten by the value form the
		connection. The set value will be cleared if something upstream in it's connection chain
		changes.
		:raise AssertionError: the respective attribute must be cached, otherwise
		the value will be lost"""
		flags = self.plug.attr.flags
		if flags & Attribute.readonly:
			raise NotWritableError( "Plug %r is not writable" % repr(self) )

		if self.plug.providesOutput( ):
			raise NotWritableError( "Plug %r is not writable as it provides an output itself" % repr(self) )

		if flags & Attribute.uncached:
			raise AssertionError( "Writable attributes must be cached - otherwise the value will not be held" )

		# check connection
		if not ignore_connection and self.input() is not None:
			raise NotWritableError( "Plug %r is connected to %r and thus not explicitly writable" % ( self, self.input() ) )

		self.setCache( value )


	def compatabilityRate( self, value ):
		"""Compute compatability rate for teh given value
		
		:return: value between 0 and 255, 0 means no compatability, 255 a perfect match
			if larger than 0, the plug can hold the value ( assumed the flags are set correctly )
		"""
		return self.plug.attr.compatabilityRate( value )


	#} END values

	#{ Connections

	def connect( self, otherplugshell, **kwargs ):
		"""Connect this plug to otherplugshell such that otherplugshell is an input plug for our output
		
		:param kwargs: everything supported by `Graph.connect`
		:return: self on success, allows chained connections
		:raise PlugAlreadyConnected: if otherplugshell is connected and force is False
		:raise PlugIncompatible: if otherplugshell does not appear to be compatible to this one"""
		if not isinstance( otherplugshell, _PlugShell ):
			raise AssertionError( "Invalid Type given to connect: %r" % repr( otherplugshell ) )

		return self.node.graph.connect( self, otherplugshell, **kwargs )


	def disconnect( self, otherplugshell ):
		"""Remove the connection to otherplugshell if we are connected to it.
		:note: does not raise if no connection is present"""
		if not isinstance( otherplugshell, _PlugShell ):
			raise AssertionError( "Invalid Type given to connect: %r" % repr( otherplugshell ) )

		return self.node.graph.disconnect( self, otherplugshell )

	def input( self, predicate = lambda shell: True ):
		""":return: the connected input plug or None if there is no such connection
		:param predicate: plug will only be returned if predicate is true for it
		:note: input plugs have on plug at most, output plugs can have more than one
			connected plug"""
		sourceshell = self.node.graph.input( self )
		if sourceshell and predicate( sourceshell ):
			return sourceshell
		return None

	def outputs( self, predicate = lambda shell: True ):
		""":return: a list of plugs being the destination of the connection
		:param predicate: plug will only be returned if predicate is true for it - shells will be passed in """
		return self.node.graph.outputs( self, predicate = predicate )

	def connections( self, inpt, output, predicate = lambda shell: True ):
		""":return: get all input and or output connections from this shell
			or to this shell as edges ( sourceshell, destinationshell )
		:param predicate: return true for each destination shell that you can except in the
			returned edge or the sourceshell where your shell is the destination.
		:note: Use this method to get edges read for connection/disconnection"""
		outcons = list()
		if inpt:
			sourceshell = self.input( predicate = predicate )
			if sourceshell:
				outcons.append( ( sourceshell, self ) )
		# END input connection handling

		if output:
			outcons.extend( ( self, oshell ) for oshell in self.outputs( predicate = predicate ) )

		return outcons

	def isConnected( self ):
		""":return: True, if the shell is connected as source or as destination of a connection"""
		return self.input() or self.outputs()

	def iterShells( self, **kwargs ):
		"""Iterate plugs and their connections starting at this plug
		:return: generator for plug shells
		:note: supports all options of `iterShells`, this method allows syntax like:
		node.outAttribute.iterShells( )"""
		return iterShells( self, **kwargs )

	#} END connections


	#{Caching
	def _cachename( self ):
		return self.plug.name() + "_c"

	def hasCache( self ):
		""":return: True if currently store a cached value"""
		return hasattr( self.node, self._cachename() )

	def setCache( self, value ):
		"""Set the given value to be stored in our cache
		:raise: TypeError if the value is not compatible to our defined type"""
		# attr compatability - always run this as we want to be warned if the compute
		# method returns a value that does not match
		if self.plug.attr.compatabilityRate( value ) == 0:
			raise TypeError( "Plug %r cannot hold value %r as it is not compatible" % ( repr( self ), repr( value ) ) )

		if self.plug.attr.flags & Attribute.uncached:
			return

		# our cache changed - dirty downstream plugs - thus clear the cache
		# NOTE: this clears our own cache by deleting it, but we re-set it
		self.clearCache( clear_affected = True )
		setattr( self.node, self._cachename(), value )

	def cache( self ):
		""":return: the cached value or raise
		:raise ValueError:"""
		if self.hasCache():
			return getattr( self.node, self._cachename() )

		raise ValueError( "Plug %r did not have a cached value" % repr( self ) )

	def clearCache( self, clear_affected = False, cleared_shells_set = None ):
		"""Empty the cache of our plug
		:param clear_affected: if True, the caches of our affected plugs ( connections
		or affects relations ) will also be cleared
		This operation is recursive, and needs to be as different shells on different nodes
		might do things differently.
		:param cleared_shells_set: if set, it can be used to track which plugs have already been dirtied to
		prevent recursive loops
		Propagation will happen even if we do not have a cache to clear ourselves """
		if self.hasCache():
			del( self.node.__dict__[ self._cachename() ] )

		if clear_affected:
			# our cache changed - dirty downstream plugs - thus clear the cache
			if not cleared_shells_set:		# initialize our tracking list
				cleared_shells_set = set()

			if self in cleared_shells_set:
				return

			cleared_shells_set.add( self )	# assure we do not come here twice

			all_shells = itertools.chain( self.node.toShells( self.plug.affected() ), self.outputs() )
			for shell in all_shells:
				shell.clearCache( clear_affected = True, cleared_shells_set = cleared_shells_set )
			# END for each shell in all_shells to clear
	#} END caching


	#{ Name Overrides
	__rshift__ = lambda self,other: self.connect( other, force=True )
	# NOTE: this will cause problems when sorting them :) - so lets just use >> for the
	# forced connection !
	# __gt__ = lambda self,other: self.connect( other, force=False )

	#} END name overrides



class Graph( nx.DiGraph, iDuplicatable ):
	"""Holds the nodes and their connections

	Nodes are kept in a separate list whereas the plug connections are kept
	in the underlying DiGraph"""

	#{ Overridden Object Methods
	def __init__( self, **kwargs ):
		"""initialize the DiGraph and add some additional attributes"""
		super( Graph, self ).__init__( **kwargs )
		self._nodes = set()			# our processes from which we can make connections

	def __del__( self ):
		"""Clear our graph"""
		self.clear()				# clear connections

		# NOTE : nodes will remove themselves once they are not referenced anymore
		self._nodes.clear()


	def __getattr__( self , attr ):
		"""Allows access to nodes by name just by accessing the graph directly"""
		try:
			return self.nodeByID( attr )
		except NameError:
			return super( Graph, self ).__getattribute__( attr )

	#} END object methods

	#{ Debugging
	def writeDot( self , fileOrPath  ):
		"""Write the connections in self to the given file object or path
		:todo: remove if no longer needed"""
		# associate every plugshell with its node create a more native look
		writegraph = nx.DiGraph()
		# but we do not use it as the edge attrs cannot be assigned anymore - dict has no unique keys
		# writegraph.allow_multiedges()

		# EXTRACT DATA
		for node in self.iterNodes():
			writegraph.add_node( node, color="#ebba66", width=4, height=2, fontsize=22 )
		# END for each node in graph

		# now all the connections - just transfer them
		for sshell,eshell in self.edges_iter():
			writegraph.add_edge( sshell,eshell )

			writegraph.add_edge( sshell.node, sshell, color="#000000" )
			
			writegraph.add_node( sshell, color="#000000", label=sshell.plug )
			writegraph.add_node( eshell, color="#000000", label=eshell.plug )

			writegraph.add_edge( eshell,eshell.node, color="#000000" )
		# END for each edge in graph

		# WRITE DOT FILE
		nx.write_dot(writegraph, fileOrPath)

	#} END debugging

	#{ iDuplicatable Interface
	def createInstance( self ):
		"""Create a copy of self and return it"""
		return self.__class__( )

	def copyFrom( self, other ):
		"""Duplicate all data from other graph into this one, create a duplicate
		of the nodes as well"""
		def copyshell( shell, nodemap ):
			nodecpy = nodemap[ shell.node ]

			# nodecpy - just get the shell of the given name directly - getattr always creates
			# shells as it is equal to node.plugname
			return getattr( nodecpy, shell.plug.name() )

		# copy name ( networkx )
		self.name = other.name

		# copy nodes first
		nodemap = dict()
		for node in other.iterNodes():
			nodecpy = node.duplicate( add_to_graph = False )		# copy node
			nodemap[ node ] = nodecpy
		# END for each node

		# add all nodemap values as nodes ( now that iteration is done
		for duplnode in nodemap.itervalues():
			self.addNode( duplnode )

		# COPY CONNECTIONS
		for sshell,eshell in other.edges_iter():
			# make fresh connections through shells - we do not know what kind of
			# plugs they use, so they could be special and thus need special
			# copy procedures
			cstart = copyshell( sshell, nodemap )
			cend = copyshell( eshell, nodemap )

			cstart.connect( cend )
		# END for each edge( startshell, endshell )


	# END iDuplicatable


	#{ Node Handling
	def addNode( self, node ):
		"""Add a new node instance to the graph
		:note: node membership is exclusive, thus node instances
		can only be in one graph at a time
		:return: self, for chained calls"""
		if not isinstance( node, NodeBase ):
			raise TypeError( "Node %r must be of type NodeBase" % node )

		# assure we do not remove ( and kill connections ) and re-add to ourselves
		if node in self._nodes:
			return self

		# remove node from existing graph
		if node.graph is not None:
			node.graph.removeNode( node )


		self._nodes.add( node )		# assure the node knows us
		node.graph = weakref.proxy( self )

		return self		# assure we have the graph set

	def removeNode( self, node ):
		"""Remove the given node from the graph ( if it exists in it )"""
		try:
			# remove connections
			for sshell, eshell in node.connections( 1, 1 ):
				self.disconnect( sshell, eshell )

			# assure the node does not call us anymore
			node.graph = None
			self._nodes.remove( node )
		except KeyError:
			pass

	def clearCache( self ):
		"""Clear the cache of all nodes in the graph - this forces the graph
		to reevaluate on the next request"""
		for node in self._nodes:
			node.clearCache()

	#} END node handling

	#{ Query

	def hasNode( self , node ):
		""":return: True if the node is in this graph, false otherwise"""
		return node in self._nodes

	def iterNodes( self, predicate = lambda node: True ):
		""":return: generator returning all nodes in this graph
		:param predicate: if True for node, it will be returned
		:note: there is no particular order"""
		for node in self._nodes:
			if predicate( node ):
				yield node
		# END for each node

	def iterConnectedNodes( self, predicate = lambda node: True ):
		""":return: generator returning all nodes that are connected in this graph,
			in no particular order.
			For an ordered itereration, use `iterShells`.
			
		:param predicate: if True for node, it will be returned"""
		# iterate digraph keeping the plugs only ( and thus connected nodes )
		nodes_seen = set()
		for node,plug in self.nodes_iter():
			if node in nodes_seen:
				continue
			nodes_seen.add( node )
			if predicate( node ):
				yield node
		# END for each node

	def nodes( self ):
		""":return: immutable copy of the nodes used in the graph"""
		return tuple( self._nodes )

	def numNodes( self ):
		""":return: number of nodes in the graph"""
		return len( self._nodes )

	def nodeByID( self, nodeID ):
		""":return: instance of a node according to the given node id
		:raise NameError: if no such node exists in graph"""
		for node in self.iterNodes():
			if node.id() == nodeID:
				return node

		raise NameError( "Node with ID %s not found in graph" % nodeID )


	#} END query

	#{ Connecitons
	def connect( self, sourceshell, destinationshell, force = False ):
		"""Connect this plug to destinationshell such that destinationshell is an input plug for our output
		
		:param sourceshell: PlugShell being source of the connection
		:param destinationshell: PlugShell being destination of the connection
		:param force: if False, existing connections to destinationshell will not be broken, but an exception is raised
			if True, existing connection may be broken
		:return: self on success, allows chained connections
		:raise PlugAlreadyConnected: if destinationshell is connected and force is False
		:raise PlugIncompatible: if destinationshell does not appear to be compatible to this one"""
		# assure both nodes are known to the graph
		if not sourceshell.node.graph is destinationshell.node.graph:
			raise AssertionError( "You cannot connect nodes from different graphs" )

		self._nodes.add( sourceshell.node )
		self._nodes.add( destinationshell.node )

		# check compatability
		if sourceshell.plug.attr.connectionAffinity( destinationshell.plug.attr ) == 0:
			raise PlugIncompatible( "Cannot connect %r to %r as they are incompatible" % ( repr( sourceshell ), repr( destinationshell ) ) )


		oinput = destinationshell.input( )
		if oinput is not None:
			if oinput == sourceshell:
				return sourceshell

			if not force:
				raise PlugAlreadyConnected( "Cannot connect %r to %r as it is already connected" % ( repr( sourceshell ), repr( destinationshell ) ) )

			# break existing one
			oinput.disconnect( destinationshell )
		# END destinationshell already connected

		# connect us
		self.add_edge( sourceshell, v = destinationshell )
		return sourceshell

	def disconnect( self, sourceshell, destinationshell ):
		"""Remove the connection between sourceshell to destinationshell if they are connected
		:note: does not raise if no connection is present"""
		self.remove_edge( sourceshell, v = destinationshell )

		# also, delete the plugshells if they are not connnected elsewhere
		for shell in sourceshell,destinationshell:
			if len( self.neighbors( shell ) ) == 0:
				self.remove_node( shell )

	def input( self, plugshell ):
		""":return: the connected input plug of plugshell or None if there is no such connection
		:note: input plugs have on plug at most, output plugs can have more than one connected plug"""
		try:
			pred = self.predecessors( plugshell )
			if pred:
				return pred[0]
		except nx.NetworkXError:
			pass

		return None

	def outputs( self, plugshell, predicate = lambda x : True ):
		""":return: a list of plugs being the destination of the connection to plugshell
		:param predicate: plug will only be returned if predicate is true for it - shells will be passed in """
		try:
			return [ s for s in self.successors( plugshell ) if predicate( s ) ]
		except nx.NetworkXError:
			return list()

	#} END connections


class _NodeBaseCheckMeta( type ):
	"""Class checking the consistency of the nodebase class before it is being created"""
	def __new__( metacls, name, bases, clsdict ):
		"""Check:
			- every plugname must correspond to a node member name
		"""
		newcls = super( _NodeBaseCheckMeta, metacls ).__new__( metacls, name, bases, clsdict )

		# EVERY PLUG NAME MUST MATCH WITH THE ACTUAL NAME IN THE CLASS
		# set the name according to its slot name in the parent class
		membersdict = inspect.getmembers( newcls )		# do not filter, as plugs could be overridden
		try:
			if hasattr( newcls, "plugsStatic" ):
				for plug in newcls.plugsStatic( ):
					for name,member in membersdict:
						if member == plug and plug.name() != name:
							# try to set it
							if hasattr( plug, 'setName' ):
								plug.setName( name )
							else:
								raise AssertionError( "Plug %r is named %s, but must be named %s as in its class %s" % ( plug, plug.name(), name, newcls ) )
							# END setName special handling
						# END if member nanme is wrong
					# END for each class member

					# ignore plugs we possibly did not find in the physical class
				# END for each plug in class
			# END if method exists
		except TypeError:
			# it can be that a subclass overrides this method and makes it an instance method
			# this is valid - the rest of the dgengine always accesses this method
			# through instance - so we have to handle it
			pass

		return newcls




class NodeBase( iDuplicatable ):
	"""Base class that provides support for plugs to the superclass.
	It will create some simple tracking attriubtes required for the plug system
	to work

	Nodes can compute values of their plugs if these do not have a cache.

	Nodes are identified by an ID - the default graph implementation though will
	be okay with just having instances.
	It is also being used for string representations of this node"""
	shellcls = _PlugShell					# class used to instantiate new shells
	__metaclass__ = _NodeBaseCheckMeta		# check the class before its being created

	#{ Overridden from Object
	def __init__( self, *args, **kwargs ):
		"""We require a directed graph to track the connectivity between the plugs.
		It must be supplied by the super class and should be as global as required to
		connecte the NodeBases together properly.
		
		:param kwargs: 'id' = id of the instance, defaults to None if it is not required
		:note: we are super() compatible, and assure our base is initialized correctly"""
		self.graph = None
		self._id = None

		# set id
		newid = kwargs.get( 'id', None )
		if newid:
			self.setID( newid )

	def __del__( self ):
		"""Remove ourselves from the graph and delete our connections"""
		# check if item does still exist - this is not the case if the graph
		# is currently being deleted
		try:
			#self.graph.removeNode( self )		# TODO: take back in and make it work ! Problems with facade nodes
			pass
		except (AttributeError,ReferenceError):		# .graph could be None
			pass

	def __str__( self ):
		"""Use our id as string or the default implementation"""
		if self.id() is not None:
			return str( self.id() )

		return super( NodeBase, self ).__str__( )
	#} Overridden from Object

	#{ iDuplicatable Interface
	def createInstance( self, *args, **kwargs ):
		"""Create a copy of self and return it
		
		:note: override by subclass  - the __init__ methods shuld do the rest"""
		return self.__class__( id = self.id() )

	def copyFrom( self, other, add_to_graph = True ):
		"""Just take the graph from other, but do not ( never ) duplicate it
		
		:param add_to_graph: if true, the new node instance will be added to the graph of
		:note: default implementation does not copy plug caches ( which are stored in
			the node dict - this is because a reevaluate is usually required on the
			duplicated node"""
		self.setID( other.id() )				# id copying would create equally named clones for now
		if add_to_graph and other.graph:		# add ourselves to the graph of the other node
			other.graph.addNode( self )

	#} END iDuplicatable

	#{ Base Interface
	def compute( self, plug, mode ):
		"""Called whenever a plug needs computation as the value its value is not
		cached or marked dirty ( as one of the inputs changed )
		
		:param plug: the static plug instance that requested which requested the computation.
			It is the instance you defined on the class
		:param mode: the mode of operation. Its completely up to the superclasses how that
			attribute is going to be used
		:note: to be implemented by superclass """
		raise NotImplementedError( "To be implemented by subclass" )

	#} END base interface

	#{ ID Handling
	def setID( self, newID ):
		"""Set id of this node to newiD
		:return: previously assigned id"""
		curid = self.id()
		self._id = newID
		return curid

	def id( self ):
		""":return: ID of this instance"""
		return self._id

	#} END id handling

	#{ Base
	def toShells( self, plugs ):
		""":return: list of shells made from plugs and our node"""
		# may not use it as generator as it binds variables ( of course ! )
		outlist = list()
		for plug in plugs:
			outlist.append( self.toShell( plug ) )
		return outlist

	def toShell( self, plug ):
		""":return: a plugshell as suitable to for this class"""
		return getattr( self, 'shellcls' )( self, plug )		# prevent cls variable to be bound !

	def clearCache( self ):
		"""Clear the cache of all plugs on this node - this basically forces it
		to recompute the next time an output plug is being queried"""
		for plug in self.plugs( ):
			self.toShell( plug ).clearCache( clear_affected = False )

	@classmethod
	def plugsStatic( cls, predicate = lambda x: True ):
		""":return: list of static plugs as defined on this node - they are class members
		:param predicate: return static plug only if predicate is true
		:note: Use this method only if you do not have an instance - there are nodes
			that actually have no static plug information, but will dynamically generate them.
			For this to work, they need an instance - thus the plugs method is an instance
			method and is meant to be the most commonly used one."""
		pred = lambda m: isinstance( m, plug )

		# END sanity check
		pluggen = ( m[1] for m in inspect.getmembers( cls, predicate = pred ) if predicate( m[1] ) )
		return list( pluggen )

	def plugs( self, predicate = lambda x: True ):
		""":return: list of dynamic plugs as defined on this node - they are usually retrieved
			on class level, but may be overridden on instance level
		:param predicate: return static plug only if predicate is true"""
		# the getmembers function appears to be ... buggy with my classes
		# use special handling to assure he gets all the instance members AND the class members
		# In ipython tests this worked as expected - get the dicts individually
		all_dict_holders = itertools.chain( ( self, ), self.__class__.mro() )
		all_dicts = ( instance.__dict__ for instance in all_dict_holders )
		pluggen = ( v for d in all_dicts for v in d.itervalues() if isinstance( v, plug ) and predicate( v ) )

		return list( pluggen )

	@classmethod
	def inputPlugsStatic( cls, **kwargs ):
		""":return: list of static plugs suitable as input
		:note: convenience method"""
		return cls.plugsStatic( predicate = lambda p: p.providesInput(), **kwargs )

	def inputPlugs( self, **kwargs ):
		""":return: list of plugs suitable as input
		:note: convenience method"""
		return self.plugs( predicate = lambda p: p.providesInput(), **kwargs )

	@classmethod
	def outputPlugsStatic( cls, **kwargs ):
		""":return: list of static plugs suitable to deliver output
		:note: convenience method"""
		return cls.plugsStatic( predicate = lambda p: p.providesOutput(), **kwargs )

	def outputPlugs( self, **kwargs ):
		""":return: list of plugs suitable to deliver output
		:note: convenience method"""
		return self.plugs( predicate = lambda p: p.providesOutput(), **kwargs )

	def connections( self, inpt, output ):
		""":return: Tuples of input shells defining a connection of the given type from
			tuple( InputNodeOuptutShell, OurNodeInputShell ) for input connections and
			tuple( OurNodeOuptutShell, OutputNodeInputShell )
		:param inpt: include input connections to this node
		:param output: include output connections ( from this node to others )"""
		outConnections = list()
		plugs = self.plugs()
		# HANDLE INPUT
		if inpt:
			shells = self.toShells( ( p for p in plugs if p.providesInput() ) )
			for shell in shells:
				ishell = shell.input( )
				if ishell:
					outConnections.append( ( ishell, shell ) )
			# END for each shell in this node's shells
		# END input handling

		# HANDLE OUTPUT
		if output:
			shells = self.toShells( ( p for p in plugs if p.providesOutput() ) )
			for shell in shells:
				outConnections.extend( ( ( shell, oshell ) for oshell in shell.outputs() ) )
		# END output handling

		return outConnections

	@classmethod
	def filterCompatiblePlugs( cls, plugs, attrOrValue, raise_on_ambiguity = False, attr_affinity = False,
							  	attr_as_source=True ):
		""":return: sorted list of (rate,plug) tuples suitable to deal with the given attribute.
			Thus they could connect to it as well as get their value set.
			Most suitable plug comes first.
			Incompatible plugs will be pruned.
		:param attrOrValue: either an attribute or the value you would like to set to the
			attr at the plug in question.
		:param raise_on_ambiguity: if True, the method raises if a plug has the same
			rating as another plug already on the output list, thus it's not clear anymore
			which plug should handle a request
		:param attr_affinity: if True, it will not check connection affinity, but attribute
			affinity only. It checks how compatible the attributes of the plugs are, disregarding
			whether they can be connected or not
			Only valid if attrOrValue is an attribute
		:param attr_as_source: if True, attrOrValue will be treated as the source of a connection or
			each plug would need to take its values.
			if False, attrOrValue is the destination of a connection and it needs to take values of the given plugs
			or they would connect to it. Only used if attrOrValue is an attribute.
		:raise TypeError: if ambiguous input was found"""

		attribute = None
		value = attrOrValue
		if isinstance( attrOrValue, Attribute ):
			attribute = attrOrValue

		outSorted = list()
		for plug in plugs:

			if attribute:
				sourceattr = attribute
				destinationattr = plug.attr
				if not attr_as_source:
					destinationattr = attribute
					sourceattr = plug.attr

				if attr_affinity:
					rate = destinationattr.affinity( sourceattr )	# how good can dest store source ?
				else:
					rate = sourceattr.connectionAffinity( destinationattr )
				# END which affinity type
			# END attribute rating
			else:
				rate = plug.attr.compatabilityRate( value )
			# END value rating

			if not rate:
				continue

			outSorted.append( ( rate, plug ) )
		# END for each plug

		outSorted.sort()
		outSorted.reverse()		# high rates first

		if raise_on_ambiguity:
			ratemap = dict()
			for rate,plug in outSorted:
				ratemap.setdefault( rate, list() ).append( plug )
			# END for each compatible plug
			report = ""
			for rate, pluglist in ratemap.iteritems( ):
				if len( pluglist ) > 1:
					report += "Rate: %i :" % rate
					for plug in pluglist:
						report += "\n%s" % str(plug)
				# END if ambiguous plugs
			# END for each rate in ratemap
			if report:
				report = "Ambiguous plugs found\n" + report
				raise TypeError( report  )
		# END ambiguous check

		return outSorted

	#} END base




