# -*- coding: utf-8 -*-
"""Contains parser allowing to retrieve dependency information from maya ascii files
and convert it into an easy-to-use networkx graph with convenience methods.
"""
__docformat__ = "restructuredtext"

from networkx import DiGraph, NetworkXError
from util import iterNetworkxGraph

import sys
import os
import re

import logging
log = logging.getLogger("mrv.mdepparse")

class MayaFileGraph( DiGraph ):
	"""Contains dependnecies between maya files including utility functions
	allowing to more easily find what you are looking for"""
	kAffects,kAffectedBy = range( 2 )

	refpathregex = re.compile( '.*-r .*"(.*)";' )

	invalidNodeID = "__invalid__"
	invalidPrefix = ":_iv_:"

	#{ Edit
	@classmethod
	def createFromFiles( cls, fileList, **kwargs ):
		""":return: MayaFileGraph providing dependency information about the files
			in fileList and their subReference.
		:param fileList: iterable providing the filepaths to be parsed and added
			to this graph
		:param kwargs: alll arguemnts of `addFromFiles` are supported """
		graph = cls( )
		graph.addFromFiles( fileList, **kwargs )
		return graph


	def _addInvalid( self, invalidfile ):
		"""Add an invalid file to our special location
		:note: we prefix it to assure it does not popup in our results"""
		self.add_edge( self.invalidNodeID, self.invalidPrefix + str( invalidfile ) )

	@classmethod
	def _parseReferences( cls, mafile, allPaths = False ):
		""":return: list of reference strings parsed from the given maya ascii file
		:raise IOError: if the file could not be read"""
		outrefs = list()
		filehandle = open( os.path.expandvars( mafile ), "r" )

		num_rdi_paths = 0		# amount of -rdi paths we found - lateron we have to remove the items
								# at the respective position as both lists match

		# parse depends
		for line in filehandle:

			# take the stupid newlines into account !
			line = line.strip()
			if not line.endswith( ";" ):
				try:
					line = line + filehandle.next()
				except StopIteration:
					break
			# END newline special handling

			match = cls.refpathregex.match( line )

			if match:
				outrefs.append( match.group(1) )
			# END -r path match

			# see whether we can abort early
			if not allPaths and line.startswith( "requires" ):
				break
		# END for each line

		filehandle.close()

		return outrefs

	def _parseDepends( self, mafile, allPaths ):
		""":return: list of filepath as parsed from the given mafile.
		:param allPaths: if True, the whole file will be parsed, if False, only
			the reference section will be parsed"""
		outdepends = list()
		log.info("Parsing %s" % ( mafile ))

		try:
			outdepends = self._parseReferences( mafile, allPaths )
		except IOError,e:
			# store as invalid
			self._addInvalid( mafile )
			log.warn("Parsing Failed: %s" % str( e ))
		# END exception handlign
		return outdepends


	def addFromFiles( self, mafiles, parse_all_paths = False,
					to_os_path = lambda f: os.path.expandvars( f ),
					os_path_to_db_key = lambda f: f):
		"""Parse the dependencies from the given maya ascii files and add them to
		this graph
		
		:note: the more files are given, the more efficient the method can be
		:param parse_all_paths: if True, default False, all paths found in the file will be used.
			This will slow down the parsing as the whole file will be searched for references
			instead of just the header of the file
		:param to_os_path: functor returning an MA file from given posssibly parsed file
			that should be existing on the system parsing the files.
			The passed in file could also be an mb file ( which cannot be parsed ), thus it
			would be advantageous to return a corresponding ma file
			This is required as references can have environment variables inside of them
		:param os_path_to_db_key: converts the given path as used in the filesystem into
			a path to be used as key in the database. It should be general.
			Ideally, os_path_to_db_key is the inverse as to_os_path.
		:note: if the parsed path contain environment variables you must start the
			tool such that these can be resolved by the system. Otherwise files might
			not be found
		:todo: parse_all_paths still to be implemented"""
		files_parsed = set()					 # assure we do not duplicate work
		for mafile in mafiles:
			depfiles = [ mafile.strip() ]
			while depfiles:
				curfile = to_os_path( depfiles.pop() )

				# ASSURE MA FILE
				if os.path.splitext( curfile )[1] != ".ma":
					log.info( "Skipped non-ma file: %s" % curfile )
					continue
				# END assure ma file

				if curfile in files_parsed:
					continue

				curfiledepends = self._parseDepends( curfile, parse_all_paths )
				files_parsed.add( curfile )

				# create edges
				curfilestr = str( curfile )
				valid_depends = list()
				for depfile in curfiledepends:
					# only valid files may be adjusted - we keep them as is otherwise
					dbdepfile = to_os_path( depfile )

					if os.path.exists( dbdepfile ):
						valid_depends.append( depfile )				# store the orig path - it will be converted later
						dbdepfile = os_path_to_db_key( dbdepfile )		# make it db key path
					else:
						dbdepfile = depfile								# invalid - revert it
						self._addInvalid( depfile )						# store it as invalid, no further processing

					self.add_edge( dbdepfile, os_path_to_db_key( curfilestr ) )

				# add to stack and go on
				depfiles.extend( valid_depends )
			# END dependency loop
		# END for each file to parse

		#} END edit

	#{ Query
	def depends( self, filePath, direction = kAffects,
				   to_os_path = lambda f: os.path.expandvars( f ),
					os_path_to_db_key = lambda f: f, return_unresolved = False,
				   invalid_only = False, **kwargs ):
		""":return: list of paths ( converted to os paths ) that are related to
			the given filePath
		:param direction: specifies search direction, either :
			kAffects = Files that filePath affects
			kAffectedBy = Files that affect filePath
		:param return_unresolved: if True, the output paths will not be translated to
			an os paths and you get the paths as stored in the graph.
			Please not that the to_os_path function is still needed to generate
			a valid key, depending on the format of filepaths stored in this graph
		:param invalid_only: if True, only invalid dependencies will be returned, all
			including the invalid ones otherwise
		:param to_os_path: see `addFromFiles`
		:param os_path_to_db_key: see `addFromFiles`
		:param kwargs: passed to `iterNetworkxGraph`"""
		kwargs[ 'direction' ] = direction
		kwargs[ 'ignore_startitem' ] = 1			# default
		kwargs[ 'branch_first' ] = 1		# default

		keypath = os_path_to_db_key( to_os_path( filePath ) )	# convert key
		invalid = set( self.invalidFiles() )

		if return_unresolved:
			to_os_path = lambda f: f

		outlist = list()

		try:
			for d, f in iterNetworkxGraph( self, keypath, **kwargs ):
				is_valid = f not in invalid
				f = to_os_path( f )		# remap only valid paths

				if is_valid and invalid_only:	# skip valid ones ?
					continue

				outlist.append( f )
			# END for each file in dependencies
		except NetworkXError:
			log.debug( "Skipped Path %s ( %s ): unknown to dependency graph" % ( filePath, keypath ) )

		return outlist

	def invalidFiles( self ):
		"""
		:return: list of filePaths that could not be parsed, most probably
			because they could not be found by the system"""
		lenp = len( self.invalidPrefix  )

		try:
			return [ iv[ lenp : ] for iv in self.successors( self.invalidNodeID ) ]
		except NetworkXError:
			return list()
		# END no invalid found exception handling
	#} END query

