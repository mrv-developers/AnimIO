# -*- coding: utf-8 -*-
"""Contains base class and common methods for all processes """
__docformat__ = "restructuredtext"
__all__ = list()

from mrv.dge import NodeBase
from mrv.dgfe import GraphNodeBase
from mrv.dge import Attribute
import mrv.automation.base as wflbase

from mrv.path import Path
from mrv.util import Or


def track_output_call( func ):
	"""Wraps the proecss.evaluateStateBase function allowing to gather plenty of information
	about the call, as well as error statistics"""

	def track_func( self, plug, mode ):
		# return simple result if tracking is disabled
		if not self.track_compute_calls:
			return func( self, plug, mode )

		pdata = self.workflow()._trackOutputQueryStart( self, plug, mode )

		try:
			result = func( self, plug, mode )
		except Exception,e:
			pdata.exception = e
			self.workflow()._trackOutputQueryEnd( None )
			raise

		self.workflow()._trackOutputQueryEnd( result )
		return result

	# END track func


	return track_func


class ProcessBase( NodeBase ):
	"""The base class for all processes, defining a common interface
	Inputs and Outputs of this node are statically described using plugs
	
	:note: the process base is able to duplcate properly as it stores in constructor
		arguments accordingly
	"""
	kNo, kGood, kPerfect = 0, 127, 255				# specify how good a certain target can be produced
	is_state, target_state, dirty_check = ( 1,2,4 )

	noun = "Noun ProcessBase,redefine in subclass"	# used in reports
	verb = "Verb ProcessBase,redefine in subclass" # used in reports

	#{ Configuration
	# if False, the computation results will not be tracked in a callgraph
	track_compute_calls = True
	#} END configuration

	__all__.append( "ProcessBase" )

	def __init__( self, id, *args, **kwargs ):
		"""Initialize process with most common information
		
		:param kwargs:
			 * noun: noun describing the process, ( i.e. "Process" )
			 * verb: verb describing the process, ( i.e. "processing" )
			 * workflow: the workflow this instance is part of"""
		self._args = args
		self._kwargs = kwargs
		NodeBase.__init__( self, id = id, *args, **kwargs )		# init last - need our info first !

	#{ iDuplicatable Interface
	def createInstance( self, *args, **kwargs ):
		"""Create a copy of self and return it"""
		return self.__class__( self.id(), *self._args, **self._kwargs )

	def copyFrom( self, other, *args, **kwargs ):
		"""
		Note: we have already given our args to the class during instance creation,
			thus we do not copy args again"""
		pass
	#} END iDuplicatable


	#{ Query

	def targetRating( self, target, check_input_plugs = True, **kwargs ):
		"""
		:return: tuple( int, PlugShell )
			int between 0 and 255 - 255 means target matches perfectly, 0
			means complete incompatability. Any inbetweens indicate the target can be
			achieved, but maybe just in a basic way
			
			If rate is 0, the object will be None, otherwise its a plugShell to the
			input attribute that can take target as input. In process terms this means
			that at least one output plug exists that produces the target.
		:param target: instance or class of target to check for compatability
		:param check_input_plugs: if True, input plugs will be checked for compatability of target,
			otherwise the output plugs
		:raise TypeError: if the result is ambiguous and raise_on_ambiguity = 1"""
		# query our ouput plugs for a compatible attr
		tarplugs = None
		if check_input_plugs:
			tarplugs = self.inputPlugs( )
		else:
			tarplugs = self.outputPlugs( )

		plugrating = self.filterCompatiblePlugs( tarplugs, target, attr_as_source=False , **kwargs )

		if not plugrating:		#	 no plug ?
			return ( 0 , None )

		# remove all non-writable plugs - they can never be targets
		writableRatedPlugs = []
		for rate,plug in plugrating:				# rate,plug tuple
			if plug.attr.flags & Attribute.readonly:
				continue			# need to set the attribute

			# connected plugs are an option, but prefer the ones being open
			if self.toShell( plug ).input():
				rate /= 2.0

			writableRatedPlugs.append( (rate,plug) )
		# END writable only filters

		if not writableRatedPlugs:
			return ( 0, None )

		writableRatedPlugs.sort()		# high comes last

		rate, plug = writableRatedPlugs[-1]
		return ( int(rate), self.toShell( plug ) )


	def supportedTargetTypes( self ):
		""":return: list target types that can be output
		:note: targetTypes are classes, not instances"""
		return [ p.attr.typecls for p in self.inputPlugs() ]

	#} END query

	#{ Interface

	def evaluateState( self, plug, mode ):
		""":return: an instance suitable to be stored in the given plug
		
		:param plug: plug that triggered the computation - use it to compare against
			your classes plugs to see which output is required and return a result suitable
			to be stored in plug
		:param mode: bit flags as follows:
		
			is_state:
				your return value represents the current state of the process - your output will
				represent what actually is present. You may not alter the state of your environment,
				thus this operation is strictly read-only.
				According to your output, when called you need to setup a certain state
				and return the results according to that state. This flag means you are requrested
				to return everything that is right according to the state you shall create.
				If this state is disabled, you should not return the current state, but behave
				according to the other ones.
				
			target_state:
				your return value must represent the 'should' state - thus you must assure
				that the environment is left in a state that matches your plug state - the result
				of that operation will be returned.
				Usually, but not necessarily, the is_state is also requested so that the output
				represents the complete new is_state ( the new state after you changed the environment
				to match the plug_state )
				
			dirty_check:
				Always comes in conjunction with is_state. You are required to return the is_state
				but raise a DirtyException if your inputs would require you to adjust the environment
				to deliver the plug state. If the is_state if the environment is the plug_state
				as there is nothing to do for you, do not raise and simply return your output.
				
			The call takes place as there is no cache for plugType.
		:note: needs to be implemented by subclasses, but subclasses can just call their
			superclass for all unhandled plugs resulting in consistent error messages"""
		raise PlugUnhandled( "Plug %s.%s cannot be handled - check your implementation" % ( self, str( plug ) ) )

	# } END interface

	@track_output_call
	def compute( self, plug, mode = None ):
		"""Base implementation of the output, called by `input` Method.
		Its used to have a general hook for the flow tracing
		
		:param plug: plug to evaluate
		:param mode: the mode of the valuation
		:return: result of the computation"""
		wfl = self.workflow()
		finalmode = wfl._mode			# use global mode

		# if we are root, we take the mode given by the caller though
		if self.track_compute_calls:
			if wfl.callgraph().callRoot().process == self:
				finalmode = mode
		else:
			# either use the explicit mode or the global one
			finalmode = mode or wfl._mode

		# exceptions are handled by dgengine
		# call actually implemented method
		return self.evaluateState( plug, finalmode )


	#{ Base
	# methods that drive the actual call

	def prepareProcess( self ):
		"""Will be called on all processes of the workflow once before a target is
		actually being queried by someone
		It should be used to do whatever you think is required to work as process.
		This uauslly is a special case for most preocesses"""
		pass

	def workflow( self ):
		""":return: the workflow instance we are connected with. Its used to query global data"""
		return self.graph

	#} END base


class WorkflowProcessBase( GraphNodeBase, ProcessBase ):
	"""A process wrapping a workflow, allowing workflows to be nested
	Derive from this class and initialize it with the workflow you would like to have wrapped
	The process works by transmitting relevant calls to its underlying workflow, allowing
	nodeInsideNestedWorkflow -> thisworkflow.node.plug connections

	Workflows are standin nodes - they can connect anything their wrapped nodes can connect
	
	:note: to prevent dependency issues, the workflow instance will be bound on first use
	"""
	__all__.append( "WorkflowProcessBase" )
	workflow_file = "name of the workflow dot file ( incl. extension )"
	workflow_directory = "directory containing workflows to load "

	exclude_connected_plugs = True				# if true, all plugs that are connected will be pruned
	duplicate_wrapped_graph = False			# we load our copies directly and thus have a copy

	def __init__( self, id, wflInstance=None, **kwargs ):
		""" Will take all important configuration variables from its class variables
		- you should override these with your subclass
		
		:param wflInstance: if given, this instance will be used instead of creating
			a new workflow. Used by copy constructor.
		:param kwargs: all arguments required to initialize the ProcessBase"""

		wrappedwfl = wflInstance
		if not wrappedwfl:
			wrappedwfl = self._createWrappedWfl( self.workflow_directory, self.workflow_file )

		# NOTE: baseclass stores wrapped wfl for us
		# init bases
		GraphNodeBase.__init__( self, wrappedwfl, **kwargs )
		ProcessBase.__init__( self, id, **kwargs )

		# adjust the ids of wrapped graph nodes with the name of their graph
		# NO: if this is done, some recurisve facades have issues with their attribute
		# names - although this could possibly be solved, renaming the nodes is in
		# fact not required
		#for node in self.wgraph.iterNodes():
		#	node.setID( "%s.%s" % ( id, node.id() ) )

		# override name - per instance in our case
		self.noun = wrappedwfl.name
		self.verb = "internally computing"

	def createInstance( self, *args, **kwargs ):
		"""Create a copy of self and return it - required due to our very special constructor"""
		return self.__class__( self.id(), wflInstance = self.wgraph )

	def _createWrappedWfl( self, wfldir, wflname ):
		"""
		:return: our wrapped workflow instance as created by a method loading a workflow
			from a file"""
		wfl = wflbase.loadWorkflowFromDotFile( Path( wfldir ) / wflname )
		return wfl

	def prepareProcess( self ):
		"""As we have different callgraphs, but want proper reports, just swap in the
		callgraph of our own workflow to allow it to be maintained correctly when the nodes
		of the wrapped graph evaluate.
		
		:note: this requires that we get called after the callgraph has bene initialized"""
		if self.graph._callgraph.number_of_nodes():
			raise AssertionError( "Callgraph of parent workflow %r was not empty" % self.graph )

		self.wgraph.copyFrom( self.graph )					# copies required attributes

		# Prepare all our wrapped nodes
		for node in self.wgraph.iterNodes( ):
			node.prepareProcess( )

		# ProcessBase.prepareProcess( self )

	def _iterNodes( self ):
		""":return: generator for nodes that have no output connections or no input connections """
		noOutput = lambda node: not node.connections( 0, 1 )
		noInput = lambda node: not node.connections( 1, 0 )
		return self.wgraph.iterNodes( predicate = Or( noInput, noOutput ) )

	def _getNodePlugs( self ):
		"""Override the base method, filtering it's output so that only unconnected plugs
		will be returned"""
		outset = super( WorkflowProcessBase, self )._getNodePlugs( )

		if self.exclude_connected_plugs:
			finalset = set()
			for node, plug in outset:
				shell = node.toShell( plug )
				if not shell.isConnected():
					finalset.add( ( node , plug ) )
				# END if shell is unconnected
			# END for each node,plug pair

			outset = finalset
			self._addIncludeNodePlugs( outset )		# assure we never filter include plugs
		# END exclude connected plugs

		return outset

