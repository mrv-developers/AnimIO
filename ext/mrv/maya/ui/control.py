# -*- coding: utf-8 -*-
"""
Contains the most controls like buttons and sliders for more convenient use
"""
__docformat__ = "restructuredtext"

import base as uibase
import util as uiutil

import logging
log = logging.getLogger("mrv.maya.ui.control")

#{ Bases

class LabelBase( uibase.SizedControl ):
	"""Base class for elements having labels"""
	_properties_ = ( 	"l", "label",
						"al", "align" ,
						"rs", "recomputeSize" )

class SliderBase( uibase.SizedControl ):
	"""Class contributing Simple Slider Events"""
	_events_ = ( 	"cc", "changeCommand",
					"dc", "dragCommand" )

	_properties_ = ( 	"min", "minValue",
					  	"max", "maxValue",
						"v", "value",
						"s", "step",
						"hr", "horizontal" )

class BooleanBase( LabelBase ):
	"""Base class for boolean controls"""
	_events_ = ( 	"onCommand", "onc",
					"offCommand", "ofc",
					"changeCommand", "cc" )

class CheckBoxBase( BooleanBase ):
	"""Base class for checkboxes"""
	_properties_ = ( "value", "v" )

class RadioButtonBase( BooleanBase ):
	"""Base class for radio buttons"""
	_properties_ = ( "select", "sl" )


class GroupBase( uibase.SizedControl ):
	"""Base allowing access to all grouped controls
	
	:note: using short property names to ... keep it sane """

	_properties_ = [ 	"cw", "columnWidth",
						"cat", "columnAttach",
						"rat", "rowAttach",
						"cal", "columnAlign",
						"adj", "adjustableColumn" ]

	# setup evil multi attributes
	for flag in ( 	"cw","columnWidth", "ct", "columnAttach",
				  	"co", "columnOffset", "cl", "columnAlign",
					"ad", "adjustableColumn" ):
		start = 1
		if flag in ( "cl", "columnAlign", "ad", "adjustableColumn" ):
			start = 2

		for i in range( start, 7 ):
			_properties_.append( flag + str( i ) )
	# END for each flag

class OptionMenuBase( uibase.ContainerMenuBase ):
	"""base class for all optionMenu like controls"""
	__metaclass__ = uibase.typ.MetaClassCreatorUI

	_events_ = ( "cc", "changeCommand" )
	_properties_ = ( 	"ils", "itemListShort",
						"ill", "itemListLong",
						"l", "label",
						"ni", "numberOfItems",
						"sl", "select",
						"v", "value" )

class FieldBase( uibase.SizedControl ):
	_events_ = 		( 	"rfc", "receiveFocusCommand",
						"ec", "enterCommand",
						"cc", "changeCommand" )

	_properties_ = ( "ed", "editable" )


class TextFieldBase( object ):
	"""Base just containing properties and events"""
	__metaclass__ = uibase.typ.MetaClassCreatorUI

	_properties_ = ( 	"fn", "font",
						"it", "insertText",
						"ip", "insertPosition"
						"fi", "fileName",
						"tx", "text" )

class TextFieldGroupBase( TextFieldBase ):
	"""Common base for the group text fields"""
	_events_ = ( 	"cc", "changeCommand" ,
					"fcc", "forceChangeCommand" )

class SliderGroupBase( GroupBase, SliderBase ):
	"""base class for all sliders"""
	_properties_ = ( 	"el", "extraLabel",
						"fieldMinValue", "fmn",
						"fieldMaxValue", "fmx",
						"fieldStep", "fs",
						"sliderStep", "ss" )


class BooleanGroupBase( GroupBase, BooleanBase ):
	"""base class for all boolean groups"""
	_events_ = list()

	# setup evil multi attributes
	for flag in ( 	"on","onCommand",
				  	"of", "offCommand",
					"cc", "changeCommand" ):

		for i in range( 1, 5 ):
			_events_.append( flag + str( i ) )
	# END for event each flag

	_properties_ = list()

	for flag in ( 	"en","enable",
				  	"da", "data",
					"l", "label",
					"la","labelArray" ):

		start = 1
		if flag in ( "la", "labelArray" ):
			start = 2

		for i in range( start, 5 ):
			_properties_.append( flag + str( i ) )
	# END for event each flag


class ButtonGroupBase( GroupBase ):
	"""Base class for all button groups"""
	_properties_ = ( 	"bl", "buttonLabel",
						"eb", "enableButton" )

	_events_ = ( "bc", "buttonCommand" )

class IconTextBase( object ):
	"""Base class for all icon text like controls"""
	#{ Configuration
	__metaclass__ = uibase.typ.MetaClassCreatorUI
	#} END configuation

	_properties_ = ( 	"image", "i",
					  	"image1", "i1",
						"image2", "i2",
						"image3", "i3",
						"disabledImage", "di",
						"highlightImage", "hi",
						"imageOverlayLabel", "iol",
						"style", "st",
						"selectionImage", "si",
						"highlightImage", "hi",
						"labelOffset", "lo",
						"font", "fn"
						)

	_events_ = ( 		"handleNodeDropCallback", "hnd",
					 	"labelEditingCallback", "lec"	)

#} END bases


class RadioButtonGrp( BooleanGroupBase, RadioButtonBase ):
	"""Warning: inherits booleanBase multiple times """
	pass


class CheckBoxGrp( BooleanGroupBase, CheckBoxBase ):
	"""Note: inherits booleanBase multiple times, this does no harm"""
	_properties_ = list()

	for flag in ( 	"v","value",
				  	"va", "valueArray" ):
		for i in range( 1, 5 ):
			if flag in ( "va", "valueArray" ) and i == 1:
				continue

			_properties_.append( flag + str( i ) )
		# END for each numbered item
	# END for each flagg


class Button( LabelBase ):
	""" Simple button interface
	
	:note: you can only use either the onpress or the onrelease event, both
		together apparently do not work"""
	_properties_ = ( "actionIsSubstitute" )
	_events_ = ( "c", "command" )

	e_pressed = uiutil.EventSenderUI._UIEvent( "command", actOnPress=True )
	e_released = uiutil.EventSenderUI._UIEvent( "command", actOnPress=False )


class IconTextButton( LabelBase, IconTextBase ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file"""
	_events_ = ( "c", "command" )
	
	
class RadioCollectionBase( object ):
	"""Keeps common properties"""
	__metaclass__ = uibase.typ.MetaClassCreatorUI
	
	_properties_ = ( 	"global", "gl",
						"select", "sl", 
						"disableCommands", "dcm", 
						"numberOfCollectionItems", "nci", 
						"collectionItemArray", "cia" )
						
	
class RadioCollection( RadioCollectionBase, uibase.NamedUI ):
	"""Required for multiple inhertance"""
	pass
	

class IconTextRadioCollection( RadioCollectionBase, uibase.NamedUI ):
	"""Required for multiple inhertance
	:note: it inherits exists() and a few others which are actually not supported for 
	some reason"""
	pass


class ToolCollection( RadioCollectionBase, uibase.NamedUI ):
	"""Required for multiple inhertance"""
	pass


class RadioMenuItemCollection( RadioCollectionBase, uibase.NamedUI ):
	"""Required for multiple inhertance"""
	pass


class IconTextCheckBox( CheckBoxBase, IconTextBase ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file"""
	pass

class IconTextRadioButton( RadioButtonBase, IconTextBase ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file"""
	pass

class TextField( FieldBase, TextFieldBase ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file"""
	pass

class ScrollField( uibase.SizedControl ):
	""":note: although the class shares some properties of the textfield, it does not share all of them"""
	_properties_ = ( 	"wordWrap", "ww",
					  	"font", 	"fn",
						"text", "tx",
						"insertText", "it",
						"insertionPosition", "ip",
						"selection", "sl",
						"clear", "cl",
						"editable", "ed",
						"numberOfLines", "nl"	)

	_events_ = ( 		"enterCommand", "ec",
					 	"keyPressCommand", "kpc",
						"changeCommand", "cc"		)


class TextScrollList( uibase.SizedControl ):
	"""Class defining attributes and events for the text-scroll list"""
	_properties_ = ( 	"append", "a",
						"appendPosition", "ap",
						"allItems", "ai",
						"allowAutomaticSelection", "aas",
						"allowMultiSelection", "ams",
						"numberOfItems", "ni",
						"numberOfRows", "nr",
						"numberOfSelectedItems", "nsi",
						"removeAll", "ra"
						"removeItem", "ri",
						"removeIndexedItem", "rii",
						"selectItem", "si",
						"selectIndexedItem", "sii",
						"deselectAll", "da",
						"deselectItem", "di",
						"deselectIndexedItem", "dii",
						"showIndexedItem", "shi",
						"font", "fn" )

	_events_ = ( 	"doubleClickCommand", "dcc",
					"deleteKeyCommand", "dkc",
					"selectCommand", "sc" )



class TextFieldGrp( GroupBase, TextFieldGroupBase ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file"""


class TextFieldButtonGrp( ButtonGroupBase, TextFieldGroupBase ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file"""

class Text( LabelBase ):
	_properties_ = ( "font", "fn" )

class Separator( uibase.SizedControl ):
	_properties_ = ( 	"style", "st",
						"horizontal", "hr" 		)

class OptionMenu( OptionMenuBase, uibase.SizedControl ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file
	
	:note: Order of inheritance matters due to method resolution order !"""
	#( Configuration
	_is_menu = True
	#) END configuration


class OptionMenuGrp( OptionMenuBase, GroupBase ):
	"""Class just for multiple inheritance - this cannot be expressed in the hierarchy
	file
	
	:note: Order of inheritance matters due to method resolution order !"""
	#( Configuration
	_is_menu = True
	#) END configuration

	#{ Special Handling Overrides

	def setActive( self ):
		"""The optionMenuGrp cannot be set as a parent as it is classified as control layout.
		A problem arises if you actually try to add new menuItems to it after it's creation which
		does not work as it is not a menu"""
		log.warn("setActive: OptionMenuGrp's instances cannot be setActive after creation due to a Maya API logic error - you will set the layout active, not the contained option menu")
		return super( OptionMenuGrp, self ).setActive()

	def setParentActive( self ):
		"""See `setActive`"""
		log.warn("setParentActive: OptionMenuGrp instances will change the parent of their control layout only, not the menu parent of the optionMenu")
		super( OptionMenuGrp, self ).setParentActive()
	#} special handling overrides


