# -*- coding: utf-8 -*-
"""Contains nodes supporting facading within a dependency graph  - this can be used
for container tyoes or nodes containing their own subgraph even
"""
__docformat__ = "restructuredtext"

from networkx import DiGraph, NetworkXError
from collections import deque
import inspect
import weakref
from util import iDuplicatable

from dge import NodeBase
from dge import _PlugShell
from dge import iPlug
from dge import Attribute

__all__ = ("FacadeNodeBase", "GraphNodeBase", "OIFacadePlug")

#{ Shells


class _OIShellMeta( type ):
	"""Metaclass building the method wrappers for the _FacadeShell class - not
	all methods should be overridden, just the ones important to use"""

	@classmethod
	def createUnfacadeMethod( cls, funcname ):
		def unfacadeMethod( self, *args, **kwargs ):
			return getattr( self._toIShell(), funcname )( *args, **kwargs )
		return unfacadeMethod

	@classmethod
	def createFacadeMethod( cls, funcname ):
		"""in our case, connections just are handled by our own OI plug, staying
		in the main graph"""
		return list()

	@classmethod
	def createMethod( cls,funcname, facadetype ):
		method = None
		if facadetype == "unfacade":
			method = cls.createUnfacadeMethod( funcname )
		else:
			method = cls.createFacadeMethod( funcname )

		if method: # could be none if we do not overwrite the method
			method.__name__ = funcname

		return method


	def __new__( metacls, name, bases, clsdict ):
		unfacadelist = clsdict.get( '__unfacade__' )
		facadelist = clsdict.get( '__facade__' )

		# create the wrapper functions for the methods that should wire to the
		# original shell, thus we unfacade them
		for funcnamelist, functype in ( ( unfacadelist, "unfacade" ), ( facadelist, "facade" ) ):
			for funcname in funcnamelist:
				method = metacls.createMethod( funcname, functype )
				if method:
					clsdict[ funcname ] = method
			# END for each funcname in funcnamelist
		# END for each type of functions

		return type.__new__( metacls, name, bases, clsdict )


class _IOShellMeta( _OIShellMeta ):
	"""Metaclass wrapping all unfacade attributes on the plugshell trying
	to get an input connection """

	@classmethod
	def createUnfacadeMethod( cls,funcname ):
		""":return: wrapper method for funcname """
		method = None
		if funcname == "get":						# drection to input
			def unfacadeMethod( self, *args, **kwargs ):
				"""apply to the input shell"""
				# behave like the base implementation and check the internal shell
				# for caches first - if it exists, we use it.
				# It would have been cleared if it is affecfted by another plug being set,
				# thus its either still cached or somenone set the cache.
				# if there is no cache, just trace the connections upwards.
				# This means for get we specifiaclly override the normal "original last"
				# behaviour to allow greater flexibility
				oshell = self._getOriginalShell( )
				if oshell.hasCache():
					return oshell.cache()

				return getattr( self._getShells( "input" )[0], funcname )( *args, **kwargs )
			method = unfacadeMethod
		else:										# direction to output
			def unfacadeMethod( self, *args, **kwargs ):
				"""Clear caches of all output plugs as well"""
				for shell in self._getShells( "output" ):
					getattr( shell, funcname )( *args, **kwargs )
			# END unfacade method
			method = unfacadeMethod
		# END funk type handling
		return method

	@classmethod
	def createFacadeMethod( cls, funcname ):
		"""Call the main shell's function"""
		def facadeMethod( self, *args, **kwargs ):
			return getattr( self._getOriginalShell( ), funcname )( *args, **kwargs )
		return facadeMethod


class _OIShell( _PlugShell ):
	"""All connections from and to the FacadeNode must actually start and end there.
	Iteration over internal plugShells is not allowed.
	Thus we override only the methods that matter and assure that the call is handed
	to the acutal internal plugshell.
	We know everything we require as we have been fed with an oiplug

	 * node = facacde node
	 * plug = oiplug containing inode and iplug ( internal node and internal plug )
	 * The internal node allows us to hand in calls to the native internal shell
	"""
	# list all methods that should not be a facade to our facade node
	__unfacade__ = [ 'set', 'get', 'clearCache', 'hasCache','setCache', 'cache' ]

	# keep this list uptodate - otherwise a default shell will be used for the missing
	# function
	# TODO: parse the plugshell class itself to get the functions automatically
	__facade__ = [ 'connect','disconnect','input', 'outputs','connections',
					'iterShells' ]

	__metaclass__ = _OIShellMeta

	def __init__( self, *args ):
		"""Sanity checking"""
		if not isinstance( args[1], OIFacadePlug ):
			raise AssertionError( "Invalid PlugType: Need %r, got %r (%s)" % ( OIFacadePlug, args[1].__class__ , args[1]) )

		# NOTE deprecated in python 2.6 and without effect in our case
		super( _OIShell, self ).__init__( *args )


	def __repr__ ( self ):
		"""Cut away our name in the possible oiplug ( printing an unnecessary long name then )"""
		plugname = str( self.plug )
		nodename = str( self.node )
		plugname = plugname.replace( nodename+'.', "" )
		return "%s.%s" % ( nodename, plugname )

	def _toIShell( self ):
		""":return: convert ourselves to the real shell actually behind this facade plug"""
		# must return original shell, otherwise call would be handed out again
		return self.plug.inode.shellcls.origshellcls( self.plug.inode, self.plug.iplug )


class _IOShell( _PlugShell ):
	"""This callable class, when called, will create a IOShell using the
	actual facade node, not the one given as input. This allows it to have the
	facade system handle the plugshell, or simply satisfy the original request"""

	__unfacade__ = [  'get', 'clearCache' ]

	# keep this list uptodate - otherwise a default shell will be used for the missing
	# function
	# TODO: parse the plugshell class itself to get the functions automatically
	__facade__ = [ 'set','hasCache','setCache', 'cache',
					'connect','disconnect','input','connections','outputs',
					'iterShells' ]

	__metaclass__ = _IOShellMeta

	def __init__( self, *args ):
		"""Initialize this instance - we can be in creator mode or in shell mode.
		ShellMode: we behave like a shell but apply customizations, true if 3 args ( node, plug, origshellcls )
		CreatorMode: we only create shells of our type in ShellMode, true if 2 args
		
		:param args:
		 * origshellcls[0] = the shell class used on the manipulated node before we , must always be set as last arg
		 * facadenode[1] = the facadenode we are connected to
		 
		:todo: optimize by creating the unfacade methods exactly as we need them and bind the respective instance
			methods - currently this is solved with a simple if conditiion.
		"""
		# find whether we are in shell mode or in class mode - depending on the
		# types of the args
		# CLASS MODE
		if hasattr( args[0], '__call__' ) or isinstance( args[0], type ):
			self.origshellcls = args[0]
			self.facadenode = args[1]
			self.iomap = dict() 							# plugname -> oiplug
			super( _IOShell, self ).__init__(  )			# initialize empty
		# END class mode
		#else:
		# NOTE: This is deprecated in python 2.6 and doesnt do anything in our case
			# we do not do anything special in shell mode ( at least value-wise
		#	super( _IOShell, self ).__init__( *args )	# init base
		# END INSTANCE ( SHELL ) MODE

	def __call__( self, *args ):
		"""This equals a constructor call to the shell class on the wrapped node.
		Simply return an ordinary shell at its base, but we catch some callbacks
		This applies to everything but connection handling
		
		:note: the shells we create are default ones with some extra handlers
			for exceptions"""
		return self.__class__( *args )

	#{ Helpers

	def _getoiplug( self ):
		""":return: oiplug suitable for this shell or None"""
		try:
			# cannot use weak references, don't want to use strong references
			return self.node.shellcls.iomap[ self.plug.name() ]
		except KeyError:
			# plug not on facadenode - this is fine as we get always called
			pass
		#except AttributeError:
		# TODO: take that back in once we use weak references or proper ids again ... lets see
		#	# facade node does not know an io plug - assure we do not try again
		#	del( self.node.shellcls[ self.plug.name() ] )

		return None

	def _getOriginalShell( self ):
		""":return: instance of the original shell class that was replaced by our instance"""
		return self.node.shellcls.origshellcls( self.node, self.plug )

	def _getTopFacadeNodeShell( self ):
		"""Recursive method to find the first facade parent having an OI shell
		
		:return: topmost facade node shell or None if we are not a managed plug"""

		# otherwise we have found the topmost parent
		return facadeNodeShell


	def _getShells( self, shelltype ):
		""":return: list of ( outside ) shells, depending on the shelltype and availability.
			If no outside shell is avaiable, return the actual shell only
			As facade nodes can be nested, we have to check each level of nesting
			for connections into the outside world - if available, we use these, otherwise
			we stay 'inside'
		
		:param shelltype: "input" - outside input shell
			"output" - output shells, and the default shell"""
		if not isinstance( self.node.shellcls, _IOShell ):
			raise AssertionError( "Shellclass of %s must be _IOShell, but is %s" % ( self.node, type( self.node.shellcls ) ) )

		# GET FACADE SHELL
		####################
		# get the oiplug on our node
		oiplug = self._getoiplug( )
		if not oiplug:
			# plug not on facadenode, just ignore and return the original shell
			return [ self._getOriginalShell( ) ]
		# END if there is no cached oiplug


		# Use the facade node shell type - we need to try to get connections now,
		# either inputs or outputs on our facade node. In case it is facaded
		# as well, we just use a default shell that will definetly handle connections
		# the way we expect it
		facadeNodeShell = self.node.shellcls.facadenode.toShell( oiplug )


		# NESTED FACADE NODES SPECIAL CASE !
		######################################
		# If a facade node is nested inside of another facade node, it will put
		# it's IO shell above our OI shell.
		# IOShells do not return connections - get a normal shell then
		connectionShell = facadeNodeShell
		if facadeNodeShell.__class__ is _IOShell:
			connectionShell = _PlugShell( facadeNodeShell.node, facadeNodeShell.plug )
		# END nested facade node special handling


		outShells = list()
		if shelltype == "input":

			# HIGHER LEVEL INPUT SHELLS
			############################
			# if we are nested, use an imput connection of our parent as they
			# override lower level connections
			if not connectionShell is facadeNodeShell:
				aboveLevelInputShells = facadeNodeShell._getShells( shelltype )

				# this is either the real input shell, or the original shell of the toplevel
				# By convention, we return the facadeshell that is connected to the input
				# in rval[1]
				# The method that calls us only uses array index [0], which is the shell it needs !
				# We just use the length as internal flag !
				if len( aboveLevelInputShells ) == 2:		# top level orverride !
					return aboveLevelInputShells

			# END aquire TL Input

			# still here means no toplevel override
			# TRY OUR LEVEL INPUT
			inputShell = connectionShell.input( )

			if inputShell:
				# FLAGGED RETURN VALUE : this indicates to our callers that
				# we have found a good input on our level and want to use it.
				# if the caller is the metaclass wrapper, it will only use the outshell[0]
				# anyways and not bother
				outShells.append( inputShell )
				outShells.append( self )
			else:
				outShells.append( self._getOriginalShell( ) )

		# END outside INPUT shell handling
		else:
			outShells.extend( connectionShell.outputs( ) )

			# ADD 'INSIDE' ORIGINAL SHELL
			# always allow our 'inside' level to get informed as well
			outShells.append( self._getOriginalShell( ) )

			# NESTED SHELL SPECIAL CASE
			##############################
			# query the IO Parent Shell for the shells on its level and add them
			if not connectionShell is facadeNodeShell:
				outShells.extend( facadeNodeShell._getShells( shelltype ) )
		# END outside OUTPUT shell handling

		return outShells

	# } END helpers


# END shells


#{ Nodes

class FacadeNodeBase( NodeBase ):
	"""Node having no own plugs, but retrieves them by querying other other nodes
	and claiming its his own ones.

	Using a non-default shell it is possibly to guide all calls through to the
	virtual PlugShell.

	Derived classes must override _plugshells which will be queried when
	plugs or plugshells are requested. This node will cache the result and do
	everything required to integrate itself.

	It lies in the nature of this class that the plugs are dependent on a specific instance
	of this node, thus classmethods of NodeBase have been overridden with instance versions
	of it.

	The facade node keeps a plug map allowing it to map plug-shells it got from
	you back to the original shell respectively. If the map has been missed,
	your node will be asked for information.

	:note: facades are intrusive for the nodes they are facading - thus the nodes
		returned by `_getNodePlugs` will be altered. Namely the instance will get a
		shellcls and plug override to allow us to hook into the callchain. Thus you should have
		your own instance of the node - otherwise things might behave differently for
		others using your nodes from another angle

	:note: this class could also be used for facades Container nodes that provide
		an interface to their internal nodes"""
	shellcls = _OIShell		# overriden from NodeBase

	#{ Configuration
	caching_enabled = True						# if true, the facade may cache plugs once queried
	#} END configuration

	def __init__( self, *args, **kwargs ):
		""" Initialize the instance"""
		self._cachedOIPlugs = list()							# simple list of names
		NodeBase.__init__( self, *args, **kwargs )


	def __getattr__( self, attr ):
		""":return: shell on attr made from our plugs - we do not have real ones, so we
			need to call plugs and find it by name
		
		:note: to make this work, you should always name the plug names equal to their
			class attribute"""
		check_ambigious = not attr.startswith( OIFacadePlug._fp_prefix )	# non long names are not garantueed to be unique

		candidates = list()
		for plug in self.plugs( ):
			if plug.name() == attr or plug.iplug.name() == attr:
				shell = self.toShell( plug )
				if not check_ambigious:
					return shell
				candidates.append( shell )
			# END if plugname matches
		# END for each of our plugs

		if not candidates:
			raise AttributeError( "Attribute %s does not exist on %s" % (attr,self) )

		if len( candidates ) == 1:
			return candidates[0]

		# must be more ...
		raise AttributeError( "More than one plug with the local name %s exist on %s - use the long name, i.e. %snode_attr" % ( attr, self, OIFacadePlug._fp_prefix ) )



	def copyFrom( self, other, **kwargs ):
		"""Actually, it does nothing because our plugs are linked to the internal
		nodes in a quite complex way. The good thing is that this is just a cache that
		will be updated once someone queries connections again.
		Basically it comes down to the graph duplicating itself using node and plug
		methods instead of just doing his 'internal' magic"""
		pass


	#{ To be Subclass-Implemented

	def _getNodePlugs( self ):
		"""Implement this as if it was your plugs method - it will be called by the
		base - your result needs processing before it can be returned
		
		:return: list( tuple( node, plug ) )
			if you have an existing node that the plug or shell  you gave is from,
			return it in the tuple, otherwise set it to a node with a shell that allows you
			to handle it - the only time the node is required is when it is used in and with
			the shells of the node's own shell class.

			The node will be altered slightly to allow input of your facade to be reached
			from the inside
		
		:note: a predicate is not supported as it must be applied on the converted
			plugs, not on the ones you hand out"""
		raise NotImplementedError( "Needs to be implemented in SubClass" )
		
	#} END to be subclass implemented


	def plugs( self, **kwargs ):
		"""Calls `_getNodePlugs` method to ask you to actuallly return your
		actual nodes and plugs or shells.
		We prepare the returned value to assure we are being called in certain occasion,
		which actually glues outside and inside worlds together """
		# check args - currently only predicate is supported
		predicate = kwargs.pop( 'predicate', lambda x: True )

		if kwargs:		# still args that we do not know ?
			raise AssertionError( "Unhandled arguments found  - update this method: %s" % kwargs.keys() )


		# HAND OUT CACHE
		#################
		if self._cachedOIPlugs:
			outresult = list()
			for oiplug in self._cachedOIPlugs:
				if predicate( oiplug ):
					outresult.append( oiplug )
			# END for each cached plug
			return outresult
		# END for each cached plug


		# GATHER PLUGS FROM SUBCLASS
		##############################
		yourResult = self._getNodePlugs( )


		def toFacadePlug( node, plug ):
			if isinstance( plug, OIFacadePlug )\
			and self is plug.inode.shellcls.facadenode: 		# we can wrap other facade nodes as well
				return plug
			return OIFacadePlug( node, plug )
		# END to facade plug helper

		# PROCESS RETURNED PLUGS
		finalres = list()
		for orignode, plug in yourResult:
			oiplug = toFacadePlug( orignode, plug )


			# Cache all plugs, ignoring the predicate
			if self.caching_enabled:
				self._cachedOIPlugs.append( oiplug )
			# END cache update


			# MODIFY NODE INSTANCE
			##################################################
			# Allowing us to get callbacks once the node is used inside of the internal
			# structures

			# ADD FACADE SHELL CLASS
			############################
			# This can also handle facaded facade nodes, as they have the type
			# of _IOShell as shellcls, but no instance
			if not isinstance( orignode.shellcls, _IOShell ):
				classShellCls = orignode.shellcls
				orignode.shellcls = _IOShell( classShellCls, self )
				# END for each shell to reconnect
			# END if we have to swap in our facadeIOShell


			# update facade shell class ( inst ) cache so that it can map our internal
			# plug to the io plug on the outside node
			# cannot create weakref to tuple type unfortunately - use name instead
			orignode.shellcls.iomap[ oiplug.iplug.name() ] = oiplug


			# UPDATE CONNECTIONS ( per plug, not per node )
			##########################
			# update all connections with the new shells - they are required when
			# walking the affects tree, as existing ones will be taken instead of
			# our new shell then.
			internalshell = orignode.toShell( oiplug.iplug )
			all_shell_cons = internalshell.connections( 1, 1 )	 				# now we get old shells

			# disconnect and reconnect with new
			for edge in all_shell_cons:
				nedge = list( ( None, None ) )
				created_shell = False

				for i,shell in enumerate( edge ):
					nedge[ i ] = shell
					# its enough to just have an io shell here, it just assures
					# our callbacks
					# edges are always ordered start->end - we could be any of these
					# thus we have to check before
					if shell == internalshell and not isinstance( shell, _IOShell ) :
						nedge[ i ] = shell.node.toShell( shell.plug )
						created_shell = True
				# END for each shell in edge

				if created_shell:
					edge[0].disconnect( edge[1] )
					nedge[0].connect( nedge[1] )
				# END new shell needs connection
			# END for each edge to update


			# ONLY AFTER EVERYTHING HAS BEEN UPDATED, WE MAY DROP IT
			##########################################################
			if not predicate( oiplug ):
				continue

			finalres.append( oiplug )

		# END for each orignode,plug in result


		# the final result has everything nicely put back together, but
		# it has been altered as well
		return finalres

	def clearPlugCache( self ):
		"""if a cache has been build as caching is enabled, this method clears
		the cache forcing it to be updated on the next demand
		
		:note: this could be more efficient by just deleting plugs that are
			not required anymore, but probably this method can expect the whole
			cache to be deleted right away ... so its fine"""
		self._cachedOIPlugs = list()


class GraphNodeBase( FacadeNodeBase ):
	"""A node wrapping a graph, allowing it to be nested within the node
	All inputs and outputs on this node are purely virtual, thus they internally connect
	to the wrapped graph.

	:todo: tests deletion of graphnodes and see whether they are being garbage collected.
		It should work with the new collector as it can handle cyclic references - these
		strong cycles we have a lot in this structure. Weakrefs will not work for nested
		facade nodes as they are tuples not allowing weak refs.
	"""
	#{ Configuration
	duplicate_wrapped_graph	 = True			# an independent copy of the wrapped graph usually is required - duplication assures that ( or the caller )
	allow_auto_plugs = True					# if True, plugs can be found automatically by iterating nodes on the graph and using their plugs
	ignore_failed_includes = False			# if True, node will not raise if a plug to be included cannot be found

	# list of node.plug strings ( like "node.inName" ) and/or node names ( like "node" )
	# defining the plugs you  would like to specifically include on the facade
	# If just a name is given, the node name is assumed and all plugs on that node will be included
	include = list()

	# same as include, but matching nodes/plugs will be excluded
	exclude = list()
	#}END configuration

	def __init__( self, wrappedGraph, *args, **kwargs ):
		""" Initialize the instance
		:param wrappedGraph: graph we are wrapping"""
		self.wgraph = wrappedGraph
		if self.duplicate_wrapped_graph:
			self.wgraph = self.wgraph.duplicate( )

		FacadeNodeBase.__init__( self, *args, **kwargs )

	def createInstance( self , **kwargs ):
		"""Create a copy of self and return it"""
		return self.__class__( self.wgraph )	# graph will be duplicated in the constructor


	#{ Base Methods

	def _iterNodes( self ):
		""":return: generator for nodes in our graph
		:note: derived classes could override this to just return a filtered view on
			their nodes"""
		return self.wgraph.iterNodes( )

	#} END base


	def _addIncludeNodePlugs( self, outset ):
		"""Add the plugs defined in include to the given output list"""
		missingplugs = list()
		nodes = self.wgraph.nodes()
		nodenames = [ str( node ) for node in nodes ]

		for nodeplugname in self.include:
			nodename = plugname = None

			# INCLUDE WHOLE NODE HANDLING
			##############################
			if nodeplugname.find( '.' ) == -1 :
				nodename = nodeplugname
			else:
				nodename, plugname = tuple( nodeplugname.split( "." ) )
			# END wholenode check

			# FIND NODE INSTANCE
			######################
			try:
				index = nodenames.index( nodename )
				node = nodes[ index ]
			except ValueError:
				missingplugs.append( nodeplugname )
				continue


			# ADD INCLUDE PLUGS
			###################
			if not plugname:
				outset.update( ( (node,plug) for plug in node.plugs() ) )
			else:
				# find matching plugs
				try:
					plug = getattr( node, plugname ).plug
				except AttributeError:
					missingplugs.append( nodeplugname )
				else:
					# finally append the located plug
					outset.add( ( node , plug ) )
					continue
			# END whole node handling
		# END for each nodeplug name

		if not self.ignore_failed_includes and missingplugs:
			msg = "%s: Could not find following include plugs: %s" % ( self, ",".join( missingplugs ) )
			raise AssertionError( msg )

	def _removeExcludedPlugs( self, outset ):
		"""remove the plugs from our exclude list and modify the outset"""
		if not self.exclude:
			return

		excludepairs = set()
		excludeNameTuples = [ tuple( plugname.split( "." ) ) for plugname in self.exclude ]
		for node,plug in outset:
			for nodeplugname  in self.exclude:

				nodename = plugname = None
				if nodeplugname.find( '.' ) == -1:			# node mode
					nodename = nodeplugname
				else:
					nodename,plugname = nodeplugname.split( '.' ) # node plug mode

				if nodename == str( node ) and ( not plugname or plugname == plug.name() ):
					excludepairs.add( ( node,plug ) )
			# END for each nodename.plugname to exclude
		# END for each node,plug pair

		# substract our pairs accordingly to modify the set
		outset -= excludepairs

	def _getNodePlugs( self ):
		""":return: all plugs on nodes we wrap ( as node,plug tuple )"""
		outset = set()

		# get the included plugs
		self._addIncludeNodePlugs( outset )

		if self.allow_auto_plugs:
			for node in self._iterNodes():
				plugresult = node.plugs(  )
				outset.update( set( ( (node,plug) for plug in plugresult ) ) )
				# END update lut map
			# END for node in nodes
		# END allow auto plugs

		# remove excluded plugs
		self._removeExcludedPlugs( outset )

		# the rest of the nitty gritty details, the base class will deal
		return outset

#} END nodes


#{ Plugs
class OIFacadePlug( tuple , iPlug ):
	"""Facade Plugs are meant to be stored on instance level overriding the respective
	class level plug descriptor.
	If used directly, it will facade the internal affects relationships and just return
	what really is affected on the facade node

	Additionally they are associated to a node instance, and can thus be used to
	find the original node once the plug is used in an OI facacde shell

	Its a tuple as it will be more memory efficient that way. Additionally one
	automatically has a proper hash and comparison if the same objects come together
	"""
	_fp_prefix = "_FP_"

	#{ Object Overridden Methods

	def __new__( cls, *args ):
		"""Store only weakrefs, throw if we do not get 3 inputs
		
		:param args:
			 * arg[0] = internal node
			 * arg[1] = internal plug"""
		count = 2
		if len( args ) != count:
			raise AssertionError( "Invalid Argument count, should be %i, was %i" % ( count, len( args ) ) )

		#return tuple.__new__( cls, ( weakref.ref( arg ) for arg in args ) )
		return tuple.__new__( cls,  args )		# NOTE: have to use string refs for recursive facade plugs


	def __getattr__( self, attr ):
		""" Allow easy attribute access
		inode: the internal node
		iplug: the internal plug

		Thus we must:
		 - Act as IOFacade returning additional information
		 
		 - Act as original plug for attribute access
		 
		This will work as long as the method names are unique
		"""
		if attr == 'inode':
			return self[0]
		if attr == 'iplug':
			return self[1]

		# still here ? try to return a value on the original plug
		return getattr( self.iplug, attr )

	#} END object overridden methods


	def name( self ):
		""" Get name of facade plug
		
		:return: name of (internal) plug - must be a unique key, unique enough
			to allow connections to several nodes of the same type"""
		return "%s%s_%s" % ( self._fp_prefix, self.inode, self.iplug )


	def _affectedList( self, direction ):
		""" Get affected shells into the given direction
		
		:return: list of all oiplugs looking in direction, if
			plugtestfunc says: False, do not prune the given shell"""
		these = lambda shell: shell.plug is self.iplug or not isinstance( shell, _IOShell ) or shell._getoiplug() is None

		iterShells = self.inode.toShell( self.iplug ).iterShells( direction=direction, prune = these, visit_once=True )
		outlist = [ shell._getoiplug() for shell in iterShells ]

		return outlist

	def affects( self, otherplug ):
		"""Affects relationships will be set on the original plug only"""
		return self.iplug.affects( otherplug )

	def affected( self ):
		"""Walk the internal affects using an internal plugshell
		
		:note: only output plugs can be affected - this is a rule followed throughout the system
		:return: tuple containing affected plugs ( plugs that are affected by our value )"""
		return self._affectedList( "down" )

	def affectedBy( self ):
		"""Walk the graph upwards and return all input plugs that are being facaded
		:return: tuple containing plugs that affect us ( plugs affecting our value )"""
		return self._affectedList( "up" )

	def providesOutput( self ):
		""":return: True if this is an output plug that can trigger computations """
		return self.iplug.providesOutput( )

	def providesInput( self ):
		""":return: True if this is an input plug that will never cause computations"""
		return self.iplug.providesInput( )


#} END plugs
