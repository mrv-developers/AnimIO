# -*- coding: utf-8 -*-
""" Contains implementations of animation specific types and utilities """
__docformat__ = "restructuredtext"

import base
import maya.OpenMaya as api
import maya.OpenMayaAnim as apianim
import util

__all__ = ( "AnimCurve", )

class AnimCurve( base.DependNode ):
	"""Type representing a maya animation cuvrve, fixes existing MFnAnimCurve
	methods and provides new convenience methods as well"""

	@classmethod
	def findAnimation( cls, iter_nodes, asNode=True ):
		"""
		:return: list-compatible object containing animation curves attached to
			the nodes in the given object.
		:param iter_nodes: MSelection list or list of MObjects or Nodes containing
			whose animation you would like to retrieve.
		:param asNode: If True, the animation curves will be wrapped, or 
			MObjects otherwise ( to gain performance )"""
		selection_list = base.toSelectionList(iter_nodes)
		anim_plugs = api.MPlugArray()
		apianim.MAnimUtil.findAnimatedPlugs(selection_list, anim_plugs, False)
		
		# it will append to this array !
		objs = api.MObjectArray()
		for anim_plug in anim_plugs:
			apianim.MAnimUtil.findAnimation(anim_plug, objs)
		# END for each animated plug
		
		if asNode:
			return map(base.NodeFromObj, objs)
		else:
			return objs
		# END handle return type

	def getTangent( self, index, isInTangent ):
		"""
		:return: tuple(x,y) tuple containing the x and y positions of the 
			tangent at index:
			
			 * x is the x value of the slope of the tangent in seconds
			 * y is the absolute y value of the slope of the tangent
			 
		:param index: Index of the key for which the tangent x,y value is required
		:param isInTangent: If true, the in-tangent is returned, else, the out-tangent is returned"""
		return util.in_two_floats_out_tuple(lambda x, y: self._api_getTangent(index, x, y, isInTangent))
		
	def getTangentAsAngle(self, index, isInTangent):
		"""
		:return: tuple(MAngle, weight) tuple containing the angle and weight of
			the tangent. 
		:note: See `getTangent` for all other parameters"""
		sud = api.MScriptUtil()
		pd = sud.asDoublePtr()
		a = api.MAngle()
		
		self._api_getTangent(index, a, pd, isInTangent)
		return (a, sud.getDouble(pd))
	
