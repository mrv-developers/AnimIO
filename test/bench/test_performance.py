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
		
		# get all nodes, get all animation from them
		for as_node in range(2):
			# find animation
			st = time.time()
			sel_list = nodes.toSelectionList(nodes.it.iterDgNodes(asNode=False))
			anim_nodes = alib.get_animation(sel_list, as_node)
			num_nodes = len(anim_nodes)
			elapsed = time.time() - st
			print >>sys.stderr, "Found %i animation nodes ( as_node=%i ) in %f s ( %f anim nodes / s )" % (num_nodes, as_node, elapsed, num_nodes/elapsed)
			
			# make selection list
			st = time.time()
			anim_sel_list = nodes.toSelectionList(anim_nodes)
			elapsed = time.time() - st
			print >>sys.stderr, "Convenient Selection List Creation: %f s" % elapsed
			
			# make selection list manually 
			st = time.time()
			anim_sel_list = nodes.api.MSelectionList()
			if as_node:
				for an in anim_nodes:
					anim_sel_list.add(an.getApiObject())
				# END for each animation node
			else:
				for apian in anim_nodes:
					anim_sel_list.add(apian)
				# END for each animation node
			# END handle as_node
			elapsed = time.time() - st
			print >>sys.stderr, "Optimized Selection List Creation: %f s" % elapsed
			
			st = time.time()
			nodes.api.MGlobal.setActiveSelectionList(anim_sel_list)
			elapsed = time.time() - st
			print >>sys.stderr, "Setting Selection List as Maya-Selection: %f s" % elapsed
		# END for each as_node value
		
		
		# compare to plain mel 
		melcmd = """select( ls("-typ", "animCurve", (listConnections ("-s", 1, "-d", 0, "-scn", 1, "-t", "animCurve", ls()))) )"""
		st = time.time()
		nodes.api.MGlobal.executeCommand(melcmd, False, False)
		elapsed = time.time() - st
		print >>sys.stderr, "MEL: Get animation of all nodes and select the animcurves: %f s" % elapsed
		
