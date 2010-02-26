# -*- coding: utf-8 -*-

#{ Initialization
def _assure_mayarv():
	"""Assure we have access to mayarv , bark nicely if this is not the case"""
	try:
		import mayarv
	except ImportError:
		raise ImportError("could not import mayarv, please make sure it exists in your PYTHONPATH")
	# END exception handling

#} END initilization

_assure_mayarv()

# import basic modules
from lib import *
from ui import *