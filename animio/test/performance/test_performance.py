# -*- coding: utf-8 -*-
"""Performance Testing"""
from animio.test.lib import *
from animio.lib import *

import mrv.maya.nt as nt

import maya.OpenMayaAnim as apianim 

import time
import sys

class TestPerformance( unittest.TestCase ):
	
	@with_scene('21kcurves.mb')
	def test_anim_handle(self):
		# manage all anim nt
		ah = AnimationHandle.create()
		ahapi = ah.object()
		
		st = time.time()
		is_not_ah = lambda n: n != ahapi
		sellist = nt.toSelectionList(nt.it.iterDgNodes(asNode=False, predicate=is_not_ah))
		ah.set_animation(sellist)
		elapsed = time.time() - st
		print >>sys.stderr, "Managed animation of roughly 21k nodes in %f s" % elapsed
		
		
		# apply animation, worst case ( as it is already connected )
		st = time.time()
		ah.apply_animation()
		elapsed = time.time() - st
		print >>sys.stderr, "Re-Applied animation onto same existing animation of roughly 21k nodes in %f s" % elapsed
		
		# clear animation
		st = time.time()
		pa = nt.api.MPlugArray()
		apianim.MAnimUtil.findAnimatedPlugs(sellist, pa)
		
		# do it the fast way - its easier to use mrv, but much faster to do it 
		# directly
		mod = nt.api.MDGModifier( )
		for anim_plug in pa:
			mod.disconnect(anim_plug.minput(), anim_plug )
		# END for each anim curve to disconnect
		mod.doIt()
		elapsed = time.time() - st
		print >>sys.stderr, "Cleared animation on %i plugs in %f s" % (len(pa), elapsed)
		
		assert len(nt.AnimCurve.findAnimation(sellist)) == 0
		
		# apply animation, best case as it is not yet connected
		st = time.time()
		ah.apply_animation()
		elapsed = time.time() - st
		print >>sys.stderr, "Applied animation of roughly 21k nodes in %f s" % elapsed
		
		
		
