# -*- coding: utf-8 -*-
"""Module importing all maya related classes into one place

:note: It will not import anything if the sphinx build system is active as it 
	will take too much memory ( ~2gig )"""
__docformat__ = "restructuredtext"
import sys
skip_import = sys.modules.has_key('sphinx')

if not skip_import:
	# maya 
	from env import *
	from ns import *
	from ref import *
	from scene import *
	from undo import *
	
	# nodes
	from nt import *
	
	if not cmds.about(batch=1):
		from ui import *
	# END selective ui import
# END selective import
