# -*- coding: utf-8 -*-
"""Contains interface definitions """
__docformat__ = "restructuredtext"

from collections import deque as Deque
import logging
log = logging.getLogger('mrv.interface')

__all__ = ("Interface", "iDagItem", "iDuplicatable", "iChoiceDialog", "iPrompt", 
           "iProgressIndicator")

class Interface( object ):
	"""Base for all interfaces.
	All interfaces should derive from here."""
	
	# assure we can be handled efficiently - subclasses are free not to define 
	# slots, but those who do will not inherit a __dict__ from here
	__slots__ = tuple()
	
	def supports( self, interface_type ):
		""":return: True if this instance supports the interface of the given type
		:param interface_type: Type of the interface you require this instance 
			to support
		:note: Must be used in case you only have a weak reference of your interface
			instance or proxy which is a case where the ordinary isinstance( obj, iInterface )
			will not work"""
		return isinstance( self, interface_type )


class iDagItem( Interface ):
	""" Describes interface for a DAG item.
	Its used to unify interfaces allowing to access objects in a dag like graph
	Of the underlying object has a string representation, the defatult implementation
	will work natively.
	Otherwise the getParent and getChildren methods should be overwritten
	
	:note: a few methods of this class are abstract and need to be overwritten
	:note: this class expects the attribute '_sep' to exist containing the
		separator at which your object should be split ( for default implementations ).
		This works as the passed in pointer will belong to derived classes that can
		define that attribute on instance or on class level"""

	kOrder_DepthFirst, kOrder_BreadthFirst = range(2)

	# assure we can be handled efficiently - subclasses are free not to define 
	# slots, but those who do will not inherit a __dict__ from here
	__slots__ = tuple()

	#{ Configuration
	# separator as appropriate for your class if it can be treated as string
	# if string treatment is not possibly, override the respective method
	_sep = None
	#} END configuration

	#{ Query Methods

	def isRoot( self ):
		""":return: True if this path is the root of the DAG """
		return self ==  self.root()

	def root( self ):
		""":return: the root of the DAG - it has no further parents"""
		parents = self.parentDeep( )
		if not parents:
			return self
		return parents[-1]

	def basename( self ):
		""":return: basename of this path, '/hello/world' -> 'world'"""
		return str(self).split( self._sep )[-1]

	def parent( self ):
		"""
		:return: parent of this path, '/hello/world' -> '/hello' or None if this path
			is the dag's root"""
		tokens =  str(self).split( self._sep )
		if len( tokens ) <= 2:		# its already root
			return None

		return self.__class__( self._sep.join( tokens[0:-1] ) )

	def parentDeep( self ):
		""":return: all parents of this path, '/hello/my/world' -> [ '/hello/my','/hello' ]"""
		return list( self.iterParents( ) )

		return out

	def children( self , predicate = lambda x: True):
		""":return: list of intermediate children of path, [ child1 , child2 ]
		:param predicate: return True to include x in result
		:note: the child objects returned are supposed to be valid paths, not just relative paths"""
		raise NotImplementedError( )

	def childrenDeep( self , order = kOrder_BreadthFirst, predicate=lambda x: True ):
		""":return: list of all children of path, [ child1 , child2 ]
		:param order: order enumeration
		:param predicate: returns true if x may be returned
		:note: the child objects returned are supposed to be valid paths, not just relative paths"""
		out = []
		if order == self.kOrder_DepthFirst:
			def depthSearch( child ):
				if not predicate( c ):
					return
				children = child.children( predicate = predicate )
				for c in children:
					depthSearch( c )
				out.append( child )
			# END recursive search method

			depthSearch( self )
		# END if depth first
		elif order == self.kOrder_BreadthFirst:
			childstack = Deque( [ self ] )
			while childstack:
				item = childstack.pop( )
				if not predicate( item ):
					continue
				children = item.children( predicate = predicate )

				childstack.extendleft( children )
				out.extend( children )
			# END while childstack
		# END if breadth first
		return out

	def isPartOf( self, other ):
		""":return: True if self is a part of other, and thus can be found in other
		:note: operates on strings only"""
		return str( other ).find( str( self ) ) != -1

	def isRootOf( self, other ):
		""":return: True other starts with self
		:note: operates on strings
		:note: we assume other has the same type as self, thus the same separator"""
		selfstr =  self.addSep( str( self ), self._sep )
		other = self.addSep( str( other ), self._sep )
		return other.startswith( selfstr )

	#} END Query Methods

	#{ Iterators
	def iterParents( self , predicate = lambda x : True ):
		""":return: generator retrieving all parents up to the root
		:param predicate: returns True for all x that you want to be returned"""
		curpath = self
		while True:
			parent = curpath.parent( )
			if not parent:
				raise StopIteration

			if predicate( parent ):
				yield parent

			curpath = parent
		# END while true


	#} END Iterators

	#{ Name Generation
	@classmethod
	def addSep( cls, item, sep ):
		""":return: item with separator added to it ( just once )
		:note: operates best on strings
		:param item: item to add separator to
		:param sep: the separator"""
		if not item.endswith( sep ):
			item += sep
		return item

	def fullChildName( self, childname ):
		"""Add the given name to the string version of our instance
		:return: string with childname added like name _sep childname"""
		sname = self.addSep( str( self ), self._sep )

		if childname.startswith( self._sep ):
			childname = childname[1:]

		return sname + childname

	#} END name generation


class iDuplicatable( Interface ):
	"""Simple interface allowing any class to be properly duplicated
	
	:note: to implement this interface, implement `createInstance` and
		`copyFrom` in your class """
	
	# assure we can be handled efficiently - subclasses are free not to define 
	# slots, but those who do will not inherit a __dict__ from here
	__slots__ = tuple()
	
	def __copyTo( self, instance, *args, **kwargs ):
		"""Internal Method with minimal checking"""
		# Get reversed mro, starting at lowest base
		mrorev = instance.__class__.mro()
		mrorev.reverse()

		# APPLY COPY CONSTRUCTORS !
		##############################
		for base in mrorev:
			if base is iDuplicatable:
				continue

			# must get the actual method directly from the base ! Getattr respects the mro ( of course )
			# and possibly looks at the base's superclass methods of the same name
			try:
				copyFromFunc = base.__dict__[ 'copyFrom' ]
				copyFromFunc( instance, self, *args, **kwargs )
			except KeyError:
				pass
			except TypeError,e:
				raise
		# END for each base

		# return the result !
		return instance
	
	#{ Interface

	def createInstance( self, *args, **kwargs ):
		"""Create and Initialize an instance of self.__class__( ... ) based on your own data
		
		:return: new instance of self
		:note: using self.__class__ instead of an explicit class allows derived
			classes that do not have anything to duplicate just to use your implementeation
			
		:note: you must support ``args`` and ``kwargs`` if one of your iDuplicate bases does"""
		return self.__class__(*args, **kwargs)

	def copyFrom( self, other, *args, **kwargs ):
		"""Copy the data from other into self as good as possible
		Only copy the data that is unique to your specific class - the data of other
		classes will be taken care of by them !
		
		:note: you must support ``args`` and ``kwargs`` if one of your iDuplicate bases does"""
		raise NotImplementedError( "Copy all data you know from other into self" )

	#} END interface

	def duplicate( self, *args, **kwargs ):
		"""Implements a c-style copy constructor by creating a new instance of self
		and applying the `copyFrom` methods from base to all classes implementing the copyfrom
		method. Thus we will call the method directly on the class
		
		:param args: passed to `copyFrom` and `createInstance` method to give additional directions
		:param kwargs: see param args"""
		try:
			createInstFunc = getattr( self, 'createInstance' )
			instance = createInstFunc( *args, **kwargs )
		except TypeError,e:
			#raise
			raise AssertionError( "The subclass method %s must support *args and or **kwargs if the superclass does, error: %s" % ( createInstFunc, e ) )


		# Sanity Check
		if not ( instance.__class__ is self.__class__ ):
			msg = "Duplicate must have same class as self, was %s, should be %s" % ( instance.__class__, self.__class__ )
			raise AssertionError( msg )

		return self.__copyTo( instance, *args, **kwargs )

	def copyTo( self, instance, *args, **kwargs ):
		"""Copy the values of ourselves onto the given instance which must be an
		instance of our class to be compatible.
		Only the common classes will be copied to instance
		
		:return: altered instance
		:note: instance will be altered during the process"""
		if type( instance ) != type( self ):
			raise TypeError( "copyTo: Instance must be of type %s but was type %s" % ( type( self ), type( instance ) ) )
		return self.__copyTo( instance, *args, **kwargs )

	def copyToOther( self, instance, *args, **kwargs ):
		"""As `copyTo`, but does only require the objects to have a common base.
		It will match the actually compatible base classes and call `copyFrom`
		if possible.
		As more checking is performed, this method performs worse than `copyTo`"""
		# Get reversed mro, starting at lowest base
		mrorev = instance.__class__.mro()
		mrorev.reverse()
		
		own_bases = self.__class__.mro()
		own_bases.reverse()
		
		# APPLY COPY CONSTRUCTORS !
		##############################
		for base in mrorev:
			if base is iDuplicatable or base not in own_bases:
				continue
			
			try:
				copyFromFunc = base.__dict__[ 'copyFrom' ]
				copyFromFunc( instance, self, *args, **kwargs )
			except KeyError:
				pass
			except TypeError,e: 
				raise AssertionError( "The subclass method %s.%s must support *args and or **kwargs if the superclass does, error: %s" % (base, copyFromFunc,e) )
		# END for each base
		return instance
	

class iChoiceDialog( Interface ):
	"""Interface allowing access to a simple confirm dialog allowing the user
	to pick between a selection of choices, one of which he has to confirm
	
	:note: for convenience, this interface contains a brief implementation as a
		basis for subclasses, using standard input  and standard ouput for communication"""

	def __init__( self, *args, **kwargs ):
		"""Allow the user to pick a choice
		
		:note: all paramaters exist in a short and a long version for convenience, given
			in the form short/long
		:param kwargs:
			 * t/title: optional title of the choice box, quickly saying what this choice is about
			 * m/message: message to be shown, informing the user in detail what the choice is about
			 * c/choices: single item or list of items identifying the choices if used as string
			 * dc/defaultChoice: choice in set of choices to be used as default choice, default is first choice
			 * cc/cancelChoice: choice in set of choices to be used if the dialog is cancelled using esc,
			   default is last choice"""
		self.title = kwargs.get( "t", kwargs.get( "title", "Choice Dialog" ) )
		self.message = kwargs.get( "m", kwargs.get( "message", None ) )
		assert self.message

		self.choices = kwargs.get( "c", kwargs.get( "choices", None ) )
		assert self.choices

		# internally we store a choice list
		if not isinstance( self.choices, ( list, tuple ) ):
			self.choices = [ self.choices ]

		self.default_choice = kwargs.get( "dc", kwargs.get( "defaultChoice", self.choices[0] ) )
		self.cancel_choice = kwargs.get( "cc", kwargs.get( "cancelChoice", self.choices[-1] ) )


	def choice( self ):
		"""Make the choice
		
		:return: name of the choice made by the user, the type shall equal the type given
			as button names
		:note: this implementation always returns the default choice"""
		log.info(self.title)
		log.info("-"*len( self.title ))
		log.info(self.message)
		log.info(" | ".join(( str( c ) for c in self.choices )))
		log.info("answer: %s" % self.default_choice)

		return self.default_choice


class iPrompt( Interface ):
	"""Prompt a value from the user, providing a default if no input is retrieved"""

	def __init__( self, **kwargs ):
		"""Configure the prompt, most parameters allow short and long names
		
		:param kwargs:
			 * m/message: Message to be presented, like "Enter your name", must be set
			 * d/default: default value to return in case there is no input
			 * cd/cancelDefault: default value if prompt is cancelled
			 * confirmToken: token to enter/hit/press to finish the prompt
			 * cancelToken: token to cancel and abort the prompt"""
		self.msg = kwargs.pop( "m", kwargs.pop( "message", None ) )
		assert self.msg is not None, "No Message given"
		self.confirmDefault = kwargs.pop( "d", kwargs.pop( "default", None ) )
		self.cancelDefault = kwargs.pop( "cd", kwargs.pop( "cancelDefault", None ) )
		self.confirmToken = kwargs.pop( "t", kwargs.pop( "confirmToken", None ) )
		self.cancelToken = kwargs.pop( "ct", kwargs.pop( "cancelToken", None ) )

		# remaining arguments for subclass use
		self._kwargs = kwargs

	def prompt( self ):
		"""activate our prompt
		:return: the prompted value
		:note: base implementation just prints a sample text and returns the default"""
		log.info("%s [ %s ]:" % ( self.msg, self.confirmDefault ))
		log.info("Hit %s to confirm or %s to cancel" % ( self.confirmToken, self.cancelToken ))
		return self.confirmDefault


class iProgressIndicator( Interface ):
	"""Interface allowing to submit progress information
	The default implementation just prints the respective messages
	Additionally you may query whether the computation has been cancelled by the user
	
	:note: this interface is a simple progress indicator itself, and can do some computations
		for you if you use the get() method yourself"""


	#{ Initialization
	def __init__( self, min = 0, max = 100, is_relative = True, may_abort = False, round_robin=False, **kwargs ):
		""":param min: the minimum progress value
		:param max: the maximum progress value
		:param is_relative: if True, the values given will be scaled to a range of 0-100,
			if False no adjustments will be done
		:param round_robin: see `setRoundRobin` 
		:param kwargs: additional arguments being ignored"""
		self.setRange( min, max )
		self.setRelative( is_relative )
		self.setAbortable( may_abort )
		self.setRoundRobin( round_robin )
		self.__progress = min



	def begin( self ):
		"""intiialize the progress indicator before calling `set` """
		self.__progress = self.__min		# refresh

	def end( self ):
		"""indicate that you are done with the progress indicator - this must be your last
		call to the interface"""
		pass

	#} END initialization

	#{ Edit
	def refresh( self, message = None ):
		"""Refresh the progress indicator so that it represents its values on screen.
		
		:param message: message passed along by the user"""
		p = self.get( )

		if not message:
			message = self.prefix( p )

		log.info(message)

	def set( self, value, message = None , omit_refresh=False ):
		"""Set the progress of the progress indicator to the given value
		
		:param value: progress value ( min<=value<=max )
		:param message: optional message you would like to give to the user
		:param omit_refresh: by default, the progress indicator refreshes on set,
			if False, you have to call refresh manually after you set the value"""
		self.__progress = value

		if not omit_refresh:
			self.refresh( message = message )

	def setRange( self, min, max ):
		"""set the range within we expect our progress to occour"""
		self.__min = min
		self.__max = max
		
	def setRoundRobin( self, round_robin ):
		"""Set if round-robin mode should be used. 
		If True, values exceeding the maximum range will be wrapped and 
		start at the minimum range""" 
		self.__rr = round_robin

	def setRelative( self, state ):
		"""enable or disable relative progress computations"""
		self.__relative = state

	def setAbortable( self, state ):
		"""If state is True, the progress may be interrupted, if false it cannot
		be interrupted"""
		self.__may_abort = state

	def setup( self, range=None, relative=None, abortable=None, begin=True, round_robin=None ):
		"""Multifunctional, all in one convenience method setting all important attributes
		at once. This allows setting up the progress indicator with one call instead of many
		
		:note: If a kw argument is None, it will not be set
		:param range: Tuple( min, max ) - start ane end of progress indicator range
		:param relative: equivalent to `setRelative`
		:param abortable: equivalent to `setAbortable`
		:param round_robin: equivalent to `setRoundRobin`
		:param begin: if True, `begin` will be called as well"""
		if range is not None:
			self.setRange( range[0], range[1] )

		if relative is not None:
			self.setRelative( relative )

		if abortable is not None:
			self.setAbortable( abortable )
			
		if round_robin is not None:
			self.setRoundRobin(round_robin)

		if begin:
			self.begin()

	#} END edit

	#{ Query
	def get( self ):
		""":return: the current progress value
		
		:note: if set to relative mode, values will range
			from 0.0 to 100.0.
			Values will always be within the ones returned by `range`"""
		p = self.value()
		mn,mx = self.range()
		if self.roundRobin():
			p = p % mx
				
		if not self.isRelative():
			return min( max( p, mn ), mx )
		# END relative handling 
		
		# compute the percentage
		return min( max( ( p - mn ) / float( mx - mn ), 0.0 ), 1.0 ) * 100.0
		
	def value( self ):
		""":return: current progress as it is stored internally, without regarding 
			the range or round-robin options.
			
		:note: This allows you to use this instance as a counter without concern to 
			the range and round-robin settings"""
		return self.__progress

	def range( self ):
		""":return: tuple( min, max ) value"""
		return ( self.__min, self.__max )

	def roundRobin( self ):
		""":return: True if roundRobin mode is enabled"""
		return self.__rr

	def prefix( self, value ):
		"""
		:return: a prefix indicating the progress according to the current range
			and given value """
		prefix = ""
		if self.isRelative():
			prefix = "%i%%" % value
		else:
			mn,mx = self.range()
			prefix = "%i/%i" % ( value, mx )

		return prefix

	def isAbortable( self ):
		""":return: True if the process may be cancelled"""
		return self.__may_abort

	def isRelative( self ):
		"""
		:return: true if internal progress computations are relative, False if
			they are treated as absolute values"""
		return self.__relative

	def isCancelRequested( self ):
		""":return: true if the operation should be aborted"""
		return False
	#} END query

