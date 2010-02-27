# -*- coding: utf-8 -*-
"""This module contiains classes and utilities affiliated with the import and export
of animation.

TODO: Write how it works with namespaces ( does it work with the ':' ( root ) namespace
as well ?)"""

import mayarv.maya.nodes as nodes
import maya.OpenMayaAnim as manim

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
	_separator = ','
	
	#{ Iteration 
	@classmethod
	def iter_instances( cls ):
		networktype = nodes.api.MFn.kAffect
		it=nodes.it.iterDgNodes( networktype, asNode=0 )
		for node in it:
			if hasattr(node, cls._s_connection_info_attr):
				yield cls(node)
			# END if it is our node
		#  END for each node 
	
	#} END iteration
	
	#{ Edit
	@classmethod
	@undoable
	def create( cls, **kwargs ):
		"""@return: Instance of our type providing the L{AnimationHandle} interface
		@param **kwargs: Passed to L{createNode} method of mayarv"""
		mynode = nodes.createNode("animHandle", "network", **kwargs)
		
		# add our custom attribute
		tfn = nodes.api.MFnTypedAttribute()
		safn = nodes.api.MFnStringArrayData()
		sa = safn.create()
		attr = tfn.create(cls._l_connection_info_attr,  cls._s_connection_info_attr,
							nodes.api.MFnData.kStringArray, sa)
		mynode.addAttribute(attr) 
		return cls(mynode.getObject())
		
	@undoable
	def clear( self ):
		"""Forget our managed animation completely"""
		# clear array plug
		for ip in self.affectedBy.p_inputs:
			ip.disconnectInput()
		# END for each array item to disconnect
		
		# clear connection data
		dplug = getattr(self, self._s_connection_info_attr) 
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
		# TODO: Deal with intermediate nodes and multiple outputs per 
		# anim node
		target_plug_strings = list()
		for apinode in anim_nodes:
			mfndep.setObject(apinode)
			outputs = mfndep.findPlug('o').p_outputs
			target_plug_strings.append(self._separator.join(p.getFullyQualifiedName() for p in outputs))
		# END for each anode
		getattr(self, self._s_connection_info_attr).setMObject(nodes.api.MFnStringArrayData().create(target_plug_strings))
	
	@undoable
	def apply_animation(self, converter=None):
		"""Apply the stored animation by (re)connecting the animatino nodes to their
		respective target plugs
		@param converter: if not None, it returns the desired target plug name to use 
		instead of the given plug name. Its called as follows: (string) convert(source_plug, target_plugname).
		This allows you to perform any modifications to the target before it will be
		connected.
		@note: Will break existing destination connections"""
		# get target strings
		target_plug_names = getattr(self, self._s_connection_info_attr).asData().array()
		
		assert len(target_plug_names) == len(self.affectedBy), "Number of animation nodes out of sync with their stored targets"
		
		# make iterator yielding source and target plug objects
		plug_sel_list = nodes.api.MSelectionList()
		mfndep = nodes.api.MFnDependencyNode()
		def source_target_iterator():
			for index, anim_node_dest_plug in enumerate(iter(self.affectedBy)):
				target_plug_name_list = target_plug_names[index].split(self._separator)
				mfndep.setObject(anim_node_dest_plug.p_input.getNodeApiObj())
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
		pass
	
	def to_file( self, output_file ):
		pass
	
	def apply( self, targetfn=None ):   #ziel pattern optional (default entspricht source) 
		pass

	#} END file io