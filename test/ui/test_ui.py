# -*- coding: utf-8 -*-
from animio.test.lib import *
from animio.ui import *
import tempfile

from mrv.maya import Scene
import mrv.maya.nt as nt
from mrv.maya.ns import Namespace, RootNamespace
from mrv.path import Path

import maya.cmds as cmds
from maya.utils import executeDeferred

class TestGeneralUI( unittest.TestCase ):
	
	_export_to_file = None
	_orig_fileDialog = None
	
	@classmethod
	def _mock_file_browser(cls, **kwargs):
		"""Simple mock returning a file we defined beforehand"""
		return cls._export_to_file
	
	def _set_export_file(self):
		"""Set the public export file to something new and return it.
		The returned Path does not exist as file."""
		# prepare mock
		type(self)._export_to_file = tempfile.mkstemp('.ma')[1]
		exp_file = Path(self._export_to_file)
		return exp_file.remove()		# just keep the path
	
	def test_user_interface( self ):
		if cmds.about( batch=1 ):
			return
		
		Scene.open(fixture_path('1still3moving.ma'), force=1)
		
		exp_file = self._set_export_file()
		
		# show UI
		awin = AnimIO_UI().show()
		ectrl = awin.main.exportctrl
		
		# TEST EXPORT 
		# nothing selected in UI - failure
		ectrl.nodeselector.set_uses_selection(False)
		ectrl.nodeselector.set_uses_selection(False)
		self.failUnlessRaises(ValueError, ectrl._on_export, None)
		assert not exp_file.isfile()
		

		# should use selected nodes, but there is no one selected in the scene
		ectrl.nodeselector.set_uses_selection(True)
		ectrl.nodeselector.set_uses_selection(True)
		self.failUnlessRaises(ValueError, ectrl._on_export, None)
		assert not exp_file.isfile()
		
		
		# something with keys is selected
		nt.select('coneAnimated')
		ectrl._on_export(None)
		assert exp_file.isfile()
		cone_anim_file = exp_file
		
		# TODO: reapply it to the same item without animation
		# for simplicity we just
		
		
		# TEST NAMESPACES
		Scene.open(fixture_path('3moving3namespaces.ma'), force=1)
		assert Scene.name() == fixture_path('3moving3namespaces.ma')
		
		# nodeselector should have 4 namespaces now, but no one is selected
		assert len(ectrl.nodeselector.selected_namespaces()) == 0
		
		# but it displays them
		assert ectrl.nodeselector.p_numberOfItems == 4	 # 3 ns + 1 sel nodes
		
		# select namespaces, retrieve them
		all_ns = RootNamespace.children()
		ectrl.nodeselector.select_namespaces(all_ns)
		assert all_ns == ectrl.nodeselector.selected_namespaces()
		assert ectrl.nodeselector.uses_selection()
		
		# export to namespaces
		exp_file = self._set_export_file()
		ectrl._on_export(None)
		assert exp_file.isfile()
		
		
		# TODO: reimport the file with namespaces, test filters and converters
		
		
		
		cmds.fileDialog = self._orig_fileDialog
		cone_anim_file.remove()
		executeDeferred(lambda: cmds.quit(force=1))
		
# apply mock 
TestGeneralUI._orig_fileDialog = cmds.fileDialog
cmds.fileDialog = TestGeneralUI._mock_file_browser

