# -*- coding: utf-8 -*-
""" Contains implementations ( or improvements ) to mayas geometric shapes """
__docformat__ = "restructuredtext"

import base
from mrv.enum import (create as enum, Element as elm)
import maya.OpenMaya as api
import logging
log = logging.getLogger("mrv.maya.nt.geometry")

__all__ = ("GeometryShape", "DeformableShape", "ControlPoint", "SurfaceShape", 
	       "Mesh")

class GeometryShape( base.Shape ):	# base for epydoc !
	"""Contains common methods for all geometry types"""
	@undoable
	def copyLightLinks( self, other, **kwargs ):
		"""Copy lightlinks from one meshShape to another
		
		:param kwargs:
			 * substitute: 
			 	if True, default False, the other shape will be put
				in place of self, effectively receiving it's light-links whereas self losses
				them. This is practical in case you create a new shape below a transform that
				had a previously visible and manipulated shape whose external connections you
				wouuld like to keep"""
		def freeLogicalIndex( parent_plug ):
			""":return: a free parent compound index"""
			ilogical = parent_plug.logicalIndex()
			array_plug = parent_plug.array()
			num_elments = array_plug.numElements()


			# one of the logical indices must be the highest one - start searching
			# at the end of the physical array
			for iphysical in xrange( num_elments - 1, -1, -1 ):
				p_plug = array_plug[ iphysical ]
				try_index = p_plug.logicalIndex() + 1
				try_plug = array_plug.elementByLogicalIndex( try_index )

				if try_plug.child( 0 ).minput().isNull():
					return try_index
			# END endless loop

			raise AssertionError( "Did not find valid free index" )
		# END helper method

		substitute = kwargs.get( "substitute", False )
		for input_plug in self.message.moutputs():
			node = input_plug.mwrappedNode()
			if node.apiType() != api.MFn.kLightLink:
				continue

			# we are always connected to the object portion of the compound model
			# from there we can conclude it all
			parent_compound = input_plug.mparent()
			target_compound_index = -1
			if substitute:
				target_compound_index = parent_compound.logicalIndex()
			else:
				target_compound_index = freeLogicalIndex(parent_compound)
			# END get some logical index

			new_parent_compound = parent_compound.array().elementByLogicalIndex( target_compound_index )

			# retrieve light link, connect other - light is only needed if we do not
			# substitute
			if not substitute:
				light_plug = parent_compound.child( 0 ).minput()
				if not light_plug.isNull():
					light_plug.mconnectTo(new_parent_compound.child( 0 ), force=False)
				# END if lightplug is connected
			# END if no substitute required

			# connect object
			other.message.mconnectTo(new_parent_compound.child(1))


		# END for each output plug


class DeformableShape( GeometryShape ):	# base for epydoc !
	pass


class ControlPoint( DeformableShape ):		# base for epydoc !
	pass


class SurfaceShape( ControlPoint ):	# base for epydoc !
	pass


#{ Helpers 

class _SingleIndexedComponentGenerator(object):
	"""Utility producing components, initialized with the given indices. See `Mesh`
	for more info. """
	__slots__ = ('_mesh', '_component')
	# to detect slices, funny thing to remark: Maya passes 1 << 31 - 1 for some reason
	# we want to be smaller, hence -2
	_int32b = ( 1 << 31 ) - 2
	
	def __init__(self, mesh, component):
		self._mesh = mesh
		self._component = component
		
	def __getslice__(self, i, j):
		comp = self._mesh.component(self._component)
		# for some reason , python inside maya returns 31 bit ints to indicate 
		# slices, instead of sys.maxint. To be sure we handle all, we just 
		# check larger/than cases
		# handle [:] slices
		if j > self._int32b:
			comp.setComplete(1)
		else:
			comp.addElements(api.MIntArray.mfromRange(i, j))
		# END handle slice range 
		return comp
		
	def __getitem__(self, *args):
		comp = self._mesh.component(self._component)
		ia = None
		if len(args) == 1:
			arg = args[0]
			if hasattr(arg, 'next'):
				ia = api.MIntArray.mfromIter(arg)
			elif isinstance(arg, (list, tuple)):
				ia = api.MIntArray.mfromList(arg)
			elif isinstance(arg, api.MIntArray):
				ia = arg
			else:
				ia = api.MIntArray.mfromMultiple(arg)
			# END handle type
		else:
			ia = api.MIntArray.mfromList(args)
		# END handle args
		
		return comp.addElements(ia)
		
	def empty(self):
		""":return: empty component of our type"""
		return self._mesh.component(self._component)
		

class _SingleIndexedComponentIterator(_SingleIndexedComponentGenerator):
	"""Utility which produces iterators for the component type
	it was initialized with. As a bonus, it allows to return 
	quick constrained iterators using the slice and get-item notation"""
	__slots__ = tuple()
	
	def __iter__(self):
		return iter(self._get_complete_iterator())
	
	def _get_complete_iterator(self):
		return self._mesh.iterComponents(self._component)

	def _check_component(self):
		"""
		:raise NotImplementedError: if comp needs double-index component, our interface
			cannot support anything else than SingleIndex components"""
		if self._component == Mesh.eComponentType.uv:
			raise NotImplementedError("This Utility does not support iteration using \
				component-constrained iterators as it can only reproduce \
				SingleIndexedComponents - create the Component yourself and \
				use iterComponents to retrieve the iterator instead")
		
	def __getslice__(self, i, j):
		self._check_component()
		# skip full slices, as in fact no components are needed there.
		if j > self._int32b:
			return self._get_complete_iterator()
		# END handle [:] slice
		
		comp = super(_SingleIndexedComponentIterator, self).__getslice__(i,j)
		return self._mesh.iterComponents(self._component, comp)
		
	def __getitem__(self, *args):
		self._check_component()
		comp = super(_SingleIndexedComponentIterator, self).__getitem__(*args)
		return self._mesh.iterComponents(self._component, comp) 
		
		
	def iterator(self):
		""":return: Iterator for all components in the mesh"""
		return self._get_complete_iterator()
		
	# shortcut alias
	iter = property(iterator)
		
#} END helpers 


class Mesh( SurfaceShape ):		# base for epydoc !
	"""Implemnetation of mesh related methods to make its handling more
	convenient
	
	**Component Access**:
	
		>>> m.cvtx[:]                   # a complete set of components
		>>> m.cvtx[1:4]                 # initialized with 3 indices
		>>> m.cvtx[1]                   # initialized with a single index
		>>> m.cvtx[1,2,3]               # initialized with multiple indices
		>>> m.cf[(1,2,3)]               # initialized with list or tuple
		>>> m.ce[iter(1,2,3)]           # initialized from iterator
		>>> m.ce[api.MIntArray()]       # initialized from MIntArray
		
	"""
	# component types that make up a mesh
	eComponentType = enum( elm("vertex", api.MFn.kMeshVertComponent), 
							elm("edge", api.MFn.kMeshEdgeComponent ), 
							elm("face", api.MFn.kMeshPolygonComponent ), 
							elm("uv", api.MFn.kMeshMapComponent ) )

	#{ Iterator Shortcuts
	def _make_component_getter(cls, component):
		def internal(self):
			return cls(self, component)
		# END internal method
		return internal
	# END pseudo-decorator
	
	# SETUP ITERATOR SHORTCUTS
	for shortname, component in zip(('vtx', 'e', 'f', 'map'), eComponentType):
		locals()[shortname] = property(_make_component_getter(_SingleIndexedComponentIterator, component))
		
	# SETUP COMPONENT SHORTCUTS
	for shortname, component in zip(('cvtx', 'ce', 'cf', 'cmap'), eComponentType):
		locals()[shortname] = property(_make_component_getter(_SingleIndexedComponentGenerator, component))
	
	#} END iterator shortcuts

	#{ Utilities

	def copyTweaksTo( self, other ):
		"""Copy our tweaks onto another mesh
		
		:note: we do not check topology for maximum flexibility"""
		opnts = other.pnts
		pnts = self.pnts
		for splug in pnts:
			opnts.elementByLogicalIndex( splug.logicalIndex() ).msetMObject( splug.asMObject() )
		# END for each source plug in pnts

	def isValidMesh( self ):
		"""
		:return: True if we are nonempty and valid - emptry meshes do not work with the mfnmesh
			although it should ! Have to catch that case ourselves"""
		try:
			self.numVertices()
			return True
		except RuntimeError:
			return False

	@undoable
	def copyAssignmentsTo( self, other, **kwargs ):
		"""Copy set assignments including component assignments to other
		
		:param kwargs: passed to set.addMember, additional kwargs are:
			 * setFilter: default is fSetsRenderable"""
		setFilter = kwargs.pop( "setFilter", base.Shape.fSetsRenderable )
		for sg, comp in self.componentAssignments( setFilter = setFilter ):
			sg.addMember( other, comp, **kwargs )


	@undoable
	def resetTweaks( self, tweak_type = eComponentType.vertex, keep_tweak_result = False ):
		"""Reset the tweaks on the given mesh shape
		
		:param tweak_type: the component type(s) whose tweaks are to be removed,
			valid values are 'vertex' and 'uv' members of the eComponentType enumeration. 
			Pass in a scalar value or a list of tweak types
		:param keep_tweak_result: if True, the effect of the tweak will be kept. If False,
			it will be removed. What actually happens depends on the context
			
			* [referenced] mesh *without* history:
				copy outMesh to inMesh, resetTweaks
				
				if referenced, plenty of reference edits are generated, ideally one operates
				on non-referenced geomtry
			   
			* [referenced] mesh *with* history:
			 	put tweakNode into mesh history, copy tweaks onto tweak node
		:note: currently vertex and uv tweaks will be removed if keep is enabled, thus they must
			both be specified"""
		check_types = ( isinstance( tweak_type, ( list, tuple ) ) and tweak_type ) or [ tweak_type ]
		type_map = {
							self.eComponentType.vertex : ( "pnts", api.MFnNumericData.k3Float, "polyTweak", api.MFn.kPolyTweak, "tweak" ),
							self.eComponentType.uv : ( "uvpt", api.MFnNumericData.k2Float, "polyTweakUV", api.MFn.kPolyTweakUV, "uvTweak" )
					}

		mia = api.MIntArray()
		for reset_this_type in check_types:
			try:
				attrname, datatype, tweak_node_type, tweak_node_type_API, tweakattr = type_map[ reset_this_type ]
			except KeyError:
				raise ValueError( "Tweak type %s is not supported" % reset_this_type )

			# KEEP MODE
			#############
			if keep_tweak_result:
				input_plug = self.inMesh.minput()

				# history check
				if input_plug.isNull():
					# assert as we had to make the handling much more complex to allow this to work right as we copy the whole mesh here
					# containing all tweaks , not only one type
					if not ( self.eComponentType.vertex in check_types and self.eComponentType.uv in check_types ):
						log.warn("Currently vertex AND uv tweaks will be removed if a mesh has no history and a reset is requested")
					# END print warning

					# take the output mesh, and stuff it into the input, then proceed
					# with the reset. This implies that all tweaks have to be removed
					out_mesh = self.outMesh.asMObject()
					self.inMesh.msetMObject( out_mesh )
					self.cachedInMesh.msetMObject( out_mesh )

					# finally reset all tweeaks
					return self.resetTweaks( check_types, keep_tweak_result = False )
				else:
					# create node of valid type
					tweak_node = input_plug.mwrappedNode()

					# create node if there is none as direct input
					if not tweak_node.hasFn( tweak_node_type_API ):
						tweak_node = base.createNode( "polyTweak", tweak_node_type, forceNewLeaf = 1  )

						# hook the node into the history
						input_plug.mconnectTo(tweak_node.inputPolymesh)
						tweak_node.output.mconnectTo(self.inMesh)

						# setup uvset tweak location to tell uvset where to get tweaks from
						if tweak_node_type_API == api.MFn.kPolyTweakUV:
							names = list()
							self.getUVSetNames( names )
							index = names.index( self.currentUVSetName( ) )

							own_tweak_location_plug = self.uvSet.elementByLogicalIndex( index ).mchildByName('uvSetTweakLocation')
							tweak_node.uvTweak.elementByLogicalIndex( index ).mconnectTo(own_tweak_location_plug)
						# END uv special setup
					# END create tweak node

					dtweak_plug = tweak_node.findPlug(tweakattr)
					stweak_plug = self.findPlug(attrname)

					# copy the tweak values - iterate manually as the plug tends to
					# report incorrect values if history is present - its odd
					stweak_plug.evaluateNumElements()
					
					mia.clear()
					stweak_plug.getExistingArrayAttributeIndices(mia)
					for i in mia:
						try:
							tplug = stweak_plug.elementByLogicalIndex(i)
						except RuntimeError:
							continue
						else:
							dtweak_plug.elementByLogicalIndex(i).msetMObject(tplug.asMObject())
						# END exception handling
					# END for each tweak plug

					# proceed with reset of tweaks
					pass
				# END history handling
			# END keep tweak result handling

			arrayplug = self.findPlug(attrname)
			dataobj = api.MFnNumericData().create( datatype )

			# reset values, do it for all components at once using a data object
			try:
				for p in arrayplug:
					p.msetMObject( dataobj )
			except RuntimeError:
				# especially uvtweak array plugs return incorrect lengths, thus we may
				# fail once we reach the end of the iteration.
				# uvpt appears to display a lenght equalling the number of uvpoints in the mesh
				# possibly only for the current uvset
				pass
		# END for tweak type to reset
		
	def component(self, component_type):
		""":return: A component object able to hold the given component type
		:param component_type: a member of the `eComponentType` enumeration"""
		if component_type not in self.eComponentType:
			raise ValueError("Invalid component type")
		return base.SingleIndexedComponent.create(component_type.value())
		# END handle face-vertex components
		
	#} END utilities
		
	#{ Iterators 
	def iterComponents(self, component_type, component=api.MObject()):
		"""
		:return: MItIterator matching your component_type to iteartor over items
			on this mesh
		:param component_type: 
		 * vertex -> MItMeshVertex
		 * edge -> MItMeshEdge
		 * face -> MItMeshPolygon
		 * uv -> MItMeshFaceVertex
		:param component: if not kNullObject, the iterator returned will be constrained
			to the given indices as described by the Component. Use `component` to retrieve 
			a matching component type's instance"""
		if component_type not in self.eComponentType:
			raise ValueError("Invalid component type")
			
		ec = self.eComponentType
		it_type = { 	ec.vertex : api.MItMeshVertex,
						ec.edge   : api.MItMeshEdge, 
						ec.face   : api.MItMeshPolygon, 
						ec.uv     : api.MItMeshFaceVertex}[component_type] 
		
		return it_type(self.dagPath(), component)
		
	#} END iterators 

	#( iDuplicatable
	def copyFrom( self, other, *args, **kwargs ):
		"""Copy tweaks and sets from other onto self
		
		:param kwargs:
			 * setFilter: if given, default is fSets, you may specify the types of sets to copy
						if None, no set conenctions will be copied """
		other.copyTweaksTo( self )

		setfilter = kwargs.pop( "setFilter", Mesh.fSets )		# copy all sets by default
		if setfilter is not None:
			other.copyAssignmentsTo( self, setFilter = setfilter )

	#) END iDuplicatable
