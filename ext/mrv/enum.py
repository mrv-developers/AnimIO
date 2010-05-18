# -*- coding: utf-8 -*-
"""This module is designed to be the equivalent of the enum type in other
languages. An enumeration object is created at run time, and contains
named members that are the enumeration elements.

The enumeration is also a tuple of all of the values in it. You can iterate
through the values, perform 'in' tests, slicing, etc. It also includes
functions to lookup specific values by name, or names by value.

You can specify your own element values, or use the create factory method
to create default Elements. These elements are unique system wide, and are
ordered based on the order of the elements in the enumeration. They also
are _repr_'d by the name of the element, which is convenient for testing,
debugging, and generation text output.

Example Code:
	>>>	# Using Element values
	>>> Colors = Enumeration.create('red', 'green', 'blue')
		
	>>> # Using explicitly specified values
	>>>Borders = Enumeration.create(('SUNKEN', 1),
	>>>							 	('RAISED', 32),
	>>>							 	('FLAT', 2))
		
	>>> x = Colors.red
	>>> y = Colors.blue
		
	>>> assert x < y
	>>> assert x == Colors('red')
	>>> assert Borders.FLAT == 2:
	>>> assert 1 in Borders

:note: slightly modified by Sebastian Thiel to be more flexible and suitable as
	base class
"""
__docformat__ = "restructuredtext"
__contact__='garret at bgb dot cc'
__license__='freeware'

import platform

__all__ = ("Element", "Enumeration", "create")

class Element(object):
	"""Internal helper class used to represent an ordered abstract value.

	The values have string representations, have strictly defined ordering
	(inside the set) and are never equal to anything but themselves.

	They are usually created through the create factory method as values
	for Enumerations.

	They assume that the enumeration member will be filled in before any
	comparisons are used. This is done by the Enumeration constructor.
	"""
	# we do not define slots to stay pickable ( without reimplementing things )
	def __init__(self, name, value):
		self._name = name
		self._value = value
		self.enumeration = None # Will be filled in later

	def __repr__(self):
		return self._name

	def _checkType( self, other ):
		""":raise TypeError: if other cannot be used with this element"""
		if ( self.__class__ != other.__class__ ) or ( self.enumeration is not other.enumeration ):
			raise TypeError( "%s is incompatible with %s" % ( other, self ) )

	def __cmp__(self, other):
		"""We override cmp only because we want the ordering of elements
		in an enumeration to reflect their position in the enumeration.
		"""
		try:
			self._checkType( other )
		except TypeError:
			return NotImplemented	# to make cmp fail

		# If we are both elements in the same enumeration, compare
		#	values for ordering
		return cmp(self._value, other._value)

	def _checkBitflag( self ):
		if not self.enumeration._supports_bitflags:
			raise TypeError( "Enumeration %s of element %s has no bitflag support" % ( self.enumeration, self ) )

	def __or__( self, other ):
		"""Allows oring values together - only works if the values are actually orable
		integer values
		
		:return: integer with the ored result
		:raise TypeError: if we are not a bitflag or other is not an element of our enumeration"""
		self._checkType( other )
		self._checkBitflag()
		return self.value() | other.value()

	def __xor__( self, other ):
		"""Allows to x-or values together - only works if element's values are xorable
		integer values.
		
		:param other: integer
		:return: integer with the xored result"""
		self._checkBitflag()
		return self.value() ^ other


	def __and__( self, other ):
		"""Allow and with integers
		
		:return: self if self & other == self or None if our bit is not set in other
		:raise TypeError: if other is not an int"""
		if not isinstance( other, int ):
			raise TypeError( "require integer, got %s" % type( other ) )

		if self.value() & other:
			return self

		return None

	def value( self ):
		""":return: own value"""
		return self._value
		
	def name( self ):
		""":return: name of the element"""
		return self._name


class Enumeration(tuple):
	"""This class represents an enumeration. You should not normally create
	multiple instances of the same enumeration, instead create one with
	however many references are convenient.

	The enumeration is a tuple of all of the values in it. You can iterate
	through the values, perform 'in' tests, slicing, etc. It also includes
	functions to lookup specific values by name, or names by value.

	You can specify your own element values, or use the create factory method
	to create default Elements. These elements are unique system wide, and are
	ordered based on the order of the elements in the enumeration. They also
	are _repr_'d by the name of the element, which is convenient for testing,
	debugging, and generation text output.

	:note: pickling this class with Elements will fail as they contain cyclic
		references that it cannot deal with
	:todo: implement proper pickle __getstate__ and __setstate__ that deal with
		that problem
	"""
	_slots_ = ( "_nameMap", "_valueMap", "_supports_bitflags" )

	def __new__(self, names, values, **kwargs ):
		"""This method is needed to get the tuple parent class to do the
		Right Thing(tm). """
		return tuple.__new__(self, values)

	def __setattr__( self, name, value ):
		"""Do not allow to change this instance"""
		if name in self._slots_:
			return super( Enumeration, self ).__setattr__( name, value )

		raise AttributeError( "No assignments allowed" )

	def __getattr__( self , attr ):
		"""Prefer to return value from our value map"""
		try:
			return self.valueFromName( attr )
		except ValueError:
			raise AttributeError( "Element %s is not part of the enumeration" % attr )


	def __init__(self, names, values, **kwargs ):
		"""The arguments needed to construct this class are a list of
		element names (which must be unique strings), and element values
		(which can be any type of value). If you don't have special needs,
		then it's recommended that you use Element instances for the values.

		This constructor is normally called through the create factory (which
		will create Elements for you), but that is not a requirement.
		"""

		assert len(names) == len(values)

		# We are a tuple of our values, plus more....
		tuple.__init__(self)

		self._nameMap = {}
		self._valueMap = {}
		self._supports_bitflags = kwargs.get( "_is_bitflag", False )		# insurance for bitflags


		for i in xrange(len(names)):
			name = names[i]
			value = values[i]

			# Tell the elements which enumeration they belong too
			if isinstance( value, Element ):
				value.enumeration = self

			# Prove that all names are unique
			assert not name in self._nameMap

			# create mappings from name to value, and vice versa
			self._nameMap[name] = value
			self._valueMap[value] = name


	def valueFromName(self, name):
		"""Look up the enumeration value for a given element name.
		
		:raise ValueError:"""
		try:
			return self._nameMap[name]
		except KeyError:
			raise ValueError("Name %r not found in enumeration, pick one of %s" % (name, ', '.join(str(e) for e in self)))
		# END exception handling

	def nameFromValue(self, value):
		"""Look up the name of an enumeration element, given it's value.

		If there are multiple elements with the same value, you will only
		get a single matching name back. Which name is undefined.
		
		:raise ValueError: if value is not a part of our enumeration"""
		try:
			return self._valueMap[value]
		except KeyError:
			raise ValueError("Value %r is not a member of this enumeration" % value)
		# END exception handling  

	def _nextOrPrevious( self, element, direction, wrap_around ):
		"""do-it method, see `next` and `previous`
		
		:param direction: -1 = previous, 1 = next """
		curindex = -1
		for i,elm in enumerate( self ):
			if elm == element:
				curindex = i
				break
			# END if elms match
		# END for each element

		assert curindex != -1

		nextindex = curindex + direction
		validnextindex = nextindex

		if nextindex >= len( self ):
			validnextindex = 0
		elif nextindex < 0:
			validnextindex = len( self ) - 1

		if not wrap_around and ( validnextindex != nextindex ):
			raise ValueError( "'%s' has no element in direction %i" % ( element, direction ) )

		return self[ validnextindex ]


	def next( self, element, wrap_around = False ):
		""":return: element following after given element
		:param element: element whose successor to return
		:param wrap_around: if True, the first Element will be returned if there is
			no next element
		:raise ValueError: if wrap_around is False and there is no next element"""
		return self._nextOrPrevious( element, 1, wrap_around )

	def previous( self, element, wrap_around = False ):
		""":return: element coming before the given element
		:param element: element whose predecessor to return
		:param wrap_around: see `next`
		:raise ValueError: if wrap_around is False and there is no previous element"""
		return self._nextOrPrevious( element, -1, wrap_around )

	__call__ = valueFromName


def create(*elements, **kwargs ):
	"""Factory method for Enumerations. Accepts of list of values that
	can either be strings or (name, value) tuple pairs. Strings will
	have an Element created for use as their value.
	If you provide elements, the member returned when you access the enumeration
	will be the element itself.

	Example:  Enumeration.create('fred', 'bob', ('joe', 42))
	Example:  Enumeration.create('fred', cls = EnumerationSubClass )
	Example:  Enumeration.create(Element('fred', Marge), ...)

	:param kwargs: 
		 * cls: The class to create an enumeration with, must be an instance of Enumeration
		 * elmcls: The class to create elements from, must be instance of Element
		 * bitflag: if True, default False, the values created will be suitable as bitflags.
					This will fail if you passed more items in than supported by the OS ( 32 , 64, etc ) or if
					you pass in tuples and thus define the values yourself.
	:raise TypeError,ValueError: if bitflags cannot be supported in your case"""
	cls = kwargs.pop( "cls", Enumeration )
	elmcls = kwargs.pop( "elmcls", Element )
	bitflag = kwargs.pop( "bitflag", False )

	assert elements
	assert Enumeration in cls.mro()
	assert Element in elmcls.mro()

	# check range
	if bitflag:
		maxbits = int( platform.architecture()[0][:-3] )
		if maxbits < len( elements ):
			raise ValueError( "You system can only represent %i bits in one integer, %i tried" % ( maxbits, len( elements ) ) )

		# prepare enum args
		kwargs[ '_is_bitflag' ] = True
	# END bitflag assertion

	names = list()
	values = list()

	for element in elements:
		# we explicitly check this per element !
		if isinstance( element, tuple ):
			assert len(element) == 2
			if bitflag:
				raise TypeError( "If bitflag support is required, tuples are not allowed: %s" % str( element ) )

			names.append(element[0])
			values.append(element[1])

		elif isinstance( element, basestring ):
			val = len( names )
			if bitflag:
				val = 2 ** val
			# END bitflag value generation
			values.append( elmcls( element, val ) )		# zero based ids
			names.append(element)
		elif isinstance(element, elmcls):
			values.append(element)
			names.append(element.name())
		else:
			raise "Unsupported element type: %s" % type( element )
	# END for each element

	return cls( names, values, **kwargs )

