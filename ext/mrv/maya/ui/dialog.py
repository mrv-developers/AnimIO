# -*- coding: utf-8 -*-
"""
Contains some default dialogs as well as layouts suitable for layout dialogs
"""
__docformat__ = "restructuredtext"

import base as uibase
import maya.cmds as cmds
import maya.utils as mutils
import mrv.util as util
from mrv.interface import iPrompt, iChoiceDialog, iProgressIndicator

import logging
log = logging.getLogger("mrv.maya.ui.dialog")


class Dialog( uibase.BaseUI ):
	""" Base for all dialog classes """


class PromptDialog( Dialog ):
	""" Wrapper class for maya prompt dialog"""

	def __init__( self, title, message, okText, cancelText, **kwargs ):
		""" Create a prompt dialog and allow to query the result
		:note: return default text in batch mode, given with 'text' key"""
		if cmds.about( batch=1 ):
			return kwargs.get( 'text', kwargs.get( 't', '' ) )

		ret = cmds.promptDialog( t = title, m = message, b = [okText,cancelText],
									db = okText, cb = cancelText,**kwargs )
		self._text = None
		if ret == okText:
			self._text = cmds.promptDialog( q=1, text = 1 )

	def text( self ):
		""":return: the entered text or None if the box has been aborted"""
		return self._text


class Prompt( iPrompt ):
	"""Implements the prompt interface using a prompt dialog"""

	def prompt( self ):
		"""Aquire the information using a prompt dialog
		
		:return: prompted value if input was confirmed using confirmToken, or the cancelValue
			if cancelToken was pressed
		:note: tokens correspond to buttons
		:note: handles batch mode correctly"""
		if cmds.about( batch = 1 ):
			return super( Prompt, self ).prompt( )

		default_text = ( self.confirmDefault is not None and self.confirmDefault ) or ""

		tokens = [ self.confirmToken ]
		token_kwargs = { "db" : self.confirmToken }
		if self.cancelToken is not None:
			tokens.append( self.cancelToken )
			token_kwargs[ "cb" ] = self.cancelToken
		# END token preparation
		token_kwargs.update( self._kwargs )

		ret = cmds.promptDialog( t="Prompt", m = self.msg, b = tokens, text = default_text, **token_kwargs )

		if ret == self.cancelToken:
			return self.cancelDefault

		if ret == self.confirmToken:
			return cmds.promptDialog( q=1, text = 1 )

		return self.confirmDefault


class ChoiceDialog( iChoiceDialog ):
	"""Maya implementation of the generic choice dialog interface"""

	def choice( self ):
		"""Return the choice made by the user"""
		# don't do anything inbatch mode
		if cmds.about( b=1 ):
			return self.default_choice

		return cmds.confirmDialog( 	t = self.title,
								  	m = self.message,
									b = [ str( c ) for c in self.choices ],
									db = self.default_choice,
									cb = self.cancel_choice,
									ds = self.cancel_choice )


class ProgressWindow( iProgressIndicator ):
	"""Simple progress window wrpping the default maya progress window"""
	def __init__( self, **kwargs ):
		"""Everything that iProgress indicator and Maya Progress Window support"""
		min = kwargs.pop( "min", kwargs.pop( "minValue" , 0 ) )
		max = kwargs.pop( "max", kwargs.pop( "maxValue", 100 ) )

		relative = kwargs.pop( "is_relative", 1 )
		super( ProgressWindow, self ).__init__( min = min, max = max, is_relative = relative )

		# remove invalid args
		kwargs.pop( "s", kwargs.pop( "step", 0 ) )
		kwargs.pop( "pr", kwargs.pop( "progress", 0 ) )
		kwargs.pop( "ep", kwargs.pop( "endProgress", 0 ) )
		kwargs.pop( "ic", kwargs.pop( "isCancelled", 0 ) )
		kwargs.pop( "e", kwargs.pop( "edit", 0 ) )

		self.kwargs = kwargs  			# store for begin

	def refresh( self, message = None ):
		"""Finally show the progress window"""
		mn,mx = ( self.isRelative() and ( 0,100) ) or self.range()
		p = self.get()

		myargs = dict()
		myargs[ "e" ] = 1
		myargs[ "min" ] = mn
		myargs[ "max" ] = mx
		myargs[ "pr" ] = p
		myargs[ "status" ] = message or ( "Progress %s" % ( "." * ( int(p) % 4 ) ) )

		try:
			cmds.progressWindow( **myargs )
		except RuntimeError,e:
			log.warn(str( e ))
			pass 		# don't know yet why that happens
		# END handle progress window errors

	def begin( self ):
		"""Show our window"""
		super( ProgressWindow, self ).begin( )
		cmds.progressWindow( **self.kwargs )

	def end( self ):
		"""Close the progress window"""
		# damn, has to be deferred to actually work
		super( ProgressWindow, self ).end( )
		mutils.executeDeferred( cmds.progressWindow, ep=1 )

	def isCancelRequested( self ):
		""":return: True if the action should be cancelled, False otherwise"""
		return cmds.progressWindow( q=1, ic=1 )

	def isAbortable( self ):
		""":return : true if the process can be aborted"""
		return cmds.progressWindow( q=1, ii=1 )

	def setAbortable( self, state ):
		cmds.progressWindow( e=1, ii=state )
		return super( ProgressWindow, self ).setAbortable( state )
