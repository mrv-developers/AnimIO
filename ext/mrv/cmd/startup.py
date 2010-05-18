# -*- coding: utf-8 -*-
"""Contains routines to startup individual programs"""
__docformat__ = "restructuredtext"

import sys
import os


#{ IPython 

def ipython_apply_user_configuration():
	"""Run optional user scripts"""
	# try to load custom settings
	if "IMRV_CONFIG" in os.environ:
		filepath = os.environ[ "IMRV_CONFIG" ]
		try:
			execfile( filepath )
		except Exception:
			print "Failed to run configuration script"
	else:
		print "Set IMRV_CONFIG to point to python script doing additional setup"

def ipython_setup_mrv():
	"""Initialize MRV"""
	# configure MRV
	# as IPython is some sort of interactive mode, we load the user preferences
	for var in ( 	'MRV_STANDALONE_AUTOLOAD_PLUGINS', 
					'MRV_STANDALONE_INIT_OPTIONVARS', 
					'MRV_STANDALONE_RUN_USER_SETUP' ): 
		os.environ[var] = "1"
	# END env var loop
	
	# init maya
	import mrv.maya
	

def ipython_setup():
	"""Perform additional ipython initialization"""
	import IPython
	import logging
	
	# make default imports
	ip = IPython.ipapi.get()
	ip.ex("from mrv.maya.all import *")
	
	# init logging
	logging.basicConfig(level=logging.INFO)
	
	# prefetch methods for convenience
	import mrv.maya.nt.typ as typ
	typ.prefetchMFnMethods()

# } END initialization


#} END ipython

#{ Startup

def mrv(args, args_modifier=None):
	"""Prepare the environment to allow the operation of maya
	:param args_modifier: Function returning a possibly modified argument list. The passed 
		in argument list was parsed already to find and extract the maya version. 
		Signature: ``arglist func(arglist, maya_version, start_maya)
		If start_maya is True, the process to be started will be maya.bin, not the 
		python interpreter. If maya_version is 0, the process will continue execution
		within this python interpreter which is assured to have mrv facilities availble 
		which do not require maya."""
	import mrv.cmd
	import mrv.cmd.base as cmdbase
	
	# handle special arguments
	config = [False, False, False]
	lrargs = list(args)
	for i, flag in enumerate((mrv.cmd.mrv_ui_flag,
							  mrv.cmd.mrv_mayapy_flag, 
							  mrv.cmd.mrv_nomaya_flag)):
		try:
			lrargs.remove(flag)
			config[i] = True
		except ValueError:
			pass
		# HANDLE maya in UI mode
	# END for each flag to handle
	start_maya, mayapy_only, no_maya = config
	rargs = lrargs
	
	if no_maya and ( start_maya or mayapy_only ):
		raise EnvironmentError("If %s is specified, %s or %s may not be given as well" % (mrv.cmd.mrv_nomaya_flag, mrv.cmd.mrv_ui_flag, mrv.cmd.mrv_mayapy_flag))
	
	if not no_maya:
		maya_version, rargs = cmdbase.init_environment(rargs)
	else:
		maya_version = 0.0
	# EMD initialize maya if required
	
	rargs = list(args_modifier(tuple(rargs), maya_version, start_maya))
	if no_maya:
		# parse the option ourselves, the optparse would throw on unknown opts
		remaining_args = list()
		eval_script = None
		module = None
		while rargs:
			arg = rargs.pop(0)
			if arg == '-c':
				eval_script = rargs.pop(0)
			elif arg == '-m':
				module = rargs.pop(0)
			else:
				remaining_args.append(arg)
			# END handle flags
		# END for each arg
		
		# overwrite our own sys.args with our parsed arguments
		arg0 = sys.argv[0]
		del(sys.argv[:])
		sys.argv.extend([arg0] + remaining_args)
		
		if eval_script:
			exec(eval_script)
		elif module:
			__import__(module)
		else:
			raise EnvironmentError("Please specify '-c CMD' or '-m MODULE' to indicate which code to execute")
		# END handle flags
		
	else:
		if start_maya:
			cmdbase.exec_maya_binary(rargs, maya_version)
		else:
			cmdbase.exec_python_interpreter(rargs, maya_version, mayapy_only)
		# END handle process to start
	# END handle flags
	
def imrv():
	"""Get the main ipython system up and running"""
	ipython_setup_mrv()

	# init ipython - needs to be available in your local python installation
	try: 
		import IPython
	except Exception, e:
		raise ImportError("Warning: Failed to load ipython - please install it for more convenient maya python interaction: %s" % str(e))
	# END exception handling
	
	ips = IPython.Shell.start()
	ipython_setup()
	ipython_apply_user_configuration()
	ips.mainloop()

#} END startup

