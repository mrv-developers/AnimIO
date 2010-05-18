# -*- coding: utf-8 -*-
"""Contains all test related startup routines"""

import os
import sys

import mrv.test.cmd as mrvtestcmd

#{ Startup

def nose():
	"""Initialize nose"""
	# It is possible to pass additional args which we append to the system args.
	# This is required in case we start nose in maya UI mode and want to pass
	# nose specific arguments
	if mrvtestcmd.env_nose_args in os.environ:
		sys.argv = ['nosetests'] + os.environ[mrvtestcmd.env_nose_args].split(mrvtestcmd.nose_args_splitter)
	# END handle extra args
	
	import nose
	nose.main()

#} END startup
