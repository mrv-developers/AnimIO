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
		"""Animate the given attribute(names) on the given nodes"""
		for node in nodes:
			for attr in attrnames:
				manim.MFnAnimCurve().create(getattr(node, attr))
			# END for each attr
		# END for each node

class TestAnimationHandle( TestBase ):
	
	def test_base( self ):
		p = nodes.Node("persp")
		t = nodes.Node("topShape")
		
		# animation handle on non-animated nodes does not raise
		handle = AnimationHandle.create()
		assert isinstance(handle, AnimationHandle)
		assert isinstance(handle, nodes.Network)
		
		# update with animation from objects
		n = (p,t.getParent())
		handle.set_animation(n)
		
		# try again with animated nodes
		self.make_animation(n, ('tx','ty','tz'))
		handle.set_animation(n)
		
		self.fail("test saved data, test connections")
		
		
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
	