# -*- coding: utf-8 -*-
"""This module contiains classes and utilities affiliated with the import and export
of animation."""
import mayarv.maya.nt as nt
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
	
	
	
class AnimationHandle( nt.Network ):  
	__mayarv_virtual_subtype__ = True
	
	_l_connection_info_attr = 'animio_conn_info'
	_s_connection_info_attr = 'aioc'
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
	
	#} END iteration
	
	#{ Edit
	@classmethod
	@undoable
	def create( cls, name="animationHandle", **kwargs ):
		"""@return: New instance of our type providing the L{AnimationHandle} interface
		@param **kwargs: Passed to L{createNode} method of mayarv"""
		mynode = nt.createNode(name, "network", **kwargs)
		
		# add our custom attribute
		sa = nt.api.MObject(nt.api.MFnStringArrayData().create())
		attr = nt.TypedAttribute.create(cls._l_connection_info_attr, cls._s_connection_info_attr,
							nt.api.MFnData.kStringArray, sa)
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
	def set_animation( self, iter_nodes ):
		"""Set this handle to manage the animation of the given nt.
		The previous animation information will be removed.
		@param iter_nodes: MSelectionList or iterable of Nodes or api objects pointing 
		to nodes with animation.
		@note: Will not raise if the nodes do not have any animation
		@note: Heavily optimized for speed, hence we work directly with the 
		apiObjects, skipping the mayarv layer as we are in a tight loop here"""
		self.clear()
		anim_nodes = nt.AnimCurve.animation(iter_nodes, asNode=False)
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
		
		# add current connection info7
		# NOTE: We know that the anim-node is connected to something
		# as this is the reason we retrieved it in the first place
		# TODO: Deal with intermediate nodes
		target_plug_strings = list()
		for apinode in anim_nodes:
			mfndep.setObject(apinode)
			outputs = mfndep.findPlug('o').moutputs()
			target_plug_strings.append(self._k_separator.join(p.mfullyQualifiedName() for p in outputs))
		# END for each anode
		self.findPlug(self._s_connection_info_attr).setMObject(nt.api.MFnStringArrayData().create(target_plug_strings))
	
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
		plug_sel_list = nt.api.MSelectionList()
		mfndep = nt.api.MFnDependencyNode()
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
					actual_plug = nt.api.MPlug()
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
		nt.api.MPlug.mconnectMultiToMulti(iterator, force=True)
		
	
	#} END edit
	
	#{ Utilitsation
	def copypaste_animation( self, sTimeRange=":", tTimeRange=":", optn="insert", predicate=lambda x:True, converter=lambda x:x ):
		"""Copy the stored animation to their respective target animation curves
		@param sTimeRange: copy just the given timerange
		@param tTimeRange: paste copied timerange to this targes timerange
		@param optn: options on how to paste
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
		exp_slist = nt.base.toSelectionList(self.iter_animation(asNode=0))
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
			nt.delete(self)
		
			
	#} END file io