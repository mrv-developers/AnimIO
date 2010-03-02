# -*- coding: utf-8 -*-
"""General library testing"""
from animIO.test.lib import *
from animIO import *

import mayarv.maya.nodes as nodes
import mayarv.maya as mrvmaya

import maya.OpenMayaAnim as manim

class TestBase( unittest.TestCase ):
	def setUp(self):
		"""Get fresh scene before each test runs"""
		mrvmaya.Scene.new(force=True)
	
	def make_animation(self, nodes, attrnames):
		"""Animate the given attribute(names) on the given nodes
		@return: list of animated plugs"""
		out_plugs = list()
		for node in nodes:
			for attr in attrnames:
				p = getattr(node, attr)
				manim.MFnAnimCurve().create(p)
				out_plugs.append(p)
			# END for each attr
		# END for each node
		return out_plugs

class TestAnimationHandle( TestBase ):
	
	def test_base( self ):
		p = nodes.Node("persp")
		t = nodes.Node("top")
		
		# animation handle on non-animated nodes does not raise
		handle = AnimationHandle.create()
		assert isinstance(handle, AnimationHandle)
		assert isinstance(handle, nodes.Network)
		
		# make sure we get a new animation handle each time we create
		handle2 = AnimationHandle.create()
		assert handle != handle2
		
		# use create, providing the name of an existing animationHandle node
		handle2same = AnimationHandle.create(handle2.name(), forceNewLeaf=False)
		assert handle2same == handle2
		
		# update with animation from objects which have no animation is fine
		n = (p,t)
		handle.set_animation(n)
		
		# try again with animated nodes
		assert len(handle.affectedBy) == 0
		anim_plugs = self.make_animation(n, ('tx','ty','tz'))
		handle.set_animation(n)
		
		assert len(handle.affectedBy) == len(anim_plugs)
		
		class TestConverter( object ):
			def __init__(self):
				self._nc = 0
				
			def __call__(self, source_plug, target_plug_name):
				assert isinstance(source_plug, nodes.api.MPlug)
				assert isinstance(target_plug_name, basestring)
				self._nc += 1
				return target_plug_name
			
			def make_assertion(self):
				assert self._nc
				self._nc = 0
		# END test class
		
		# apply animation after disconnecting existing one
		for converter in (None, TestConverter()):
			for plug in anim_plugs:
				plug.disconnectInput()
			# END disconnect anim curves
			
			handle.apply_animation(converter)
			if converter is not None:
				converter.make_assertion()
			# END handle converter
			
			for plug in anim_plugs:
				assert isinstance(plug.p_input.node(), nodes.AnimCurve)
		# END for each converter
		
		# test it breaks existing target animation
		assert isinstance(t.tx.p_input.node(), nodes.AnimCurve)
		p.tx >> t.tx
		
		handle.apply_animation()
		
		assert isinstance(t.tx.p_input.node(), nodes.AnimCurve)
		
	@with_scene('3handles.ma')
	def test_iteration( self ):
		handles = list(AnimationHandle.iter_instances())
		assert len(handles) == 3
		for h in handles:
			assert isinstance(h, AnimationHandle)
			assert isinstance(h, nodes.Network)
		# END for each handle
	
class TestLibrary( TestBase ):
	
	def test_base( self ):
		pass	
	