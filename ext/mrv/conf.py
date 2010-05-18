# -*- coding: utf-8 -*-
"""
Contains implementation of the configuration system allowing to flexibly control
the programs behaviour.

 * read and write sections with key=value pairs from and to INI style file-like objects !
 * Wrappers for these file-like objects allow virtually any source for the operation
 * configuration inheritance
 * allow precise control over the inheritance behaviour and inheritance
   defaults
 * final results of the inheritance operation will be cached into the `ConfigManager`
 * Environment Variables can serve as final instance to override values using the `DictConfigINIFile`
 * Creation and Maintenance of individual configuration files as controlled by
   submodules of the application
 * These configuration go to a default location, or to the given file-like object
 * embed more complex data to be read by specialised classes using URLs
 * its safe and easy to write back possibly altered values even if complex inheritance
   schemes are applied
"""
__docformat__ = "restructuredtext"

from ConfigParser import (	RawConfigParser,
							NoSectionError,
							NoOptionError,
							ParsingError)
from exc import MRVError
import copy
import re
import sys
import StringIO
import os
import logging
log = logging.getLogger("mrv.conf")

__all__ = ("ConfigParsingError", "ConfigParsingPropertyError", "DictToINIFile", 
           "ConfigAccessor", "ConfigManager", "ExtendedFileInterface", "ConfigFile", 
           "DictConfigINIFile", "ConfigStringIO", "ConfigChain", "BasicSet", 
           "Key", "Section", "PropertySection", "ConfigNode", "DiffData", 
           "DiffKey", "DiffSection", "ConfigDiffer")

#{ Exceptions
################################################################################
class ConfigParsingError( MRVError ):
	""" Indicates that the parsing failed """
	pass

class ConfigParsingPropertyError( ConfigParsingError ):
	""" Indicates that the property-parsing encountered a problem """
	pass
#} End Exceptions




#{ INI File Converters
################################################################################
# Wrap arbitary sources and implicitly convert them to INI files when read
class DictToINIFile( StringIO.StringIO ):
	""" Wraps a dictionary into an objects returning an INI file when read

	This class can be used to make configuration information as supplied by os.environ
	natively available to the configuration system

	:note: writing back values to the object will not alter the original dict
	:note: the current implementation caches the dict's INI representation, data
		is not generated on demand
	
	:note: implementation speed has been preferred over runtime speed """
	@classmethod
	def _checkstr( cls, string ):
		"""
		:return: unaltered string if there was not issue
		:raise ValueError: if string contains newline """
		if string.find( '\n' ) != -1:
			raise ValueError( "Strings in INI files may not contain newline characters: %s" % string )
		return string

	def __init__( self, option_dict, section = 'DEFAULT', description = "" ):
		"""Initialize the file-like object
		
		:param option_dict: dictionary with simple key-value pairs - the keys and
			values must translate to meaningful strings ! Empty dicts are allowed
			
		:param section: the parent section of the key-value pairs
		:param description: will be used as comment directly below the section, it
			must be a single line only

		:raise ValueError: newlines are are generally not allowed and will cause a parsing error later on """
		StringIO.StringIO.__init__( self )

		self.write( '[' + str(section) + ']\n' )
		if len(description):
			self.write( '#'+ self._checkstr( description ) + "\n" )
		for k in option_dict:
			self.write( str(k) + " = " + str( option_dict[k] ) + "\n" )

		# reset the file to the beginning
		self.seek( 0 )


#} END GROUP


#{ Configuration Access
################################################################################
# Classes that allow direct access to the respective configuration

class ConfigAccessor( object ):
	"""Provides full access to the Configuration

	**Differences to ConfigParser**:
		As the functionality and featureset is very different from the original
		ConfigParser implementation, this class does not support the interface directly.
		It contains functions to create original ConfigParser able to fully write and alter
		the contained data in an unchecked manner.

		Additional Exceptions have been defined to cover extended functionality.

	**Sources and Nodes**:
		Each input providing configuration data is stored in a node. This node
		knows about its writable state. Nodes that are not writable can be altered in memory,
		but the changes cannot be written back to the source.
		This does not impose a problem though as changes will be applied as long as there is
		one writable node in the chain - due to the inheritance scheme applied by the configmanager,
		the final configuration result will match the changes applied at runtime.

	**Additional Information**:
		The term configuration is rather complex though
		configuration is based on an extended INI file format
		its not fully compatible, but slightly more narrow regarding allowed input to support extended functionality
		configuration is read from file-like objects
		a list of file-like objects creates a configuration chain
		keys have properties attached to them defining how they behave when being overridden
		once all the INI configurations have been read and processed, one can access
		the configuration as if it was just in one file.
		Direct access is obtained though `Key` and `Section` objects
		Keys and Sections have property attributes of type `Section`
		Their keys and values are used to further define key merging behaviour for example
		
	:note: The configaccessor should only be used in conjunction with the `ConfigManager`"""
	__slots__ = "_configChain"

	def __init__( self ):
		""" Initialize instance variables """
		self._configChain = ConfigChain( )  # keeps configuration from different sources

	def __repr__( self ):
		stream = ConfigStringIO()
		fca = self.flatten( stream )
		fca.write( close_fp = False )
		return stream.getvalue()

	@classmethod
	def _isProperty( cls, propname ):
		""":return: true if propname appears to be an attribute """
		return propname.startswith( '+' )

	@classmethod
	def _getNameTuple( cls, propname ):
		""":return: [sectionname,keyname], sectionname can be None"""
		tokens = propname[1:].split( ':' )	# cut initial + sign

		if len( tokens ) == 1:		# no fully qualified name
			tokens.insert( 0, None )
		return tokens

	def _parseProperties( self ):
		"""Analyse the freshly parsed configuration chain and add the found properties
		to the respective sections and keys

		:note: we are userfriendly regarding the error handling - if there is an invlid
			property, we warn and simply ignore it - for the system it will stay just a key and will
			thus be written back to the file as required
		
		:raise ConfigParsingPropertyError: """
		sectioniter = self._configChain.sectionIterator()
		exc = ConfigParsingPropertyError( )
		for section in sectioniter:
			if not self._isProperty( section.name ):
				continue

			# handle attributes
			propname = section.name
			targetkeytokens = self._getNameTuple( propname ) # fully qualified property name

			# find all keys matching the keyname !
			keymatchtuples = self.keysByName( targetkeytokens[1] )

			# SEARCH FOR KEYS primarily !
			propertytarget = None		# will later be key or section
			lenmatch = len( keymatchtuples )
			excmessage = ""				# keeps exc messages until we know whether to keep them or not

			if lenmatch == 0:
				excmessage += "Key '" + propname + "' referenced by property was not found\n"
				# continue searching in sections
			else:
				# here it must be a key - failure leads to continuation
				if targetkeytokens[0] != None:
					# search the key matches for the right section
					for fkey,fsection in keymatchtuples:
						if not fsection.name == targetkeytokens[0]: continue
						else: propertytarget = fkey

					if propertytarget is None:
						exc.message += ( "Section '" + targetkeytokens[0] + "' of key '" + targetkeytokens[1] +
										"' could not be found in " + str(lenmatch) + " candiate sections\n" )
						continue
				else:
					# section is not qualified - could be section or keyname
					# prefer keynames
					if lenmatch == 1:
						propertytarget = keymatchtuples[0][0]	# [ (key,section) ]
					else:
						excmessage += "Key for property section named '" + propname + "' was found in " + str(lenmatch) + " sections and needs to be qualified as in: 'sectionname:"+propname+"'\n"
						# continue searching - perhaps we find a section that fits perfectly


			# could be a section property
			if propertytarget is None:
				try:
					propertytarget = self.section( targetkeytokens[1] )
				except NoSectionError:
					# nothing found - skip it
					excmessage += "Property '" + propname + "' references unknown section or key\n"

			# safety check
			if propertytarget is None:
				exc.message += excmessage
				continue

			propertytarget.properties.mergeWith( section )

		# finally raise our report-exception if required
		if len( exc.message ):
			raise exc


	#{ IO Interface
	def readfp( self, filefporlist, close_fp = True ):
		""" Read the configuration from the file like object(s) representing INI files.
		
		:note: This will overwrite and discard all existing configuration.
		:param filefporlist: single file like object or list of such
		
		:param close_fp: if True, the file-like object will be closed before the method returns,
			but only for file-like objects that have actually been processed

		:raise ConfigParsingError: """
		fileobjectlist = filefporlist
		if not isinstance( fileobjectlist, (list,tuple) ):
			fileobjectlist = ( filefporlist, )

		# create one parser per file, append information to our configuration chain
		tmpchain = ConfigChain( )			# to be stored later if we do not have an exception

		for fp in fileobjectlist:
			try:
				node = ConfigNode( fp )
				tmpchain.append( node )
				node.parse()
			finally:
				if close_fp:
					fp.close()

		# keep the chain - no error so far
		self._configChain = tmpchain

		try:
			self._parseProperties( )
		except ConfigParsingPropertyError:
			self._configChain = ConfigChain()	# undo changes and reraise
			raise

	def write( self, close_fp=True ):
		""" Write current state back to files.
			During initialization in `readfp`, `ExtendedFileInterface` objects have been passed in - these
			will now be used to write back the current state of the configuration - the files will be
			opened for writing if possible.

		:param close_fp: close the file-object after writing to it
		
		:return: list of names of files that have actually been written - as files can be read-only
			this list might be smaller than the amount of nodes in the accessor.
		"""
		writtenFiles = list()

		# for each node put the information into the parser and write to the node's
		# file object after assuring it is opened
		for cn in self._configChain:
			try:
				writtenFiles.append( cn.write( _FixedConfigParser(), close_fp=close_fp ) )
			except IOError:
				pass

		return writtenFiles

	#} END GROUP


	#{Transformations
	def flatten( self, fp ):
		"""Copy all our members into a new ConfigAccessor which only has one node, instead of N nodes

		By default, a configuration can be made up of several different sources that create a chain.
		Each source can redefine and alter values previously defined by other sources.

		A flattened chain though does only conist of one of such node containing concrete values that
		can quickly be accessed.

		Flattened configurations are provided by the `ConfigManager`.
		
		:param fp: file-like object that will be used as storage once the configuration is written
		:return: Flattened copy of self"""
		# create config node
		ca = ConfigAccessor( )
		ca._configChain.append( ConfigNode( fp ) )
		cn = ca._configChain[0]

		# transfer copies of sections and keys - requires knowledge of internal
		# data strudctures
		count = 0
		for mycn in self._configChain:
			for mysection in mycn._sections:
				section = cn.sectionDefault( mysection.name )
				section.order = count
				count += 1
				section.mergeWith( mysection )
		return ca

	#} END GROUP

	#{ Iterators
	def sectionIterator( self ):
		""":return: iterator returning all sections"""
		return self._configChain.sectionIterator()

	def keyIterator( self ):
		""":return: iterator returning tuples of (`Key`,`Section`) pairs"""
		return self._configChain.keyIterator()

	#} END GROUP

	#{ Utitlities
	def isEmpty( self ):
		""":return: True if the accessor does not stor information"""
		if not self._configChain:
			return True
			
		for node in self._configChain:
			if node.listSections():
				return False
		# END for each node 
		return True
		
	#} END GROUP 

	#{ General Access ( disregarding writable state )
	def hasSection( self, name ):
		""":return: True if the given section exists"""
		try:
			self.section( name )
		except NoSectionError:
			return False

		return True

	def section( self, section ):
		""" :return: first section with name
		:note: as there might be several nodes defining the section for inheritance,
			you might not get the desired results unless this config accessor acts on a
			`flatten` ed list.
			
		:raise NoSectionError: if the requested section name does not exist """
		for node in self._configChain:
			if section in node._sections:
				return node.section( section )

		raise NoSectionError( section )

	def keyDefault( self, sectionname, keyname, value ):
		"""Convenience Function: get key with keyname in first section with sectionname with the key's value being initialized to value if it did not exist.
		
		:param sectionname: the name of the sectionname the key is supposed to be in - it will be created if needed
		:param keyname: the name of the key you wish to find
		:param value: the value you wish to receive as as default if the key has to be created.
			It can be a list of values as well, basically anything that `Key` allows as value
			
		:return: `Key`"""
		return self.sectionDefault( sectionname ).keyDefault(keyname, value )[0]

	def keysByName( self, name ):
		""":param name: the name of the key you wish to find
		:return: List of  (`Key`,`Section`) tuples of key(s) matching name found in section, or empty list"""
		return list( self.iterateKeysByName( name ) )

	def iterateKeysByName( self, name ):
		"""As `keysByName`, but returns an iterator instead"""
		return self._configChain.iterateKeysByName( name )
		
	def get( self, key_id, default = None ):
		"""Convenience function allowing to easily specify the key you wish to retrieve
		with the option to provide a default value
		
		:param key_id: string specifying a key, either as ``sectionname.keyname``
			or ``keyname``.
			In case you specify a section, the key must reside in the given section, 
			if only a keyname is given, it may reside in any section
			
		:param default: Default value to be given to a newly created key in case 
			there is no existing value. If None, the method may raise in case the given
			key_id does not exist.
			
		:return: `Key` instance whose value may be queried through its ``value`` or 
			``values`` attributes"""
		sid = None
		kid = key_id
		if '.' in key_id:
			sid, kid = key_id.split('.', 1)
		# END split key id into section and key
		
		if sid is None:
			keys = self.keysByName(kid)
			try:
				return keys[0][0]
			except IndexError:
				if default is None:
					raise NoOptionError(kid, sid)
				else:
					for section in self.sectionIterator():
						return section.keyDefault(kid, default)[0]
					# create default section 
					return self.sectionDefault('default').keyDefault(kid, default)[0]
				# END default handling
			# END option exception handling
		else:
			if default is None:
				return self.section(sid).key(kid)
			else:
				return self.keyDefault(sid, kid, default)
			# END default handling 
		# END has section handling
		
		
	#} END GROUP

	#{ Operators
	def __getitem__( self, key ):
		defaultvalue = None
		if isinstance( key, tuple ):
			defaultvalue = key[1]
			key = key[0]
		# END default value handling
		
		return self.get(key, defaultvalue)

	#} END GROUP


	#{ Structure Adjustments Respecting Writable State
	def sectionDefault( self, section ):
		""":return: section with given name.
		:raise IOError: If section does not exist and it cannot be created as the configuration is readonly
		:note: the section will be created if it does not yet exist
		"""
		try:
			return self.section( section )
		except:
			pass

		# find the first writable node and create the section there
		for node in self._configChain:
			if node.writable:
				return node.sectionDefault( section )

		# we did not find any writable node - fail
		raise IOError( "Could not find a single writable configuration file" )

	def removeSection( 	self, name ):
		"""Completely remove the given section name from all nodes in our configuration
		
		:return: the number of nodes that did *not* allow the section to be removed as they are read-only, thus
			0 will be returned if everything was alright"""
		numReadonly = 0
		for node in self._configChain:
			if not node.hasSection( name ):
				continue

			# can we write it ?
			if not node._isWritable( ):
				numReadonly += 1
				continue

			node._sections.remove( name )

		return numReadonly


	def mergeSection( self, section ):
		"""Merge and/or add the given section into our chain of nodes. The first writable node will be used
		
		:raise IOError: if no writable node was found
		:return: name of the file source that has received the section"""
		for node in self._configChain:
			if node._isWritable():
				node.sectionDefault( str( section ) ).mergeWith( section )
				return node._fp.name( )

		raise IOError( "No writable section found for merge operation" )


	#} END GROUP


class ConfigManager( object ):
	""" Cache Configurations for fast access and provide a convenient interface

	The the ConfigAccessor has limited speed due to the hierarchical nature of 
	configuration chains.
	The config manager flattens the chain providing fast access. Once it is being
	deleted or if asked, it will find the differences between the fast cached
	configuration and the original one, and apply the changes back to the original chain,
	which will then write the changes back ( if possible ).

	This class should be preferred over the direct congiguration accessor.
	This class mimics the ConfigAccessor inteface as far as possible to improve ease of use.
	Use self.config to directly access the configuration through the `ConfigAccessor` interface
	
	To use this class, read a list of ini files and use configManager.config to access
	the configuration.
	
	For convenience, it will wire through all calls it cannot handle to its `ConfigAccessor`
	stored at .config"""
	
	__slots__ = ( '__config', 'config', '_writeBackOnDestruction', '_closeFp' ) 

	def __init__( self, filePointers=list(), write_back_on_desctruction=True, close_fp = True ):
		"""Initialize the class with a list of Extended File Classes
		
		:param filePointers: Point to the actual configuration to use
			If not given, you have to call the `readfp` function with filePointers respectively
		:type filePointers: `ExtendedFileInterface`

		:param close_fp: if true, the files will be closed and can thus be changed.
			This should be the default as files might be located on the network as shared resource

		:param write_back_on_desctruction: if True, the config chain and possible
			changes will be written once this instance is being deleted. If false,
			the changes must explicitly be written back using the write method"""
		self.__config = ConfigAccessor( )
		self.config = None					# will be set later
		self._writeBackOnDestruction = write_back_on_desctruction
		self._closeFp = close_fp

		self.readfp( filePointers, close_fp=close_fp )


	def __del__( self ):
		""" If we are supposed to write back the configuration, after merging
		the differences back into the original configuration chain"""
		if self._writeBackOnDestruction:
			# might trow - python will automatically ignore these issues
			self.write( )

	def __getattr__( self, attr ):
		"""Wire all queries we cannot handle to our config accessor"""
		try:
			return getattr(self.config, attr)
		except Exception:
			return object.__getattribute__(self, attr)

	#{ IO Methods
	def write( self ):
		""" Write the possibly changed configuration back to its sources.
		
		:raise IOError: if at least one node could not be properly written.
		:raise ValueError: if instance is not properly initialized.
		
		:note: It could be the case that all nodes are marked read-only and
			thus cannot be written - this will also raise as the request to write
			the changes could not be accomodated.
		
		:return: the names of the files that have been written as string list"""
		if self.config is None:
			raise ValueError( "Internal configuration does not exist" )


		# apply the changes done to self.config to the original configuration
		try:
			diff = ConfigDiffer( self.__config, self.config )
			report = diff.applyTo( self.__config )
			outwrittenfiles = self.__config.write( close_fp = self._closeFp )
			return outwrittenfiles
		except Exception,e:
			log.error(str( e )) 
			raise
			# for now we reraise
			# TODO: raise a proper error here as mentioned in the docs
			# raise IOError()

	def readfp( self, filefporlist, close_fp=True ):
		""" Read the configuration from the file pointers.
		
		:raise ConfigParsingError:
		:param filefporlist: single file like object or list of such
		:return: the configuration that is meant to be used for accessing the configuration"""
		self.__config.readfp( filefporlist, close_fp = close_fp )

		# flatten the list and attach it
		self.config = self.__config.flatten( ConfigStringIO() )
		return self.config

	#} End IO Methods


	#{ Utilities
	@classmethod
	def taggedFileDescriptors( cls, directories, taglist, pattern=None ):
		"""Finds tagged configuration files in given directories and return them.
		
		The files retrieved can be files like "file.ext" or can contain tags. Tags are '.'
		separated files tags that are to be matched with the tags in taglist in order.

		All tags must match to retrieve a filepointer to the respective file.

		Example Usage: you could give two paths, one is a global one in a read-only location,
		another is a local one in the user's home ( where you might have precreated a file already ).

		The list of filepointers returned would be all matching files from the global path and
		all matching files from the local one, sorted such that the file with the smallest amount
		of tags come first, files with more tags ( more specialized ones ) will come after that.

		If fed into the `readfp` or the `__init__` method, the individual file contents can override each other.
		Once changes have been applied to the configuration, they can be written back to the writable
		file pointers respectively.

		:param directories: [ string( path ) ... ] of directories to look in for files
		:param taglist: [ string( tag ) ... ] of tags, like a tag for the operating system, or the user name
		:param pattern: simple fnmatch pattern as used for globs or a list of them ( allowing to match several
			different patterns at once )
		"""

		# get patterns
		workpatterns = list()
		if isinstance( pattern, ( list , set ) ):
			workpatterns.extend( pattern )
		else:
			workpatterns.append( pattern )


		# GET ALL FILES IN THE GIVEN DIRECTORIES
		########################################
		from path import Path
		matchedFiles = list()
		for folder in directories:
			for pattern in workpatterns:
				matchedFiles.extend( Path( folder ).files( pattern ) )
			# END for each pattern/glob 
		# END for each directory

		# APPLY THE PATTERN SEARCH
		############################
		tagMatchList = list()
		for taggedFile in sorted( matchedFiles ):
			filetags = os.path.split( taggedFile )[1].split( '.' )[1:-1]

			# match the tags - take the file if all can be found
			numMatched = 0
			for tag in taglist:
				if tag in filetags:
					numMatched += 1

			if numMatched == len( filetags ):
				tagMatchList.append( ( numMatched, taggedFile ) )

		# END for each tagged file

		outDescriptors = list()
		for numtags,taggedFile in sorted( tagMatchList ):
			outDescriptors.append( ConfigFile( taggedFile ) )	# just open for reading
		return outDescriptors

	#} end Utilities


#}END GROUP




#{Extended File Classes

class ExtendedFileInterface( object ):
	""" Define additional methods required by the Configuration System
	:warning: Additionally, readline and write must be supported - its not mentioned
	here for reasons of speed
	:note: override the methods with implementation"""
	__slots__ = tuple()

	def isWritable( self ):
		""":return: True if the file can be written to """
		raise False

	def isClosed( self ):
		""":return: True if the file has been closed, and needs to be reopened for writing """
		raise NotImplementedError

	def name( self ):
		""" :return: a name for the file object """
		raise NotImplementedError

	def openForWriting( self ):
		""" Open the file to write to it
		:raise IOError: on failure"""
		raise NotImplementedError


class ConfigFile( ExtendedFileInterface ):
	""" file object implementation of the ExtendedFileInterface"""
	__slots__ = [ '_writable', '_fp' ]

	def __init__( self, *args, **kwargs ):
		""" Initialize our caching values - additional values will be passed to 'file' constructor"""
		self._fp = file(*args, **kwargs)
		self._writable = self._isWritable()

	def __getattr__(self, attr):
		return getattr(self._fp, attr)

	def _modeSaysWritable( self ):
		return ( self._fp.mode.find( 'w' ) != -1 ) or ( self._fp.mode.find( 'a' ) != -1 )

	def _isWritable( self ):
		""" Check whether the file is effectively writable by opening it for writing
		:todo: evaluate the usage of stat instead - would be faster, but I do not know whether it works on NT with user rights etc."""
		if self._modeSaysWritable( ):
			return True

		wasClosed = self._fp.closed
		lastMode = self._fp.mode
		pos = self.tell()

		if not self._fp.closed:
			self.close()

		# open in write append mode
		rval = True
		try:
			self._fp = file(self._fp.name, "a")
		except IOError:
			rval = False

		# reset original state
		if wasClosed:
			self.close()
			self._fp.mode = lastMode
		else:
			# reopen with changed mode
			self._fp = file(self._fp.name, lastMode)
			self.seek( pos )
		# END check was closed

		return rval

	def isWritable( self ):
		""":return: True if the file is truly writable"""
		# return our cached value
		return self._writable

	def isClosed( self ):
		return self._fp.closed

	def name( self ):
		return self._fp.name

	def openForWriting( self ):
		if self._fp.closed or not self._modeSaysWritable():
			self._fp = file(self._fp.name, 'w')

		# update writable value cache
		self._writable = self._isWritable(  )

class DictConfigINIFile( DictToINIFile, ExtendedFileInterface ):
	""" dict file object implementation of ExtendedFileInterface """
	__slots__ = tuple()
	
	def isClosed( self ):
		return self.closed

	def name( self ):
		""" We do not have a real name """
		return 'DictConfigINIFile'

	def openForWriting( self ):
		""" We cannot be opened for writing, and are always read-only """
		raise IOError( "DictINIFiles do not support writing" )


class ConfigStringIO( StringIO.StringIO, ExtendedFileInterface ):
	""" cStringIO object implementation of ExtendedFileInterface """
	__slots__ = tuple()

	def isWritable( self ):
		""" Once we are closed, we are not writable anymore """
		return not self.closed

	def isClosed( self ):
		return self.closed

	def name( self ):
		""" We do not have a real name """
		return 'ConfigStringIO'

	def openForWriting( self ):
		""" We if we are closed already, there is no way to reopen us """
		if self.closed:
			raise IOError( "cStringIO instances cannot be written once closed" )

#} END extended file interface 


#{ Utility Classes

class _FixedConfigParser( RawConfigParser ):
	"""The RawConfigParser stores options lowercase - but we do not want that
	and keep the case - for this we just need to override a method"""
	__slots__ = tuple()
	
	def optionxform( self, option ):
		return option


class ConfigChain( list ):
	""" A chain of config nodes

	This utility class keeps several `ConfigNode` objects, but can be operated
	like any other list.

	:note: this solution is mainly fast to implement, but a linked-list like
		behaviour is intended """
	__slots__ = tuple()
	
	#{ List Overridden Methods
	def __init__( self ):
		""" Assures we can only create plain instances """
		list.__init__( self )

	@classmethod
	def _checktype( cls, node ):
		if not isinstance( node, ConfigNode ):
			raise TypeError( "A ConfigNode instance is required", node )


	def append( self, node ):
		""" Append a `ConfigNode` """
		self._checktype( node )
		list.append( self, node )


	def insert( self, node, index ):
		""" Insert L?{ConfigNode} before index """
		self._checktype( node )
		list.insert( self, node, index )

	def extend( self, *args, **kwargs ):
		""" :raise NotImplementedError: """
		raise NotImplementedError

	def sort( self, *args, **kwargs ):
		""" :raise NotImplementedError: """
		raise NotImplementedError
	#} END list overridden methodss

	#{ Iterators
	def sectionIterator( self ):
		""":return: section iterator for whole configuration chain """
		return ( section for node in self for section in node._sections )

	def keyIterator( self ):
		""":return: iterator returning tuples of (key,section) pairs"""
		return ( (key,section) for section in self.sectionIterator() for key in section )

	def iterateKeysByName( self, name ):
		""":param name: the name of the key you wish to find
		:return: Iterator yielding (`Key`,`Section`) of key matching name found in section"""
		# note: we do not use iterators as we want to use sets for faster search !
		return ( (section.keys[name],section) for section in self.sectionIterator() if name in section.keys )
	#} END ITERATORS


def _checkString( string, re ):
	"""Check the given string with given re for correctness
	:param re: must match the whole string for success
	:return: the passed in and stripped string
	:raise ValueError: """
	string = string.strip()
	# ALLOW EMPTY STRINGS AS VALUES
	if not len( string ):
		return string
	#	raise ValueError( "string must not be empty" )

	match = re.match( string )
	if match is None or match.end() != len( string ):
		raise ValueError( _("'%s' Invalid Value Error") % string )

	return string

def _excmsgprefix( msg ):
	""" Put msg in front of current exception and reraise
	:warning: use only within except blocks"""
	exc = sys.exc_info()[1]
	if hasattr(exc, 'message'):
		exc.message = msg + exc.message


class BasicSet( set ):
	""" Set with ability to return the key which matches the requested one

	This functionality is the built-in in default STL sets, and I do not understand
	why it is not provided here ! Of course I want to define custom objects with overridden
	hash functions, put them into a set, and finally retrieve the same object again !

	:note: indexing a set is not the fastest because the matching key has to be searched.
		Good news is that the actual 'is k in set' question can be answered quickly"""
	__slots__ = tuple()
	
	def __getitem__( self, item ):
		# assure we have the item
		if not item in self:
			raise KeyError()

		# find the actual keyitem
		for key in iter( self ):
			if key == item:
				return key

		# should never come here !
		raise AssertionError( "Should never have come here" )


class _PropertyHolderBase( object ):
	"""Simple Base defining how to deal with properties
	:note: to use this interface, the subclass must have a 'name' field"""
	__slots__ = ( 'properties', 'name', 'order') 

	def __init__( self, name, order ):
		# assure we do not get recursive here
		self.properties = None
		self.name = name
		self.order = order
		try:
			if not isinstance( self, PropertySection ):
				self.properties = PropertySection( "+" + self.name, self.order+1 ) # default is to write our properties after ourselves		# will be created on demand to avoid recursion on creation
		except:
			pass
		# END exception handling


class Key( _PropertyHolderBase ):
	""" Key with an associated values and an optional set of propterties

	:note: a key's value will be always be stripped if its a string
	:note: a key's name will be stored stripped only, must not contain certain chars
	:todo: add support for escpaing comas within quotes - currently it split at
		comas, no matter what"""
	__slots__ = ( '_name', '_values', 'values' )
	validchars = r'[\w\(\)]'
	_re_checkName = re.compile( validchars+r'+' )			# only word characters are allowed in key names, and paranthesis
	_re_checkValue = re.compile( r'[^\n\t\r]+' )					# be as open as possible

	def __init__( self, name, value, order ):
		""" Basic Field Initialization
		
		:param order: -1 = will be written to end of list, or to given position otherwise """
		self._name			= ''
		self._values 		= list()				# value will always be stored as a list
		self.values 		= value				# store the value
		_PropertyHolderBase.__init__( self, name, order )

	def __hash__( self ):
		return self._name.__hash__()

	def __eq__( self, other ):
		return self._name == str( other )

	def __repr__( self ):
		""" :return: ini string representation """
		return self._name + " = " + ','.join( [ str( val ) for val in self._values ] )

	def __str__( self ):
		""" :return: key name """
		return self._name

	@classmethod
	def _parseObject( cls, valuestr ):
		""" :return: int,float or str from valuestring """
		types = ( long, float )
		for numtype in types:
			try:
				val = numtype( valuestr )

				# truncated value ?
				if val != float( valuestr ):
					continue

				return val
			except (ValueError,TypeError):
				continue

		if not isinstance( valuestr, basestring ):
			raise TypeError( "Invalid value type: only int, long, float and str are allowed", valuestr )

		return _checkString( valuestr, cls._re_checkValue )


	def _excPrependNameAndRaise( self ):
		_excmsgprefix( "Key = " + self._name + ": " )
		raise

	def _setName( self, name ):
		""" Set the name
		:raise ValueError: incorrect name"""
		if not len( name ):
			raise ValueError( "Key names must not be empty" )
		try:
			self._name = _checkString( name, self._re_checkName )
		except (TypeError,ValueError):
			self._excPrependNameAndRaise()

	def _getName( self ):
		return self._name

	def _setValue( self, value ):
		""":note: internally, we always store a list
		:raise TypeError:
		:raise ValueError: """
		validvalues = value
		if not isinstance( value, ( list, tuple ) ):
			validvalues = [ value ]

		for i in xrange( 0, len( validvalues ) ):
			try:
				validvalues[i] = self._parseObject( validvalues[i] )
			except (ValueError,TypeError):
				 self._excPrependNameAndRaise()

		# assure we have always a value - if we write zero values to file, we
		# throw a parse error - thus we may not tolerate empty values
		# NO: Allow that at runtime, simply drop these keys during file write
		# to be consistent with section handling
		self._values = validvalues

	def _getValue( self ): return self._values

	def _getValueSingle( self ): return self._values[0]

	def _addRemoveValue( self, value, mode ):
		"""Append or remove value to/from our value according to mode
		
		:param mode: 0 = remove, 1 = add"""
		tmpvalues = value
		if not isinstance( value, (list,tuple) ):
			tmpvalues = ( value, )

		finalvalues = self._values[:]
		if mode:
			finalvalues.extend( tmpvalues )
		else:
			for val in tmpvalues:
				if val in finalvalues:
					finalvalues.remove( val )

		self.values = finalvalues


	#{ Utilities
	def appendValue( self, value ):
		"""Append the given value or list of values to the list of current values
		
		:param value: list, tuple or scalar value
		:todo: this implementation could be faster ( costing more code )"""
		self._addRemoveValue( value, True )

	def removeValue( self, value ):
		"""remove the given value or list of values from the list of current values
		
		:param value: list, tuple or scalar value
		:todo: this implementation could be faster ( costing more code )"""
		self._addRemoveValue( value, False )

	def valueString( self ):
		""" Convert our value to a string suitable for the INI format """
		strtmp = [ str( v ) for v in self._values ]
		return ','.join( strtmp )

	def mergeWith( self, otherkey ):
		"""Merge self with otherkey according to our properties
		
		:note: self will be altered"""
		# merge properties
		if self.properties != None:
			self.properties.mergeWith( otherkey.properties )

		#:todo: merge properly, default is setting the values
		self._values = otherkey._values[:]

	#} END utilities

	#{Properties
	name = property( _getName, _setName )
	""" Access the name of the key"""
	values = property( _getValue, _setValue )
	""" read: values of the key as list
	write: write single values or llist of values """
	value = property( _getValueSingle, _setValue )
	"""read: first value if the key's values
	write: same effect as write of 'values' """
	#} END properties 


class Section( _PropertyHolderBase ):
	""" Class defininig an indivual section of a configuration file including
	all its keys and section properties

	:note: name will be stored stripped and must not contain certain chars """
	__slots__ = ( '_name', 'keys' )
	_re_checkName = re.compile( r'\+?\w+(:' + Key.validchars+ r'+)?' )

	def __iter__( self ):
		""":return: key iterator"""
		return iter( self.keys )

	def __init__( self, name, order ):
		"""Basic Field Initialization
		
		:param order: -1 = will be written to end of list, or to given position otherwise """
		self._name 			= ''
		self.keys 			= BasicSet()
		_PropertyHolderBase.__init__( self, name, order )

	def __hash__( self ):
		return self._name.__hash__()

	def __eq__( self, other ):
		return self._name == str( other )

	def __str__( self ):
		""" :return: section name """
		return self._name

	#def __getattr__( self, keyname ):
		""":return: the key with the given name if it exists
		:raise NoOptionError: """
	#	return self.key( keyname )

	#def __setattr__( self, keyname, value ):
		"""Assign the given value to the given key  - it will be created if required"""
	#	self.keyDefault( keyname, value ).values = value

	def _excPrependNameAndRaise( self ):
		_excmsgprefix( "Section = " + self._name + ": " )
		raise

	def _setName( self, name ):
		""":raise ValueError: if name contains invalid chars"""
		if not len( name ):
			raise ValueError( "Section names must not be empty" )
		try:
			self._name = _checkString( name, Section._re_checkName )
		except (ValueError,TypeError):
			self._excPrependNameAndRaise()

	def _getName( self ):
		return self._name

	def mergeWith( self, othersection ):
		"""Merge our section with othersection
		
		:note:self will be altered"""
		# adjust name - the default name is mostly not going to work - property sections
		# possibly have non-qualified property names
		self.name = othersection.name

		# merge properties
		if othersection.properties is not None:
			self.properties.mergeWith( othersection.properties )

		for fkey in othersection.keys:
			key,created = self.keyDefault( fkey.name, 1 )
			if created:
				key._values = list()	# reset the value if key has been newly created

			# merge the keys
			key.mergeWith( fkey )

	#{ Properties
	name = property( _getName, _setName )
	#}

	#{Key Access
	def key( self, name ):
		""":return: `Key` with name
		:raise NoOptionError: """
		try:
			return self.keys[ name ]
		except KeyError:
			raise NoOptionError( name, self.name )

	def keyDefault( self, name, value ):
		""":param value: anything supported by `setKey`
		:return: tuple: 0 = `Key` with name, create it if required with given value, 1 = true if newly created, false otherwise"""
		try:
			return ( self.key( name ), False )
		except NoOptionError:
			key = Key( name, value, -1 )
			# set properties None if we are a propertysection ourselves
			if isinstance( self, PropertySection ):
				key.properties = None
			self.keys.add( key )
			return ( key, True )

	def setKey( self, name, value ):
		""" Set the value to key with name, or create a new key with name and value
		
		:param value: int, long, float, string or list of any of such
		:raise ValueError: if key has incorrect value
		"""
		k = self.keyDefault( name, value )[0]
		k.values = value
	#} END key acccess


class PropertySection( Section ):
	"""Define a section containing keys that make up properties of somethingI"""
	__slots__ = tuple()


class ConfigNode( object ):
	""" Represents node in the configuration chain

	It keeps information about the origin of the configuration and all its data.
	Additionally, it is aware of it being element of a chain, and can provide next
	and previous elements respectively """
	#{Construction/Destruction
	__slots__ = ( '_sections', '_fp' )
	def __init__( self, fp ):
		""" Initialize Class Instance"""
		self._sections	= BasicSet()			# associate sections with key holders
		self._fp		= fp					# file-like object that we can read from and possibly write to
	#}


	def _isWritable( self ):
		return self._fp.isWritable()

	#{Properties
	writable = property( _isWritable )		# read-only attribute
	#}

	def _update( self, configparser ):
		""" Update our data with data from configparser """
		# first get all data
		snames = configparser.sections()
		validsections = list()
		for i in xrange( 0, len( snames ) ):
			sname = snames[i]
			items = configparser.items( sname )
			section = self.sectionDefault( sname )
			section.order = i*2		# allows us to have ordering room to move items in - like properties
			for k,v in items:
				section.setKey( k, v.split(',') )
			validsections.append( section )

		self._sections.update( set( validsections ) )


	def parse( self ):
		""" parse default INI information into the extended structure

		Parse the given INI file using a _FixedConfigParser, convert all information in it
		into an internal format
		
		:raise ConfigParsingError: """
		rcp = _FixedConfigParser( )
		try:
			rcp.readfp( self._fp )
			self._update( rcp )
		except (ValueError,TypeError,ParsingError):
			name = self._fp.name()
			exc = sys.exc_info()[1]
			# if error is ours, prepend filename
			if not isinstance( exc, ParsingError ):
				_excmsgprefix( "File: " + name + ": " )
			raise ConfigParsingError( str(exc) )

		# cache whether we can possibly write to that destination x

	@classmethod
	def _check_and_append( cls, sectionsforwriting, section ):
		"""Assure we ignore empty sections
		
		:return: True if section has been appended, false otherwise"""
		if section is not None and len( section.keys ):
			sectionsforwriting.append( section )
			return True
		return False

	def write( self, rcp, close_fp=True ):
		""" Write our contents to our file-like object
		
		:param rcp: RawConfigParser to use for writing
		:return: the name of the written file
		:raise IOError: if we are read-only"""
		if not self._fp.isWritable( ):
			raise IOError( self._fp.name() + " is not writable" )

		sectionsforwriting = list()		# keep sections - will be ordered later for actual writing operation
		for section in iter( self._sections ):
			# skip 'old' property sections - they have been parsed to the
			# respective object ( otherwise we get duplicate section errors of rawconfig parser )
			if ConfigAccessor._isProperty( section.name ):
				continue

			# append section and possibly property sectionss
			ConfigNode._check_and_append( sectionsforwriting, section )
			ConfigNode._check_and_append( sectionsforwriting, section.properties )

			# append key sections
			# NOTE: we always use fully qualified property names if they have been
			# automatically generated
			# Autogenerated ones are not in the node's section list
			for key in section.keys:
				if ConfigNode._check_and_append( sectionsforwriting, key.properties ):
					# autocreated ?
					if not key.properties in self._sections:
						key.properties.name = "+"+section.name+":"+key.name


		# sort list and add sorted list
		sectionsforwriting = sorted( sectionsforwriting, key=lambda x: -x.order )	# inverse order

		for section in sectionsforwriting:
			rcp.add_section( section.name )
			for key in section.keys:
				if len( key.values ) == 0:
					continue
				rcp.set( section.name, key.name, key.valueString( ) )


		self._fp.openForWriting( )
		rcp.write( self._fp )
		if close_fp:
			self._fp.close()

		return self._fp.name()

	#{Section Access

	def listSections( self ):
		""" :return: list() with string names of available sections
		:todo: return an iterator instead"""
		out = list()
		for section in self._sections: out.append( str( section ) )
		return out


	def section( self, name ):
		""":return: `Section` with name
		:raise NoSectionError: """
		try:
			return self._sections[ name ]
		except KeyError:
			raise NoSectionError( name )

	def hasSection( self, name ):
		""":return: True if the given section exists"""
		return name in self._sections

	def sectionDefault( self, name ):
		""":return: `Section` with name, create it if required"""
		name = name.strip()
		try:
			return self.section( name )
		except NoSectionError:
			sectionclass = Section
			if ConfigAccessor._isProperty( name ):
				sectionclass = PropertySection

			section = sectionclass( name, -1 )
			self._sections.add( section )
			return section
			
	#} END section access
#} END utility classes


#{ Configuration Diffing Classes

class DiffData( object ):
	""" Struct keeping data about added, removed and/or changed data
	Subclasses should override some private methods to automatically utilize some
	basic functionality
	
	Class instances define the following values:
	 * ivar added: Copies of all the sections that are only in B ( as they have been added to B )
	 * ivar removed: Copies of all the sections that are only in A ( as they have been removed from B )
	 * ivar changed: Copies of all the sections that are in A and B, but with changed keys and/or properties"""
	__slots__ = ( 'added', 'removed', 'changed', 'unchanged','properties','name' )


	def __init__( self , A, B ):
		""" Initialize this instance with the differences of B compared to A """
		self.properties = None
		self.added = list()
		self.removed = list()
		self.changed = list()
		self.unchanged = list()
		self.name = ''
		self._populate( A, B )

	def toStr( self, typename ):
		""" Convert own data representation to a string """
		out = ''
		attrs = [ 'added','removed','changed','unchanged' ]
		for attr in attrs:
			attrobj = getattr( self, attr )
			try:
				if len( attrobj ) == 0:
					# out += "No " + attr + " " + typename + "(s) found\n"
					pass
				else:
					out += str( len( attrobj ) ) + " " + attr + " " + typename + "(s) found\n"
					if len( self.name ):
						out += "In '" + self.name + "':\n"
					for item in attrobj:
						out += "'" + str( item ) + "'\n"
			except:
				raise
				# out += attr + " " + typename + " is not set\n"

		# append properties
		if self.properties is not None:
			out += "-- Properties --\n"
			out += str( self.properties )

		return out

	def _populate( self, A, B ):
		""" Should be implemented by subclass """
		pass

	def hasDifferences( self ):
		""":return: true if we have stored differences ( A  is not equal to B )"""
		return  ( len( self.added ) or len( self.removed ) or len ( self.changed ) or \
				( self.properties is not None and self.properties.hasDifferences() ) )


class DiffKey( DiffData ):
	""" Implements DiffData on Key level """
	__slots__ = tuple()
	
	def __str__( self ):
		return self.toStr( "Key-Value" )

	@classmethod
	def _subtractLists( cls, a, b ):
		"""Subtract the values of b from a, return the list with the differences"""
		acopy = a[:]
		for val in b:
			try:
				acopy.remove( val )
			except ValueError:
				pass

		return acopy

	@classmethod
	def _matchLists( cls, a, b ):
		""":return: list of values that are common to both lists"""
		badded = cls._subtractLists( b, a )
		return cls._subtractLists( b, badded )

	def _populate( self, A, B ):
		""" Find added and removed key values
		
		:note: currently the implementation is not index based, but set- and thus value based
		:note: changed has no meaning in this case and will always be empty """

		# compare based on string list, as this matches the actual representation in the file
		avals = frozenset( str( val ) for val in A._values  )
		bvals = frozenset( str( val ) for val in B._values  )
		# we store real
		self.added = self._subtractLists( B._values, A._values )
		self.removed = self._subtractLists( A._values, B._values )
		self.unchanged = self._subtractLists( B._values, self.added )	# this gets the commonalities
		self.changed = list()			# always empty -
		self.name = A.name
		# diff the properties
		if A.properties is not None:
			propdiff = DiffSection( A.properties, B.properties )
			self.properties = propdiff			# attach propdiff no matter what


	def applyTo( self, key ):
		"""Apply our changes to the given Key"""

		# simply remove removed values
		for removedval in self.removed:
			try:
				key._values.remove( removedval )
			except ValueError:
				pass

		# simply add added values
		key._values.extend( self.added )

		# there are never changed values as this cannot be tracked
		# finally apply the properties if we have some
		if self.properties is not None:
			self.properties.applyTo( key.properties )


class DiffSection( DiffData ):
	""" Implements DiffData on section level """
	__slots__ = tuple()
	
	def __str__( self ):
		return self.toStr( "Key" )

	def _populate( self, A, B  ):
		""" Find the difference between the respective """
		# get property diff if possible
		if A.properties is not None:
			propdiff = DiffSection( A.properties, B.properties )
			self.properties = propdiff			# attach propdiff no matter what
		else:
			self.properties = None	# leave it Nonw - one should simply not try to get propertydiffs of property diffs
		
		self.added = list( copy.deepcopy( B.keys - A.keys ) )
		self.removed = list( copy.deepcopy( A.keys - B.keys ) )
		self.changed = list()
		self.unchanged = list()
		self.name = A.name
		# find and set changed keys
		common = A.keys & B.keys
		for key in common:
			akey = A.key( str( key ) )
			bkey = B.key( str( key ) )
			dkey = DiffKey( akey, bkey )

			if dkey.hasDifferences( ): self.changed.append( dkey )
			else: self.unchanged.append( key )

	@classmethod
	def _getNewKey( cls, section, keyname ):
		""":return: key from section - either existing or properly initialized without default value"""
		key,created = section.keyDefault( keyname, "dummy" )
		if created: key._values = list()			# reset value if created to assure we have no dummy values in there
		return key

	def applyTo( self, targetSection ):
		"""Apply our changes to targetSection"""
		# properties may be None
		if targetSection is None:
			return

		# add added keys - they could exist already, which is why they are being merged
		for addedkey in self.added:
			key = self._getNewKey( targetSection, addedkey.name )
			key.mergeWith( addedkey )

		# remove moved keys - simply delete them from the list
		for removedkey in self.removed:
			if removedkey in targetSection.keys:
				targetSection.keys.remove( removedkey )

		# handle changed keys - we will create a new key if this is required
		for changedKeyDiff in self.changed:
			key = self._getNewKey( targetSection, changedKeyDiff.name )
			changedKeyDiff.applyTo( key )

		# apply section property diff
		if self.properties is not None:
			self.properties.applyTo( targetSection.properties )


class ConfigDiffer( DiffData ):
	"""Compares two configuration objects and allows retrieval of differences

	Use this class to find added/removed sections or keys or differences in values
	and properties.

	**Example Applicance**:
		Test use it to verify that reading and writing a ( possibly ) changed
		configuration has the expected results
		Programs interacting with the User by a GUI can easily determine whether
		the user has actually changed something, applying actions only if required
		alternatively, programs can simply be more efficient by acting only on
		items that actually changed
	
	**Data Structure**:
		* every object in the diffing structure has a 'name' attribute
		
		* ConfigDiffer.added|removed|unchanged: `Section` objects that have been added, removed
		  or kept unchanged respectively
		  
		* ConfigDiffer.changed: `DiffSection` objects that indicate the changes in respective section
		
		 * DiffSection.added|removed|unchanged: `Key` objects that have been added, removed or kept unchanged respectively
		 
		 * DiffSection.changed: `DiffKey` objects that indicate the changes in the repsective key
		 
		  * DiffKey.added|removed: the key's values that have been added and/or removed respectively
		  
		  * DiffKey.properties: see DiffSection.properties
		  
		  * DiffSection.properties:None if this is a section diff, otherwise it contains a DiffSection with the respective differences
	"""
	__slots__ = tuple()
	
	def __str__( self ):
		""" Print its own delta information - useful for debugging purposes """
		return self.toStr( 'section' )

	@classmethod
	def _getMergedSections( cls, configaccessor ):
		"""within config nodes, sections must be unique, between nodes,
		this is not the case - sets would simply drop keys with the same name
		leading to invalid results - thus we have to merge equally named sections
		
		:return: BasicSet with merged sections
		:todo: make this algo work on sets instead of individual sections for performance"""
		sectionlist = list( configaccessor.sectionIterator() )
		if len( sectionlist ) < 2:
			return BasicSet( sectionlist )

		out = BasicSet( )				# need a basic set for indexing
		for section in sectionlist:
			# skip property sections - they have been parsed into properties, but are
			# still available as ordinary sections
			if ConfigAccessor._isProperty( section.name ):
				continue

			section_to_add = section
			if section in out:
				# get a copy of A and merge it with B
				# assure the merge works left-to-right - previous to current
				# NOTE: only the first copy makes sense - all the others that might follow are not required ...
				merge_section = copy.deepcopy( out[ section ] )	# copy section and all keys - they will be altered
				merge_section.mergeWith( section )

				#remove old and add copy
				out.remove( section )
				section_to_add = merge_section
			out.add( section_to_add )
		return out

	def _populate( self, A, B ):
		""" Perform the acutal diffing operation to fill our data structures
		:note: this method directly accesses ConfigAccessors internal datastructures """
		# diff sections  - therefore we actually have to treat the chains
		#  in a flattened manner
		# built section sets !
		asections = self._getMergedSections( A )
		bsections = self._getMergedSections( B )
		# assure we do not work on references !
		
		# Deepcopy can be 0 in case we are shutting down - deepcopy goes down too early 
		# for some reason
		assert copy.deepcopy is not None, "Deepcopy is not available"
		self.added = list( copy.deepcopy( bsections - asections ) )
		self.removed = list( copy.deepcopy( asections - bsections ) )
		self.changed = list( )
		self.unchanged = list( )
		self.name = ''
		common = asections & bsections		# will be copied later later on key level
		
		# get a deeper analysis of the common sections - added,removed,changed keys
		for section in common:
			# find out whether the section has changed
			asection = asections[ section ]
			bsection = bsections[ section ]
			dsection = DiffSection( asection, bsection )
			if dsection.hasDifferences( ): 
				self.changed.append( dsection )
			else: 
				self.unchanged.append( asection )
		# END for each common section

	def applyTo( self, ca ):
		"""Apply the stored differences in this ConfigDiffer instance to the given ConfigAccessor

		If our diff contains the changes of A to B, then applying
		ourselves to A would make A equal B.

		:note: individual nodes reqpresenting an input source ( like a file )
			can be marked read-only. This means they cannot be altered - thus it can
			be that section or key removal fails for them. Addition of elements normally
			works as long as there is one writable node.

		:param ca: The configacceesor to apply our differences to
		:return: tuple of lists containing the sections that could not be added, removed or get
			their changes applied
		
			 - [0] = list of `Section` s failed to be added
			 
			 - [1] = list of `Section` s failed to be removed
			 
			 - [2] = list of `DiffSection` s failed to apply their changes """
			 

		# merge the added sections - only to the first we find
		rval = (list(),list(),list())
		for addedsection in self.added:
			try:
				ca.mergeSection( addedsection )
			except IOError:
				rval[0].append( addedsection )

		# remove removed sections - everywhere possible
		# This is because diffs will only be done on merged lists
		for removedsection in self.removed:
			numfailedremoved = ca.removeSection( removedsection.name )
			if numfailedremoved:
				rval[1].append( removedsection )

		# handle the changed sections - here only keys or properties have changed
		# respectively
		for sectiondiff in self.changed:
			# note: changes may only be applied once ! The diff works only on
			# merged configuration chains - this means one secion only exists once
			# here we have an unmerged config chain, and to get consistent results,
			# the changes may only be applied to one section - we use the first we get
			try:
				targetSection = ca.sectionDefault( sectiondiff.name )
				sectiondiff.applyTo( targetSection )
			except IOError:
				rval[2].append( sectiondiff )

		return rval

#} END configuration diffing classes

