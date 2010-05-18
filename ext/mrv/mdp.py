#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Module containing the commandline interface for the Maya Depdendency Parser"""
# may not be imported directly
__all__ = None
# assure we have the main module initialized
import mrv
from mdepparse import *

from networkx.readwrite import gpickle

from itertools import chain
import getopt
import sys



def main( fileList, **kwargs ):
	"""Called if this module is called directly, creating a file containing
		dependency information
	
	:param kwargs: will be passed directly to `createFromFiles`"""
	return MayaFileGraph.createFromFiles( fileList, **kwargs )


def _usageAndExit( msg = None ):
	sys.stdout.write("""bpython mdepparse.py [-shortflags ] [--longflags] file_to_parse.ma [file_to_parse, ...]

OUTPUT
------
All actual information goes to stdout, everything else to stderr

EDIT
-----
-t	Target file used to store the parsed dependency information
	If not given, the command will automatically be in query mode.
	The file format is simply a pickle of the underlying Networkx graph

-s	Source dependency file previously written with -t. If specified, this file
	will be read to quickly be read for queries. If not given, the information
	will be parsed first. Thus it is recommended to have a first run storing
	the dependencies and do all queries just reading in the dependencies using
	-s

-i	if given, a list of input files will be read from stdin. The tool will start
	parsing the files as the come through the pipe

-a	if given, all paths will be parsed from the input files. This will take longer
	than just parsing references as the whole file needs to be read
	TODO: actual implementation

--to-fs-map	tokenmap
	map one part of the path to another in order to make it a valid path
	in the filesystem, i.e:
	--to-fs-map source=target[=...]
	--to-fs-map c:\\=/mnt/data/
	sort it with the longest remapping first to assure no accidential matches.
	Should be used if environment variables are used which are not set in the system
	or if there are other path inconsistencies

--to-db-map tokenmap
	map one part of the fs path previously remapped by --to-fs-map to a
	more general one suitable to be a key in the dependency database.
 	The format is equal to the one used in --to-fs-map

-o	output the dependency database as dot file at the given path, so it can
	be read by any dot reader and interpreted that way.
	If input arguments are given, only the affected portions of the database
	will be available in the dot file. Also, the depths of the dependency information
	is lost, thus there are only direct connections, although it might in
	fact be a sub-reference.

QUERY
-----
All values returned in query mode will be new-line separated file paths
--affects 		retrieve all files that are affected by the input files
--affected-by 	retrieve all files that are affect the input files

-l				if set, only leaf paths, thus paths being at the end of the chain
				will be returned.
				If not given, all paths, i.e. all intermediate references, will
				be returned as well

-d int			if not set, all references and subreferences will be retrieved
				if 1, only direct references will be returned
				if > 1, also sub[sub...] references will returned

-b				if set and no input arg exists, return all bad or invalid files stored in the database
				if an input argument is given, it acts as a filter and only returns
				filepaths that are marked invalid

-e				return full edges instead of only the successors/predecessors.
				This allows tools to parse the output and make more sense of it
				Will be ignored in nice mode

-n 				nice output, designed to be human-readable

-v				enable more verbose output

""")
	if msg:
		sys.stdout.write(msg+"\n")
	# END print message
	
	sys.exit( 1 )


def tokensToRemapFunc( tokenstring ):
	"""Return a function applying remapping as defined by tokenstring
	
	:note: it also applies a mapping from mb to ma, no matter what.
		Thus we currently only store .ma files as keys even though it might be mb files"""
	tokens = tokenstring.split( "=" )
	if len( tokens ) % 2 != 0:
		raise ValueError( "Invalid map format: %s" % tokenstring )

	remap_tuples = zip( tokens[0::2], tokens[1::2] )

	def path_replace( f ):
		for source, dest in remap_tuples:
			f = f.replace( source, dest )
		return f

	return path_replace



# COMMAND LINE INTERFACE
############################
if __name__ == "__main__":
	# parse the arguments as retrieved from the command line !
	try:
		opts, rest = getopt.getopt( sys.argv[1:], "iat:s:ld:benvo:", [ "affects", "affected-by",
								   										"to-fs-map=","to-db-map=" ] )
	except getopt.GetoptError,e:
		_usageAndExit( str( e ) )


	if not opts and not rest:
		_usageAndExit()

	opts = dict( opts )
	fromstdin = "-i" in opts

	# PREPARE KWARGS_CREATEGRAPH
	#####################
	allpaths = "-a" in opts
	kwargs_creategraph = dict( ( ( "parse_all_paths", allpaths ), ) )
	kwargs_query = dict()

	# PATH REMAPPING
	##################
	# prepare ma to mb conversion
	# by default, we convert from mb to ma hoping there is a corresponding
	# ma file in the same directory
	for kw,flag in ( "to_os_path","--to-fs-map" ),( "os_path_to_db_key", "--to-db-map" ):
		if flag not in opts:
			continue

		remap_func = tokensToRemapFunc( opts.get( flag ) )
		kwargs_creategraph[ kw ] = remap_func
		kwargs_query[ kw ] = remap_func			# required in query mode as well
	# END for each kw,flag pair


	# PREPARE FILELIST
	###################
	filelist = rest
	if fromstdin:
		filelist = chain( sys.stdin, rest )


	targetFile = opts.get( "-t", None )
	sourceFile = opts.get( "-s", None )


	# GET DEPENDS
	##################
	graph = None
	verbose = "-v" in opts

	if not sourceFile:
		graph = main( filelist, **kwargs_creategraph )
	else:
		if verbose:
			sys.stdout.write("Reading dependencies from: %s\n" % sourceFile)
		graph = gpickle.read_gpickle( sourceFile )



	# SAVE ALL DEPENDENCIES ?
	#########################
	# save to target file
	if targetFile:
		if verbose:
			sys.stdout.write("Saving dependencies to %s\n" % targetFile)
		gpickle.write_gpickle( graph, targetFile )


	# QUERY MODE
	###############
	return_invalid = "-b" in opts
	depth = int( opts.get( "-d", -1 ) )
	as_edge = "-e" in opts
	nice_mode = "-n" in opts
	dotgraph = None
	dotOutputFile = opts.get( "-o", None )
	kwargs_query[ 'invalid_only' ] = return_invalid		# if given, filtering for invalid only is enabled

	if dotOutputFile:
		dotgraph = MayaFileGraph()

	queried_files = False
	for flag, direction in (	( "--affects", MayaFileGraph.kAffects ),
								("--affected-by",MayaFileGraph.kAffectedBy ) ):
		if not flag in opts:
			continue

		# PREPARE LEAF FUNCTION
		prune = lambda i,g: False
		if "-l" in opts:
			degreefunc = ( ( direction == MayaFileGraph.kAffects ) and MayaFileGraph.out_degree ) or MayaFileGraph.in_degree
			prune = lambda i,g: degreefunc( g, i ) != 0

		listcopy = list()			# as we read from iterators ( stdin ), its required to copy it to iterate it again


		# write information to stdout
		for filepath in filelist:
			listcopy.append( filepath )
			queried_files = True			# used as flag to determine whether filers have been applied or not
			filepath = filepath.strip()		# could be from stdin
			depends = graph.depends( filepath, direction = direction, prune = prune,
									   	visit_once=1, branch_first=1, depth=depth,
										return_unresolved=0, **kwargs_query )

			# skip empty depends
			if not depends:
				continue

			# FILTERED DOT OUTPUT ?
			#########################
			if dotgraph is not None:
				for dep in depends:
					dotgraph.add_edge( ( filepath, dep ) )

			# match with invalid files if required
			if nice_mode:
				depthstr = "unlimited"
				if depth != -1:
					depthstr = str( depth )

				affectsstr = "is affected by: "
				if direction == MayaFileGraph.kAffects:
					affectsstr = "affects: "

				headline = "\n%s ( depth = %s, invalid only = %i )\n" % ( filepath, depthstr, return_invalid )
				sys.stdout.write( headline )
				sys.stdout.write( "-" * len( headline ) + "\n" )

				sys.stdout.write( affectsstr + "\n" )
				sys.stdout.writelines( "\t - " + dep + "\n" for dep in depends )
			else:
				prefix = ""
				if as_edge:
					prefix = "%s->" % filepath
				sys.stdout.writelines( ( prefix + dep + "\n" for dep in depends )  )
			# END if not nice modd
		# END for each file in file list

		# use copy after first iteration
		filelist = listcopy

	# END for each direction to search

	# ALL INVALID FILES OUTPUT
	###########################
	if not queried_files and return_invalid:
		invalidFiles = graph.invalidFiles()
		sys.stdout.writelines( ( iv + "\n" for iv in invalidFiles ) )


	# DOT OUTPUT
	###################
	if dotOutputFile:
		if verbose:
			sys.stdout.write("Saving dot file to %s\n" % dotOutputFile)
		try:
			import networkx.drawing.nx_pydot as pydot
		except ImportError:
			sys.stderr.write( "Required pydot module not installed" )
		else:
			if queried_files and dotgraph is not None:
				pydot.write_dot( dotgraph, dotOutputFile )
			else:
				pydot.write_dot( graph, dotOutputFile )
	# END dot writing
