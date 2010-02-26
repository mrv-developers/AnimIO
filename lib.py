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
	def collect( self, iter_nodes ):
		"""@return: Animation handle"""
		pass
	
	def apply( self, handle ):
		pass
	
	#} END Export/Import/Load
	
	#{ Query
	
	def get_animation( self, selection_list, as_node=False ):
		"""@return: list-compatible object containing of curves attached to the given nodes.
		@todo: Find out about blends / mutes / other inbetween nodes - does it work 
		for them
		@param selection_list: MSelection list containing the nodes and plugs 
		whose animation you want to find
		@param as_node: If True, the animation curves will be wrapped, or 
		MObjects otherwise ( to gain performance )"""
		anim_plugs = nodes.api.MPlugArray()
		manim.MAnimUtil.findAnimatedPlugs(selection_list, anim_plugs, False)
		
		# it will append to this array !
		objs = nodes.api.MObjectArray()
		for anim_plug in anim_plugs:
			manim.MAnimUtil.findAnimation(anim_plug, objs)
		# END for each animated plug
		
		if as_node:
			Node = nodes.Node
			MObject = nodes.api.MObject
			return [ Node(obj) for obj in objs ]
		else:
			return objs

	#} END query
	
	def _create_plug_node( self ):
		raise NotImplementedError("todo")
	
	
	
class AnimationHandle( nodes.Network ):  
	__mayarv_virtual_subtype__ = True
	
	@classmethod
	def iter_instances( cls ):
		networktype = nodes.api.MFn.kAffect
		it=nodes.it.iterDgNodes( networktype, asNode=0 )
		for node in it:
			# TODO: check its a handle for real
			yield cls(node)
		#  END for each node 
	
	@classmethod		
	def create( cls, iter_nodes ):
		pass
	
	@classmethod
	def from_file( cls, input_file ):
		pass
	
	def to_file( self, output_file ):
		pass
	
	def apply( self, targetfn=None ):   #ziel pattern optional (default entspricht source) 
		pass
