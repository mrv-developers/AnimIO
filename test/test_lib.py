# -*- coding: utf-8 -*-
"""General library testing"""
from animIO.test.lib import *
from animIO import *

import mrv.test.maya as tmrv
import mrv.maya.nt as nt
import mrv.maya as mrvmaya

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
		p = nt.Node("persp")
		t = nt.Node("top")
		
		# animation handle on non-animated nodes does not raise
		handle = AnimationHandle.create()
		assert isinstance(handle, AnimationHandle)
		assert isinstance(handle, nt.Network)
		
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
				assert isinstance(source_plug, nt.api.MPlug)
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
				assert isinstance(plug.minput().mnode(), nt.AnimCurve)
		# END for each converter
		
		# test it breaks existing target animation
		assert isinstance(t.tx.minput().mnode(), nt.AnimCurve)
		p.tx.mconnectTo(t.tx)
		
		handle.apply_animation()
		assert isinstance(t.tx.minput().mnode(), nt.AnimCurve)
		
		# disconnected animation curve does not interrpt apply_animation
		t.ty.minput().mnode().message.mdisconnectNode(handle)
		t.ty.minput().mdisconnectNode(t)
		t.tz.minput().mdisconnectNode(t)
		handle.apply_animation()
		assert isinstance(t.tz.minput().mnode(), nt.AnimCurve)
		assert t.ty.minput().isNull()
		
		# cannot initialize von blank network node
		netw_node=nt.Network().object()
		self.failUnlessRaises(TypeError, AnimationHandle, netw_node)
		
	@with_scene('3handles.ma')
	def _test_iteration( self ):
		handles = list(AnimationHandle.iter_instances())
		assert len(handles) == 3
		for h in handles:
			assert isinstance(h, AnimationHandle)
			assert isinstance(h, nt.Network)
		# END for each handle
	
	@with_scene('blendNmute.ma')
	def _test_mute_and_blend( self ):
		self.fail("TODO")
		
	@with_scene('1still3moving.ma')
	def _test_export_import( self ):
		def iter_dag():
			return nt.iterDgNodes(nt.api.MFn.kDagNode, asNode=0)
			
		ah = AnimationHandle.create()
		ah.set_animation(iter_dag())
		
		# test iter_animation
		managed = len(list(ah.iter_animation(asNode=0)))
		assert managed == len(ah.affectedBy)
		
		# test iter_animtion return types
		assert isinstance(ah.iter_animation().next(), nt.Node)
		assert isinstance(ah.iter_animation(asNode=0).next(), nt.api.MObject) 
		
		# selection is maintained across exports
		slist = nt.toSelectionList(iter_dag())
		nt.select(slist)                           
		
		## EXPORT ##
		filename = ospath.join(tempfile.gettempdir(), "test_export2.ani.ma")
		assert filename == ah.to_file(filename, force=True, type="mayaAscii")
		
		# check if testselection is still alive
		assert len(slist)==len(nt.activeSelectionList())
		
		# AnimationHandle deletes correctly when not referenced
		ahname = ah.name()
		ah.delete()
		assert not ah.isValid()
		
		## IMPORT ##
		# try different namespaces - it should work no matter which namespace
		# is current
		namespaces=(":", "not:in:rootns", "not")
		# dummyAnimationHandle for iteration tests
		dummy=AnimationHandle()
		for namespace in namespaces:
			sns = Namespace.create(namespace)
			sns.setCurrent()
			
			# check return values of from_file and get AnimationHandle
			ahref, ahit = AnimationHandle.from_file(filename)
			assert isinstance(ahref, FileReference)
			
			loaded_ah = ahit.next()
			assert isinstance(loaded_ah, AnimationHandle)
			
			# expecting only one AnimationHandle from iterator (no dummyAnimationHandle)
			# which is in our scene already
			assert len(list(ahit)) == 0
			
			# check if AnimationHandle is the one we saved before
			loaded_ah_ns = loaded_ah.namespace()
			assert loaded_ah_ns + ahname == Namespace.rootpath + loaded_ah.name()
			
			# check if AnimationHandle is from file we wanted
			assert ospath.realpath(filename) == ospath.realpath(loaded_ah.referenceFile())
			
			# stored and loaded managed animCurves are in sync
			assert managed == len(loaded_ah.affectedBy) 
			
			# AnimationHandle deletes correctly when referenced
			loaded_ah.delete()
			assert not loaded_ah.isValid()
		# END test different namespaces
		
		os.remove(filename)
		
	@with_scene('1still3moving.ma')
	def test_copypaste( self ):
		ah = AnimationHandle.create()
		ah.set_animation(nt.it.iterDgNodes( nt.api.MFn.kTransform, asNode=0))
		
		ah.testAttr = "neueNamenBraucht das land"
		print "gespeichert wurde: %s" % ah.testAttr
		
		filename = ospath.join(tempfile.gettempdir(), "3movin_export.ani.ma")
		assert filename == ah.to_file(filename, force=True, type="mayaAscii")
		num_nodes=len(list(nt.it.iterDgNodes(asNode=0)))
		print "handling %i animationcurves of %i nodes in scene" % (len(ah.affectedBy), num_nodes)
		ah.copypaste_animation(predicate=lambda x:'Cube' in x)
		ah.delete()
		assert num_nodes -1 == len(list(nt.it.iterDgNodes(asNode=0)))
		
		ahb = AnimationHandle.from_file(filename)[1].next()
		print "after reload %i nodes in scene" % len(list(nt.it.iterDgNodes(asNode=0)))
		ahb.copypaste_animation(predicate=lambda x:'nurbs' in x, converter=lambda x:x.replace("Cube", "nurbs"))
					
class TestLibrary( TestBase ):
	
	def test_base( self ):
		pass	
	