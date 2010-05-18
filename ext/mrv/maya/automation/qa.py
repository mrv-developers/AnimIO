# -*- coding: utf-8 -*-
"""Specialization of workflow to allow checks to be natively implemented in MEL """
__docformat__ = "restructuredtext"

from mrv.automation.qa import QACheck, QACheckAttribute, QACheckResult
from mrv.maya.util import Mel
from mrv.dge import _NodeBaseCheckMeta
import sys
import logging
log = logging.getLogger("mrv.maya.automation.qa")

__all__ = ("QAMELCheckAttribute", "QAMELCheck", "QAMetaMel", "QAMELMixin")


class QAMELCheckAttribute( QACheckAttribute ):
	"""Attribute identifying a MEL check carrying additional mel specific attributes"""
	pass


class QAMELCheck( QACheck ):
	"""Specialized version of the QACheck allowing to use our own MEL attribute
	contianiing more information"""
	check_attribute_cls = QAMELCheckAttribute


class QAMetaMel( _NodeBaseCheckMeta ):
	"""Metaclass allowing to create plugs based on a MEL implementation, allowing
	to decide whether checks are Python or MEL implemented, but still running natively
	in python"""
	@classmethod
	def _getMelChecks( metacls, index_proc, check_cls ):
		"""
		:return: list( checkInstance, ... ) list of checkinstances represeting
			mel based checkes
		:param index_proc: method returning the index declaring the tests
		:param check_cls: class used to instance new checks"""
		output = list()
		try:
			index = Mel.call( index_proc )
		except RuntimeError, e:
			log.warn( str( e ) )
		else:
			# assure its working , never fail here
			if len( index ) % 3 == 0:
				iindex = iter( index )
				for checkname, description, can_fix in zip( iindex, iindex, iindex ):
					# check name - it may not contain spaces for now
					if " " in checkname:
						log.warn( "Invalid name: %s - it may not contain spaces, use CamelCase or underscores" % checkname )
						continue
					# END name check

					plug = check_cls( annotation = description, has_fix = int( can_fix ) )
					plug.setName( checkname )
					output.append( plug )
				# END for each information tuple
			# END if index is valid
			else:
				log.warn( "Invalid proc index returned by %s" % index_proc )
			# END index has valid format
		# END index could be retrieved

		return output

	def __new__( metacls, name, bases, clsdict ):
		"""Search for configuration attributes allowing to auto-generate plugs
		referring to the respective mel implementation"""
		index_proc = clsdict.get( "mel_index_proc", None )
		check_cls = clsdict.get( "check_plug_cls", QAMELCheck )
		static_plugs = clsdict.get( "static_mel_plugs", True )

		if static_plugs and index_proc and check_cls is not None:
			check_list = metacls._getMelChecks( index_proc, check_cls )
			for check in check_list:
				clsdict[ check.name() ] = check
		# END create plugs

		# finally create the class
		newcls = super( QAMetaMel, metacls ).__new__( metacls, name, bases, clsdict )
		return newcls


class QAMELMixin( object ):
	"""Base class allowing to process MEL baesd plugs as created by our metaclass
	
	:note: this class assumes it is used on a process

	**Configuration**:
		The following variables MUST be used to setup this class once you have derived
		from it:
	
		 * mel_index_proc:
		  	produdure name with signature func( ) returning string array in following format:
				[n*3+0] = checkname : the name of the check, use CamelCase names or names_with_underscore
				The checkname is also used as id to identify the check lateron
				[n*3+1] = description: Single sentence desciption of the check targeted at the end user
				[n*3+2] = can_fix: 	Boolean value indicating whether the check can also fix the issue

		 * mel_check_proc:
		 	procedure called to actually process the given check, signature is:
				func( check_name, should_fix )
				returning list of strings as follows:
				
					[0] = x number of fixed items
					[1] = header
					[1:1+x] = x fixed items
					[2+x:n] = n invalid items
			
			items are either objects or in general anything you check for. The check is
			considered to be failed if there is at least one invalid item.
			
			If you fixed items, all previously failed items should now be returned as
			valid items

		static_mel_plugs:
			Please note that your class must implemnent plugs and extend the super class
			result by the result of `listMELChecks` to dynamically retrieve the available
			checks
	"""
	__metaclass__ = QAMetaMel

	#{ Configuration

	# see class docs
	mel_index_proc = None

	# see class docs
	mel_check_proc = None

	# if True, the mel based checks will be created as class members upon class
	# creation. If False, they will be retrieved on demand whenever plugs are
	# queried. The latter one can be slow, but might be required if the indices
	# are dynamically generated
	static_mel_plugs = True

	# qa check result compatible class to be used as container for MEL return values
	check_result_cls = QACheckResult

	# qa check plug class to use for the plugs to be created - it will always default
	# to QACheck
	check_plug_cls = QAMELCheck
	#} END configuration

	def listMELChecks( self ):
		"""
		:return: list all checks ( Plugs ) available on this class that are implemented
			in MEL"""
		return self.listChecks( predicate = lambda p: isinstance( p.attr , QAMELCheckAttribute ) )

	def isMELCheck( self, check ):
		"""
		:return: True if the given check plug is implemented in MEL and can be handled
			there accordingly"""
		plug = check
		try:
			plug = check.plug
		except AttributeError:
			pass

		return isinstance( plug.attr, QAMELCheckAttribute )

	def _rval_to_checkResult( self, string_array, **kwargs ):
		""":return: check result as parsed fom string array
		:param kwargs: will be given to initializer of check result instance"""
		if not string_array:
			return self.check_result_cls( **kwargs )

		assert len( string_array ) > 1	# need a header at least

		num_fixed = int( string_array[0] )
		end_num_fixed = 2 + num_fixed

		kwargs[ 'header' ] = string_array[1]
		kwargs[ 'fixed_items' ] = string_array[ 2 : end_num_fixed ]
		kwargs[ 'failed_items' ] = string_array[ end_num_fixed : ]

		return self.check_result_cls( **kwargs )


	@classmethod
	def melChecks( cls, predicate = lambda p: True ):
		""":return: list of MEL checks ( plugs ) representing checks defined by MEL
		:param predicate: only return plug if predicate( item ) yield True"""
		return [ c for c in QAMetaMel._getMelChecks( cls.mel_index_proc, cls.check_plug_cls ) if predicate( c ) ]

	def handleMELCheck( self, check, mode ):
		"""Called to handle the given check in the given mode
		
		:raise RuntimeError: If MEL throws an error
		:return: QACheckResult of the result generated by MEL"""
		assert self.mel_check_proc
		assert isinstance( check.attr, QAMELCheckAttribute )

		rval = Mel.call( self.mel_check_proc, check.name(), int( mode == self.eMode.fix ) )

		return self._rval_to_checkResult( rval )

