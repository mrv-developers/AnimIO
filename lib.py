# -*- coding: utf-8 -*-
"""This module contiains classes and utilities affiliated with the import and export
of animation.

TODO: Write how it works with namespaces ( does it work with the ':' ( root ) namespace
as well ?)"""

import mayarv.maya.nt as nodes
from mayarv.maya.ns import Namespace
from mayarv.maya.ref import FileReference
from mayarv.maya.scene import Scene

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
				yield cls(node.object())
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
		return cls(mynode.object())
		
	@undoable
	def clear( self ):
		"""Forget our managed animation completely"""
		# clear array plug
		for ip in self.affectedBy.minputs():
			ip.disconnectInput()
		# END for each array item to disconnect
		
		# clear connection data
		dplug = self.findPlug(self._s_connection_info_attr)
		data = dplug.masData()
		dplug.setMObject(data.create(list()))

	@undoable
	def iter_animation( self, asNode=False, predicate=lambda x:True, converter=lambda x:x ):
		"""iterate our managed animation
		@param asNode: if true, iterator returns mayarv nodes otherwise unwrapped api objects"""
		for anim_node_dest_plug in self.affectedBy:
			anode=anim_node_dest_plug.minput().mnode()
			convert_to=converter(anode.name())
			anode.converted=convert_to
			if predicate(convert_to):
				if asNode:
					yield anode
				else:
					yield anim_node_dest_plug.minput().node()
		# END iterator

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
		anim_nodes = nodes.AnimCurve.animation(iter_nodes, asNode=False)
		mfndep = nodes.api.MFnDependencyNode()
		def iter_plugs():
			affected_by_plug = self.affectedBy
			for pindex, apinode in enumerate(anim_nodes):
				mfndep.setObject(apinode)
				yield (mfndep.findPlug('msg'), affected_by_plug.elementByLogicalIndex(pindex))
			# END for each pair to yield
		# END iterator helper
		
		iterator = iter_plugs()
		nodes.api.MPlug.mconnectMultiToMulti(iterator, force=False)
		
		# add current connection info
		# NOTE: We know that the anim-node is connected to something
		# as this is the reason we retrieved it in the first place
		# TODO: Deal with intermediate nodes
		target_plug_strings = list()
		for apinode in anim_nodes:
			mfndep.setObject(apinode)
			outputs = mfndep.findPlug('o').moutputs()
			target_plug_strings.append(self._k_separator.join(p.mfullyQualifiedName() for p in outputs))
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
		target_plug_names = self.findPlug(self._s_connection_info_attr).masData().array()
		
		assert len(target_plug_names) == len(self.affectedBy), "Number of animation nodes out of sync with their stored targets"
		
		# make iterator yielding source and target plug objects
		plug_sel_list = nodes.api.MSelectionList()
		mfndep = nodes.api.MFnDependencyNode()
		def source_target_iterator():
			for index, anim_node_dest_plug in enumerate(self.affectedBy):
				target_plug_name_list = target_plug_names[index].split(self._k_separator)
				mfndep.setObject(anim_node_dest_plug.minput().node())
				anim_node_otp_plug = mfndep.findPlug('o')
				
				# convert target names to actual plugs
				for tindex, tplug_name in enumerate(target_plug_name_list):
					if converter:
						tplug_name = converter(anim_node_otp_plug, tplug_name)
					# END handle converter
					actual_plug = nodes.api.MPlug()
					plug_sel_list.add(tplug_name)
					plug_sel_list.getPlug(tindex, actual_plug)
					
					yield (anim_node_otp_plug, actual_plug)
				# END for each plugname to convert
				
				# make sure it doesnt build up
				plug_sel_list.clear()
			# END for each anim node source plug
		# END iterator  
		
		# do actual connection ( best case is 38k connections per second
		iterator = source_target_iterator()
		nodes.api.MPlug.mconnectMultiToMulti(iterator, force=True)
		
	
	#} END edit
	
	#{ Utilitsation
	def copypaste_animation( self, sTimeRange=":", tTimeRange=":", optn="insert", predicate=lambda x:True, converter=lambda x:x ):
		"""Copy the stored animation to their respective target animation curves
		@param sTimeRange: copy just the given timerange
		@param tTimeRange: paste copied timerange to this targes timerange
		@param optn: options on how to paste
		@param contverter: if not None, the function returns the desired target plug name to use 
		instead of the given plug name. Its called as follows: (string) convert(source_plug, target_plugname).
		@param predicate: returns true if animation of the given node should be copy-pasted"""
		anim = list(self.iter_animation(asNode=1, predicate=predicate, converter=converter))
		if len(anim):
			print cmds.findKeyframe(anim, which="first")
			print cmds.findKeyframe(anim, which="last")
		else: print "None"
		print "test auf node %s converted: %s" % (anim[0], anim[0].converted) 
		print "test auf node %s converted: %s" % (anim[-1], anim[-1].converted)
		# cmds.copyKey(anim, time=sTimeRange, option="curve"  )
		# tganim=list()
		# for n in anim:
			# tganim.add(n.converted)		
		# cmds.pasteKey(tganim, time=tTimeRange, option="fitInsert")
	
	
	#} END utilisation
	
	#{ File IO
	@classmethod
	@notundoable
	def from_file( cls, input_file ):
		"""get a list of AnimationHandles from a file by referencing it
		@param input_file: string of a file in the current project or full path name"""
		
		# find unused namespace
		newns = Namespace.findUnique("mfLA")
		
		# load file if exists otherwise return nothing
		if cmds.file(input_file, q=True, exists=True ):
			cmds.file( input_file, r=True, namespace=newns, loadReferenceDepth="topOnly") 
		else:
			raise IOError("file \"" + input_file + "\" not found!")
		
		if Namespace.current() != Namespace.rootpath:
			newns = Namespace.current() + newns
		# END patching namespace 
		print "wir testen auf namespace: %s" % newns		
		return list(cls.iter_instances(predicate = lambda x: x.namespace() == newns))
	
	@notundoable
	def to_file( self, output_file, **kwargs ):
		"""export the AnimationHandle and all nodes connected to the affectesBy plug
		@param output_file: filname to export to in current project or full path name
		@param **kwargs: passed to the Scene.export method"""
		
		# build selectionlist for export
		exp_slist = nodes.base.toSelectionList(self.iter_animation())
		exp_slist.add(self.object())
		print exp_slist
		
		# export selected
		return Scene.export(output_file, exp_slist, **kwargs ) 
			
	def unload( self ):
		"""AnimationHandle will disapear without a trace, no matter if it was created in
		the current file or if it came from a referenced file"""
		
		if self.isReferenced():
			FileReference(self.referenceFile()).remove()
		else:
			nodes.delete(self)
		
			
	#} END file io