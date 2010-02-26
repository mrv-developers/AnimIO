# -*- coding: utf-8 -*-
"""General library testing"""
from animIO.test.lib import *
from animIO import *

import mayarv.maya.nodes as nodes
import mayarv.maya as mrvmaya

class TestBase( unittest.TestCase ):
	def setUp(self):
		"""Get fresh scene before each test runs"""
		mrvmaya.Scene.new(force=True)
	

class TestAnimationHanlde( TestBase ):
	
	def test_creatiion( self ):
		p = nodes.Node("persp")
		t = nodes.Node("topShape")
		
		# animation handle on non-animated nodes does not raise
		handle = AnimationHandle.create([p,t])
		assert isinstance(handle, AnimationHandle)
		assert isinstance(handle, nodes.Network)
		
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
		p = nodes.Node("persp")
		
		# translate is animated
		for tc in p.translate.getChildren():
			manim.MFnAnimCurve().create(tc)	
		# END set animation
		
		# test animation iteration
		alib = AnimInOutLibrary()
		for as_node in range(2):
			nc = 0
			target_type = nodes.api.MObject
			if as_node:
				target_type = nodes.Node
			# END define target type
			for anode in alib.get_animation(nodes.toSelectionList([p]), as_node):
				assert isinstance(anode, target_type)
				nc += 1
			# END for each anim node
			assert nc == 3
		# END for each as_node mode
		
		
		
	