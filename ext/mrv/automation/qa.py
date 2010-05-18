# -*- coding: utf-8 -*-
"""Specialization of workflow to provide quality assurance capabilities.

General Idiom of a quality assurance facility is to provide read-only checks for
possibly quaility issues and possibly a fix for them.

The interface is determined by plugs that define the capabilities of the node implementing
the checks.

The quality assurance framework is defined by:
	 * `QAWorkflow`
	 * `QAProcessBase`
	 * `QACheckResult`
	 * `QACheckAttribute`

They specialize the respective parts of the workflow"""
__docformat__ = "restructuredtext"

from workflow import Workflow
from process import ProcessBase
from mrv.util import EventSender, Event
from mrv.dge import Attribute, plug, ComputeFailed
from mrv.enum import create as enum
import sys

import logging
log = logging.getLogger("mrv.automation.qa")

#{ Exceptions
class CheckIncompatibleError( ComputeFailed ):
	"""Raised if a check cannot accomdate the requested mode and thus cannot run"""
	pass


#} END exceptions


class QAProcessBase( ProcessBase ):
	"""Quality Assurance Process including a specialized QA interface"""

	# query: find issues and report them using `QACheckResult`, but do not attempt to fix
	# fix: find issues and fix them, report fixed ( and possibly failed ) items by
	eMode = enum( "query", "fix" )	# computation mode for QAProcessBasees

	#( Configuration
	# QA Processes do not require this feature due to their quite simplistic call structure
	# If required, subclasses can override this though
	track_compute_calls = False
	#) END configuration


	#{ Interface
	def assureQuality( self, check, mode, *args, **kwargs ):
		"""Called when the test identified by plug should be handled
		
		:param check: QACheck to be checked for issues
		:param mode: mode of the computation, see `QAProcessBase.eMode`
		:return: QACheckResult instance keeping information about the outcome of the test"""
		raise NotImplementedError( "To be implemented by subclass" )

	def listChecks( self, **kwargs ):
		""":return: list( QACheck, ... ) list of our checks
		:param kwargs: see `QAWorkflow.filterChecks`"""
		return self.workflow().filterChecks( [ self ], **kwargs )

	#} END interface

	def evaluateState( self, plug, mode, *args, **kwargs ):
		"""Prepares the call to the actual quality check implemenetation and assuring
		test identified by plug can actually be run in the given mode"""
		if mode is self.eMode.fix and not plug.attr.implements_fix:
			raise CheckIncompatibleError( "Plug %s does not implement issue fixing" % plug )

		return self.assureQuality( plug, mode, *args, **kwargs )


class QACheckAttribute( Attribute ):
	"""The Test Attribute represents an interface to a specific test as implemented
	by the parent `QAProcessBase`.
	The QA Attribute returns specialized quality assurance results and provides
	additional information about the respective test
	
	:note: as this class holds meta information about the respective test ( see `QACheck` )
		user interfaces may use it to adjust it's display
	:note: this class depends on unknown mel implementations - on error we abort
		but do not throw as this would cause class creation to fail and leave the whole
		qa system unusable"""

	def __init__( 	self, annotation, has_fix = False,
				 	flags = Attribute.computable ):
		"""Initialize attribute with meta information
		
		:param annotation: information string describing the purpose of the test
		:param has_fix: if True, the check must implement a fix for the issues it checks for,
			if False, it can only report issues
		:param flags: configuration flags for the plug - default to trigger computation even without
			input"""
		super( QACheckAttribute, self ).__init__( QACheckResult, flags )
		self.annotation = annotation
		self.implements_fix = has_fix


class QACheck( plug ):
	"""Defines a test suitable to be run and computed by a `QAProcessBase`
	It's nothing more than a convenience class as the actual information is held by the
	respective `QACheckAttribute`.
	All non-plug calls are passed on to the underlying attribute, allowing it to
	be treated like one"""
	#{ Configuration

	# class of the check attribute to use when instanciating this check
	check_attribute_cls = QACheckAttribute
	#} END configuration

	def __init__( self, *args, **kwargs ):
		super( QACheck, self ).__init__( self.check_attribute_cls( *args, **kwargs ) )

	def __getattr__( self, attrname ):
		return getattr( self.attr, attrname )


class QAWorkflow( Workflow, EventSender ):
	"""Represents a workflow of QAProcessBase instances and allows to query them more
	conveniently"""

	#( Configuration
	sender_as_argument = False

	# if True, we will abort once the first error has been raised during check execution
	# It is also held as instance variable so it can be set on per instance basis, allowing
	# error check callbacks to adjust the error handling behaviour and abort the operation
	abort_on_error = False

	# as checks can take some time, it might be useful to have realtime results
	# to std out in UI mode at least. It accompanies the feedback the workflow
	# gives and keeps the default unittest style
	info_to_stdout = True
	#) END configuration

	#( Filters
	fIsQAProcessBase = staticmethod( lambda n: isinstance( n, QAProcessBase ) )
	fIsQAPlug = staticmethod( lambda p: isinstance( p, QACheck ) )
	#) END filters

	#{ Events
	# called before a check is run as func: func( event, check )
	e_preCheck = Event()

	# called if a check fails with an error: func( event, check, exception, workflow )
	e_checkError = Event()

	# called after a check has been run: func( event, check, result )
	e_postCheck = Event()
	#}

	def __init__( self, *args, **kwargs ):
		"""Initialize our instance"""
		super( QAWorkflow, self ).__init__( *args, **kwargs )

		# store abort on error as instance variable so that it can easily be overwritten
		self.abort_on_error = QAWorkflow.abort_on_error

	def listQAProcessBasees( self, predicate = lambda p: True ):
		""":return: list( Process, ... ) list of QA Processes known to this QA Workflow
		:param predicate: include process p in result if func( p ) returns True"""
		return self.iterNodes( predicate = lambda n: self.fIsQAProcessBase( n ) and predicate( n ) )

	def filterChecks( self, processes, predicate = lambda c: True ):
		"""As `listChecks`, but allows you do define the processes to use
		
		:param predicate: func( p ) for plug p returns True for it to be included in the result"""
		outchecks = list()
		for node in processes:
			outchecks.extend( node.toShells( node.plugs( lambda c: self.fIsQAPlug( c ) and predicate( c ) ) ) )
		return outchecks

	def listChecks( self, predicate = lambda c: True  ):
		"""List all checks as supported by `QAProcessBase` es in this QA Workflow
		
		:param predicate: include check c in result if func( c ) returns True"""
		return self.filterChecks( self.listQAProcessBasees( ), predicate = predicate )

	def runChecks( self, checks, mode = QAProcessBase.eMode.query, clear_result = True ):
		"""Run the given checks in the given mode and return their results
		
		:param checks: list( QACheckShell, ... ) as retrieved by `listChecks`
		:param mode: `QAProcessBase.eMode`
		:param clear_result: if True, the plug's cache will be removed forcing a computation
			if False, you might get a cached value depending on the plug's setup
		:return: list( tuple( QACheckShell, QACheckResult ), ... ) list of pairs of
			QACheckShells and the check's result. The test result will be empty if the test
			did not run or failed with an exception
		:note: Sends the following events: ``e_preCheck`` , ``e_postCheck``, ``e_checkError``
			e_checkError may set the abort_on_error variable to True to cause the operation
			not to proceed with other checks"""
		# reset abort on error to class default
		self.abort_on_error = self.__class__.abort_on_error
		self._clearState( mode )	# assure we get a new callgraph

		outresult = list()
		for checkshell in checks:
			if self.info_to_stdout:
				checkplug = checkshell.plug
				log.info( "Running %s: %s ... " % ( checkplug.name(), checkplug.annotation ) )
			# END extra info

			self.e_preCheck.send( self.e_preCheck, checkshell )

			result = QACheckResult()	 	# null value
			if clear_result:
				checkshell.clearCache( clear_affected = False )

			shellmode = mode
			# some only can do check mode
			if not checkshell.plug.implements_fix:
				shellmode = checkshell.node.eMode.query

			try:
				result = checkshell.get( shellmode )
			except Exception, e:
				self.e_checkError.send( self.e_checkError, checkshell, e, self )

				if self.abort_on_error:
					raise
			# END error handling

			if self.info_to_stdout:
				msg = "FAILED"
				if result.isSuccessful():
					msg = "OK"
				log.info(msg)
			# END extra info

			# record result
			outresult.append( ( checkshell, result ) )
			self.e_postCheck.send( self.e_postCheck, checkshell, result )
		# END for each check to run

		return outresult

class QACheckResult( object ):
	"""Wrapper class declaring test results as a type that provides a simple interface
	to retrieve the test results
	
	:note: test results are only reqtrieved by QACheckAttribute plugs"""
	def __init__( self , fixed_items = None , failed_items = None, header = "" ):
		"""Initialize ourselves with default values
		
		:param fixed_items: if list of items, the instance is initialized with it
		:param failed_items: list of items that could not be fixed
		:param header: optional string giving additional specialized information on the
			outcome of the test. Tests must supply a header - otherwise the result will be treated
			as failed check"""
		self.header = header
		self.fixed_items = ( isinstance( fixed_items, list ) and fixed_items ) or list()
		self.failed_items = ( isinstance( failed_items, list ) and failed_items ) or list()

	def fixedItems( self ):
		"""
		:return: list( Item , ... ) list of items ( the exact type may differ
			depending on the actual test ) which have been fixed so they represent the
			desired state"""
		return self.fixed_items

	def failedItems( self ):
		"""
		:return: ( list( Item, ... ) list of failed items being items that could not be
			fixed and are not yet in the desired state"""
		return self.failed_items

	def isNull( self ):
		""":return: True if the test result is empty, and thus resembles a null value"""
		return not self.header or ( not self.failed_items and not self.fixed_items )

	def isSuccessful( self ):
		""":return: True if the check is successful, and False if there are at least some failed objects"""
		if not self.header:
			return False

		# we are successful if there are no failed items left
		return not self.failed_items

	def __str__( self ):
		if not self.header:
			return "No check-result available"

		msg = self.header + "\n"
		if self.fixed_items:
			msg += ", ".join( str( i ) for i in self.fixed_items ) + "\n"
		msg += ", ".join( str( i ) for i in self.failed_items )
		return msg


