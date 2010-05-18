# -*- coding: utf-8 -*-
"""general methods and classes """
__docformat__ = "restructuredtext"

from mrv.dge import PlugAlreadyConnected
import logging
log = logging.getLogger("mrv.automation.base")

#{ Edit

def _toSimpleType( stringtype ):
	for cls in [ int, float, str ]:
		try:
			return cls( stringtype )
		except ValueError:
			pass
	# END for each simple type
	raise ValueError( "Could not convert %r to any simple type" % stringtype )

def _getNodeInfo( node ):
	""":return: ( nodename, args, kwargs ) - all arguments have been parsed"""
	args = [ node.get_name().strip('"') ]
	nodeattrs = node.get_attributes()
	tl = nodeattrs.get('toplabel', '').strip('"')
	if tl:
		args.extend( [ _toSimpleType( a ) for a in tl.split(',') ] )
	# END if args are set

	kwargs = dict()
	bl = nodeattrs.get('bottomlabel', '').strip('"')
	if bl:
		for kwa in bl.split(','):
			k,v = tuple(kwa.split('='))
			kwargs[ k ] = _toSimpleType( v )
		# END for each kw value
	# END if bottom label is set

	# convert name such that if one can write nodename(args,kwargs), without
	# destroing the original node name
	typename = node.get_label()
	if typename:
		typename = typename.strip('"').split( "(" )[0]

	return ( typename, args,kwargs )

def loadWorkflowFromDotFile( dotfile, workflowcls = None ):
	"""Create a graph from the given dotfile and create a workflow from it.
	The workflow will be fully intiialized with connected process instances.
	The all compatible plugs will automatically be connected for all processes
	connected in the dot file
	
	:param workflowcls: if not None, a dgengine.Graph compatible class to be used
		for workflow creation. Defaults to automation.workflow.Workflow.
	:return: List of initialized workflow classes - as they can be nested, the
		creation of one workflow can actually create several of them"""
	import pydot
	import processes
	from workflow import Workflow
	wflclass = workflowcls or Workflow
	dotgraph = pydot.graph_from_dot_file( dotfile )

	if not dotgraph:
		raise AssertionError( "Returned graph from file %r was None" % dotfile )


	# use the filename as name
	edge_lut = {}									# string -> processinst
	wfl = wflclass( name=dotfile.namebase() )


	for node in dotgraph.get_node_list():
		# can have initializers
		nodeid = node.get_name().strip( '"' )
		# ignore default node
		if nodeid == "node":
			continue	
		processname,args,kwargs = _getNodeInfo( node )

		# skip nodes with incorrect label - the parser returns one node each time it appears
		# in the file, although its mentioned in connections, at least if labels are used
		if not isinstance( processname, basestring ):
			continue

		# GET PROCESS CLASS
		try:
			processcls = getattr( processes, processname )
		except AttributeError:
			raise TypeError( "Process '%s' not found in 'processes' module" % processname )

		# create instance and add to workflow
		try:
			processinst = processcls( *args, **kwargs )
		except TypeError:
			log.error( "Process %r could not be created as it required a different init call" % processcls )
			raise
		else:
			edge_lut[ nodeid ] = processinst
			wfl.addNode( processinst )
	# END for each node in graph


	# ADD EDGES
	#############
	# create most suitable plug connections
	for edge in dotgraph.get_edge_list():
		snode = edge_lut[ edge.get_source().strip('"') ]
		dnode = edge_lut[ edge.get_destination().strip('"') ]
		destplugs = dnode.inputPlugs( )

		numConnections = 0
		for sourceplug in snode.outputPlugs():
			try:
				# first is best
				targetcandidates = snode.filterCompatiblePlugs( destplugs, sourceplug.attr, raise_on_ambiguity = 0, attr_affinity = False, attr_as_source = True )
			except ( TypeError,IndexError ),e:	# could have no compatible plugs or is ambigous
				log.debug(str(e.args))		# debug
				continue
			else:
				# if a plug is already connected, try another one
				blockedDestinationShells = list()
				numplugconnections = 0
				for rate,targetplug in targetcandidates:
					try:
						sshell = snode.toShell( sourceplug )
						dshell = dnode.toShell( targetplug )
						sshell.connect( dshell )

						numConnections += 1
						numplugconnections += 1
					except PlugAlreadyConnected:
						# remember the connected d-shell - we might disconnect it later
						blockedDestinationShells.append( dnode.toShell( targetplug ) )
					else:
						pass 			# allow several connections ( if no other claims one ... )
				# END for each candidate

				# if we have no connecitons, and one node already connected has at least two from
				# the same plug disconnect the node in question
				# Dont do anything if we are connected or have less than 2 blocked
				if numplugconnections > 0 or len( blockedDestinationShells ) < 2:
					continue

				# count connections by sourceshell
				sourcemap = dict()			# source->list( edge( s->d  ) ... )
				for shell in blockedDestinationShells:
					inshell = dshell.input()
					sourcemap.setdefault( inshell, list() ).append( ( inshell,dshell ) )

				# find multiple edges
				for sourceshell, edgelist in sourcemap.iteritems():
					if len( edgelist ) < 2:
						continue
					sshell = snode.toShell( sourceplug )
					dshell = edgelist[-1][1]				# take the last edge as it possibly has lowest connection priority
					sshell.connect( dshell, force = 1 )	# connect breaking existing ones

					numConnections += 1
					break
				# END for each sourceshell record

			# END try connecting plugs
		# END for each output plug on snode

		# assure we have a connection
		if numConnections == 0:
			raise AssertionError( "Found no compatible connection from %s to %s in workflow %s - check your processes" % ( snode, dnode, wfl ) )
	# END for each edge
	
	return wfl


def addWorkflowsFromDotFiles( module, dotfiles, workflowcls = None ):
	"""Create workflows from a list of dot-files and add them to the module
	
	:param workflowcls: see `loadWorkflowFromDotFile`
	:return: list of workflow instances created from the given files"""
	outwfls = list()
	for dotfile in dotfiles:
		wflname = dotfile.namebase()
		# it can be that a previous nested workflow already created the workflow
		# in which case we do not want to recreate it
		if hasattr( module, wflname ):
			continue

		wflinst = loadWorkflowFromDotFile( dotfile, workflowcls = workflowcls )
		setattr( module, wflname , wflinst )
		outwfls.append( wflinst )

	return outwfls

#} END interface

