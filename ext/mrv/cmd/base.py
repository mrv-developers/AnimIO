# -*- coding: utf-8 -*-
"""Contains routines required to initialize mrv"""
import os
import sys
import subprocess
from mrv.path import Path

__docformat__ = "restructuredtext"

__all__ = ( 'is_supported_maya_version', 'python_version_of', 'parse_maya_version', 'update_env_path', 
			'maya_location', 'update_maya_environment', 'exec_python_interpreter', 
			'exec_maya_binary', 'available_maya_versions', 'python_executable', 'find_mrv_script' )

#{ Globals
maya_to_py_version_map = {
	8.5 : 2.4, 
	2008: 2.5, 
	2009: 2.5, 
	2010: 2.6,
	2011: 2.6
}

#} END globals


#{ Maya-Intiialization
	
def is_supported_maya_version(version):
	""":return: True if version is a supported maya version
	:param version: float which is either 8.5 or 2008 to 20XX"""
	if version == 8.5:
		return True
		
	return str(version)[:2] == "20"
	
def parse_maya_version(arg, default):
	""":return: tuple(bool, version) tuple of bool indicating whether the version could 
	be parsed and was valid, and a float representing the parsed or default version.
	:param default: The desired default maya version"""
	try:
		candidate = float(arg)
		if not is_supported_maya_version(candidate):
			# in that case, we don't claim the arg and just use the default
			return (False, default)
		# END verify version
		return (True, candidate)
	except ValueError:
		return (False, default)
	# END exception handling
	
def python_version_of(maya_version):
	""":return: python version matching the given maya version
	:raise EnvironmentError: If there is no known matching python version"""
	try:
		return maya_to_py_version_map[maya_version]
	except KeyError:
		raise EnvironmentError("Do not know python version matching the given maya version %g" % maya_version) 
	
def update_env_path(environment, env_var, value, append=False):
	"""Set the given env_var to the given value, but append the existing value
	to it using the system path separator
	
	:param append: if True, value will be appended to existing values, otherwise it will 
		be prepended"""
	curval = environment.get(env_var, None)
	# rule out empty strings
	if curval:
		if append:
			value = curval + os.pathsep + value
		else:
			value = value + os.pathsep + curval
		# END handle append
	# END handle existing value
	environment[env_var] = value

def available_maya_versions():
	""":return: list of installed maya versions which are locally available - 
	they can be used in methods that require the maya_version to be given. 
	Versions are ordered such that the latest version is given last."""
	versions = list()
	for version_candidate in sorted(maya_to_py_version_map.keys()):
		try:
			loc = maya_location(version_candidate)
			versions.append(version_candidate)
		except Exception:
			pass
		# END check maya location
	# END for each version
	return versions

def maya_location(maya_version):
	""":return: string path to the existing maya installation directory for the 
	given maya version
	:raise EnvironmentError: if it was not found"""
	mayaroot = None
	suffix = ''
	
	if sys.platform.startswith('linux'):
		mayaroot = "/usr/autodesk/maya"
		if os.path.isdir('/lib64'):
			suffix = "-x64"
		# END handle 64 bit systems
	elif sys.platform == 'darwin':
		mayaroot = "/Applications/Autodesk/maya"
	elif sys.platform.startswith('win'):
		# try to find it in all kinds of program files, prefer 64 bit versions
		tried_paths = list()
		for envvar in ('PROGRAMW6432', 'PROGRAMFILES','PROGRAMFILES(X86)'):
			if envvar not in os.environ: 
				continue
			basepath = Path(os.environ[envvar]) / "Autodesk"
			if basepath.isdir():
				mayaroot = basepath / 'Maya'
				break
			# END if we have found Autodesk installations
			tried_paths.append(basepath)
		# END for each envvar
		if mayaroot is None:
			raise EnvironmentError("Could not find any maya installation, searched %s" % (', '.join(tried_paths)))
	# END os specific adjustments
	
	if mayaroot is None:
		raise EnvironmentError("Current platform %r is unsupported" % sys.platform)
	# END assure existance of maya root
	
	mayalocation = "%s%g%s" % (mayaroot, maya_version, suffix)
	
	# OSX special handling
	if sys.platform == 'darwin':
		mayalocation=os.path.join(mayalocation, 'Maya.app', 'Contents')
	
	if not os.path.isdir(mayalocation):
		raise EnvironmentError("Could not find maya installation at %r" % mayalocation)
	# END verfy maya location
	
	return mayalocation
	
def update_maya_environment(maya_version):
	"""Configure os.environ to allow Maya to run in standalone mode
	:param maya_version: The maya version to prepare to run, either 8.5 or 2008 to 
	20XX. This requires the respective maya version to be installed in a default location.
	:raise EnvironmentError: If the platform is unsupported or if the maya installation could not be found"""
	py_version = python_version_of(maya_version)
	
	pylibdir = None
	envppath = "PYTHONPATH"
	
	if sys.platform.startswith('linux'):
		pylibdir = "lib"
	elif sys.platform == 'darwin':
		pylibdir = "Frameworks/Python.framework/Versions/Current/lib"
	elif sys.platform.startswith('win'):
		pylibdir = "Python"
	# END os specific adjustments
	
	
	# GET MAYA LOCATION
	###################
	mayalocation = maya_location(maya_version)
	
	if not os.path.isdir(mayalocation):
		raise EnvironmentError("Could not find maya installation at %r" % mayalocation)
	# END verfy maya location
	
	
	env = os.environ
	
	# ADJUST LD_LIBRARY_PATH or PATH
	################################
	# Note: if you need something like LD_PRELOAD or equivalent, add the respective
	# variables to the environment of this process before starting it
	if sys.platform.startswith('linux'):
		envld = "LD_LIBRARY_PATH"
		ldpath = os.path.join(mayalocation, 'lib')
		update_env_path(env, envld, ldpath)
	elif sys.platform == 'darwin':
		# adjust maya location to point to the actual directtoy
		dldpath = os.path.join(mayalocation, 'MacOS')
		update_env_path(env, "DYLD_LIBRARY_PATH", dldpath)
		
		dldframeworkpath = os.path.join(mayalocation, 'Frameworks')
		update_env_path(env, "DYLD_FRAMEWORK_PATH", dldframeworkpath)
		
		env['MAYA_NO_BUNDLE_RESOURCES'] = "1"
		
		# on osx, python will only use the main frameworks path and ignore 
		# its own sitelibraries. We put them onto the PYTHONPATH for that reason
		# MayaRV will take care of the initialization
		ppath = "/Library/Python/%s/site-packages" % py_version
		update_env_path(env, envppath, ppath, append=True)
		
	elif sys.platform.startswith('win'):
		mayadll = os.path.join(mayalocation, 'bin')
		mayapydll = os.path.join(mayalocation, 'Python', 'DLLs')
		update_env_path(env, 'PATH', mayadll+os.pathsep+mayapydll, append=False)
	else:
		raise EnvironmentError("Current platform %s is unsupported" % sys.platform)
	# END handle os's
	
	
	# ADJUST PYTHON PATH
	####################
	# mrv is already in the path, we just make sure that the respective path can 
	# be found in the python path. We add additional paths as well
	ospd = os.path.dirname
	if not sys.platform.startswith('win'):
		ppath = os.path.join(mayalocation, pylibdir, "python%s"%py_version, "site-packages")
	else:
		ppath = os.path.join(mayalocation, pylibdir, "lib", "site-packages")
	# END windows special handling
	
	ppath += os.pathsep + ospd(ospd(ospd(__file__)))
	update_env_path(env, envppath, ppath, append=True)
	
	# SET MAYA LOCATION
	###################
	# its important to do it here as osx adjusts it 
	env['MAYA_LOCATION'] = mayalocation 
	
	# export the actual maya version to allow scripts to pick it up even before maya is launched
	env['MRV_MAYA_VERSION'] = "%g" % maya_version
	
def mangle_args(args):
	"""Enclose arguments in quotes if they contain spaces ... on windows only
	:return: tuple of possibly modified arguments
	
	:todo: remove this function, its unused"""
	if not sys.platform.startswith('win'):
		return args
	
	newargs = list()
	for arg in args:
		if ' ' in arg:
			arg = '"%s"' % arg
		# END put quotes around strings with spaces
		newargs.append(arg)
	# END for each arg
	return tuple(newargs)
	
def mangle_executable(executable):
	""":return: possibly adjusted path to executable in order to allow its execution
		This currently only kicks in on windows as we can't handle spaces properly.
	
	:note: Will change working dir
	:todo: remove this function, its unused"""
	if not sys.platform.startswith('win'):
		return executable
		
	# execv appears to call the shell, hence we make sure we handle whitespaecs
	# in the path, which usually happens on windows !
	# Problem here is that it cannot find the executable if it has a space in the
	# path as it will split it, and if quotes are put around, it can't find 
	# it either. Hence we chdir into it and use a relative path
	if ' ' in executable:
		os.chdir(os.path.dirname(executable))
		executable = os.path.basename(executable)
	# END handle freakin' spaces
	return executable

def init_environment(args):
	"""Intialize MRV up to the point where we can replace this process with the 
	one we prepared
	
	:param args: commandline arguments excluding the executable ( usually first arg )
	:return: tuple(maya_version, args) tuple of maya_version, and the remaining args"""
	# see if first argument is the maya version
	maya_version=None
	if args:
		parsed_successfully, maya_version = parse_maya_version(args[0], maya_version)
		if parsed_successfully:
			args = args[1:]
		# END cut version arg
	# END if there are args at all
	
	# choose the newest available maya version if none was specified
	if maya_version is None:
		versions = available_maya_versions()
		if versions:
			maya_version = versions[-1]
		# END set latest
	# END set maya version 
	
	if maya_version is None:
		raise EnvironmentError("Maya version not specified on the commandline, couldn't find any maya version on this system")
	# END abort if not installed
	
	update_maya_environment(maya_version)
	return (maya_version, tuple(args))
	
def _execute(executable, args):
	"""Perform the actual execution of the executable with the given args.
	This method does whatever is required to get it right on windows, which is 
	the only reason this method exists !
	
	:param args: arguments, without the executable as first argument
	:note: does not return """
	# on windows we spawn, otherwise we don't get the interactive input right
	actual_args = (executable, ) + args
	if sys.platform.startswith('win'):
		p = subprocess.Popen(actual_args, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
		sys.exit(p.wait())
	else:
		os.execvp(executable, actual_args)
	# END handle windows

def python_executable(py_version=None):
	""":return: name or path to python executable in this system, deals with 
	linux and windows specials"""
	if py_version is None:
		return 'python'
	# END handle simple case
	
	py_executable = "python%g" % py_version
	if sys.platform.startswith('win'):
		# so, on windows the executables don't have a . in their name, most likely
		# because windows threats the '.' in a special way as ... anyway. 
		py_executable = "python%g" % (py_version*10)
	# END win specials
	return py_executable
	
def find_mrv_script(name):
	"""Find an mrv script of the given name. This method should be used if you 
	want to figure out where the mrv executable with the given name is located.
	The returned path is either relative or absolute.

	:return: Path to script 
	:raise EnvironmentError: if the executable could not be found
	:note: Currently it only looks for executables, but handles projects
	which use mrv as a subproject"""
	import mrv
	mrvroot = os.path.dirname(mrv.__file__)
	
	tried_paths = list()
	for base in ('', 'ext', mrvroot):
		for subdir in ('bin', 'doc', os.path.join('test', 'bin')):
			path = None
			if base:
				path = os.path.join(base, subdir, name)
			else:
				path = os.path.join(subdir, name)
			# END handle base
			if os.path.isfile(path):
				return Path(path)
			tried_paths.append(path)
		# END for each subdir
	# END for each base
	
	raise EnvironmentError("Script named %s not found, looked at %s" % (name, ', '.join(tried_paths))) 
	
def exec_python_interpreter(args, maya_version, mayapy_only=False):
	"""Replace this process with a python process as determined by the given options.
	This will either be the respective python interpreter, or mayapy.
	If it works, the function does not return
	
	:param args: remaining arguments which should be passed to the process
	:param maya_version: float indicating the maya version to use
	:param mayapy_only: If True, only mayapy will be considered for startup.
	Use this option in case the python interpreter crashes for some reason.
	:raise EnvironmentError: If no suitable executable could be started"""
	py_version = python_version_of(maya_version)
	py_executable = python_executable(py_version) 
	
	args = tuple(args)
	tried_paths = list()
	try:
		if mayapy_only:
			raise OSError()
		tried_paths.append(py_executable)
		_execute(py_executable, args)
	except OSError:
		if not mayapy_only:
			print "Python interpreter named %r not found, trying mayapy ..." % py_executable
		# END print error message
		mayalocation = maya_location(maya_version)
		mayapy_executable = os.path.join(mayalocation, "bin", "mayapy")
		
		try:
			tried_paths.append(mayapy_executable)
			_execute(mayapy_executable, args)
		except OSError, e:
			raise EnvironmentError("Could not find suitable python interpreter at paths %s : %s" % (', '.join(tried_paths), e))
		# END final exception handling
	# END exception handling
	
def exec_maya_binary(args, maya_version):
	"""Replace this process with the maya executable as specified by maya_version.
	
	:param args: The arguments to be provided to maya
	:param maya_version: Float identifying the maya version to be launched
	:rase EnvironmentError: if the respective maya version could not be found"""
	mayalocation = maya_location(maya_version)
	mayabin = os.path.join(mayalocation, 'bin', 'maya')
	
	# although execv would work on windows, we use our specialized _execute method 
	# in order to keep things consistent
	_execute(mayabin, tuple(args))
	
	
#} END Maya initialization





