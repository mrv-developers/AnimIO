# -*- coding: utf-8 -*-
from animIO.test.lib import *
from animIO import *

from mrv.maya import Scene
import maya.cmds as cmds

def fixture_base():
	return os.path.abspath(os.path.join( os.path.dirname(__file__), "../fixtures"))

class TestGeneralUI( unittest.TestCase ):
	def test_something( self ):
		if cmds.about( batch=1 ):
			return
		
		Scene.open(fixture_path("1still3moving.ma"), force=True)
		
		AnimIO_UI().show()
		
if __name__ == "__main__":
	unittest.main()
		
