# -*- coding: utf-8 -*-
"""Performance Testing"""
from animIO.test.lib import *
from animIO import *

import mayarv.maya.nodes as nodes
import time
import sys

class TestPerformance( unittest.TestCase ):
	
	@with_scene('21kcurves.mb')
	def test_iter_animation(self):
		
		alib = AnimInOutLibrary()
		
		# TODO
