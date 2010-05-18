# -*- coding: utf-8 -*-
"""
Contains some basic  classes that are required to run the UI system
"""
__docformat__ = "restructuredtext"
import maya.cmds as cmds
from mrv.util import capitalize
from mrv.interface import iDagItem
from util import EventSenderUI
import util as uiutil
from mrv.exc import MRVError
import typ
_uidict = None 			# set during initialization

############################
#### Methods		  	####
##########################

def getUIType( uiname ):
	"""
	:return: uitype string having a corresponding mel command - some types returned do not correspond
		to the actual name of the command used to manipulate the type """
	uitype = cmds.objectTypeUI( uiname )
	return typ._typemap.get( uitype, uitype )


def wrapUI( uinameOrList, ignore_errors = False ):
	"""
	:return: a new instance ( or list of instances ) of a suitable python UI wrapper class for the
		UI with the given uiname(s)
	:param uinameOrList: if single name, a single instance will be returned, if a list of names is given,
		a list of respective instances. None will be interpreted as empty list
	:param ignore_errors: ignore ui items that cannot be wrapped as the type is unknown.
	:raise RuntimeError: if uiname does not exist or is not wrapped in python """
	uinames = uinameOrList
	islisttype = isinstance( uinameOrList, ( tuple, list, set ) )
	if not islisttype:
		if uinameOrList is None:
			islisttype = True
			uinames = list()
		else:
			uinames = [ uinameOrList ]
	# END input list handling
	out = list()
	for uiname in uinames:
		uitype = getUIType( uiname )
		clsname = capitalize( uitype )

		try:
			out.append( _uidict[clsname]( name=uiname,  wrap_only = 1 ) )
		except KeyError:
			if not ignore_errors:
				raise RuntimeError( "ui module has no class named %s, failed to wrap %s" % ( clsname, uiname ) )
	# END for each uiname

	if islisttype:
		return out

	return out[0]

# alias, allowing new items to be easily wrapped
UI = wrapUI



def lsUI( **kwargs ):
	""" List UI elements as python wrapped types
	
	:param kwargs: flags from the respective maya command are valid
		If no special type keyword is specified, all item types will be returned
	:return: list of NamedUI instances of respective UI elements """
	long = kwargs.pop( 'long', kwargs.pop( 'l', True ) )
	head = kwargs.pop( 'head', kwargs.pop( 'hd', None ) )
	tail = kwargs.pop( 'tail', kwargs.pop( 'tl', None) )

	if not kwargs:
		kwargs = {
			'windows': 1, 'panels' : 1, 'editors' : 1, 'controls' : 1,
			'controlLayouts' : 1,'collection' : 1, 'radioMenuItemCollections' : 1,
			'menus' : 1, 'menuItems' : 1, 'contexts' : 1, 'cmdTemplates' : 1 }
	# END kwargs handling

	kwargs['long'] = long
	if head is not None: kwargs['head'] = head
	if tail is not None: kwargs['tail'] = tail

	# NOTE: controls and controlLayout will remove duplcate entries - we have to
	# prune them ! Unfortunately, you need both flags to get all items, even layouts
	# NOTE: have to ignore errors as there are still plenty of items that we cannot
	# wrap
	return wrapUI( set( cmds.lsUI( **kwargs ) ), ignore_errors = True )


############################
#### Classes		  	####
##########################

class BaseUI( object ):

	__melcmd__	= None					# every class deriving directly from it must define this !

	def __init__( self, *args, **kwargs ):
		if self.__class__ == BaseUI:
			raise MRVError( "Cannot instantiate" + self.__class__.__name__ + " directly - it can only be a base class" )

		# return object.__init__( self , *args, **kwargs )
		super( BaseUI, self ).__init__( *args, **kwargs )


class NamedUI( unicode, BaseUI , iDagItem, EventSenderUI ):
	"""Implements a simple UI element having a name  and most common methods one
	can apply to it. Derived classes should override these if they can deliver a
	faster implementation.
	If the 'name' keyword is supplied, an existing UI element will be wrapped

	**Events**
		
		As subclass of EventSenderUI, it can provide events that are automatically
		added by the metaclass as described by the _events_ attribute list.
		This allows any number of clients to register for one maya event. Derived classes
		may also use their own events which is useful if you create components
	
		Register for an event like:
		
		>>> uiinstance.e_eventlongname = yourFunction( sender, *args, **kwargs )
		>>> *args and **kwargs are determined by maya

	:note: although many access methods look quite 'repeated' as they are quite
		similar except for a changing flag, they are hand-written to provide proper docs for them"""
	__metaclass__ = typ.MetaClassCreatorUI

	#( Configurtation
	_sep = "|"			# separator for ui elements in their name, same as for dag paths
	_is_menu = False	# if True, some methods will handle special cases for menus
	#) end configuration

	#{ Overridden Methods
	@classmethod
	def _exists( cls, uiname ):
		"""
		:return: 1 if the given UI element exists, 0 if it does not exist
			and 2 it exists but the passed in name does not guarantee there are not more
			objects with the same name"""
		try:
			uitype = cmds.objectTypeUI( uiname )
		except RuntimeError:
			return 0
		else:
			# short names can only be used with top level items like
			# windows - for everything else we cannot know how many items
			# with the same name exist and which one we should actually wrap
			# Claim it does not exist
			if "Window" not in uitype and cls._sep not in uiname:
				return 2
			return 1

	def __new__( cls, *args, **kwargs ):
		"""If name is given, the newly created UI will wrap the UI with the given name.
		Otherwise the UIelement will be created

		:param kwargs:
		
			 * name: 
			 	name of the user interface to wrap or the target name of a new elf element.
				Valid names for creation are short names ( without a | in it's path ), valid names
				for wrapping are short and preferably long names.
				
			 * wrap_only: 
				if True, default False, a wrap will be done even if the passed
				in name uses the short form ( for non-window elements ). If it exists, one cannot be sure
				whether more elements with the given name exist. If False, the system will create a new
				element of our type.
				
			 * force_creation: 
				if True, default False, a new item will be created
				even if an item with the given name uniquely exists. This might be necessary that
				you wish to create the given named item under the current parent, although an item
				with that name might already exist below another parent. This is required if
				you have a short name only
				
		:note: you can use args safely for your own purposes
		:note: if name is set but does not name a valid user interface, a new one
			will be created, and passed to the constructor"""
		name = kwargs.pop( "name", None )
		exists = ( ( name is not None ) and NamedUI._exists( str( name ) ) ) or False
		force_creation = kwargs.pop( "force_creation", False )

		# pretend named element does not exist if existance is ambigous
		if not kwargs.pop( "wrap_only", False ) and exists == 2:
			exists = 0

		if name is None or not exists or force_creation:
			try:
				if name:	# use name to create named object
					name = cls.__melcmd__( name, **kwargs )

					# assure we have a long name - mel sometimes returns short ones
					# that are ambigous ...
					if cls._sep not in name and Window not in cls.mro():
						raise AssertionError( "%s instance named '%s' does not have a long name after creation" % ( cls, name ) )
				else:
					name = cls.__melcmd__( **kwargs )
			except (RuntimeError,TypeError), e:
				raise RuntimeError( "Creation of %s using melcmd %s failed: %s" % ( cls, cls.__melcmd__, str( e ) ) )
			# END name handling
		# END auto-creation as required
		
		inst = unicode.__new__( cls, name )
		
		# UI DELETED HANDLING
		# check for ui deleted override on subclass. If so, we initialize a run-once event
		# to get notification. We use cmds for this as we can spare the callbackID handling 
		# in that case ( run-once is not available in the API )
		if cls.uiDeleted != NamedUI.uiDeleted:
			cmds.scriptJob(uiDeleted=(name, inst.uiDeleted), runOnce=1) 
		# END register ui deleted event
		
		return inst

	def __repr__( self ):
		return u"%s('%s')" % ( self.__class__.__name__, self )

	def __setattr__( self, attr, value ):
		"""Prevent properties or events that do not exist to be used by anyone,
		everything else is allowed though"""
		if ( attr.startswith( "p_" ) or attr.startswith( "e_" ) ):
			try:
				getattr( self, attr )
			except AttributeError:
				raise AttributeError( "Cannot create per-instance properties or events: %s.%s ( did you misspell an existing one ? )" % ( self, attr ) )
			except Exception:
				# if there was another exception , then the attribute is at least valid and MEL did not want to
				# accept the querying of it
				pass
			# END exception handling
		# END check attribute validity
		return super( NamedUI, self ).__setattr__( attr, value )

	def __init__( self , *args, **kwargs ):
		""" Initialize instance and check arguments """
		# assure that new instances are being created initially
		forbiddenKeys = [ 'edit', 'e' , 'query', 'q' ]
		for fkey in forbiddenKeys:
			if fkey in kwargs:
				raise ValueError( "Edit or query flags are not permitted during initialization as interfaces must be created onclass instantiation" )
			# END if key found in kwargs
		# END for each forbidden key

		super( NamedUI, self ).__init__( *args, **kwargs )
	#} END overridden methods

	def children( self, **kwargs ):
		""":return: all intermediate child instances
		:note: the order of children is lexically ordered at this time
		:note: this implementation is slow and should be overridden by more specialized subclasses"""
		return filter( lambda x: len( x.replace( self , '' ).split('|') ) - 1 ==len( self.split( '|' ) ), self.childrenDeep() )

	def childrenDeep( self, **kwargs ):
		""":return: all child instances recursively
		:note: the order of children is lexically ordered at this time
		:note: this implementation is slow and should be overridden by more specialized subclasses"""
		kwargs['long'] = True
		return filter( lambda x: x.startswith(self) and not x == self, lsUI(**kwargs))

	def parent( self ):
		""":return: parent instance of this ui element"""
		return wrapUI( '|'.join( self.split('|')[:-1] ) )

	#{ Hierachy Handling

	@classmethod
	def activeParent( cls ):
		""":return: NameUI of the currently set parent
		:raise RuntimeError: if no active parent was set"""
		# MENU
		wrapuiname = None
		if cls._is_menu:
			wrapuiname = cmds.setParent( q=1, m=1 )
		else:
			# NON-MENU
			wrapuiname = cmds.setParent( q=1 )

		if not wrapuiname or wrapuiname == "NONE":
			raise RuntimeError( "No current parent set" )

		return wrapUI( wrapuiname )

	#}	END hierarchy handling

	def uiDeleted(self):
		"""If overridden in subclass, it will be called once the UI gets deleted 
		within maya ( i.e. the user closed the window )eee
		The base implementation assures that all event-receivers that are bound to 
		your events will be freed, allowing them to possibly be destroyed as well.
		
		Use this callback to register yourself from all your event senders, then call 
		the base class method.
		
		:note: This is not related to the __del__ method of your object. Its worth
			noting that your instance will be strongly bound to a maya event, hence 
			your instance will exist as long as your user interface element exists 
			within maya."""
		self.clearAllEvents()
	
	def type( self ):
		""":return: the python class able to create this class
		:note: The return value is NOT the type string, but a class """
		uitype = getUIType( self )
		return getattr( ui, capitalize( uitype ) )

	def shortName( self ):
		""":return: shortname of the ui ( name without pipes )"""
		return self.split('|')[-1]

	def delete( self ):
		"""Delete this UI - the wrapper instance must not be used after this call"""
		cmds.deleteUI( self )

	def exists( self ):
		""":return: True if this instance still exists in maya"""
		try:
			return self.__melcmd__( self, ex=1 )
		except RuntimeError:
			# although it should just return False if it does NOT exist, it raises
			return False
			
	#{ Properties
	p_exists = property(exists)
	p_ex = p_exists
	#} END properties


class SizedControl( NamedUI ):
	"""Base Class for all controls having a dimension"""
	__metaclass__ = typ.MetaClassCreatorUI
	_properties_ = ( 	"dt", "defineTemplate",
					  	"ut", "useTemplate",
						"w","width",
						"h", "height",
						"vis", "visible",
						"m", "manage",
						"en", "enable",
						"io", "isObscured",
						"npm", "numberOfPopupMenus",
						"po", "preventOverride",
						"bgc", "backgroundColor",
						"dtg", "doctTag" )

	_events_ = ( 	"dgc", "dragCallback" ,
					"dpc", "dropCallback" )

	#{ Query Methods

	def annotation( self ):
		""":return : the annotation string """
		try:
			return self.__melcmd__( self, q=1, ann=1 )
		except TypeError:
			return ""

	def dimension( self ):
		""":return: (x,y) tuple of x and y dimensions of the UI element"""
		return ( self.__melcmd__( self, q=1, w=1 ), self.__melcmd__( self, q=1, h=1 ) )

	def popupMenuArray( self ):
		""":return: popup menus attached to this control"""
		return wrapUI( self.__melcmd__( self, q=1, pma=1 ) )

	#}END query methods

	#{ Edit Methods

	def setAnnotation( self, ann ):
		"""Set the UI element's annotation
		:note: not all named UI elements can have their annotation set"""
		self.__melcmd__( self, e=1, ann=ann )

	def setDimension( self, dimension ):
		"""Set the UI elements dimension
		:param dimension: (x,y) : tuple holding desired x and y dimension"""
		self.__melcmd__( self, e=1, w=dimension[0] )
		self.__melcmd__( self, e=1, h=dimension[1] )
		
	def setFocus(self):
		"""Set the global keyboard focus to this control"""
		cmds.setFocus(self)

	#}END edit methods

	p_annotation = property( annotation, setAnnotation )
	p_ann = p_annotation
	p_dimension = property( dimension, setDimension )
	p_pma = property( popupMenuArray )
	p_popupMenuArray = property( popupMenuArray )



class Window( SizedControl, uiutil.UIContainerBase ):
	"""Simple Window Wrapper
	
	:note: Window does not support some of the properties provided by sizedControl"""
	__metaclass__ = typ.MetaClassCreatorUI
	_properties_ = (	"t", "title",
					   	"i", "iconify",
						"s", "sizeable",
						"wh", "widthHeight"
						"in", "iconName",
						"tb","titleBar",
					   	"mnb", "minimizeButton",
						"mxb", "maximizeButton",
						"tlb", "toolbox",
						"tbm", "titleBarMenu",
						"mbv", "menuBarVisible",
						"tlc", "topLeftCorner",
						"te", "topEdge",
						"tl", "leftEdge",
						"mw", "mainWindow",
						"rt", "resizeToFitChildren",
						"dt", "docTag" )

	_events_ = ( "rc", "restoreCommand", "mnc", "minimizeCommand" )


	#{ Window Specific Methods

	def show( self ):
		""" Show Window
		:return: self"""
		cmds.showWindow( self )
		return self

	def numberOfMenus( self ):
		""":return: number of menus in the menu array"""
		return int( self.__melcmd__( self, q=1, numberOfMenus=1 ) )

	def menuArray( self ):
		""":return: Menu instances attached to this window"""
		return wrapUI( self.__melcmd__( self, q=1, menuArray=1 ) )

	def isFrontWindow( self ):
		""":return: True if we are the front window """
		return bool( self.__melcmd__( self, q=1, frontWindow=1 ) )

	def setMenuIndex( self, menu, index ):
		"""Set the menu index of the specified menu
		
		:param menu: name of child menu to set
		:param index: new index at which the menu should appear"""
		return self.__melcmd__( self, e=1, menuIndex=( menu, index ) )

	#} END window speciic

	p_numberOfMenus = property( numberOfMenus )
	p_nm = p_numberOfMenus


class MenuBase( NamedUI ):
	"""Common base for all menus"""

	#( Configuration
	_is_menu = True
	#) END configuration

	_properties_ = (
					   "en", "enable",
					   	"l", "label",
						"mn", "mnemonic",
						"aob", "allowOptionBoxes",
						"dt", "docTag"
					 )

	_events_ = (
					 	"pmc", "postMenuCommand",
						"pmo", "postMenuCommandOnce"
				)


class ContainerMenuBase( uiutil.UIContainerBase ):
	"""Implements the container abilities of all menu types"""

	def setActive( self ):
		"""Make ourselves the active menu
		
		:return: self"""
		cmds.setParent( self, m=1 )
		return self

	def setParentActive( self ):
		"""Make our parent the active menu layout
		
		:return: self
		:note: only useful self is a submenu"""
		cmds.setParent( ".." , m=1 )
		return self


class Menu( MenuBase, ContainerMenuBase ):
	_properties_ = (
					  	"hm", "helpMenu",
						"ia", "itemArray",
						"ni", "numberOfItems",
						"dai", "deleteAllItems",
						"fi", "familyImage"
					)


class MenuItem( MenuBase ):

	_properties_ = (
						"d", "divider",
						"cb", "checkBox",
						"icb", "isCheckBox",
						"rb", "radioButton",
						"irb", "isRadioButton",
						"iob", "isOptionBox",
						"cl", "collection",
						"i", "image",
						"iol", "imageOverlayLabel",
						"sm", "subMenu",
						"ann", "annotation",
						"da", "data",
						"rp", "radialPosition",
						"ke", "keyEquivalent",
						"opt", "optionModifier",
						"ctl", "controlModifier",
						"sh", "shiftModifier",
						"ecr", "enableCommandRepeat",
						"ec", "echoCommand",
						"it", "italicized",
						"bld", "boldFont"
					)

	_events_ = (
						"dmc", "dragMenuCommand",
						"ddc", "dragDoubleClickCommand",
						"c", "command"
				)

	def toMenu( self ):
		""":return: Menu representing self if it is a submenu
		:raise TypeError: if self i no submenu"""
		if not self.p_sm:
			raise TypeError( "%s is not a submenu and cannot be used as menu" )

		return Menu( name = self )

# type is returned in some cases by objectTypeUI
CommandMenuItem = MenuItem
