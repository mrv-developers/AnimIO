#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forward the call to mrv's setup routine"""
import os
__docformat__ = "restructuredtext"


#{ Initialization
def include_setup_py():
	"""#import mrvs setup.py"""
	# project/setup.py -> project/ext/mrv/setup.py
	setuppath = os.path.join(os.path.dirname(os.path.realpath(os.path.abspath(__file__))) , 'ext', 'mrv', 'setup.py')
	
	try:
		execfile(setuppath, globals())
	except Exception, e:
		# lets show the original error
		print "Could not execute setup.py at %r" % setuppath
		raise
	# END exception handling

# main will be executed automatically
include_setup_py()
