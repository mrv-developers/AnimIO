# -*- coding: utf-8 -*-
"""General library testing"""
from animIO.test.lib import *
from animIO import *

import mayarv.test.maya as tmrv
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
	
	def test_base( self ):
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
		
		# quick creation
		handle3=AnimationHandle()
		assert isinstance(handle3, AnimationHandle)
		assert handle3.isValid()
		
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
				plug.mdisconnectInput()
			# END disconnect anim curves
			
			handle.apply_animation(converter)
			if converter is not None:
				converter.make_assertion()
			# END handle converter
			
			for plug in anim_plugs:
				assert isinstance(plug.minput().mnode(), nodes.AnimCurve)
		# END for each converter
		
		# test it breaks existing target animation
		assert isinstance(t.tx.minput().mnode(), nodes.AnimCurve)
		p.tx.mconnectTo(t.tx)
		
		handle.apply_animation()
		assert isinstance(t.tx.minput().mnode(), nodes.AnimCurve)
		
		# disconnected animation curve does not interrpt apply_animation
		t.ty.minput().mnode().message.mdisconnectNode(handle)
		t.ty.minput().mdisconnectNode(t)
		t.tz.minput().mdisconnectNode(t)
		handle.apply_animation()
		assert isinstance(t.tz.minput().mnode(), nodes.AnimCurve)
		assert t.ty.minput().isNull()
		
		# cannot initialize von blank network node
		netw_node=nt.Network().object()
		self.failUnlessRaises(TypeError, AnimationHandle, netw_node)
		
		
	@with_scene('3handles.ma')
	def test_iteration( self ):
		handles = list(AnimationHandle.iter_instances())
		print "test_iteration is running\n"
		assert len(handles) == 3
		for h in handles:
			assert isinstance(h, AnimationHandle)
			assert isinstance(h, nodes.Network)
		# END for each handle
	
	@with_scene('blendNmute.ma')
	def _test_mute_and_blend( self ):
		self.fail("TODO")
		
	
	
	@with_scene('1still3moving.ma')
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
		managed = len(list(ah.iter_animation(asNode=0)))
		print "collecting %i nodes managing %i animation curves took %f s" % (numnodes, managed, elapsed)
		
		# test iter_animtion return types
		assert isinstance(ah.iter_animation().next(), nt.Node)
		assert isinstance(ah.iter_animation(asNode=0).next(), nt.api.MObject)
		
		# testselect some nodes
		slist = nodes.toSelectionList(iter_nuber_of_dagNodes(3))				
		nodes.api.MGlobal.setActiveSelectionList(slist)
		
		## EXPORT ##
		filename = ospath.join(tempfile.gettempdir(), "test_export2.ani.ma")
		assert filename == ah.to_file(filename, force=True, type="mayaAscii")
		
		# check if testselection is still alive
		slist_after=nodes.api.MSelectionList()
		nodes.api.MGlobal.getActiveSelectionList(slist_after)
		print "still %i nodes selected" % len(slist_after)
		assert len(slist)==len(slist_after)
		
		# removing AnimationHandle #
		ahname = ah.name()
		ah.delete()
		assert nodes.objExists(ahname) == 0 , "AnimationHandle is still existing"
		
		# dummyAnimationHandle for iteration tests
		dummy=AnimationHandle() 
		
		## IMPORT ##
		# try some cases
		namespaces=(":", "not:in:rootns", "not")
		for namespace in namespaces:
			sns = Namespace.create(namespace)
			sns.setCurrent()
			print "------------------test on namespace--%s---------------------" % Namespace.current()
			
			ahref, ahit = AnimationHandle.from_file(filename)
			assert isinstance(ahref, FileReference)
			
			loaded_ah= ahit.next()
			assert isinstance(loaded_ah, AnimationHandle)
			
			# expecting only one AnimationHandle form iterator (no dummyAnimationHandle)
			assert len(list(ahit)) == 0
		
			loaded_ah_ns = loaded_ah.namespace()
			assert loaded_ah_ns + ":" + ahname == ":" + loaded_ah.name()
			assert ospath.realpath(filename) == ospath.realpath(loaded_ah.referenceFile())
			
			loaded_nodes = list(loaded_ah_ns.iterNodes(depth=-1))
			print "namepace of Animhandle is %s and contains %i nodes" % (loaded_ah_ns,len(loaded_nodes))
			assert managed == len(loaded_ah.affectedBy) , "stored and loaded managed animCurves out of sync"
			
			loaded_ahname = loaded_ah.name()
			loaded_ah.delete()
			assert nodes.objExists(loaded_ahname) == 0 , "AnimationHandle is still existing"
		# END test different namespaces
		
	@with_scene('1still3moving.ma')
	def _test_copypaste( self ):
		ah = AnimationHandle.create()
		ah.set_animation(nodes.it.iterDgNodes( nodes.api.MFn.kTransform, asNode=0))
		
		ah.testAttr = "neueNamenBraucht das land"
		print "gespeichert wurde: %s" % ah.testAttr
		
		filename = ospath.join(tempfile.gettempdir(), "3movin_export.ani.ma")
		assert filename == ah.to_file(filename, force=True, type="mayaAscii")
		num_nodes=len(list(nodes.it.iterDgNodes(asNode=0)))
		print "handling %i animationcurves of %i nodes in scene" % (len(ah.affectedBy), num_nodes)
		ah.copypaste_animation(predicate=lambda x:'Cube' in x)
		ah.delete()
		assert num_nodes -1 == len(list(nodes.it.iterDgNodes(asNode=0)))
		
		ahb = AnimationHandle.from_file(filename)[1].next()
		print "after reload %i nodes in scene" % len(list(nodes.it.iterDgNodes(asNode=0)))
		ahb.copypaste_animation(predicate=lambda x:'nurbs' in x, converter=lambda x:x.replace("Cube", "nurbs"))
					
class TestLibrary( TestBase ):
	
	def test_base( self ):
		pass	
	