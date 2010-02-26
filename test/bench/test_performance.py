# -*- coding: utf-8 -*-
"""Performance Testing"""
from animIO.test.lib import *
from animIO import *

import mayarv.maya.nodes as nodes
import time
import sys

class TestPerformance( unittest.TestCase ):
	
	@with_scene('21kcurves.mb')
	def test_anim_handle(self):
		# manage all anim nodes
		ah = AnimationHandle.create()
		st = time.time()
		ah.set_animation(nodes.it.iterDgNodes(asNode=False))
		elapsed = time.time() - st
		print >>sys.stderr, "Managed animation of roughly 21k nodes in %f s" % elapsed
