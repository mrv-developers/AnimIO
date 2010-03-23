# -*- coding: utf-8 -*-
"""This module contiains classes and utilities affiliated with the import and export
of animation."""
import mrv.maya.nt as nt
from mrv.maya.ns import Namespace
from mrv.maya.ref import FileReference
from mrv.maya.scene import Scene

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
	
	
	
class AnimationHandle( nt.Network ):  
	__mrv_virtual_subtype__ = True
	
	_l_connection_info_attr = 'destArray'
	_s_connection_info_attr = 'destArray'
	_l_tmp_attr = 'justAString'
	_s_tmp_attr = 'justAString'
	_k_separator = ','
	_networktype = nt.api.MFn.kAffect
	
	def __new__( cls, *args ): 
		if not args:
			return cls.create()
		# END empty args create new node
		self=super(AnimationHandle, cls).__new__(cls, *args)
		if not cls._is_handle(self):
			raise TypeError('%r is not a valid %s' % (self, cls)) 
		return self
		
	@classmethod
	def _is_handle( cls, ah ):
		"""@return: True if ah in a propper AnimationHandle"""
		return hasattr(ah, cls._s_connection_info_attr)
		
	#{ Iteration 
	@classmethod
	def iter_instances( cls, **kwargs ):
		"""@return: iterator yielding AnimationHandle instances of scene"""
		it=nt.it.iterDgNodes( cls._networktype, asNode=1, **kwargs )
		for node in it:
			if cls._is_handle(node):
				yield cls(node.object())
			# END if it is our node
		#  END for each node 
	
	def iter_animation( self, asNode=True):
		"""@return: iterator yielding managed animation curves as wrapped Node or MObject
		@param asNode: if true, iterator yields Node instances else MObjects"""
		for anim_node_dest_plug in self.affectedBy:
			miplug=anim_node_dest_plug.minput()
			if asNode:
				yield miplug.mnode()
			else:
				yield miplug.node()
			# END if asNode
		# END iterator
		
	def iter_source_target_plg( self, converter=None, predicate=lambda x, y: True):
		"""@return: iterator yielding source, target pairs
		@param converter: if not None, the function returns the desired target plug name to use 
		instead of the given plug name. Its called as follows: (string) convert(source_plug, target_plugname).
		@param predicate: after conversion source_plug, target_plugname is testet to pass this filter"""
		
		# get target strings as array
		# mayarv provides this:
		target_plug_names = self.findPlug(self._s_connection_info_attr).masData().array()
		
		#  for a better understanding, without mayarv and just api step by step it would look like this:
		#  first we need a funktionset initialisted with the MObject of our node (ins this case MFnDependencyNode)
		# mfndep=nt.api.MFnDependencyNode(self.object())
		#  the functionset MFnDependencyNode provides the findPlug function returning the MPlug of our attribute
		# mplug=mfndep.findPlug(self._s_connection_info_attr)
		#  MPlug offers no asStringArrayData so we have to get the data asMObject end initialise the MFnStingArrayData functionset with it 
		# mfnstr=nt.api.MFnStringArrayData(mplug.asMObject())
		#  finaly we get the data as arry from MFnStringArrayData functionset
		# target_plug_names=mfnstr.array()
		
		assert len(target_plug_names) == len(self.affectedBy), "Number of animation nodes out of sync with their stored targets"
		
		# make iterator yielding source and target plug objects
		plug_sel_list = nt.api.MSelectionList()
		mfndep = nt.api.MFnDependencyNode()
		for index, anim_node_dest_plug in enumerate(self.affectedBy):
			target_plug_name_list = target_plug_names[index].split(self._k_separator)
			anim_node_msg_plug=anim_node_dest_plug.minput()
			if anim_node_msg_plug.isNull():
				print "no animation curve found on %s" % anim_node_dest_plug.mfullyQualifiedName()
				continue
			# END check for nullPlug
				
			mfndep.setObject(anim_node_msg_plug.node())
			anim_node_otp_plug = mfndep.findPlug('o')
				
			# convert target names to actual plugs
			for tindex, tplug_name in enumerate(target_plug_name_list):
				if converter:
					tplug_name = converter(anim_node_otp_plug, tplug_name)
				# END handle converter
				if not predicate(anim_node_otp_plug, tplug_name):
					continue
				actual_plug = nt.api.MPlug()
				plug_sel_list.add(tplug_name)
				plug_sel_list.getPlug(tindex, actual_plug)
					
				yield (anim_node_otp_plug, actual_plug)
				# END for each plugname to convert
								
				# make sure it doesnt build up
				plug_sel_list.clear()
			# END for each anim node source plug
		# END iterating  
	
	
	#} END iteration
	
	#{ Edit
	@classmethod
	@undoable
	def create( cls, name="animationHandle", **kwargs ):
		"""@return: New instance of our type providing the L{AnimationHandle} interface
		@param **kwargs: Passed to L{createNode} method of mayarv"""
		mynode = nt.createNode(name, "network", **kwargs)
		
		# add our custom attribute
		attr = nt.TypedAttribute.create(cls._l_connection_info_attr, cls._s_connection_info_attr,
							nt.api.MFnData.kStringArray, nt.StringArrayData.create(list()))
		attr2 = nt.TypedAttribute.create(cls._l_tmp_attr, cls._s_tmp_attr, nt.api.MFnData.kString, nt.StringData.create("empty"))
		mynode.addAttribute(attr)
		mynode.addAttribute(attr2)
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
		dplug.setMObject(nt.StringArrayData.create(list()))
	
	@undoable
	def set_animation( self, iter_nodes ):
		"""Set this handle to manage the animation of the given nodes.
		The previous animation information will be removed.
		@param iter_nodes: MSelectionList or iterable of Nodes or api objects pointing 
		to nodes connected to animation.
		@note: Will not raise if the nodes do not have any animation
		@note: Heavily optimized for speed, hence we work directly with the 
		apiObjects, skipping the mayarv layer as we are in a tight loop here"""
		self.clear()
		anim_nodes = nt.AnimCurve.findAnimation(iter_nodes, asNode=False)
		mfndep = nt.api.MFnDependencyNode()
		def iter_plugs():
			affected_by_plug = self.affectedBy
			for pindex, apinode in enumerate(anim_nodes):
				mfndep.setObject(apinode)
				yield (mfndep.findPlug('msg'), affected_by_plug.elementByLogicalIndex(pindex))
			# END for each pair to yield
		# END iterator helper
		
		iterator = iter_plugs()
		nt.api.MPlug.mconnectMultiToMulti(iterator, force=False)
		
		# add current connection info
		# NOTE: We know that the anim-node is connected to something
		# as this is the reason we retrieved it in the first place
		# TODO: Deal with intermediate nodes
		target_plug_strings = list()
		for apinode in anim_nodes:
			mfndep.setObject(apinode)
			outputs = mfndep.findPlug('o').moutputs()
			target_plug_strings.append(self._k_separator.join(p.mfullyQualifiedName() for p in outputs))
		# END for each node
		self.findPlug(self._s_connection_info_attr).setMObject(nt.StringArrayData.create(target_plug_strings))
	
	@undoable
	def apply_animation( self, converter=None ):
		"""Apply the stored animation by (re)connecting the animation nodes to their
		respective target plugs
		@param: converter see L{iter_source_target_plg}
		This allows you to perform any modifications to the target before it will be
		connected.
		@note: Will break existing destination connections"""
		
		# do actual connection ( best case is 38k connections per second
		iterator = self.iter_source_target_plg(converter=converter)
		nt.api.MPlug.mconnectMultiToMulti(iterator, force=True)
		
		
	#} END edit
	
	#{ Utilitsation
	def copypaste_animation( self, sTimeRange=":", tTimeRange=":", optn="insert", predicate=lambda x:True, converter=lambda x:x ):
		"""Copy the stored animation to their respective target animation curves
		@param sTimeRange: copy just the given timerange
		@param tTimeRange: paste copied timerange to this targes timerange
		@param optn: options on how to paste
		@param predicate: returns true if animation of the given node should be copy-pasted"""
		anim = list(self.iter_animation(asNode=1))
		if len(anim):
			print cmds.findKeyframe(anim, which="first")
			print cmds.findKeyframe(anim, which="last")
		else: print "None"
		print "test auf node %s converted: %s" % (anim[0], anim[0]) 
		print "test auf node %s converted: %s" % (anim[-1], anim[-1])
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
		"""references imput_file into scene by using an unique namespace, returning
		FileReference as well as an iterator yielding AmimationHandles of input_file
		@return: tuple(FileReference, iterator of AnimationHandles)
		@param input_file: valid path to a maya file"""
		ahref=FileReference.create(input_file, loadReferenceDepth="topOnly")
		refns=ahref.namespace()
		return (ahref, cls.iter_instances(predicate = lambda x: x.namespace() == refns))
	
	@notundoable
	def to_file( self, output_file, **kwargs ):
		"""export the AnimationHandle and all managed nodes to the given file 
		@return: path to exported file
		@param output_file: Path object or path string to export file.
		Parent directories will be created as needed
		@param **kwargs: passed to the L{Scene.export} method"""
		# build selectionlist for export
		exp_slist = nt.toSelectionList(self.iter_animation(asNode=0))     
		exp_slist.add(self.object())
		return Scene.export(output_file, exp_slist, **kwargs ) 
			
	def delete( self ):
		"""AnimationHandle will disapear without a trace, no matter if it was created in
		the current file or if it came from a referenced file"""
		
		if self.isReferenced():
			FileReference(self.referenceFile()).remove()
		else:
			super(AnimationHandle, self).delete()
		# END handle referencing
			
	#} END file io