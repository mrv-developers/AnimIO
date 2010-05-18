# -*- coding: utf-8 -*-
"""path.py - An object representing a path to a file or directory.

Example:
	>>> from path import path
	>>> d = path('/home/guido/bin')
	>>> for f in d.files('*.py'):
	>>>		f.chmod(0755)

This module requires Python 2.4 or later.

TODO
----
   - Tree-walking functions don't avoid symlink loops.	Matt Harrison sent me a patch for this.
   - Tree-walking functions can't ignore errors.  Matt Harrison asked for this.

   - Two people asked for path.chdir().	 This just seems wrong to me,
	 I dunno.  chdir() is moderately evil anyway.

   - Bug in write_text().  It doesn't support Universal newline mode.
   - Better error message in listdir() when self isn't a
	 directory. (On Windows, the error message really sucks.)
   - Make sure everything has a good docstringc.
   - Add methods for regex find and replace.
   - guess_content_type() method?
   - Could add split() and join() methods that generate warnings.
"""
from __future__ import generators
__docformat__ = "restructuredtext"

__license__='Freeware'

import sys
import logging
import os
import fnmatch
import glob
import shutil
import codecs
import re
from interface import iDagItem
log = logging.getLogger("mrv.path")

__version__ = '3.0'
__all__ = ['Path']

# Platform-specific support for path.owner
if os.name == 'nt':
	try:
		import win32security
	except ImportError:
		win32security = None
else:
	try:
		import pwd
	except ImportError:
		pwd = None

# Pre-2.3 support.	Are unicode filenames supported?
_base = str
_getcwd = os.getcwd
try:
	if os.path.supports_unicode_filenames:
		_base = unicode
		_getcwd = os.getcwdu
except AttributeError:
	pass

# Pre-2.3 workaround for booleans
try:
	True, False
except NameError:
	True, False = 1, 0

# Pre-2.3 workaround for basestring.
try:
	basestring
except NameError:
	basestring = (str, unicode)

# Universal newline support
_textmode = 'r'
if hasattr(file, 'newlines'):
	_textmode = 'U'


# cache used for path expansion
_varprog = re.compile(r'\$(\w+|\{[^}]*\})')

class TreeWalkWarning(Warning):
	pass

class Path( _base, iDagItem ):
	""" Represents a filesystem path.

	For documentation on individual methods, consult their
	counterparts in os.path.
	"""
	# Configuration
	_sep = os.path.sep

	#{ Special Python methods

	def __repr__(self):
		return '%s(%s)' % ( self.__class__.__name__, _base.__repr__(self) )

	# Adding a path and a string yields a path.
	def __add__(self, more):
		try:
			resultStr = _base.__add__(self, more)
		except TypeError:  #Python bug
			resultStr = NotImplemented
		if resultStr is NotImplemented:
			return resultStr
		return self.__class__(resultStr)

	def __radd__(self, other):
		if isinstance(other, basestring):
			return self.__class__(other.__add__(self))
		else:
			return NotImplemented

	# The / operator joins paths.
	def __div__(self, rel):
		""" fp.__div__(rel) == fp / rel == fp.joinpath(rel)

		Join two path components, adding a separator character if
		needed.
		"""
		return self.__class__(os.path.join(self, rel))

	# Make the / operator work even when true division is enabled.
	__truediv__ = __div__

	def __eq__( self, other ):
		"""Comparison method with expanded variables, just to assure
		the comparison yields the results we would expect"""
		return unicode( os.path.expandvars( self ) ) == unicode( os.path.expandvars( unicode(other) ) )

	def __ne__( self, other ):
		return not self.__eq__( other )

	def __hash__( self ):
		"""Expanded hash method"""
		return hash( unicode( self._expandvars() ) )

	#} END Special Python methods

	def _expandvars( self ):
		"""Internal version returning a string only
		
		:note: It is a slightly changed copy of the version in posixfile
			as the windows version was implemented differently ( it expands
			variables to an empty space which is undesireable )"""
		if '$' not in self:
			return self
		
		i = 0
		while True:
			m = _varprog.search(self, i)
			if not m:
				break
			i, j = m.span(0)
			name = m.group(1)
			if name.startswith('{') and name.endswith('}'):
				name = name[1:-1]
			if name in os.environ:
				tail = self[j:]
				self = self[:i] + os.environ[name]
				i = len(self)
				self += tail
			else:
				i = j
			# END handle variable exists in environ
		# END loop forever
		return self


	@classmethod
	def getcwd(cls):
		""":return: the current working directory as a path object. """
		return cls(_getcwd())

	#{ iDagItem Implementation

	def parent( self ):
		""":return: the parent directory of this Path or None if this is the root"""
		parent = self.dirname()
		if parent == self:
			return None
		return parent

	def children( self, predicate = lambda p: True, pattern = None ):
		""":return: child paths as retrieved by queryiing the file system.
		:note: files cannot have children, and willl return an empty array accordingly
		:param predicate: return p if predicate( p ) returns True
		:param pattern: list only elements that match the given simple  pattern
			i.e. *.*"""
		try:
			children = self.listdir( pattern )
		except OSError:
			return list()

		return [ c for c in children if predicate( c ) ]

	#} END idagitem implementation

	#{ Operations on path strings.

	isabs = os.path.isabs
	def abspath(self):		 return self.__class__(os.path.abspath(self._expandvars()))
	def normcase(self):		 return self.__class__(os.path.normcase(self))
	def normpath(self):		 return self.__class__(os.path.normpath(self))
	def realpath(self):		 return self.__class__(os.path.realpath(self._expandvars()))
	def expanduser(self):	 return self.__class__(os.path.expanduser(self))
	def expandvars(self):	 return self.__class__(self._expandvars())
	def dirname(self):		 return self.__class__(os.path.dirname(self))
	basename = os.path.basename

	def expand(self):
		""" Clean up a filename by calling expandvars() and expanduser()

		This is commonly everything needed to clean up a filename
		read from a configuration file, for example.
		
		If you are not interested in trailing slashes, you should call
		normpath() on the resulting Path as well.
		"""
		return self.expandvars().expanduser()

	def containsvars( self ):
		""":return: True if this path contains environment variables"""
		return self.find( '$' ) != -1
		
	def expand_or_raise(self):
		""":return: Copy of self with all variables expanded ( using `expand` )
		
		:raise ValueError: If we could not expand all environment variables as
			their values where missing in the environment"""
		rval = self.expand()
		if rval.containsvars():
			raise ValueError("Failed to expand all environment variables in %r, got %r" % (self, rval))
		return rval

	def namebase(self):
		"""The same as path.basename(), but with one file extension stripped off.

		For example, path('/home/guido/python.tar.gz').name		== 'python.tar.gz',
		but			 path('/home/guido/python.tar.gz').namebase == 'python.tar'"""
		base, ext = os.path.splitext(self.basename())
		return base

	def ext(self):
		""" The file extension, for example '.py'. """
		f, ext = os.path.splitext(_base(self))
		return ext

	def drive(self):
		""" The drive specifier, for example 'C:'.
		This is always empty on systems that don't use drive specifiers.
		"""
		drive, r = os.path.splitdrive(self)
		return self.__class__(drive)

	def splitpath(self):
		""" p.splitpath() -> Return (p.parent(), p.basename()). """
		parent, child = os.path.split(self)
		return self.__class__(parent), child

	def splitdrive(self):
		""" p.splitdrive() -> Return (p.drive, <the rest of p>).

		Split the drive specifier from this path.  If there is
		no drive specifier, p.drive is empty, so the return value
		is simply (path(''), p).  This is always the case on Unix.
		"""
		drive, rel = os.path.splitdrive(self)
		return self.__class__(drive), rel

	def splitext(self):
		""" p.splitext() -> Return (p.stripext(), p.ext).

		Split the filename extension from this path and return
		the two parts.	Either part may be empty.

		The extension is everything from '.' to the end of the
		last path segment.	This has the property that if
		(a, b) == p.splitext(), then a + b == p.
		"""
		filename, ext = os.path.splitext(self)
		return self.__class__(filename), ext

	def stripext(self):
		""" p.stripext() -> Remove one file extension from the path.

		For example, path('/home/guido/python.tar.gz').stripext()
		returns path('/home/guido/python.tar').
		"""
		return self.splitext()[0]

	if hasattr(os.path, 'splitunc'):
		def splitunc(self):
			unc, rest = os.path.splitunc(self)
			return self.__class__(unc), rest

		def isunshared(self):
			unc, r = os.path.splitunc(self)
			return self.__class__(unc)

	def joinpath(self, *args):
		""" Join two or more path components, adding a separator
		character (os.sep) if needed.  Returns a new path
		object. """
		return self.__class__(os.path.join(self, *args))

	def splitall(self):
		""" Return a list of the path components in this path.

		The first item in the list will be a path.	Its value will be
		either os.curdir, os.pardir, empty, or the root directory of
		this path (for example, '/' or 'C:\\').	 The other items in
		the list will be strings.

		path.path.joinpath(\*result) will yield the original path.
		"""
		parts = []
		loc = self
		while loc != os.curdir and loc != os.pardir:
			prev = loc
			loc, child = prev.splitpath()
			if loc == prev:
				break
			parts.append(child)
		parts.append(loc)
		parts.reverse()
		return parts

	def relpath(self):
		""" Return this path as a relative path,
		originating from the current working directory.
		"""
		return self.relpathto(os.getcwd())

	def relpathto(self, dest):
		""" Return a relative path from self to dest.

		If there is no relative path from self to dest, for example if
		they reside on different drives in Windows, then this returns
		dest.abspath().
		"""
		def commonprefix(m):
			if not m: return ''
			s1 = min(m)
			s2 = max(m)
			for i, c in enumerate(s1):
				if c != s2[i]:
					return s1[:i]
			return s1
		# END common prefix 
		
		start_list = os.path.abspath(dest).split(os.sep)
		path_list = os.path.abspath(self._expandvars()).split(os.sep)
		
		# Work out how much of the filepath is shared by start and path.
		i = len(commonprefix([start_list, path_list]))
	
		rel_list = [os.pardir] * (len(start_list)-i) + path_list[i:]
		if not rel_list:
			return os.curdir
		return self.__class__(os.path.join(*rel_list))
		
	def relpathfrom(self, dest):
		""" Return a relative path from dest to self"""
		return self.__class__(dest).relpathto(self)

	def tonative( self ):
		r"""Convert the path separator to the type required by the current operating
		system - on windows / becomes \ and on linux \ becomes /
		
		:return: native version of self"""
		s = "\\"
		d = "/"
		if sys.platform.startswith( "win" ):
			s = "/"
			d = "\\"
		return Path( self.replace( s, d ) )

	#} END Operations on path strings

	#{ Listing, searching, walking, and matching

	def listdir(self, pattern=None):
		"""return list of items in this directory.

		Use D.files() or D.dirs() instead if you want a listing
		of just files or just subdirectories.

		The elements of the list are path objects.

		With the optional 'pattern' argument, this only lists
		items whose names match the given pattern.
		"""
		names = os.listdir(self._expandvars())
		if pattern is not None:
			names = fnmatch.filter(names, pattern)
		return [self / child for child in names]

	def dirs(self, pattern=None):
		""" D.dirs() -> List of this directory's subdirectories.

		The elements of the list are path objects.
		This does not walk recursively into subdirectories
		(but see path.walkdirs).

		With the optional ``pattern`` argument, this only lists
		directories whose names match the given pattern.  For
		example, d.dirs("build-\*").
		"""
		return [p for p in self.listdir(pattern) if p.isdir()]

	def files(self, pattern=None):
		""" D.files() -> List of the files in this directory.

		The elements of the list are path objects.
		This does not walk into subdirectories (see path.walkfiles).

		With the optional ``pattern`` argument, this only lists files
		whose names match the given pattern.  For example,
		d.files("\*.pyc").
		"""

		return [p for p in self.listdir(pattern) if p.isfile()]

	def walk(self, pattern=None, errors='strict', predicate=lambda p: True):
		"""create iterator over files and subdirs, recursively.

		The iterator yields path objects naming each child item of
		this directory and its descendants.

		It performs a depth-first traversal of the directory tree.
		Each directory is returned just before all its children.

		:param pattern: fnmatch compatible pattern or None
		:param errors: controls behavior when an
			error occurs.  The default is 'strict', which causes an
			exception.	The other allowed values are 'warn', which
			reports the error via log.warn(), and 'ignore'.
		:param predicate: returns True for each Path p to be yielded by iterator
		"""
		if errors not in ('strict', 'warn', 'ignore'):
			raise ValueError("invalid errors parameter")

		try:
			childList = self.listdir()
		except Exception:
			if errors == 'ignore':
				return
			elif errors == 'warn':
				log.warn(
					"Unable to list directory '%s': %s"
					% (self, sys.exc_info()[1]))
				childList = list()
			else:
				raise
			# END handle errors value
		# END listdir exception handling

		for child in childList:
			if ( pattern is None or child.fnmatch(pattern) ) and predicate(child):
				yield child
				
			try:
				isdir = child.isdir()
			except Exception:
				isdir = False
				if errors == 'ignore':
					pass
				elif errors == 'warn':
					log.warn(
						"Unable to access '%s': %s"
						% (child, sys.exc_info()[1]))
				else:
					raise
				# END handle errors value
			# END directory access exception handling
			
			if not isdir:
				continue
				
			for item in child.walk(pattern, errors, predicate):
				yield item
			# END for each item
		# END for each child in childlist

	def walkdirs(self, pattern=None, errors='strict', predicate=lambda p: True):
		""" D.walkdirs() -> iterator over subdirs, recursively.
		see `walk` for a parameter description """
		pred = lambda p: p.isdir() and predicate(p)
		return self.walk(pattern, errors, pred)

	def walkfiles(self, pattern=None, errors='strict', predicate=lambda p: True):
		""" D.walkfiles() -> iterator over files in D, recursively.
		see `walk` for a parameter description"""
		pred = lambda p: p.isfile() and predicate(p)
		return self.walk(pattern, errors, pred)
		
	def fnmatch(self, pattern):
		""" Return True if self.basename() matches the given pattern.

		pattern - A filename pattern with wildcards,
			for example "\*.py".
		"""
		pathexpanded = self.expandvars()
		return fnmatch.fnmatch(pathexpanded.basename(), pattern)

	def glob(self, pattern):
		""" Return a list of path objects that match the pattern.

		pattern - a path relative to this directory, with wildcards.

		For example, path('/users').glob('*/bin/*') returns a list
		of all the files users have in their bin directories.
		"""
		cls = self.__class__
		pathexpanded = self.expandvars()
		return [cls(s) for s in glob.glob(_base(pathexpanded / pattern))]

	#} END Listing, searching, walking and watching


	#{ Reading or writing an entire file at once

	def open(self, *args, **kwargs):
		""" Open this file.	 Return a file object. """
		return open(self._expandvars(), *args, **kwargs)

	def bytes(self):
		""" Open this file, read all bytes, return them as a string. """
		f = self.open('rb')
		try:
			return f.read()
		finally:
			f.close()

	def write_bytes(self, bytes, append=False):
		""" Open this file and write the given bytes to it.

		Default behavior is to overwrite any existing file.
		Call p.write_bytes(bytes, append=True) to append instead.
		:return: self
		"""
		if append:
			mode = 'ab'
		else:
			mode = 'wb'
		f = self.open(mode)
		try:
			f.write(bytes)
		finally:
			f.close()
			
		return self

	def text(self, encoding=None, errors='strict'):
		r""" Open this file, read it in, return the content as a string.

		This uses "U" mode in Python 2.3 and later, so "\r\n" and "\r"
		are automatically translated to '\n'.

		Optional arguments:
		 * encoding - The Unicode encoding (or character set) of
		   the file.  If present, the content of the file is
		   decoded and returned as a unicode object; otherwise
		   it is returned as an 8-bit str.
		 * errors - How to handle Unicode errors; see help(str.decode)
		   for the options.  Default is 'strict'.
		"""
		mode = 'U'	# we are in python 2.4 at least
		
		f = None
		if encoding is None:
			f = self.open(mode)
		else:
			f = codecs.open(self, 'r', encoding, errors)
		# END handle encoding
		
		try:
			return f.read()
		finally:
			f.close()
		# END handle file read

	def write_text(self, text, encoding=None, errors='strict', linesep=os.linesep, append=False):
		r""" Write the given text to this file.

		The default behavior is to overwrite any existing file;
		to append instead, use the 'append=True' keyword argument.

		There are two differences between path.write_text() and
		path.write_bytes(): newline handling and Unicode handling.
		See below.

		**Parameters**:
		  - text - str/unicode - The text to be written.

		  - encoding - str - The Unicode encoding that will be used.
			This is ignored if 'text' isn't a Unicode string.

		  - errors - str - How to handle Unicode encoding errors.
			Default is 'strict'.  See help(unicode.encode) for the
			options.  This is ignored if 'text' isn't a Unicode
			string.

		  - linesep - keyword argument - str/unicode - The sequence of
			characters to be used to mark end-of-line.	The default is
			os.linesep.	 You can also specify None; this means to
			leave all newlines as they are in 'text'.

		  - append - keyword argument - bool - Specifies what to do if
			the file already exists (True: append to the end of it;
			False: overwrite it.)  The default is False.


		**Newline handling**:
		 - write_text() converts all standard end-of-line sequences
			("\n", "\r", and "\r\n") to your platforms default end-of-line
			sequence (see os.linesep; on Windows, for example, the
			end-of-line marker is "\r\n").
	
		 - If you don't like your platform's default, you can override it
			using the "linesep=" keyword argument.	If you specifically want
			write_text() to preserve the newlines as-is, use "linesep=None".
	
		 - This applies to Unicode text the same as to 8-bit text, except
			there are additional standard Unicode end-of-line sequences, check 
			the code to see them.
	
		 - (This is slightly different from when you open a file for
			writing with fopen(filename, "w") in C or file(filename, "w")
			in Python.)


		**Unicode**:
			If "text" isn't Unicode, then apart from newline handling, the
			bytes are written verbatim to the file.	 The "encoding" and
			'errors' arguments are not used and must be omitted.
	
			If 'text' is Unicode, it is first converted to bytes using the
			specified 'encoding' (or the default encoding if 'encoding'
			isn't specified).  The 'errors' argument applies only to this
			conversion.
		
		:return: self
		"""
		bytes = ""
		if isinstance(text, unicode):
			if linesep is not None:
				# Convert all standard end-of-line sequences to
				# ordinary newline characters.
				text = (text.replace(u'\r\n', u'\n')
							.replace(u'\r\x85', u'\n')
							.replace(u'\r', u'\n')
							.replace(u'\x85', u'\n')
							.replace(u'\u2028', u'\n'))
				text = text.replace(u'\n', linesep)
			if encoding is None:
				encoding = sys.getdefaultencoding()
			bytes = text.encode(encoding, errors)
		else:
			# It is an error to specify an encoding if 'text' is
			# an 8-bit string.
			assert encoding is None

			if linesep is not None:
				text = (text.replace('\r\n', '\n')
							.replace('\r', '\n'))
				bytes = text.replace('\n', linesep)

		self.write_bytes(bytes, append)
		return self

	def write_lines(self, lines, encoding=None, errors='strict',
					linesep=os.linesep, append=False):
		r""" Write the given lines of text to this file.

		By default this overwrites any existing file at this path.

		This puts a platform-specific newline sequence on every line.
		See 'linesep' below.

		lines - A list of strings.

		encoding - A Unicode encoding to use.  This applies only if
			'lines' contains any Unicode strings.

		errors - How to handle errors in Unicode encoding.	This
			also applies only to Unicode strings.

		linesep - The desired line-ending.	This line-ending is
			applied to every line.	If a line already has any
			standard line ending, that will be stripped off and
			this will be used instead.	The default is os.linesep,
			which is platform-dependent ('\r\n' on Windows, '\n' on
			Unix, etc.)	 Specify None to write the lines as-is,
			like file.writelines().

		Use the keyword argument append=True to append lines to the
		file.  The default is to overwrite the file.  Warning:
		When you use this with Unicode data, if the encoding of the
		existing data in the file is different from the encoding
		you specify with the encoding= parameter, the result is
		mixed-encoding data, which can really confuse someone trying
		to read the file later.
		
		:return: self
		"""
		if append:
			mode = 'ab'
		else:
			mode = 'wb'
		f = self.open(mode)
		try:
			for line in lines:
				isUnicode = isinstance(line, unicode)
				if linesep is not None:
					# Strip off any existing line-end and add the
					# specified linesep string.
					if isUnicode:
						if line[-2:] in (u'\r\n', u'\x0d\x85'):
							line = line[:-2]
						elif line[-1:] in (u'\r', u'\n',
										   u'\x85', u'\u2028'):
							line = line[:-1]
					else:
						if line[-2:] == '\r\n':
							line = line[:-2]
						elif line[-1:] in ('\r', '\n'):
							line = line[:-1]
					line += linesep
				if isUnicode:
					if encoding is None:
						encoding = sys.getdefaultencoding()
					line = line.encode(encoding, errors)
				f.write(line)
		finally:
			f.close()
			
		return self

	def lines(self, encoding=None, errors='strict', retain=True):
		r""" Open this file, read all lines, return them in a list.

		Optional arguments:
			 * encoding: The Unicode encoding (or character set) of
				the file.  The default is None, meaning the content
				of the file is read as 8-bit characters and returned
				as a list of (non-Unicode) str objects.
				
			 * errors: How to handle Unicode errors; see help(str.decode)
				for the options.  Default is 'strict'
				
			 * retain: If true, retain newline characters; but all newline
				character combinations ("\r", "\n", "\r\n") are
				translated to "\n".	 If false, newline characters are
				stripped off.  Default is True.
		
		This uses "U" mode in Python 2.3 and later.
		"""
		if encoding is None and retain:
			f = self.open(_textmode)
			try:
				return f.readlines()
			finally:
				f.close()
		else:
			return self.text(encoding, errors).splitlines(retain)

	def digest(self, hashobject):
		""" Calculate the  hash for this file using the given hashobject. It must 
		support the 'update' and 'digest' methods.

		:note: This reads through the entire file.
		"""

		f = self.open('rb')
		try:
			while True:
				d = f.read(8192)
				if not d:
					break
				hashobject.update(d)
		finally:
			f.close()
		# END assure file gets closed
		
		return hashobject.digest()

	#} END Reading or writing an enitre file at once

	#{ Methods for querying the filesystem

	exists = lambda self: os.path.exists( self._expandvars() )
	if hasattr(os.path, 'lexists'):
		lexists = lambda self: os.path.lexists( self._expandvars() )
	isdir = lambda self: os.path.isdir( self._expandvars() )
	isfile = lambda self: os.path.isfile( self._expandvars() )
	islink = lambda self: os.path.islink( self._expandvars() )
	ismount = lambda self: os.path.ismount( self._expandvars() )

	if hasattr(os.path, 'samefile'):
		samefile = lambda self, other: os.path.samefile( self._expandvars(), other )

	atime = lambda self: os.path.getatime( self._expandvars() )
	mtime = lambda self: os.path.getmtime( self._expandvars() )
	if hasattr(os.path, 'getctime'):
		ctime = lambda self: os.path.getctime( self._expandvars() )
	size = lambda self: os.path.getsize( self._expandvars() )

	if hasattr(os, 'access'):
		def access(self, mode):
			""" Return true if current user has access to this path.

			mode - One of the constants os.F_OK, os.R_OK, os.W_OK, os.X_OK
			"""
			return os.access(self._expandvars(), mode)

	def stat(self):
		""" Perform a stat() system call on this path. """
		return os.stat(self._expandvars())

	def lstat(self):
		""" Like path.stat(), but do not follow symbolic links. """
		return os.lstat(self._expandvars())

	def owner(self):
		""" Return the name of the owner of this file or directory.

		This follows symbolic links.

		On Windows, this returns a name of the form ur'DOMAIN\User Name'.
		On Windows, a group can own a file or directory.
		"""
		if os.name == 'nt':
			if win32security is None:
				raise Exception("path.owner requires win32all to be installed")
			desc = win32security.GetFileSecurity(
				self, win32security.OWNER_SECURITY_INFORMATION)
			sid = desc.GetSecurityDescriptorOwner()
			account, domain, typecode = win32security.LookupAccountSid(None, sid)
			return domain + u'\\' + account
		else:
			if pwd is None:
				raise NotImplementedError("path.owner is not implemented on this platform.")
			st = self.stat()
			return pwd.getpwuid(st.st_uid).pw_name

	if hasattr(os, 'statvfs'):
		def statvfs(self):
			""" Perform a statvfs() system call on this path. """
			return os.statvfs(self._expandvars())

	if hasattr(os, 'pathconf'):
		def pathconf(self, name):
			"""see os.pathconf"""
			return os.pathconf(self._expandvars(), name)

	def isWritable( self ):
		""":return: true if the file can be written to"""
		if not self.exists():
			return False		# assure we do not create anything not already there

		try:
			fileobj = self.open( 'a' )
		except:
			return False
		else:
			fileobj.close()
			return True
		# END handle file open


	#} END Methods for querying the filesystem

	#{ Modifying operations on files and directories

	def setutime(self, times):
		""" Set the access and modified times of this file.
		
		:return: self"""
		os.utime(self._expandvars(), times)
		return self

	def chmod(self, mode):
		"""Change file mode
		
		:return: self"""
		os.chmod(self._expandvars(), mode)
		return self

	if hasattr(os, 'chown'):
		def chown(self, uid, gid):
			"""Change file ownership
			
			:return: self"""
			os.chown(self._expandvars(), uid, gid)
			return self

	def rename(self, new):
		"""os.rename
		
		:return: Path to new file"""
		os.rename(self._expandvars(), new)
		return type(self)(new)

	def renames(self, new):
		"""os.renames, super rename
		
		:return: Path to new file"""
		os.renames(self._expandvars(), new)
		return type(self)(new)

	#} END Modifying operations on files and directories

	#{ Create/delete operations on directories

	def mkdir(self, mode=0777):
		"""Make this directory, fail if it already exists
		
		:return: self"""
		os.mkdir(self._expandvars(), mode)
		return self

	def makedirs(self, mode=0777):
		"""Smarter makedir, see os.makedirs
		
		:return: self"""
		os.makedirs(self._expandvars(), mode)
		return self

	def rmdir(self):
		"""Remove this empty directory
		
		:return: self"""
		os.rmdir(self._expandvars())
		return self

	def removedirs(self):
		"""see os.removedirs
		
		:return: self"""
		os.removedirs(self._expandvars())
		return self

	#} END Create/delete operations on directories

	#{ Modifying operations on files

	def touch(self, flags = os.O_WRONLY | os.O_CREAT, mode = 0666):
		""" Set the access/modified times of this file to the current time.
		Create the file if it does not exist.
		
		:return: self
		"""
		fd = os.open(self._expandvars(), flags, mode)
		os.close(fd)
		os.utime(self._expandvars(), None)
		return self

	def remove(self):
		"""Remove this file
		
		:return: self"""
		os.remove(self._expandvars())
		return self

	def unlink(self):
		"""unlink this file
		
		:return: self"""
		os.unlink(self._expandvars())
		return self

	#} END Modifying operations on files

	#{ Links

	if hasattr(os, 'link'):
		def link(self, newpath):
			""" Create a hard link at 'newpath', pointing to this file. 
			
			:return: Path to newpath"""
			os.link(self._expandvars(), newpath)
			return type(self)(newpath)
			

	if hasattr(os, 'symlink'):
		def symlink(self, newlink):
			""" Create a symbolic link at 'newlink', pointing here. 
			
			:return: Path to newlink"""
			os.symlink(self._expandvars(), newlink)
			return type(self)(newlink)

	if hasattr(os, 'readlink'):
		def readlink(self):
			""" Return the path to which this symbolic link points.

			The result may be an absolute or a relative path.
			"""
			return self.__class__(os.readlink(self._expandvars()))

		def readlinkabs(self):
			""" Return the path to which this symbolic link points.

			The result is always an absolute path.
			"""
			p = self.readlink()
			if p.isabs():
				return p
			else:
				return (self.parent() / p).abspath()

	#} END Links

	#{ High-level functions from shutil

	def copyfile(self, dest):
		"""Copy self to dest
		
		:return: Path to dest"""
		shutil.copyfile( self._expandvars(), dest )
		return type(self)(dest)
	
	def copymode(self, dest):
		"""Copy our mode to dest
		
		:return: Path to dest"""
		shutil.copymode( self._expandvars(), dest )
		return type(self)(dest)
		
	def copystat(self, dest):
		"""Copy our stats to dest
		
		:return: Path to dest"""
		shutil.copystat( self._expandvars(), dest )
		return type(self)(dest)
		
	def copy(self, dest):
		"""Copy data and source bits to dest
		
		:return: Path to dest"""
		shutil.copy( self._expandvars(), dest )
		return type(self)(dest)
	
	def copy2(self, dest):
		"""Shutil.copy2 self to dest
		
		:return: Path to dest"""
		shutil.copy2( self._expandvars(), dest )
		return type(self)(dest)
		
	def copytree(self, dest, **kwargs):
		"""Deep copy this file or directory to destination
		
		:param kwargs: passed to shutil.copytree
		:return: Path to dest"""
		shutil.copytree( self._expandvars(), dest, **kwargs )
		return type(self)(dest)
		
	if hasattr(shutil, 'move'):
		def move(self, dest):
			"""Move self to dest
			
			:return: Path to dest"""
			shutil.move( self._expandvars(), dest )
			return type(self)(dest)
			
	def rmtree(self, **kwargs):
		"""Remove self recursively
		
		:param kwargs: passed to shutil.rmtree
		:return: self"""
		shutil.rmtree( self._expandvars(),  **kwargs )
		return self
			
	#} END High-Level


	#{ Special stuff from os
	if hasattr(os, 'chroot'):
		def chroot(self):
			"""Change the root directory path
			
			:return: self"""
			os.chroot(self._expandvars())
			return self

	if hasattr(os, 'startfile'):
		def startfile(self):
			"""see os.startfile
			
			:return: self"""
			os.startfile(self._expandvars())
			return self
	#} END Special stuff from os
