# -*- coding: utf-8 -*-
"""
Contains the most important mel-layouts wrapped into easy to use python classes
These are specialized and thus more powerful than the default wraps
"""
__docformat__ = "restructuredtext"
import base as uibase
import maya.cmds as cmds
import mrv.maya.util as mutil
import util as uiutil


class Layout( uibase.SizedControl, uiutil.UIContainerBase ):
	""" Structural base  for all Layouts allowing general queries and name handling
	Layouts may track their children
	"""
	_properties_ = ( "nch", "numberOfChildren" )

	def __init__( self, *args, **kwargs ):
		"""Initialize the layout"""
		super( Layout, self ).__init__( *args, **kwargs )

	def __getitem__( self, key ):
		"""Implemented by `UIContainerBase`"""
		return uiutil.UIContainerBase.__getitem__( self, key )

	def children( self ):
		""" :return: children of this layout """
		childnames = mutil.noneToList( cmds.layout( self, q=1, ca=1 ) )
		# assure we have long names to ensure uniqueness
		return uibase.wrapUI( [ "%s|%s" % ( self, c ) for c in childnames ] )

	def setParentActive( self ):
		"""Set the parent ( layout ) of this layout active - newly created items
		will be children of the parent layout
		
		:return: self
		:note: can safely be called several times """
		cmds.setParent( self.parent( ) )
		return self

	#{ Properties
	p_ca = property(children)
	p_childArray = p_ca
	#} End Properties


class FormLayout( Layout ):
	""" Wrapper class for maya form layout """
	# tuple with side strings - to quickly define your attachments, assign it to letters
	# like : t,b,l,r = kSides
	# and use the letters accordingly to save space and make the layout easier to read
	kSides = ( "top", "bottom", "left", "right" )

	class FormConstraint( object ):
		""" defines the way a child is constrained, possibly to other children
		
		:todo: proper constraint system, but could be complicated to make it really easy to use"""

	def setup( self, **kwargs ):
		"""Apply the given setup to the form layout, specified using kwargs
		
		:param kwargs: arguments you would set use to setup the form layout"""
		self.__melcmd__( self, e=1, **kwargs )


class FrameLayout( Layout ):
	"""Simple wrapper for a frame layout"""
	_properties_ = (	"bw", "borderVisible",
					   	"bs",  "borderStyle",
						"cl", "collapse",
						"cll", "collapsable",
						"l", "label",
						"lw", "labelWidth",
						"lv", "labelVisible",
						"la", "labelAlign",
						"li", "labelIndent",
						"fn", "font",
						"mw", "marginWidth",
						"mh", "marginHeight" )

	_events_ = ( 	"cc", "collapseCommand",
					"ec", "expandCommand",
					"pcc", "preCollapseCommand",
					"pec", "preExpandCommand" )


class RowLayout( Layout ):
	"""Wrapper for row column layout"""
	_properties_ = [ 	"columnWidth", "cw",
						"columnAttach", "cat",
						"rowAttach", "rat",
					  	"columnAlign", "cal",
						"adjustableColumn", "adj",
					  	"numberOfColumns", "nc" ]

	for flag in ( 	"columnWidth", "cw", "columnAttach", "ct", "columnOffset",
				  	"co", "columnAlign", "cl", "adjustableColumn", "ad" ):
		for i in range( 1, 7 ):
			_properties_.append( flag + str( i ) )


class ColumnLayoutBase( Layout ):
	_properties_ = (   	"columnAlign", "cal",
						"columnAttach", "cat",
						"columnOffset", "co" ,
						"columnWidth", "cw",
						"rowSpacing", "rs" )

class RowColumnLayout( ColumnLayoutBase ):
	"""Wrapper for row column layout"""
	_properties_ = ( 	"numberOfColumns", "nc",
					  	"numberOfRows", "nr",
						"rowHeight", "rh",
						"rowOffset", "ro",
					  	"rowSpacing", "rs" )


class ColumnLayout( ColumnLayoutBase ):
	"""Wrapper class for a simple column layout"""

	_properties_ = ( 	"adjustableColumn", "adj" )

class ScrollLayout( Layout ):
	"""Wrapper for a scroll layout"""
	_properties_ = ( 	"scrollAreaWIdth", "saw",
					  	"scrollAreaHeight", "sah",
						"scrollAreaValue", "sav",
						"minChildWidth", "mcw",
						"scrollPage", "sp",
						"scrollByPixel", "sbp"	)

	_event_ = ( "resizeCommand", "rc" )
	
class TabLayout( Layout ):
	"""Simple wrapper for a tab layout"""
	_properties_ = (	"tv", "tabsVisible",
					   	"st",  "selectTab",
						"sti", "selectTabIndex",
						"tl", "tabLabel",
						"tli", "tabLabelIndex",
						"scr", "scrollable",
						"hst", "horizontalScrollBarThickness",
						"vst", "verticalScrollBarThickness",
						"imw", "innerMarginWidth",
						"imh", "innerMarginHeight",
						"i", "image",
						"iv", "imageVisible",
						"cr", "childResizable",
						"mcw", "minChildWidth",
						"mt", "moveTab" )

	_events_ = ( 	"cc", "changeCommand",
					"sc", "selectCommand",
					"psc", "preSelectCommand",
					"dcc", "doubleClickCommand" )

