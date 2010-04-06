# -*- coding: utf-8 -*-
from animio.test.lib import *
from animio import *
import tempfile

from mrv.maya import Scene
import mrv.maya.nt as nt
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
	
	@with_scene('1still3moving.ma')
	def test_user_interface( self ):
		if cmds.about( batch=1 ):
			return
		
		# prepare mock
		type(self)._export_to_file = tempfile.mkstemp('.ma')[1]
		exp_file = Path(self._export_to_file)
		exp_file.remove()		# just keep the path
		
		# show UI
		awin = AnimIO_UI().show()
		ectrl = awin.main.exportctrl
		
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
		
		
		# and reapply it to the same item without animation
		# for simplicity we just 
		
		
		
		cmds.fileDialog = self._orig_fileDialog
		exp_file.remove()
		executeDeferred(lambda: cmds.quit(force=1))
		
# apply mock 
TestGeneralUI._orig_fileDialog = cmds.fileDialog
cmds.fileDialog = TestGeneralUI._mock_file_browser

