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
	

class TestAnimationHandle( TestBase ):
	
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
		pass	
	