# -*- coding: utf-8 -*-
"""
Contains a modular UI able to display quality assurance checks, run them and
present their results. It should be easy to override and adjust it to suit additional needs
"""
__docformat__ = "restructuredtext"
import control
import util as uiutil
import layout
from mrv.automation.qa import QAWorkflow
import maya.OpenMaya as api
from itertools import chain
import re
from mrv.util import capitalize

import logging
log = logging.getLogger("mrv.maya.ui.qa")

class QACheckLayout( layout.RowLayout ):
	"""Row Layout able to display a qa check and related information
	
	:note: currently we make assumptions about the positions of the children in the
		RowLayout, thus you may only append new ones"""
	reNiceNamePattern = re.compile( "[A-Z][a-z]" )

	#{ Configuration
	# paths to icons to display
	# [0] = check not run
	# [1] = check success
	# [2] = check failed
	# [3] = check threw exception
	icons = [ "offRadioBtnIcon.xpm", "onRadioBtnIcon.xpm", "fstop.xpm", "fstop.xpm" ]	# explicitly a list to allow assignments

	# height of the UI control
	height = 25

	# number of columns to use - assure to fill the respective slots
	numcols = 3
	#} END configuration

	def __new__( cls, *args, **kwargs ):
		"""Initialize this RowColumnLayout instance with a check instance
		
		:param kwargs:
			 * check:
				the check this instance should attach itself to - it needs to be set
				or the instance creation will fail"""
		check = kwargs.pop( "check" )

		numcols = cls.numcols # without fix
		if check.plug.implements_fix:
			numcols += 1

		assert numcols < 7	# more than 6 not supported by underlying layout

		kwargs[ 'numberOfColumns' ] = numcols
		kwargs[ 'adj' ] = 1
		kwargs[ 'h' ] = cls.height
		kwargs[ 'cw%i' % numcols ] = ( cls.height + 2, ) * numcols
		self = super( QACheckLayout, cls ).__new__( cls, *args, **kwargs )

		# create instance variables
		self._check = check
		return self

	def __init__( self, *args, **kwargs ):
		"""Initialize our instance with members"""
		super( QACheckLayout, self ).__init__( *args, **kwargs )

		# populate
		self._create( )

	@staticmethod
	def _replInsSpace( match ):
		"""Generate a replace string from the match in the match object
		
		:note: match should contain only a range of two chars"""
		assert match.end() - match.start() == 2
		if match.start() == 0:	# in the beginning , replace by itself
			return match.string[ match.start() : match.end() ]

		# otherwise insert a space between items
		return " " + match.string[ match.start() : match.end() ]


	def _toNiceName( self, name ):
		"""
		:return: nice name version of name, replacing underscores by spaces, and
			separating camel cases, as well as chaning to the capitalizaion of word"""
		name_tokens = name.split( "_" )

		# parse camel case
		for i, token in enumerate( name_tokens ):
			 repl_token = self.reNiceNamePattern.sub( self._replInsSpace, token )
			 name_tokens[ i ] = repl_token
		# END for each token camel case parse

		final_tokens = list()

		# split once more on inserted spaces, capitalize
		for token in name_tokens:
			final_tokens.extend( capitalize( t ) for t in token.split( " " ) )

		return " ".join( final_tokens )


	def _create( self ):
		"""Create our layout elements according to the details given in check"""
		# assume we are active
		checkplug = self.check().plug
		nice_name = self._toNiceName( checkplug.name() )
		self.add( control.Text( label = nice_name, ann = checkplug.annotation ) )

		ibutton = self.add( control.IconTextButton( 	style="iconOnly",
														h = self.height, w = self.height ) )
		sbutton = self.add( control.Button( label = "S", w = self.height,
												ann = "Select faild or fixed items" ) )

		# if we can actually fix the item, we add an additional button
		if checkplug.implements_fix:
			fbutton = self.add( control.Button( label = "Fix", ann = "Attempt to fix failed items" ) )
			fbutton.e_released = self._runCheck
		# END fix button setup

		# attach callbacks
		ibutton.e_command = self._runCheck
		sbutton.e_released = self.selectPressed

	def update( self ):
		"""Update ourselves to match information in our stored check"""
		# check the cache for a result - if so, ask it for its state
		# otherwise we are not run and indicate that
		bicon = self.listChildren()[1]
		bicon.p_image = self.icons[0]

		check = self.check()
		if check.hasCache():
			result = check.cache()
			self.setResult( result )
		# END if previous result exists


	def check( self ):
		""":return: check we are operating upon"""
		return self._check

	#{ Check Callbacks

	def _runCheck( self, *args, **kwargs ):
		"""Run our check
		
		:note: we may also be used as a ui callback and figure out ourselves
			whether we have been pressed by the fix button or by the run button
		:param kwargs: will be passed to the workflow's runChecks method. The following 
			additional kwargs may be specified:
			
			 * force_check: 
			 	if True, default True, a computation will be forced,
				otherwise a cached result may be used
			
		:return: result of our check"""
		check = self.check()
		wfl = check.node.workflow()
		force_check = kwargs.pop( "force_check", True )

		mode = check.node.eMode.query
		if args and isinstance( args[0], control.Button ):
			mode = check.node.eMode.fix
		# END fix button handling

		return wfl.runChecks( [ check ], mode = mode, clear_result = force_check, **kwargs )[0][1]

	def selectPressed( self, *args ):
		"""Called if the selected button has been pressed
		Triggers a workflow run if not yet done"""
		# use the cache directly to prevent the whole runprocess to be kicked on
		# although the result is already known
		check = self.check()
		result = None
		if check.hasCache():
			result = check.cache()
		else:
			result = self._runCheck( force_check = False )

		# select items , ignore erorrs if it is not selectable
		sellist = api.MSelectionList()
		for item in chain( result.fixedItems(), result.failedItems() ):
			try:
				sellist.add( str( item ) )
			except RuntimeError:
				pass
		# END for each item to select

		api.MGlobal.setActiveSelectionList( sellist )

	def preCheck( self ):
		"""Runs before the check starts"""
		text = self.listChildren()[0]
		text.p_label = "Running ..."

	def postCheck( self, result ):
		"""Runs after the check has finished including the given result"""
		text = self.listChildren()[0]
		text.p_label = str( self._toNiceName( self.check().plug.name() ) )

		self.setResult( result )

	def checkError( self, exception, workflow ):
		"""Called if the checks fails with an error
		
		:param exception: exception object that was thrown by our check
		:param workflow: workflow that ran the check"""
		text = self.listChildren()[0]
		text.p_label = str( self._toNiceName( self.check().plug.name() ) + " ( ERROR )" )
		log.error(str( exception ))

	def setResult( self, result ):
		"""Setup ourselves to indicate the given check result
		
		:return: our adjusted iconTextButton Member"""
		target_icon = self.icons[2]		# failed by default

		if result.isSuccessful():
			target_icon = self.icons[1]
		elif result.isNull():		# indicates failure, something bad happened
			target_icon = self.icons[3]

		# annotate the text with the result
		children = self.listChildren()
		text = children[0]

		bicon = children[1]
		bicon.p_image = target_icon

		return bicon
	#} END interface

class QALayout( layout.FormLayout, uiutil.iItemSet ):
	"""Layout able to dynamically display QAChecks, run them and display their result"""

	#{ Configuration
	# class used to create a layout displaying details about the check
	# it must be compatible to QACheckLayout as a certain API is expected
	checkuicls = QACheckLayout

	# if True, a button to run all checks at once will be appended
	# Can be passed in as per-instance value during creation
	run_all_button = True

	# class used to access default workflow events
	qaworkflowcls = QAWorkflow

	# if True, there will be an informational text if no checks have been found
	# otherwiise the layout will simply be empty
	show_text_if_empty = True


	# if True, a scroll layout will be created around the layout containing a
	# possibly long list of checks. Set False if you would like to handle the
	# scrolling with an own interface
	# Can be passed in as per-instance value during creation
	scrollable = True
	#} END configuration

	def __new__( cls, *args, **kwargs ):
		"""Set some default arguments"""
		scrollable = kwargs.pop( "scrollable", cls.scrollable )
		run_all_button = kwargs.pop( "run_all_button", cls.run_all_button )
		self = super( QALayout, cls ).__new__( cls, *args, **kwargs )
		self.scrollable = scrollable
		self.run_all_button = run_all_button

		return self

	def __init__( self, *args, **kwargs ):
		"""Initialize our basic interface involving a column layout to store the
		actual check widgets"""
		super( QALayout, self ).__init__( *args, **kwargs )
		scroll_layout = None

		if self.scrollable:
			scroll_layout = self.add( layout.ScrollLayout( cr=1 ) )

		# will contain the checks
		self.col_layout = layout.ColumnLayout( adj = 1 )
		if scroll_layout:
			scroll_layout.add( self.col_layout )
		else:
			self.add( self.col_layout )

		# END scroll_layout
		self.setActive()

		# name of text indicating there are no checks set
		self.no_checks_text = None
	#{ Interface

	def setChecks( self, checks ):
		"""Set the checks this layout should display
		
		:param checks: iterable of qa checks as retrieved by `checks`
		:raise ValueErorr: if one check is from a different workflow and there is a run_all button"""
		# we might change the layout, so be active
		# IMPORTANT: if this is not the case, we might easily confuse layouts ...
		# figure out why exactly that happens
		curparent = self.parent()
		self.setActive()

		# map check names to actual checks
		name_to_check_map = dict( ( ( str( c ), c ) for c in checks ) )
		name_to_child_map = dict()

		self.setItems( name_to_check_map.keys(), 	name_to_check_map = name_to_check_map,
					  								name_to_child_map = name_to_child_map )

		# HANDLE NO CHECKS
		####################
		if checks and self.no_checks_text:
			self.no_checks_text.delete()
			self.no_checks_text = None
		# END checks text existed

		if not checks and self.no_checks_text is None and self.show_text_if_empty:
			prevparent = self.parent()
			self.col_layout.setActive()
			self.no_checks_text = control.Text( label = "No checks available" )
			prevparent.setActive()
		# END no checks existed handling


		# SET EVENTS
		#############
		# NOTE: currently we only register ourselves for callbacks, and deregeister
		# automatically through the weak reference system
		wfls_done = list()
		for check in checks:
			cwfl = check.node.workflow()
			if cwfl in wfls_done:
				continue
			wfls_done.append( cwfl )

			if self.run_all_button and len( wfls_done ) > 1:
				raise ValueError( "This UI can currently only handle checks from only one workflow at a time if run_all_button is set" )

			cwfl.e_preCheck = self.checkHandler
			cwfl.e_postCheck = self.checkHandler
			cwfl.e_checkError = self.checkHandler
		# END for each check

		# POSSIBLY ADD BUTTON TO THE END
		#################################
		# remove possibly existing button ( ignore the flag, its about the button here )
		# its stored in a column layout
		button_layout_name = "additionals_column_layout"
		layout_child = self.listChildren( predicate = lambda c: c.basename() == button_layout_name )
		if layout_child:
			assert len( layout_child ) == 1
			self.deleteChild( layout_child[0] )

		# create child layout ?
		if self.run_all_button:
			self.setActive()
			layout_child = self.add( layout.ColumnLayout( adj = 1, name = button_layout_name ) )
			if layout_child:
				control.Separator( style = "single", h = 10 )
				run_button = control.Button( label = "Run All", ann = "Run all checks in one go",
											 	enable = len( checks ) > 0 )
				run_button.e_pressed = self.runAllPressed
			# END button layout setup
			self.setActive()
		# END if run all button is requested

		# setup form layout - depending on the amount of items - we have 1 or two
		# children, never more
		children = self.listChildren()
		assert len( children ) < 3
		o = 2	# offset
		t,b,l,r = self.kSides
		if len( children ) == 1:
			c = children[0]
			self.setup( af = ( ( c, b, o ), ( c, t, o ), ( c, l, o ), ( c, r, o ) ) )
		# END case one child
		else:
			c1 = children[0]
			c2 = children[1]
			self.setup( af = ( 	( c1, l, o ), ( c1, r, o ), ( c1, t, o ),
							 	( c2, l, o ), ( c2, r, o ), ( c2, b, o ) ),
						ac = ( 	( c1, b, o, c2 ) ),
						an = (	( c2, t ) ) )
		# END case two children

		# reset to the previous parent
		curparent.setActive()


	def checkLayouts( self ):
		""":return: list of checkLayouts representing our checks"""
		ntcm = dict()
		self.currentItemIds( name_to_child_map = ntcm )
		return ntcm.values()

	def checks( self ):
		""":return: list of checks we are currently holding in our layout"""
		return [ l.check() for l in self.checkLayouts() ]

	#} END interface

	def currentItemIds( self, name_to_child_map = None, **kwargs ):
		""":return: current check ids as defined by exsiting children.
		:note: additionally fills in the name_to_child_map"""
		outids = list()
		for child in self.col_layout.listChildren( predicate = lambda c: isinstance( c, QACheckLayout ) ):
			check = child.check()
			cid = str( check )
			outids.append( cid )

			name_to_child_map[ cid ] = child
		# END for each of our children
		return outids

	def handleEvent( self, eventid, **kwargs ):
		"""Assure we have the proper layouts active"""
		if eventid == self.eSetItemCBID.preCreate:
			self.col_layout.setActive()
		if eventid == self.eSetItemCBID.postCreate:
			self.setActive()

	def createItem( self, checkid, name_to_child_map = None, name_to_check_map = None, **kwargs ):
		"""Create and return a layout displaying the given check instance
		
		:param kwargs: will be passed to checkui class's initializer, allowing subclasses to easily
			adjust the paramter list
		:note: its using self.checkuicls to create the instance"""
		self.col_layout.setActive()
		check_child = self.checkuicls( check = name_to_check_map[ checkid ], **kwargs )
		name_to_child_map[ checkid ] = check_child
		newItem = self.col_layout.add( check_child )

		return newItem

	def updateItem( self, checkid, name_to_child_map = None, **kwargs ):
		"""Update the item identified by the given checkid so that it represents the
		current state of the application"""
		name_to_child_map[ checkid ].update( )

	def removeItem( self, checkid, name_to_child_map = None, **kwargs ):
		"""Delete the user interface portion representing the checkid"""
		self.col_layout.deleteChild( name_to_child_map[ checkid ] )

	#{ Eventhandlers

	def _checkLayoutHasCheck( self, checkLayout, check ):
		""":return: True if the given `QACheckLayout` manages the given check"""
		return checkLayout.check() == check

	def checkHandler( self, event, check, *args ):
		"""Called for the given event - it will find the UI element handling the
		call respective function on the UI instance
		
		:note: find the check using predefined names as they server as unique-enough keys.
			This would possibly be faster, but might not make a difference after all"""

		# as we do not track the deletion of the window, our class might actually
		# persist even though the window is long gone - throw if we are not existing
		# to get auto-removed from the handler
		assert self.exists()

		# find a child handling the given check
		# skip ones we do not find
		checkchild = None
		for child in self.checkLayouts():
			if self._checkLayoutHasCheck( child, check ):
				checkchild = child
				break
			# END if check matches
		# END for each child in children

		# this could actually happen as we get calls for all checks, not only
		# for the ones we actually have
		if checkchild is None:
			return

		if event == self.qaworkflowcls.e_preCheck:
			checkchild.preCheck( )
		elif event == self.qaworkflowcls.e_postCheck:
			result = args[0]
			checkchild.postCheck( result )
		elif event == self.qaworkflowcls.e_checkError:
			exc = args[0]
			wfl = args[1]
			checkchild.checkError( exc, wfl )

	def runAllPressed( self, *args, **kwargs ):
		"""Called once the Run-All button is pressed
		
		:param kwargs: will be passed to runChecks method of workflow
		:note: we assume all checks are from one workflow only as we
			do not sort them by workflow
		:note: currently we only run in query mode as sort of safety measure - check and fix
			on all might be too much and lead to unexpected results"""
		checks = self.checks()
		if not checks:
			log.error("No checks found to run")
			return
		# END check assertion

		wfl = checks[0].node.workflow()
		wfl.runChecks( checks, clear_result = 1, **kwargs )

	#} END Eventhandlers

