# -*- coding: utf-8 -*-
"""This module contiains classes and utilities affiliated with the import and export
of animation.

TODO: Write how it works with namespaces ( does it work with the ':' ( root ) namespace
as well ?)"""

import mayarv.maya.nodes as nodes
import mayarv.maya.ns as ns
import maya.OpenMayaAnim as manim
import maya.cmds as cmds

class AnimInOutLibrary( object ):
	"""contains default implementation"""
	#{ Export/Import/Load 
	
	#} END Export/Import/Load
	
	#{ Query
	
	#} END query
	
	def _create_plug_node( self ):
		raise NotImplementedError("todo")
	
	
	
class AnimationHandle( nodes.Network ):  
	__mayarv_virtual_subtype__ = True
	
	_l_connection_info_attr = 'animio_conn_info'
	_s_connection_info_attr = 'aioc'
	_k_separator = ','
	_networktype = nodes.api.MFn.kAffect
	
	#{ Iteration 
	@classmethod
	def iter_instances( cls, **kwargs ):
		it=nodes.it.iterDgNodes( cls._networktype, asNode=1, **kwargs )
		for node in it:
			if hasattr(node, cls._s_connection_info_attr):
				yield cls(node.getMObject())
			# END if it is our node
		#  END for each node 
	
	#} END iteration
	
	#{ Edit
	@classmethod
	@undoable
	def create( cls, name="animationHandle", **kwargs ):
		"""@return: New instance of our type providing the L{AnimationHandle} interface
		@param **kwargs: Passed to L{createNode} method of mayarv"""
		mynode = nodes.createNode(name, "network", **kwargs)
		
		# add our custom attribute
		tfn = nodes.api.MFnTypedAttribute()
		sa = nodes.api.MObject(nodes.api.MFnStringArrayData().create())
		attr = tfn.create(cls._l_connection_info_attr, cls._s_connection_info_attr,
							nodes.api.MFnData.kStringArray, sa)
		mynode.addAttribute(attr)
		return cls(mynode.getMObject())
		
	@undoable
	def clear( self ):
		"""Forget our managed animation completely"""
		# clear array plug
		for ip in self.affectedBy.getInputs():
			ip.disconnectInput()
		# END for each array item to disconnect
		
		# clear connection data
		dplug = self.findPlug(self._s_connection_info_attr)
		data = dplug.asData()
		dplug.setMObject(data.create(list()))


	@undoable
	def set_animation( self, iter_nodes ):
		"""Set this handle to manage the animation of the given nodes.
		The previous animation information will be removed.
		@param iter_nodes: MSelectionList or iterable of Nodes or api objects pointing 
		to nodes with animation.
		@note: Will not raise if the nodes do not have any animation
		@note: Heavily optimized for speed, hence we work directly with the 
		apiObjects, skipping the mayarv layer as we are in a tight loop here"""
		self.clear()
		anim_nodes = nodes.AnimCurve.getAnimation(iter_nodes, asNode=False)
		mfndep = nodes.api.MFnDependencyNode()
		def iter_plugs():
			affected_by_plug = self.affectedBy
			for pindex, apinode in enumerate(anim_nodes):
				mfndep.setObject(apinode)
				yield mfndep.findPlug('msg')
				yield affected_by_plug.getByLogicalIndex(pindex)
			# END for each pair to yield
		# END iterator helper
		
		iterator = iter_plugs()
		nodes.api.MPlug.connectMultiToMulti(iterator, iterator, force=False)
		
		# add current connection info
		# NOTE: We know that the anim-node is connected to something
		# as this is the reason we retrieved it in the first place
		# TODO: Deal with intermediate nodes
		target_plug_strings = list()
		for apinode in anim_nodes:
			mfndep.setObject(apinode)
			outputs = mfndep.findPlug('o').getOutputs()
			target_plug_strings.append(self._k_separator.join(p.getFullyQualifiedName() for p in outputs))
		# END for each anode
		self.findPlug(self._s_connection_info_attr).setMObject(nodes.api.MFnStringArrayData().create(target_plug_strings))
	
	@undoable
	def apply_animation( self, converter=None ):
		"""Apply the stored animation by (re)connecting the animatino nodes to their
		respective target plugs
		@param converter: if not None, the function returns the desired target plug name to use 
		instead of the given plug name. Its called as follows: (string) convert(source_plug, target_plugname).
		This allows you to perform any modifications to the target before it will be
		connected.
		@note: Will break existing destination connections"""
		# get target strings
		target_plug_names = self.findPlug(self._s_connection_info_attr).asData().array()
		
		assert len(target_plug_names) == len(self.affectedBy), "Number of animation nodes out of sync with their stored targets"
		
		# make iterator yielding source and target plug objects
		plug_sel_list = nodes.api.MSelectionList()
		mfndep = nodes.api.MFnDependencyNode()
		def source_target_iterator():
			for index, anim_node_dest_plug in enumerate(self.affectedBy):
				target_plug_name_list = target_plug_names[index].split(self._k_separator)
				mfndep.setObject(anim_node_dest_plug.p_input.getNodeMObject())
				anim_node_otp_plug = mfndep.findPlug('o')
				
				# convert target names to actual plugs
				for tindex, tplug_name in enumerate(target_plug_name_list):
					if converter:
						tplug_name = converter(anim_node_otp_plug, tplug_name)
					# END handle converter
					actual_plug = nodes.api.MPlug()
					plug_sel_list.add(tplug_name)
					plug_sel_list.getPlug(tindex, actual_plug)
					
					yield anim_node_otp_plug
					yield actual_plug
				# END for each plugname to convert
				
				# make sure it doesnt build up
				plug_sel_list.clear()
			# END for each anim node source plug
		# END iterator  
		
		# do actual connection ( best case is 38k connections per second
		iterator = source_target_iterator()
		nodes.api.MPlug.connectMultiToMulti(iterator, iterator, force=True)
		
	
	#} END edit
	
	#{ File IO
	@classmethod
	def from_file( cls, input_file ):
		# find unused namespace
		newns = ns.getUnique("mfLA")
		
		# load file if exists otherwise return nothing
		if cmds.file(input_file, q=True, exists=True ):
			cmds.file( input_file, r=True, namespace=newns, loadReferenceDepth="topOnly") 
		else:
			return ""
		
		if ns.Namespace.getCurrent() !=  ns.Namespace(ns.Namespace.rootNamespace):
			newns = ns.Namespace.getCurrent() + newns
		# END patching namespace 
				
		return list(cls.iter_instances(predicate = lambda x: x.getNamespace() == newns))
	
	def to_file( self, output_file, **kwargs ):
		# store current selectionlist
		stored_slist = nodes.api.MSelectionList()
		nodes.api.MGlobal.getActiveSelectionList(stored_slist)
		
		# make selectionlist for export
		exp_slist = nodes.api.MSelectionList()
		for anim_node_dest_plug in self.affectedBy:
			exp_slist.add(anim_node_dest_plug.p_input.getNodeMObject())
		# END for affectedBy plug add nodeMObject 
		exp_slist.add(self.getMObject())
		
		# export selected and take care of current active selection list
		try:
			nodes.api.MGlobal.setActiveSelectionList(exp_slist)
			cmds.file(output_file, exportSelected=True, **kwargs ) 
		finally:
			nodes.api.MGlobal.setActiveSelectionList(stored_slist)
			
	def unload( self ):
		"""AnimationHandle will disapears without a trace, no matter if it was created in
		the current file or if it came from a referenced file"""
		pass
			
	#} END file io