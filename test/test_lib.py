# -*- coding: utf-8 -*-
"""General library testing"""
from animIO.test.lib import *
from animIO import *

import mayarv.maya.nt as nodes
import mayarv.maya as mrvmaya

import maya.OpenMayaAnim as manim
import time
import tempfile
import os.path as ospath

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
	
	def _test_base( self ):
		p = nodes.Node("persp")
		t = nodes.Node("top")
		
		print "test_base is running\n"
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
		
#	@with_scene('3handles.ma')
	def _test_iteration( self ):
		handles = list(AnimationHandle.iter_instances())
		print "test_iteration is running\n"
		assert len(handles) == 3
		for h in handles:
			assert isinstance(h, AnimationHandle)
			assert isinstance(h, nodes.Network)
		# END for each handle
	
	@with_scene('21kcurves.mb')
	def test_export_import( self ):
		# create AnimationHAndle and manage some nodes
		ah = AnimationHandle.create()
		
		def iter_nuber_of_dagNodes(max):
			itlist = nodes.it.iterDgNodes( nodes.api.MFn.kDagNode, asNode=0)
			for i in range(0, max):
				yield itlist.next()
		# END iterating a limited number of DagNodes		
		 
		numnodes = 25
		st = time.time()
		ah.set_animation(iter_nuber_of_dagNodes(numnodes))
		elapsed = time.time() - st
		managed = len(ah.affectedBy)
		print "collecting %i nodes managing %i animation curves took %f s" % (numnodes, managed, elapsed)
		
		# testselect some nodes
		slist = nodes.toSelectionList(iter_nuber_of_dagNodes(3))				
		nodes.api.MGlobal.setActiveSelectionList(slist)
		
		## EXPORT ##
		filename = ospath.join(tempfile.gettempdir(), "test_export.ani.ma")
		assert filename == ah.to_file(filename, force=True, type="mayaAscii")
		
		# check if testselection is still alive
		slist_after=nodes.api.MSelectionList()
		nodes.api.MGlobal.getActiveSelectionList(slist_after)
		print "still %i nodes selected" % len(slist_after)
		assert len(slist)==len(slist_after)
		
		# removing AnimationHandle #
		ahname = ah.name()
		ah.unload()
		assert nodes.objExists(ahname) == 0 , "AnimationHandle is still existing"
		
		## IMPORT ##
		def importhandle(i_filename, compare_to, namespace):
			sns = Namespace.create(namespace)
			sns.setCurrent()
			print "------------------test on namespace--%s---------------------" % Namespace.getCurrent()
			loaded_ah = AnimationHandle.from_file(i_filename)[0]
			assert isinstance(loaded_ah, AnimationHandle)
		
			# get namespace of AnimationHandle
			ah_ns = loaded_ah.getNamespace()
			
			# give some feedback
			loaded = list(ah_ns.iterNodes(depth=-1))
			
			print "AnimationHandle named %s found" % loaded_ah
			assert ospath.realpath(i_filename) == ospath.realpath(loaded_ah.getReferenceFile())
			print "namepace of Animhandle is %s and contains %i nodes" % (ah_ns,len(loaded))
			print "%i animCurves saved before, now loaded %i" % (compare_to, len(loaded_ah.affectedBy))
			assert compare_to == len(loaded_ah.affectedBy) , "stored and loaded managed animCurves out of sync"
			print "current namespace is %s containing %i nodes" % (Namespace.getCurrent(), len(loaded))
			
			lahname = loaded_ah.name()
			loaded_ah.unload()
			assert nodes.objExists(lahname) == 0 , "AnimationHandle is still existing"
				
		# imort in root namespace, subns and try none existing filename
		importhandle(filename, managed, Namespace.root)
		importhandle(filename, managed, "in:meiner:Dose")
		self.failUnlessRaises(IOError,  importhandle, "not_existing.ma", managed, ":")
		
			
class TestLibrary( TestBase ):
	
	def test_base( self ):
		pass	
	