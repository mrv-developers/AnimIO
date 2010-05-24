#!/usr/bin/env python
import os
ospd = os.path.dirname
import sys
import __builtin__

from distutils.core import setup
from distutils.dist import Distribution as BaseDistribution
from distutils import log, dir_util


import distutils.command
import distutils.sysconfig
from distutils.sysconfig import get_makefile_filename, get_python_lib
from distutils.cmd import Command
from distutils.command.install_lib import install_lib
from distutils.command.install import install
from distutils.command.build_py import build_py
from distutils.command.build_scripts import build_scripts
from distutils.command.sdist import sdist
from distutils.util import convert_path
from itertools import chain
import subprocess
import fnmatch
import shutil
import new
import re


#{ Distutils Fixes 

def __init__(self, dist):
	"""Okay, its getting interesting: cmd checks for the type of dist - we 
	have derived from it and provide our own type. Distribution is an oldstyle class
	which doesn't even work with isinstance - to workaround this, we derive from object
	as well. In the moment we call __init__ on the BaseDistribution part of our instance, 
	it claims not to be an instance of type Distribution(Base) anymore. Something is 
	fishy here. As a workaround, we get rid of the typecheck in the command base."""
	self.distribution = dist
	self.initialize_options()
	self._dry_run = None
	self.verbose = dist.verbose
	self.force = None
	self.help = 0
	self.finalized = 0

distutils.cmd.Command.__init__ = __init__

def find_packages(where='.', exclude=()):
	"""
	NOTE: This method is not easily available which is a problem for us. Hence
	we just put it here, duplicating code from the setup tools.
	
	Return a list all Python packages found within directory 'where'

	'where' should be supplied as a "cross-platform" (i.e. URL-style) path; it
	will be converted to the appropriate local path syntax.	 'exclude' is a
	sequence of package names to exclude; '*' can be used as a wildcard in the
	names, such that 'foo.*' will exclude all subpackages of 'foo' (but not
	'foo' itself).
	"""
	out = []
	stack=[(convert_path(where), '')]
	while stack:
		where,prefix = stack.pop(0)
		for name in os.listdir(where):
			fn = os.path.join(where,name)
			if ('.' not in name and os.path.isdir(fn) and
				os.path.isfile(os.path.join(fn,'__init__.py'))
			):
				out.append(prefix+name); stack.append((fn,prefix+name+'.'))
	for pat in list(exclude)+['ez_setup']:
		from fnmatch import fnmatchcase
		out = [item for item in out if not fnmatchcase(item,pat)]
	return out


def zipcompatible_get_makefile_filename():
	"""The maya installation of python 2.5 on linux is incomplete, that is the Makefile
	is not physically present on disk, but is instead to be found in a zip archive.
	We will detect that, and extract a temporary file instead that we will pass
	on to the parser.
	
	note: the temp file is not currently being deleted"""
	makefilepath = get_makefile_filename()
	if os.path.isfile(makefilepath):
		return makefilepath
	# END all fine
	
	# try to extract it from zip file
	zipfilepath = os.path.join(ospd(ospd(sys.executable)), 'lib', 'python%s%s.zip' % sys.version_info[:2])
	if not os.path.exists(zipfilepath):
		raise OSError("Could not find zipfile containing makefile at %r" % zipfilepath)
	# END handle zip file doesn't exist
	
	import tempfile
	import zipfile
	zf = zipfile.ZipFile(zipfilepath)
	
	libdir = get_python_lib(plat_specific=1, standard_lib=1)
	zipmakefilepath = makefilepath.replace(libdir + os.path.sep, '')
	data = zf.read(zipmakefilepath)
	tfp, tfn = tempfile.mkstemp('makefile')
	os.write(tfp, data)
	os.close(tfp)
	
	return tfn
	
	
distutils.sysconfig.get_makefile_filename = zipcompatible_get_makefile_filename 
	

#} END Distutils fixes


#{ Commands 


class _GitMixin(object):
	"""Provides functionality to add files and folders within a base directory 
	into the **root** of a git repository of our choice"""
	
	#{ Configuration
	# name of symbolic reference which keeps the previous reference name to which 
	# HEAD pointed before we changed HEAD
	prev_head_name = 'DIST_ORIG_HEAD'
	
	# Variable holding the commit sha of the source repository at the time of the 
	# distribution creation
	commit_sha_var_name = 'src_commit_sha'
	
	branch_suffix = None
	#} END configuration 
	
	class RemotePush(object):
		"""Functor representing a hashable push call to a remote"""
		def __init__(self, inst, *args):
			self.inst = inst
			self.args = tuple(args)
			
		def __hash__(self):
			return hash(self.args)
			
		def __eq__(self, rhs):
			return hash(self) == hash(rhs)
		
		def __call__(self):
			return self.inst._push_to_remotes(*self.args)
		
	# END utility class
	
	def __new__(cls, *args, **kwargs):
		"""Because of our old-style bases, new needs to be overridden to 
		call the object constructor without arguments"""
		self = object.__new__(cls)
		# have to manually call init on all bases because the old-style classes
		# don't really cut it here
		for c in cls.mro():
			c.__init__(self, *args, **kwargs)
		return self
	
	def __init__(self, *args, **kwargs):
		"""Allows to configure some details, such as 
		* remote name - name of the remote for which branches should be created/updated"""
		self.root_remotes = list()
		self.dist_remotes = list()
	
	def finalize_options(self):
		"""Assure our args are of the correct type"""
		self.root_remotes = self.distribution.fixed_list_arg(self.root_remotes)
		self.dist_remotes = self.distribution.fixed_list_arg(self.dist_remotes)
	
	#{ Utilities
	
	@classmethod
	def adjust_user_options(cls, options):
		"""Append git specific user options to the given options"""
		options.append(('dist-remotes=', 'd', "Default remotes to push the distribution branches to"))
		options.append(('root-remotes=', 'r', "Default remotes to push the the main source branch to"))
	
	def branch_name(self):
		""":return: name of the branch identifying our current release configuration"""
		root_name = self.distribution.pinfo.root_package
		if self.branch_suffix is None:
			raise ValueError("Branch suffix is not set")
		return root_name + self.branch_suffix
		
	def set_head_to(self, repo, head_name):
		"""et our head to point to the given head_name. If possible, 
		update the index to represent the tree the head points to
		
		:return: Head named head_name
		:note: In the worst case, the head points to non-existing ref, as the 
			repository is still empty"""
		import git
		
		# store the previous ref in a new symbolic ref
		git.SymbolicReference.create(repo, self.prev_head_name, repo.head.ref, force=True)
		
		
		# if the head ref exists or not, we want to change the branch to the one
		# we define. This is why we do this explicitly here. Resetting the index
		# and setting the head will just set the current branch to the commit we 
		# reset to
		head_ref = git.Head(repo, git.Head.to_full_path(head_name))
		repo.head.ref = head_ref
		
		if head_ref.is_valid():
			repo.index.reset(head_ref, working_tree=False, head=False)
		# END handle index
			
		# END head exists handling
		return head_ref
	
	def item_chooser(self, description, items):
		"""Utility allowing the user to easily select items from the items list
		:param items: objects that can be converted into a string
		:return: list of selected items"""
		if not items:
			return list()
		
		assert sys.stdout.isatty(), "Need a tty for item chooser"
		
		while True:
			print description
			print "Type the numbers to select the items, i.e. 1,2,5 or 0 to select all"
			print ""
			print "0 == All Items"
			for i, item in enumerate(items):
				print "%i == %s" % (i+1, item)
			# END for each item to print
			
			indices = list()
			sel_items = list()
			while True:
				try:
					answer = raw_input("Choice: " )
					indices.extend(int(i.strip()) for i in answer.split(','))
					break
				except Exception:
					print "Failed to parse your choice, please try again: %s" % answer
					continue
				# END excpetion handling
			# END parse loop
			
			if not indices:
				asw = 'abort'
				print "No item selected - would you like to abort ?"
				answer = raw_input("%s/continue [%s]" % (asw, asw)) or asw
				if answer == asw:
					print "User aborted selection"
					return list()
				else:
					continue
				# END handle answer
			# END handle nothing choosen
			
			# gather indices
			if 0 in indices:
				sel_items.extend(items)
			else:
				for index in indices:
					try:
						sel_items.append(items[index-1])
					except IndexError:
						pass
					# END handle invalid indices
				# END for each index
			# END for each 
			
			# present the selection
			if sel_items:
				print "Your selection: "
				for item in sel_items:
					print str(item)
				# END for each item
			else:
				print "You didn't select anything"
			# END present items
			asw = "proceed"
			print "Would you like to proceed or re-select ?"
			answer = raw_input("%s/reselect [%s]: " % (asw, asw)) or asw
			
			if answer != asw:
				continue
			
			return sel_items
		# END while user is unhappy
		
		return items
	
	def push_to_remotes(self, repo, heads=list(), remotes=list()):
		"""For the actual documentation, please see ``_push_to_remotes``
		This method stores the call for later execution"""
		self.distribution.push_queue.append(self.RemotePush(self, repo, tuple(heads), tuple(remotes)))
	
	def _push_to_remotes(self, repo, heads=list(), remotes=list()):
		"""Push the given branchs to the given remotes.
		If one of the lists is empty, it the respective items 
		will be queried from the user"""
		_heads = heads
		_remotes = remotes
		all_remotes = repo.remotes
		
		if not _remotes:
			_remotes = all_remotes
		if not _heads:
			_heads = repo.heads
		
		if not _remotes or not _heads:
			return
		# END skip empty remotes
		
		# cannot push if we don't know exactly what to do ( and if we cannot
		# ask the user )
		have_tty = sys.stdout.isatty()
		if not have_tty and (not heads or not remotes):
			log.info("Skipped push to %r as no push information was provided" % repo)
			return
		# END handle tty
		
		if have_tty:
			asw = "yes"
			man = 'manual'
			print "\nWould you like to push your changes in repo %s ?" % repo
			print "Currently selected heads: %s" % ', '.join(str(h) for h in heads) or 'None'
			print "Currently selected remotes: %s" % ', '.join(str(r) for r in remotes) or 'None'
			print "You can the given values, force manual (re)selection or skip this ?"
			answer = raw_input("%s/%s/skip [%s]: " % (asw, man, asw)) or asw
			if answer == man:
				remotes = list()
				heads = list()
			elif answer != asw:
				print "You can push your changes manually any time"
				return 
			# END see if the user wants to push
		# END last query
		
		if not remotes:
			desc = "Please choose the remotes to push to"
			_remotes = self.item_chooser(desc, _remotes)
		# END query if not given
		
		if not heads:
			desc = "Please choose your branches to push to the selected remotes" 
			_heads = self.item_chooser(desc, _heads)
		# END query if not given 
		 
		if not _remotes or not _heads:
			print "No remotes or heads selected - won't push anything"
			return
		# END abort if there is nothing to do
		
		tags = repo.tags
		tag_map = dict((tag.commit, tag) for tag in tags)
		
		# walk the history of all branches and select all tags on the way
		actual_tags = list()
		for head in _heads:
			curcommit = head.commit
			while True:
				if curcommit in tag_map:
					actual_tags.append(tag_map[curcommit])
				# END found tag
				if not curcommit.parents:
					break
				curcommit = curcommit.parents[0]
			# END pseudo do-while
		# END for each branch
		
		# prep refspec
		specs = list()
		for item in chain(_heads, actual_tags):
			specs.append("+%s:%s" % (item.path, item.path))
		# END for each item to push
		
		# do the operation
		for remote in _remotes:
			# might be a string if it was a preconfigured remote - hence we 
			# retrieve the object no matter what
			remote = all_remotes[str(remote)]
			
			print "Force-Pushing to %s: %s ..." % (remote, ", ".join(str(i) for i in chain(_heads, actual_tags)))
			remote.push(specs)
			print "Done"
		# END for each remote to push to

	def _adjust_commit_sha(self, root_commit, root_dir):
		"""Write the src_commit_sha in the info.py file to the value in root_commit
		or skip it if the file is not available"""
		info_module_path = os.path.join(root_dir, 'info.py')
		if not os.path.isfile(info_module_path):
			log.warn("Couldn't write the %s value as the info module at %r did not exist" % (self.commit_sha_var_name, info_module_path))
			return
		# END handle file existence
		
		# BREAK HARD LINKS
		##################
		# if the file is hard-linked, which is the default for source distributions, 
		# copy the file into place
		stat = os.stat(info_module_path)
		if stat.st_nlink > 1:
			info_module_source_path = os.path.splitext(self.distribution.pinfo.__file__)[0] + ".py"
			if not os.path.isfile(info_module_source_path):
				log.error("Couldn't remove hardlink of info file as the file's source did not exist at %r" % info_module_source_path)
				return
			# END handle source doesn't exist
			os.remove(info_module_path)
			shutil.copyfile(info_module_source_path, info_module_path)
		# END remove hard link
		
		# MAKE REPLACEMENT
		# parse the file, find our line, expect it unaltered
		adjusted = False
		lines = open(info_module_path, 'r').readlines()
		fexc = ValueError("Line could not be parsed, expecting: %s = '0'*40|SHA" % self.commit_sha_var_name)
		
		for ln, line in enumerate(lines):
			if not line.strip().startswith(self.commit_sha_var_name):
				continue
			# END skip if not our line
			
			try:
				var_name, value = [ t.strip() for t in line.split('=') ]
			except ValueError:
				log.error(line)
				raise fexc
			# END handle parsing errors
			
			if len(value) > 40:
				log.info("Skipping adjustment of line %r as commit value was already set" % line)
				return
			# END handle commit already set
			
			# rewrite the line with the sha
			lines[ln] = "%s = %r\n" % (self.commit_sha_var_name, root_commit.sha)
			adjusted = True
			break
		# END for each line
		
		# WRITE CHANGES
		if adjusted:
			open(info_module_path, 'w').writelines(lines)
			log.info("Adjusted line with %s of info module at %r" % (self.commit_sha_var_name, info_module_path))
		else:
			log.info("Didn't find line with %s in info module at %r" % ( self.commit_sha_var_name, info_module_path))
		# END write changes
		
		
	def add_files_and_commit(self, root_repo, repo, root_dir, root_tag):
		"""
		Add all files recursively to the index as found below root_dir and commit the
		index.
		
		As a special ability, we will rewrite their paths and thus add them relative
		to the root directory, even though the git repository might be on another level.
		It also sports a simple way to determine whether the commit already exists, 
		so it will not recommit data that has just been committed.
		
		Additionally we will try to find the info.py file and adjust its commit_sha
		to the actual sha of our root_repo's original branch.
		
		:param root_repo: Repository containing the data of the main project
		:param repo: dedicated repository containing the distribution data
		:return: tuple(root_original_head, (Created)Commit object) The head to which
			the root repository pointed before we changed it to our distribution head, 
			and the commit object we possible created in the distribution repository"""
		import git
		
		# the path to cut is (root_dir - repo.working_dir)
		cut_path = os.path.abspath(root_dir)[len(os.path.abspath(repo.working_tree_dir))+1:]
		def path_rewriter(entry):
			# remove the root portion of the path as it is supposed to be relative
			# to the repository. 
			return entry.path[len(cut_path)+1:]	# +1 to cut the separator
		# END path rewriter
		
		def path_generator():
			for root, dirs, files in os.walk(root_dir):
				for f in files:
					yield os.path.join(root, f)
				# END for each file
			# END for each iteration
		# END path generator
		
		# clear out the original index by deleting it
		try:
			os.remove(repo.index.path)
		except OSError:
			# it doesn't even exist
			pass
		# END remove index
		
		# Get root_head information
		# Provide a good comment that helps associating the distribution commit
		# with the current repository commit. We handle the case that the distribution
		# repository is the root repository, hence the last actual head reference is 
		# stored in a temporary symbolic ref. It will not exist of root_repo and repo
		# are different repositories
		prev_root_head = git.SymbolicReference(root_repo, self.prev_head_name)
		root_commit = None
		suffix = ''
		if not prev_root_head.is_valid():
			prev_root_head = root_repo.head
		# END get actual commit reference
		root_commit = prev_root_head.commit
		
		if root_repo.is_dirty(index=False, working_tree=True, untracked_files=False):
			suffix = "-dirty"
		# END handle suffix
		
		# important to associate the build with the source
		###############################################
		self._adjust_commit_sha(root_commit, root_dir)
		###############################################
		
		# add all files, rewriting their paths accordingly, must be done now as 
		# we have to wait for the last in-place adjustment
		#############################################################
		repo.index.add(path_generator(), path_rewriter=path_rewriter)
		#############################################################
		
		commit = repo.index.commit("%s@%s%s" % (self.distribution.get_fullname(), root_commit, suffix), head=True)
		
		# check whether the commit encapsulates new information - did the tree change ?
		if commit.parents and commit.parents[0].tree == commit.tree:
			log.info("Dropped created commit %s as it contained the same tree as its parent commit" % commit)
			commit = commit.parents[0] 
			repo.head.commit = commit
		# END check duplicate data and drop commit if required
		
		# finally, create a tag which is unique for the branches and the actual version
		# If the commit didn't change anything, it might already exist, but we 
		# don't care about that
		# In case the user managed to adjust data and create a new tree, but kept 
		# the version the same for some reason ( you could do that if you really 
		# want to ), we force the tag creation to update it in these cases
		# If the user wants it, we do it, no questions asked
		tag_name = "%s-%s" % (self.branch_name(), root_tag.name)
		git.Tag.create(repo, tag_name, force=True)
			 
		return prev_root_head, commit
		
	#} END utilities
	
	#{ Interface 
	def update_git(self, root_dir):
		"""Put the contents in the root_dir into the configured git repository
		Its important to note that the actual relative location of root_dir does not
		matter as long as it is inside the git repository. The later object paths
		within the git repository will all be relative to root_dir."""
		if not self.distribution.use_git:
			return
		
		from mrv.util import CallOnDeletion
		try:
			import git
		except ImportError:
			raise ImportError("Could not import git, please make sure that gitpython is available in your installation")
		# END end 
		
		# searches for closest available repo in parent dirs, might end up in 
		# the developers dir which is okay as well.
		repo = git.Repo(root_dir)
		root_repo = self.distribution.root_repo
		
		dirty_kwargs = dict(index=True, working_tree=False, untracked_files=False)
		if root_repo.is_dirty(**dirty_kwargs):
			raise EnvironmentError("Please commit your changes in index of repository %s and try again" % root_repo)
		
		if repo.is_dirty(**dirty_kwargs):
			raise EnvironmentError("Cannot operate on a dirty index - please have a look at git repository at %s" % repo)
		# END abort on dirty index
		
		
		# we require the current commit to be tagged
		root_tag = self.distribution.handle_version_and_tag()
		
		try:
			prev_head_ref = repo.head.ref
			__IndexCleanup = CallOnDeletion(lambda : self.set_head_to(repo, prev_head_ref))
		except TypeError:
			# ignore detached heads
			pass 
		# END handle head is detached
		
		
		# checkout the target branch gently ( index and head only )
		branch_name = self.branch_name()
		head_ref = self.set_head_to(repo, branch_name)
		assert repo.head.ref == head_ref
		
		# add our all files below our root
		root_head, commit = self.add_files_and_commit(root_repo, repo, root_dir, root_tag)
		
		# PUSH CHANGES
		##############
		# allow to auto-push to all or given remotes for both repositories
		# fill in defaults
		root_head = (root_head.is_detached and root_head) or root_head.ref
		self.push_to_remotes(root_repo, [root_head], self.root_remotes)
		self.push_to_remotes(repo, [head_ref], self.dist_remotes)
		
	
	#} END interface 


class _RegressionMixin(object):
	"""Provides a simple interface allowing to perform a regression test"""
	
	#{ Configuration
	# default directory containing the actual tests.
	# Specifying subdirectories may limit the amount of tests run
	test_dir_default = 'test'
	#} END configuration
	
	
	def __init__(self, *args, **kwargs):
		self.post_testing = list()
		self.test_dir = self.test_dir_default
	
	
	#{ Interface 
	
	@classmethod
	def adjust_user_options(cls, user_options):
		user_options.append(('post-testing=', 't', "Specifies the maya version(s) with which post-build testing will be performed"))
		user_options.append(('test-dir=', 'd', "Specifies directory containing test modules, relative to the distribution"))
		
	def finalize_options(self):
		self.post_testing = self.distribution.fixed_list_arg(self.post_testing)
		
	def _find_test_modules(self, root_dir):
		"""
		:return: list of files within the root_dir which appear to be containing tests.
			Explicit selection is required if we are byte-compiling modules, nose skips .pyc
			even if there is no .py file ;)"""
		if not os.path.isdir(root_dir):
			return list()
		# END handle non-existing directory
		test_modules = list()
		seen_paths = set()
		for root, dirs, files in os.walk(root_dir):
			for f in files:
				fpath = os.path.join(root, f)
				bpath, ext = os.path.splitext(fpath)
				if bpath in seen_paths:
					continue
				# END handle py/pyc extension
				seen_paths.add(bpath)
				if os.path.basename(bpath).startswith('test_'):
					test_modules.append(fpath)
				# END pick path
			# END for each file
		# END while walking
		return test_modules
		
	def post_regression_test(self, testexecutable, test_root_dir):
		"""Perform a regression test for the maya version's the user supplied.
		:param testexecutable: path to the tmrv-compatible executable - it is 
			expected to be inside a tree which allows the project to put itself into the path.
		:param root_dir: root directory under which tests can be found
		:raise EnvironmentError: if started process returned non-0"""
		if not self.post_testing:
			return 
		# END early abort
		
		# need explicit test modules
		test_modules = tuple(self._find_test_modules(test_root_dir))
		if not test_modules:
			return 
		
		# select everything which looks like a test for it as nose officially 
		# ignores compiled files
		for maya_version_str in self.post_testing:
			args = (testexecutable, maya_version_str ) + test_modules
			if self.distribution.spawn_python_interpreter(args).wait():
				raise EnvironmentError("Post-Operation test failed")
			# END call test program
		# END for each maya version
	#} END interface
	
	

class BuildPython(_GitMixin, _RegressionMixin, build_py):
	"""Customize the command preparing python modules in order to skip copying 
	original py files if compile is specified. Additionally we allow the python 
	interpreter to be specified as the bytecode is incompatible between the versions"""
	
	description="Implements byte-compilation with different python interpreter versions"
	
	#{ Configuration
	# If True, the source module will be deleted ( in the build directory ) 
	# after it was compiled to byte code
	remove_py_after_byte_compile = True
	
	# if set, pyo will be renamed to pyc, for some reason the pyo extension is not
	# common and not properly supported by python itself
	rename_pyo_to_pyc = True
	
	# if we create optimized bytecode, prune out all tests as they use assert 
	# statements which would be dropped by the 'optimization'
	remove_tests_if_optimize = True
	
	
	build_py.user_options.extend(
	[('exclude-from-compile=', 'e', "Exclude the given comma separated list of file(globs) from being compiled"), 
	 ('exclude-items=', 'm', "Exclude the given comma separated list of modules or packages from being build, i.e. .test")]
									)
	
	_GitMixin.adjust_user_options(build_py.user_options)
	_RegressionMixin.adjust_user_options(build_py.user_options)
	#} END configuration 
	
	#{ Internals
	
	def _filter_by_token(self, token, array):
		"""Use a simple filter function and return all array items which do not contain
		the token"""
		return [ p for p in array if token not in p ]
	
	def _exclude_items(self, package_name):
		"""Exclude the given package name from our packages and datafiles
		:param package_name: The name of the package, i.e. '.test'"""
		token = package_name
		if self.packages:
			self.packages = self._filter_by_token(token, self.packages)
		if self.py_modules:
			self.py_modules = self._filter_by_token(token, self.py_modules)
			
		# additionally, remove all data files which appear to be tests
		if self.data_files:
			# its sooo terrible that it is named 'data_files', but in fact contains
			# a tuple with much more information !
			# Besides, every module we build is represented in here, even though 
			# there are no 'data files' ... !
			self.data_files = [ 	(package, src_dir, build_dir, filenames) 
									for package, src_dir, build_dir, filenames in self.data_files 
									if token not in package ]
		# END handle data files
	
	def handle_exclusion(self):
		"""Apply the exclusion patterns"""
		for exclude_pattern in self.exclude_items:
			self._exclude_items(exclude_pattern)
		
	#} END internals
	
	#{ Paths
	
	def _build_dir(self):
		""":return: directory into which all files will be put"""
		# this works ... checked their code which seems hacky, so we continue with the 
		# hackiness
		return os.path.join(self.build_lib, self.distribution.pinfo.root_package)
		
	def _test_abspath(self):
		"""
		:return: First the executable in our build dir, then the one our distro
			deems best"""
		build_exec = os.path.join(self._build_dir(), self.distribution._test_relapath())
		if os.path.isfile(build_exec):
			return build_exec
		return self.distribution._test_relapath()
		
	#} END paths
	
	#{ Overridden Methods 
	
	def initialize_options(self):
		build_py.initialize_options(self)
		self.py_version = None
		self.maya_version = None		# set later by distutils
		self.needs_compilation = None
		self.exclude_from_compile = list()
		self.exclude_items = list()
		
	def finalize_options(self):
		build_py.finalize_options(self)
		_GitMixin.finalize_options(self)
		_RegressionMixin.finalize_options(self)
		
		self.maya_version = self.distribution.maya_version
		self.py_version = self.distribution.py_version
		self.needs_compilation = self.compile or self.optimize
		self.exclude_from_compile = self.distribution.fixed_list_arg(self.exclude_from_compile)
		self.exclude_items = self.distribution.fixed_list_arg(self.exclude_items)
		
		# as optimize removes assertions
		if self.optimize and self.remove_tests_if_optimize:
			log.info("Pruning all tests from output as they would fail with optimized bytecode")
			self.exclude_items = list(self.exclude_items)
			self.exclude_items.insert(0, '.test')
		# END handle tests
		
		self.handle_exclusion()
		
		# HANDLE BRANCH SUFFIX
		if self.needs_compilation:
			# force recompilation, its important in case of files which might
			# just have been compiled by a different python version, and hence
			# don't need recompilation when just regarding the timestamp
			self.force = True
			self.branch_suffix = '-py'+sys.version[:3]
		else:
			self.branch_suffix = '-pyany'
		# END handle suffix
		
	def byte_compile( self, files, **kwargs):
		"""If we are supposed to compile, remove the original file afterwards"""
		
		if self.needs_compilation and self.py_version is None:
			raise ValueError("If compilation is requested, the'%s' option must be specified" % self.distribution.opt_maya_version)
		# END handle errors
		
		# MAKE EXCLUSION
		for exclude_pattern in self.exclude_from_compile:
			remove_files = fnmatch.filter(files, convert_path(exclude_pattern))
			for f in remove_files:
				files.remove(f)
			# END remove all matched files
		# END for each exclude pattern to apply
		
		# assure we byte-compile in a standalone interpreter, manipulating the 
		# sys.executable as it will be used later
		# During installation, we can use this interpreter as it is the one for which 
		# we install
		prev_debug = __debug__
		prev_executable = sys.executable
		if self.needs_compilation and 'install' not in self.distribution.commands:
			# this forces to use a standalone process
			__builtin__.__debug__ = False
			
			# which is hopefully in the path
			sys.executable = "python%g" % self.py_version
		# END preparation
		
		rval = build_py.byte_compile(self, files, **kwargs)
		
		if self.needs_compilation:
			# restore original values
			__builtin__.__debug__ = prev_debug
			sys.executable = prev_executable
			
			# super class implementation handles the compilation and optimization 
			# as if it was a totally separate case and duplicates code for whichever 
			# reason 
			for py_file in (f for f in files if f.endswith('.py')):
				if self.remove_py_after_byte_compile:
					try:
						os.remove(py_file)
						log.debug("Removed original file after byte compile: %s" % py_file)
					except OSError:
						# it can happen that the file gets deleted by the conversion 
						# script itself ... don't fully understand it though.
						pass
					# END handle file doesn't exist anymore
				# END if remove py after byte compile
				
				if self.rename_pyo_to_pyc:
					base, ext = os.path.splitext(py_file)
					pyo_file = base + ".pyo"
					if os.path.isfile(pyo_file):
						pyc_file = base + ".pyc"
						os.rename(pyo_file, pyc_file)
						log.debug("Renamed %s to %s" % (pyo_file, pyc_file))
					# END check and rename
				# END rename file
			# END for each python file to remove
		# END post processing
		
		
		return rval
		
	def get_data_files(self):
		"""Can you feel the pain ? So, in python2.5 and python2.4 coming with maya, 
		the line dealing with the ``plen`` has a bug which causes it to truncate too much.
		It is fixed in the system interpreters as they receive patches, and shows how
		bad it is if something doesn't have proper unittests.
		The code here is a plain copy of the python2.6 version which works for all.
		
		Generate list of '(package,src_dir,build_dir,filenames)' tuples"""
		data = []
		if not self.packages:
			return data
		for package in self.packages:
			# Locate package source directory
			src_dir = self.get_package_dir(package)

			# Compute package build directory
			build_dir = os.path.join(*([self.build_lib] + package.split('.')))

			# Length of path to strip from found files
			plen = 0
			if src_dir:
				plen = len(src_dir)+1

			# Strip directory from globbed filenames
			filenames = [
				file[plen:] for file in self.find_data_files(package, src_dir)
				]
			data.append((package, src_dir, build_dir, filenames))
		return data
	
	def find_data_files(self, package, src_dir):
		"""Fixes the underlying method by allowing to specify whole directories
		whose files will be copied recursively. Thanks python for not even providing 
		the bare mininum so people end up reimplementing parts of the 'distribution system'"""
		# ALLOW DIRECTORY RECURSION
		# preprocess the globs listing in package data: If it is not a glob, but 
		# appears to be a directory, expand the directory tree and simple append
		# the respective files ourselves
		patterns = self.package_data.get(package, None)
		add_files = list()
		ignore_patterns = list()
		if patterns:
			cl = len(src_dir) + 1	# cut length including path separator 
			for pt in patterns[:]:
				if pt.startswith('!'):
					patterns.remove(pt)
					ignore_patterns.append(pt[1:])
					continue
				# END handle ignore pattern
				d = os.path.join(src_dir, pt)
				if os.path.isdir(d):
					patterns.remove(pt)		# remove original
					for root, dirs, files in os.walk(d):
						for f in files:
							add_files.append(os.path.join(root, f))
						# END for each actual directory
					# END for each directory to walk
				# END expand directory
			# END for each patterm
		# END handle expand patterns
		
		files = build_py.find_data_files(self, package, src_dir)
		
		if ignore_patterns:
			for pt in ignore_patterns:
				for flist in (files, add_files):
					ignored_files = fnmatch.filter(flist, convert_path(pt))
					for f in ignored_files:
						flist.remove(f)
					# END brute force remove files
				# END for list to handle
			# END for each ignore pattern
		# END remove ignored files
		
		# FIX DIRECTORIES
		# additionally ... prune out items which are directories, as the system
		# is as stupid as it gets, so it ends up trying to copy a directory as 
		# if it was a file
		for f in files[:]:
			if os.path.isdir(f):
				files.remove(f)
			# END remove directories
		# END for each file
		return files + add_files
		
	def _filtered_module_list(self, modules):
		"""Because things multiply in our base class ...  argh"""
		# yes, its  a special format again totally undocumented except for the code
		# ... its hacky shit, so this becomes hacky shit as well ... :(
		# brute force ...
		filtered_modules = list()
		for p, m, f  in modules:
			skip = False
			for token in self.exclude_items:
				if token in ("%s.%s" % (p, m)):
					skip = True
				# END token was not found
				if skip: break
			# END for each token
			if not skip:
				filtered_modules.append((p, m, f))
			else:
				log.info("Skipped : %s.%s" % (p, m))
			# END handle skipping
		# END for each unpacked module info
		
		return filtered_modules
		
	def find_package_modules(self, package, package_dir):
		"""Overridden to filter return value using our exludes"""
		return self._filtered_module_list(build_py.find_package_modules(self, package, package_dir))
		
	def find_all_modules(self):
		"""Same as above, but ... different. Instaed of using the find_package_modules method, 
		it reimplements the same functionality ... wtf ??"""
		return self._filtered_module_list(build_py.find_all_modules(self))
		
	def fix_scripts(self):
		"""Check what the user classified as script and fix the first line
		to point to the right python interpreter version (only if we are compiling).
		Additionally, make the file executable on linux"""
		if not self.distribution.scripts:
			return
		# END check scripts are available
		out_dir = self._build_dir()
		scripts_abs = [ os.path.join(out_dir, s) for s in self.distribution.scripts ]
		scripts_abs = [ s for s in scripts_abs if os.path.isfile(s) ]	# skip pruned
		if not scripts_abs:
			return
		# END early abort
		
		BuildScripts.handle_scripts(scripts_abs, self.needs_compilation)
		
	def run(self):
		"""Perform the main operation, and handle git afterwards
		:note: It is done at a point where the py modules as well as the executables
		are available. In case there are c-modules, these wouldn't be availble here."""
		build_py.run(self)
		
		# POST REGRESSION TESTING
		#########################
		test_root = os.path.join(self._build_dir(), self.test_dir)
		self.post_regression_test(self._test_abspath(), test_root)
		
		# FIX SCRIPTS
		##############
		self.fix_scripts()
		
		# HANDLE GIT
		############
		self.update_git(self._build_dir())

	#} END overridden methods 


class BuildScripts(build_scripts):
	"""Uses our way to adjust the first line of the script, additionally rename 
	the executable to indicate the required interpreter. Otherwise scripts 
	would override each other anyway."""
	
	re_script_first_line = re.compile('^(#!.*python)[0-9.]*([ \t].*)?$')
	
	build_scripts.user_options.extend(
	[('exclude-scripts=', 'e', "Exclude the given comma separated list of scripts(globs) from being copied and installed"), ]
									)
	
	def initialize_options(self):
		build_scripts.initialize_options(self)
		self.exclude_scripts = list()
	
	def finalize_options(self):
		build_scripts.finalize_options(self)
		self.exclude_scripts = self.distribution.fixed_list_arg(self.exclude_scripts)
	
	#{ Interface 
	
	@classmethod
	def uses_mayapy(cls):
		""":return: True if the executable is mayapy"""
		return ('%smaya' % os.path.sep) in sys.executable.lower()
	
	@classmethod
	def handle_scripts(cls, scripts, adjust_first_line, suffix=''):
		"""Handle the given scripts to work for later installation
		:param scripts: paths to scripts to hanlde
		:param adjust_first_line: if True, the first line will receive the actual 
			python version to match the version of the this python interpreter
		:param suffix: if given, the suffix is assumed to be a suffix for all scripts.
			If scripts want to execfile each other, the name of the script needs adjustment
			to actually work, which is unknown to the script in advance. Hence we fix
			the string ourselves.
			The suffix is assumed to be appended to all input script files, revealing the 
			original script basename if the suffix is removed. The latter one is searched for 
			in the script.
			
			Note: The suffix cannot be used if we are running in mayapy. In that case the first 
			line will point to our current executable directly as mayapy can only be used for maya anyway."""
		if cls.uses_mayapy() and suffix:
			raise Exception("Suffixes may not be specified in mayapy mode: %s" % suffix)
		# END handle suffix in mayapy mode 
		
		re_includefile_path = None
		if suffix:
			basenames = [ os.path.basename(s)[:-len(suffix)] for s in scripts ]
			re_includefile_path = re.compile("""(\s*includefile_path.*['"])(%s)(['"].*)""" % '|'.join(basenames))
		# END handle suffix
			
		if adjust_first_line:
			for file in scripts:
				lines = open(file).readlines()
				if not lines:
					continue
				# END skip empty
				
				changed = False
				m = cls.re_script_first_line.match(lines[0])
				if m:
					if not cls.uses_mayapy():
						lines[0] = "%s%s%s\n" % (m.group(1), sys.version[:3], m.group(2) or '')
					else:
						# important: On posix, which is the only platform where this matters anyway, 
						# mayapy just prepares the environment and startsup python.
						# Hence we just force mayapy into the path, OSX compatible !
						exec_path = sys.executable
						if os.name == "posix":
							exec_path = os.path.join(sys.executable[:sys.executable.find('/bin/')], 'bin/mayapy')
							# on OSX though, mayapy is just a shell script that wants to be started with the
							# shell to actually work :)
							if sys.platform == 'darwin':
								exec_path = "/bin/sh %s" % exec_path
							# END OSX special handling
						# END adjust exec path
						lines[0] = "#!%s\n" % exec_path
					# END handle mayapy specifically
					changed=True
				# END handle shebang line
				
				if re_includefile_path:
					for i, line in enumerate(lines):
						m = re_includefile_path.match(line)
						if m is None: continue
						
						nline = m.group(1) + m.group(2) + suffix + m.group(3) + "\n"
						lines[i] = nline
						log.info("Adjusted line %r to %r" % (line, nline))
						changed = True
				# END handle execfile replacements
				
				if changed:
					open(file, 'wb').writelines(lines)
				# END write changes
			# END for each file
		# END fix first line
		
		if os.name == 'posix':
			for file in scripts:
				oldmode = os.stat(file).st_mode & 07777
				newmode = (oldmode | 0555)
				if newmode != oldmode:
					log.info("changing mode of %s from %o to %o", file, oldmode, newmode)
					os.chmod(file, newmode)
				# END change mode
			# END for each script
		# END make executable
	
	
	#} END interface 
	
	def copy_scripts(self):
		if self.dry_run:
			return
		# END not implemented
		
		self.mkpath(self.build_dir)
		outfiles = list()
		suffix = sys.version[:3]
		if self.uses_mayapy():
			suffix = ''
		# END no suffix for mayapy
		
		# on windows, we don't process scripts as they end up in distinctive
		# python installation directories
		if os.name == 'nt':
			suffix = ''
		# END handle windows suffix  
		
		# only copy what's left
		rmscripts = set()
		for pattern in self.exclude_scripts:
			# NOTE: no pattern conversion required, here its all based on 
			# linux setup script information	
			rmscripts.update(set(fnmatch.filter(self.scripts, pattern)))
		# END for each pattern 
		for rms in rmscripts:
			log.info("Excluding script: %r" % rms)
			self.scripts.remove(rms)
		# END remove matching script
		 
		for script in self.scripts:
			outfile = os.path.join(self.build_dir, os.path.basename(script))
			base, ext = os.path.splitext(outfile)
			
			# append py version !
			outfile = base + suffix + ext
			
			self.copy_file(script, outfile)
			outfiles.append(outfile)
		# END for each script 
		
		self.handle_scripts(outfiles, adjust_first_line=True, suffix=suffix)
	

class InstallLibCommand(install_lib):
	"""Makes sure the compilation does not happen - if the user wants it, it will 
	only work in the build_py command."""
	
	def byte_compile(self, files):
		"""Ignore it"""
		log.info("Skipping byte compilation - it should be done by build_py")
		

class InstallCommand(install):
	"""Assure compilation is done by build_py"""
	
	def run(self):
		"""initialize build_py with our compile options"""
		
		bcmd = self.distribution.get_command_obj('build_py')
		bcmd.compile = (self.compile is None and 1) or self.compile
		bcmd.optimize = self.optimize or 0
		
		install.run(self)


class GitSourceDistribution(_GitMixin, _RegressionMixin, sdist):
	"""Instead of creating an archive, we put the source tree into a git repository"""
	#{ Configuration 
	branch_suffix = '-src'
	#} END configuration
	
	_GitMixin.adjust_user_options(sdist.user_options)
	_RegressionMixin.adjust_user_options(sdist.user_options)


	def __init__(self, *args, **kwargs):
		# special solution to temporarily override the default distribution directory
		self._alternate_sdist_directory = None

	#{ Paths 
	def _sdist_directory(self):
		""":return: direcory containing the source distribution
		:note: there is no official function for this ... its just in the code ..."""
		if self._alternate_sdist_directory:
			return self._alternate_sdist_directory
		# END handle alternates
		return self.distribution.get_fullname()
	
	#} END paths

	#{ Overridden Functions
	
	def finalize_options(self):
		"""As the inheritance hierarchy is screwed up with old-style classes, 
		we have to forward to the call manually to our bases ... """
		sdist.finalize_options(self)
		_GitMixin.finalize_options(self)
		_RegressionMixin.finalize_options(self)
	
	def make_archive(self, base_name, format, root_dir=None, base_dir=None):
		self.update_git(base_dir)
		super(_GitMixin, self).make_archive(base_name, format, root_dir, base_dir)
		
	def make_distribution(self):
		"""Make s source distribution, but set it up to allow post-testing if desired"""
		# prevent deletion before test possibly ran
		keep_tmp = self.keep_temp
		self.keep_temp = True
		sdist.make_distribution(self)
		self.keep_temp = keep_tmp
		
		base_dir = self._sdist_directory()
		
		# If our root package is directly in the root folder, we have to rename
		# the basedir to match the root package name ( temporarily )
		package_dir = self.distribution.package_dir.get(self.distribution.pinfo.root_package)
		prev_base_dir = None
		inbetween_dir = 'sdist_tmp'
		if package_dir == '':	# if we have a root package in our root folder
			# special case: mrv tries to import itself to see whether it is in the 
			# path natively. This would work if we would just rename 
			# the folder to the root package name, causing lots of trouble down
			# the road. Hence we create a subdirectory to prevent this from 
			# happening.
			if not os.path.isdir(inbetween_dir):
				os.mkdir(inbetween_dir)
			# END handle dir creation
			
			target_dir = os.path.join(inbetween_dir, self.distribution.pinfo.root_package)
			os.rename(base_dir, target_dir)
			prev_base_dir = base_dir
			base_dir = target_dir
		# END rename base-dir 
		
		# RUN REGRESSION TEST
		#######################
		# will only actually run if it is enabled - we need the preprartion to
		# build the docs anyway
		testexec = os.path.join(base_dir, self.distribution._test_relapath())
		test_root = os.path.join(base_dir, self.test_dir)
		self.post_regression_test(testexec, test_root)
		
		# HOOK IN DOC DISTRO
		####################
		# The makedoc tool can only with our altered directory structure - hence
		# we must trigger the documentation generation now.
		if DocDistro.cmdname in self.distribution.commands: 
			dcmd = self.distribution.get_command_obj(DocDistro.cmdname, create=True)
			if dcmd is not None:
				self._alternate_sdist_directory = base_dir
				dcmd.ensure_finalized()
				try:
					dcmd.run()
				finally:
					self._alternate_sdist_directory = None
				# END build docs
			# END handle dcmd
		# END if docdist was set on commandline
		
		# finally clear the temp directory if requested
		if not self.keep_temp:
			dir_util.remove_tree(base_dir, dry_run=self.dry_run)
		else:
			# possibly rename the directory back to what it was
			if prev_base_dir is not None:
				os.rename(base_dir, prev_base_dir)
			# END handle rename 
		# END clean temp directory
		
		if os.path.isdir(inbetween_dir):
			os.rmdir(inbetween_dir)
		# END handle inbetween dir
		
	#} END overridden functions


class DocDistro(_GitMixin, Command):
	"""Build the documentation, and include everything into the git repository if 
	required."""
	
	cmdname = 'docdist'
	
	#{ Configuration
	user_options = [ 
					('zip-archive', 'z', "If set, a zip archive will be created"),
					('from-build-version', 'b', "If set, the documentation will be built from the recent build_py or sdist version")
					]
					
	branch_suffix = '-doc'
	
	# directory name containing the documentation
	doc_dir = 'doc'
	
	_GitMixin.adjust_user_options(user_options)
	#} END configuration
	
	def __init__(self, *args):
		self.docgen = None
		self.dist_dir = None
		self.zip_archive = False
		self.from_build_version = False
		self.handled_docs = False
	
	def initialize_options(self):
		# this needs to be here or we get an error because of the bitchy base class
   	   pass
   
	def finalize_options(self):
		_GitMixin.finalize_options(self)
		# documentation generator instance, only set if docs should be included
		self.docgen = None
		if self.dist_dir is None:
			self.dist_dir = self.distribution.dist_dir
		self._init_doc_generator()
	
	def run(self):
		if not self.distribution.use_git and not self.zip_archive:
			raise ValueError("Please specify to use git or to generate a zip-archive")
		# END assert config
		
		html_out_dir, was_built = self.build_documentation()
		
		# skip it if it does not exist anymore - in a previous invocation it could
		# have been handled already
		if not os.path.isdir(html_out_dir):
			return
		# END early abort
		
		if self.zip_archive:
			self.create_zip_archive(html_out_dir)
		# END create zip
	
		if self.distribution.use_git:
			self.update_git(html_out_dir)
		# END handle git
	
	#{ Interface
	
	def create_zip_archive(self, html_out_dir):
		"""Create a zip archive from the data in the html output directory
		:return: path to the created zip file"""
		fname = "%s-doc" % self.distribution.get_fullname()
		base_name = os.path.join(self.dist_dir, fname)
		
		zfile = self.make_archive(base_name, "zip", base_dir='.', root_dir=html_out_dir)
		self.distribution.dist_files.append((self.cmdname, '', zfile))
		return zfile
	
	def build_documentation(self):
		"""Build the documentation with our current version tag - this allows
		it to be included in the release as it has been updated
		
		:return: tuple(html_base, Bool) tuple with base directory containing all html
			files ( possibly with subdirectories ), and a boolean which is True if 
			the documentation was build, False if it was still uptodate """
		# reinit the generator, which will update its base dir as well
		docgen = self._init_doc_generator()
		if self.handled_docs:
			return (self.docgen.html_output_dir(), False)
		# END handle multiple calls
		self.handled_docs = True
		
		doc_dir = docgen.base_dir()
		
		# CHECK IF BUILD IS REQUIRED
		############################
		html_out_dir = docgen.html_output_dir()
		index_file = html_out_dir / 'index.html'
		needs_build = True
		if index_file.isfile():
			needs_build = False
			# version file for sphinx really should exist at least, its the main 
			# documentation no matter what
			st = 'sphinx'
			if not docgen.version_file_name(st, basedir=doc_dir).isfile():
				needs_build = True
			# END check existing version info
			
			if not needs_build:
				for token in ('coverage', 'epydoc', st):
					# check if the docs need to be rebuild
					try:
						docgen.check_version('release', token)
					except EnvironmentError:
						needs_build = True
					# END docs don't need to be build
				# END for each token
			# END additional search
		# END check version as index exists
		
		if not needs_build:
			log.info("Skipped building documentation as it was uptodate and complete")
			return (html_out_dir, False)
		# END skip build
		
		# when actually creating the docs, we start the respective script as found
		# in our project info
		makedocpath = self.distribution._makedoc_relapath()
		
		# makedoc must be started from the doc directory
		p = self.distribution.spawn_python_interpreter((makedocpath, ), cwd=doc_dir)
		if p.wait():
			raise ValueError("Building of Documentation failed")
		# END wait for build to complete
		
		return (html_out_dir, True)
	#} END interface 
	
	#{ Paths
	
	def _doc_directory(self):
		"""
		:return: path to the doc directory which (usually) contains the makedoc 
			executable"""
		doc_dir = self.doc_dir
		if self.from_build_version:
			base_dir = None
			
			# try build_py - sdist handles us directly
			cmds = self.distribution.commands
			if 'sdist' in cmds:
				scmd = self.get_finalized_command('sdist', create=True)
				base_dir = scmd._sdist_directory()
			elif 'build_py' in cmds or 'build' in cmds:
				bcmd = self.get_finalized_command('build_py', create=True)
				base_dir = bcmd._build_dir()
			# END handle build_py
			
			if base_dir is None:
				raise EnvironmentError("Could not determine valid documentation directory")
			# END handle error
			doc_dir = os.path.join(base_dir, doc_dir)
		# END handle build version docs generation
		
		return doc_dir
		
	#} END paths
	
	#{ Internal
	
	def _init_doc_generator(self):
		"""initialize the docgen instance, and return it"""
		doc_dir = self._doc_directory()
		if self.docgen is not None:
			# assure the base_dir is still pointing to the right location - it 
			# may change during runtime
			return self.docgen.set_base_dir(doc_dir)
		# END handle duplicate calls
		
		# try to use an overriden docgenerator, then our own one
		GenCls = None
		try:
			docbase = __import__("%s.doc.base" % self.pinfo.root_package, fromlist=['doesntmatter'])
			GenCls = docbase.DocGenerator
		except (ImportError, AttributeError):
			import mrv.doc.base as docbase
			GenCls = docbase.DocGenerator
		# END get doc generator class
		
		if not os.path.isdir(doc_dir):
			raise EnvironmentError("Cannot build documentation as '%s' directory does not exist" % doc_dir)
		# END check doc dir exists
		
		self.docgen = GenCls(base_dir=doc_dir)
		return self.docgen
	
	#} END internal


class Distribution(object, BaseDistribution):
	"""Customize available options and behaviour to work with mrv and derived projects"""
	
	#{ Configuration
	
	# module providing project related information
	pinfo = None 
	
	# root package module, will be set by the main routine, must be set 
	# for this class to work
	rootpackage = None
	
	# directory to which all of our comamnds will store their distribution data
	# Please note that other subcommands that are not overridden by us redefined
	# this value privately, hence it is not recommended to change this here.
	dist_dir = 'dist'
	
	# directory containing all external packages
	ext_dir = 'ext'
	#} END configuration
	
	
	# Additional Global Options
	opt_maya_version = 'maya-version'
	
	BaseDistribution.global_options.extend(
		( ('%s=' % opt_maya_version, 'm', "Specify the maya version to operate on"),
		  ('regression-tests=', 't', "If set (default), the regression tests will be executed, distribution fails if one test fails"),
		  ('use-git=', 'g', "If set (default), the build results will be put into a git repository"),
		  ('force-git-tag', 'f', "If set, the corresponding git tag will be moved to your current root repository commit"),
		  ('add-requires=', 'r', "Specifies a comma separated list of 'requires' ids to be added to ones given to setup()"),
		  ('package-search-dirs=', 'p', "If set, defaults to 'ext', packages within the given directories will be distributed as well"),)
	)
	
	
	#{ Internals
	
	@classmethod 
	def modifiy_sys_args(cls):
		"""Parse our own arguments off the args list and modify the argument 
		stream accordingly.
		
		:note: needs to be called before setup of the distutils is called"""
		rargs = [sys.argv[0]]
		args = sys.argv[1:]
		while args:
			arg = args.pop(0)
			rargs.append(arg)
		# END while there are args
		
		del(sys.argv[:])
		sys.argv.extend(rargs)
	
	@classmethod
	def version_string(cls, version_info):
		""":return: version string from the given version info which is assumed to 
		be in the default python version_info format ( sys.version_info )"""
		base = "%i.%i.%i" % version_info[:3]
		if version_info[3]:
			base += "-%s" % version_info[3]
		return base
		
	def get_fullname(self):
		""":return: Full name, including the python version we are compiling the code"""
		basename = self.metadata.get_fullname()
		bcmd = self.get_command_obj('build_py', create=False)
		if bcmd and bcmd.finalized and bcmd.needs_compilation:
			basename += "-py%s" % sys.version[:3]
		# END make names dependent on the actual version if bytecode is used
		return basename
		
	def _query_user_token(self, tokens):
		"""Read tokens from user and finally return a token he picked
		:raise Exception: if user failed in some point.
		:return: tuple with version info in corresponding format"""
		ml = 5
		assert len(tokens) == ml, "invalid token format: %s" % str(tokens)
		
		while True:
			ot = list()
			
			# provide all tokens to the user and allow him to change each one
			print "The current version is: %s" % ', '.join(str(t) for t in tokens)
			print "Each version token will be presented to you in order, and you may provide an alternative"
			print "Once you are happy with the result, it will be written to the init file"
			print ""
			for count, (token, ttype) in enumerate(zip(tokens, (int, int, int, str, int))):
				while True:
					answer = raw_input("%s %i of %i == %s [%s]: " % (ttype.__name__, count+1, ml, token, token))
					if answer == '':
						answer = str(token)
					# END handle default answer
					
					try:
						converted = ttype(answer)
						if issubclass(ttype, basestring):
							converted = converted.strip()
							for char in "\"'":
								if converted.endswith(char): 
									converted = converted[:-1]
								if converted.startswith(char):
									converted = converted[1:]
							# END for each character to truncate
						# END handle strings
							
						ot.append(converted)
						break		# get out of the type loop
					except ValueError:
						print "Answer %r could not be converted to %s - please try again" % (answer, ttype.__name__)
						continue
					# END exception handline
				# END get type right loop
			# END for each token/type pair
			
			# present the version to the user, one last time
			print "The version you selected is: %s" % ', '.join(str(t) for t in ot)
			print "Continue with it or try again ?"
			asw = 'continue'
			answer = raw_input("%s/retry [%s]: " % (asw, asw)) or asw
			if answer != asw:
				tokens = ot
				continue
			# END handle retry
			
			return tuple(ot)
		# END while to determine user is happy
		
	def handle_version_and_tag(self):
		"""Assure our current commit in the main repository is tagged properly
		If so, continue, if not, try to create a tag with the current version.
		If the version was already tagged before, help the user to adjust his 
		version string in the root module, make a commit, and finally create 
		the tag we were so desperate for. The main idea is to enforce a unique 
		version each time we make a release, and to make that easy.
		
		:return: TagReference object created
		:raise EnvironmentError: if we could not get a valid tag"""
		import git
		
		root_repo = self.root_repo
		root_head_commit = root_repo.head.commit
		tags = [ t for t in git.TagReference.iter_items(root_repo) if t.commit == root_head_commit ]
		if len(tags) == 1:
			return tags[0]
		# END tag existed
		
		
		msg = "Please create a tag at your main repository at your currently checked-out commit to mark your release"
		createexc = EnvironmentError(msg)
		if not sys.stdout.isatty():
			raise createexc
		# END abort if we cannot communicate
			
		def version_tag(vi):
			tag_name = 'v%i.%i.%i' % vi[:3]
			if vi[3]:
				tag_name += "-%s" % vi[3]
			# END append suffix
			
			out_tag = None
			return git.Tag.from_path(root_repo, git.Tag.to_full_path(tag_name))
		# END version tag creator 
		
		# CREATE TAG ?
		##############
		# from current version
		# ask the user to create a tag - make sure it does not yet exist 
		# before asking
		target_tag = version_tag(self.pinfo.version)
		
		# if force is specified, we may just create the tag forcibly and proceed
		# This only works for us if we have a string tag in our version - this 
		# is usually not the case for non-release versions, but for alphas, preview, 
		# betas etc.
		can_set_tag = not target_tag.is_valid() 
		may_force = self.force_git_tag and not can_set_tag and self.pinfo.version[3]	# string descriptor
		if not may_force and (self.force_git_tag and not can_set_tag):
			log.warn("Cannot force git tag if string identifier of your info.version is not set")
		# END emit warning
		
		if may_force or can_set_tag:
			asw = "abort"
			add = (may_force and not can_set_tag and '*forcibly* ') or '' 
			msg = "Would you like me to %screate the tag %s in your repository at %s to proceed ?\n" % (add, target_tag.name, root_repo.working_tree_dir)
			msg += "yes/%s [%s]: " % (asw, asw)
			answer = raw_input(msg) or asw
			if answer != 'yes':
				raise createexc
			# END check query
			
			return git.TagReference.create(root_repo, target_tag.name, force=may_force)
		# END could create the tag with current version 
		
		# INCREMENT VERSION AND CREATE TAG
		##################################
		asw = "adjust version"
		msg = """Your current commit is not tagged - the automatically generated tag name %s does already exist at a previous commit.
Would you like to adjust your version info or abort ?
%s/abort [%s]: """ % (target_tag.name, asw, asw) 
		answer = raw_input(msg) or asw
		if answer != asw:
			raise createexc
		# END abort automated creation
		
		# ASSURE INIT FILE UNCHANGED
		# parse the init script and adjust it - if there are changes in the 
		# working tree file, abort !
		info_file = os.path.splitext(self.pinfo.__file__)[0] + ".py"
		if not os.path.isfile(info_file):
			raise EnvironmentError("Project information file source does not exist at %r" % info_file)
		if len(root_repo.index.diff(None, paths=info_file)):
			raise EnvironmentError("The init file %r that would be changed contains uncommitted changes. Please commit them and try again" % info_file)
		# END assure init file unchanged
		
		out_lines = list()
		made_adjustment = False
		fmtexc = ValueError("Expecting following version format: version = (1, 0, 0, 'string', 0)")
		for line in open(info_file, 'r'):
			if not made_adjustment and line.strip().startswith('version'):
				# present the stripped strings separated by commas - it must be a tuple
				# fail on parsing errors
				sline = line.strip()
				if not sline.endswith(')'):
					raise fmtexc
					
				tokens = [ t.strip() for t in sline[sline.find('(')+1:-1].split(',') ]
				
				if len(tokens) != 5:
					raise fmtexc
				
				while True:
					tokens = self._query_user_token( tokens )
					
					# verify the version provides a unique tag name
					target_tag = version_tag(tokens)
					if not target_tag.is_valid():
						break
					# END have valid tag ( as it does not yet exist )
					
					asw = 'increment'
					print "The tag created according to your version info %r does already exist. Increment the minor version and retry ?" % target_tag.name
					answer = raw_input("%s/abort [%s]: " % (asw, asw)) or asw
					if answer != asw:
						raise createexc
					# END handle answer
					
					# increment minor
					ptl = list(tokens)
					ptl[2] += 1
					tokens = tuple(ptl)  
					print "\nIncremented minor version to %i" % ptl[2]
					print "You will be asked to verify the new version again, allowing you to adjust it manually as well\n"
				# END while user didn't provide a unique token
				
				# build a new line with our updated version info
				line = "version = ( %i, %i, %i, '%s', %i )\n" % tokens
				
				made_adjustment = True
			# END adjust version-info line with user help
			out_lines.append(line)
		# END for each line
		
		if not made_adjustment:
			raise fmtexc
		
		# query the commit message
		cmsg = "Adjusted version to %s " % target_tag.name[1:]
		
		print "The changes to the init file at %r will be committed." % info_file 
		print "Please enter your commit message or hit Ctrl^C to abort without a change to your file"
		cmsg = raw_input("[%s]: " % cmsg) or cmsg
		
		# write the file back - at this point the index is garantueed to be clean
		# so our init file is the only one that changes
		open(info_file, 'wb').writelines(out_lines)
		root_repo.index.add([info_file])
		commit = root_repo.index.commit(cmsg, head=True)
		
		# create tag on the latest head 
		git.TagReference.create(root_repo, target_tag.name, force=False)
		
		return target_tag
			
	def spawn_python_interpreter(self, args, cwd=None):
		"""Start the default python interpreter, and handle the windows special case
		:param args: passed to the python interpreter, must not include the executable
		:param cwd: if not None, it will be set for the childs working directory
		:return: Spawned Process
		:note: All output channels of our process will be connected to the output channels 
			of the spawned one"""
		import mrv.cmd.base
		py_executable = mrv.cmd.base.python_executable()
		
		actual_args = (py_executable, ) + tuple(args)
		cwdinfo = (cwd and " at %r" % cwd) or ''
		log.info("Spawning%s: %s" % (cwdinfo, ' '.join(actual_args)))
		proc = subprocess.Popen(actual_args, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd)
		return proc
		
	def perform_regression_tests(self):
		"""Run regression tests and fail with a report if one of the regression 
		test fails""" 
		import mrv.cmd.base
		tmrvrpath = self._regressiontest_relapath()
		
		p = self.spawn_python_interpreter((tmrvrpath, ))
		if p.wait():
			raise ValueError("Regression Tests failed")
			
	#} END Internals 
	
	
	#{ Path Generators
	
	def _rootpath(self):                   
		""":return: path to the root of the rootpackage, which includes all modules
		and subpackages directly"""
		return ospd(os.path.abspath(self.pinfo.__file__)) 

	def _test_relapath(self):
		""":return: tmrv compatible test executable"""
		return self.pinfo.nosetest_exec
		
	def _regressiontest_relapath(self):
		""":return: tmrvr compatible test executable relative to the project root"""
		return self.pinfo.regression_test_exec

	def _makedoc_relapath(self):
		""":return: relative path to makedoc executable"""
		return self.pinfo.makedoc_exec
		
	#} END path generators

	
	#{ Interface
	
	@classmethod
	def fixed_list_arg(cls, value):
		"""As the comamndline parsing is as bad as it gets, it will not parse the 
		correct types, nor will it split ',' separated items into a list correctly.
		If options are provided via the comandline, they are generally screwed up
		as they are plain strings, so each and every command has to check and verify
		them by itself. Well done, could have been a nice base task job.
		We check value for a comman separated string, and return the parsed list
		if necessary, or the value itself if it is already a list or tuple"""
		if isinstance(value, (list, tuple)):
			return value
		return [ s.strip() for s in value.split(',') ]
	
	@classmethod
	def retrieve_project_info(cls):
		"""import the project information module
		:return: package info module object"""
		try:
			import info
			cls.pinfo = info
		except ImportError:
			raise ImportError("Failed to import package information module (info.py)"); 
		# END import exception handling
		
		return cls.pinfo
		
	@classmethod
	def retrieve_root_package(cls, basedir='.'):
		"""Make sure the root package is in the python path and is set as our root
		:return: root package object"""
		try:
			cls.rootpackage = __import__(cls.pinfo.root_package)
		except ImportError:
			packageroot = os.path.realpath(os.path.abspath(basedir))
			sys.path.append(ospd(packageroot))
			try:
				cls.rootpackage = __import__(cls.pinfo.root_package)
			except ImportError:
				log.info("Contents of your sys.path:")
				for p in sys.path: log.info("%r" % p)
				del(sys.path[-1])
				raise ImportError("Failed to import root package %r as it could not be found in your syspath" % (cls.pinfo.root_package)); 
			# END second attempt exception handling
		# END import exception handling
		
		return cls.rootpackage
	
	def get_packages(self):
		""":return: list of all packages in rootpackage in __import__ compatible form"""
		base_packages = [self.pinfo.root_package] + [ self.pinfo.root_package + '.' + pkg for pkg in find_packages(self._rootpath())]

		for search_path in self.package_search_dirs:
			if not os.path.isdir(search_path):
				log.debug("package search path %r did not exist" % search_path)
				continue
			# END skip non-existing
			
			# try to get an iterator - followlinks is not supported in the easy_install
			# pseudosandbox ...
			try:
				dirwalker = os.walk(search_path, followlinks=True)
			except TypeError:
				dirwalker = os.walk(search_path)
			# END handle sandbox
			
			for root, dirs, files in dirwalker:
				# remove hidden paths, or paths with a '.' in them as they cannot 
				# be handled properly
				for dir in dirs[:]:
					if '.' not in dir:
						continue
					try:
						dirs.remove(dir)
					except ValueError:
						pass
					# END exception handling
				# END for each path to check
				
				# process paths
				for dir in dirs:
					dirpath = os.path.join(root, dir)
					base_packages.append(self.pinfo.root_package+"."+dirpath.replace(os.sep, '.'))
				# END for each remaining valid directory
			# END walking external dir
		# END for each search dir
		return base_packages
		
	#} END interface 
	
	#{ Overridden Methods
	def __new__(cls, *args, **kwargs):
		"""Fix the objet.__new__ call with arguments that would occur. This
		is a serious issue, not only here but also for mixin classes that need 
		initialization - types don't know who derives from them, and which hierarchy
		they are in, and they have to call super to pass on the __init__ call to 
		possible mixins in the derived hierarchy"""
		return object.__new__(cls)
		
	def __init__(self, *args, **kwargs):
		"""Initialize base and set some useful defaults"""
		BaseDistribution.__init__(self, *args, **kwargs)
		if self.pinfo is None:
			self.retrieve_project_info()
		# END assure root is set
		
		# at this point, the options have not yet been parsed
		self.py_version = float(sys.version[:3])
		self.maya_version = None
		self.regression_tests = False
		self.use_git = False
		self.root_repo = None
		self.force_git_tag = 0
		self.add_requires = list()
		self.package_search_dirs = None
		self.push_queue = list()
		
		# Override Commands
		self.cmdclass[build_py.__name__] = BuildPython
		self.cmdclass[build_scripts.__name__] = BuildScripts
		self.cmdclass[sdist.__name__] = GitSourceDistribution
		self.cmdclass[install_lib.__name__] = InstallLibCommand
		self.cmdclass[install.__name__] = InstallCommand
		
		self.cmdclass[DocDistro.cmdname] = DocDistro
		
		# well, here it comes: For some reason, the superclass dynamically attaches
		# access methods from the distmetadata class onto itself. Its amazing, 
		# so to override it, we have to do the same ... .
		self.get_fullname = new.instancemethod(type(self).get_fullname.im_func, self, type(self))
		
	def __del__(self):
		"""undo monkey patches"""
		if sys is None:
			return
		
		if hasattr(self, '_orig_sys_version'):
			sys.version = self._orig_sys_version
		
	def parse_command_line(self):
		"""Handle our custom options"""
		rval = BaseDistribution.parse_command_line(self)
		
		if self.package_search_dirs is None:
			self.package_search_dirs = [self.ext_dir]
		else:
			self.package_search_dirs = self.fixed_list_arg(self.package_search_dirs)
		# END handle package search dirs
		
		# handle packages
		if not self.packages:
			self.packages = self.get_packages()
		# END auto-generate packages if not explicitly set
		
		# handle evil types - the underlying systems puts strings into the variables
		# ... how can you ?
		self.use_git = int(self.use_git)
		self.regression_tests = int(self.regression_tests)


		is_build_mode = 'install' not in self.commands and 'bdist_egg' not in self.commands

		# in install mode, we never use git or run regression tests
		if not is_build_mode:
			log.debug("Disabled usage of git and regression testing as install command is present")
			self.use_git = False
			self.regression_tests = False
			self.maya_version = None
		else:
			# import the root module to allow us importing mrv. This is only required
			# if a few commands are used, and may not always be possible. Problem
			# here is that we don't know all commands in advance, so we have a few 
			# hardcoded cases here when NOT to use the root package
			self.retrieve_root_package()
		# END handle install mode
		
		
		if self.maya_version is not None:
			import mrv.cmd.base
			try:
				self.py_version = mrv.cmd.base.python_version_of(float(self.maya_version))
				
				# APPLY MONKEY PATCHES
				# NOTE: There is a method called get_python_version, but it is not used
				# by all commands, so the safest thing is to override sys.version ... 
				# ... yeah, whatever
				self._orig_sys_version = sys.version
				sys.version = "%g" % (self.py_version)
			except ValueError:
				raise ValueError("Incorrect MayaVersion format: %s" % self.maya_version)
		# END handle python version
		
		
		if isinstance(self.add_requires, basestring):
			# well, lets parse the requires addition manually, metadata cannot 
			# be set by the commandline, but only queried ... so we have to make 
			# it a special case, yipeee.
			if self.metadata.requires is None:
				self.metadata.requires = list()
			# END assure we have a list
			
			# assign unique depends
			self.add_requires = self.fixed_list_arg(self.add_requires)
			self.metadata.set_requires(sorted(list(set(self.metadata.requires) | set(self.add_requires)))) 
		# END process requires
		
		
		# setup git if required
		if self.use_git:
			try:
				import git
			except ImportError:
				raise ImportError("Please make sure that GitPython is available to python %s" % sys.version[:3])
			# END handle git nicely just once
			self.root_repo = git.Repo(ospd(self.pinfo.__file__))
		# END init root repo


		return rval
		
	def run_commands(self):
		"""Perform required pre- and post-run actions"""
		if self.use_git:
			self.handle_version_and_tag()
		# END assure git tag is set correctly
		
		if self.regression_tests:
			self.perform_regression_tests()
		# END regression tests
		
		# safety check: do make sure we don't get confused with the interpreter 
		# version, verify that building and installation are separate steps
		if 'install' in self.commands and \
			('sdist' in self.commands or len([c for c in self.commands if c.startswith('build')])):
			raise ValueError("Cannot create build or sdist distribution in the same run as installing them. Please separate the calls")
		# END handle special case
		
		BaseDistribution.run_commands(self)
		
		# once everything worked, push to remotes if something is on the stack
		optimization_set = set()
		for pcall in self.push_queue:
			if pcall in optimization_set:
				continue
			# END skip similar ones
			pcall()
			optimization_set.add(pcall)
		# END for each call
		
		del(self.push_queue[:])
		
	
	#} END overridden methods


#} END commands



def main(args, distclass=Distribution):
	distclass.modifiy_sys_args()
	info = distclass.retrieve_project_info()
	
	setup(
	      distclass=distclass,
	      name = info.project_name,
		  version = distclass.version_string(info.version),
		  description = info.description,
		  author = info.author,
		  author_email = info.author_email,
		  url = info.url,
		  license = info.license,
		  package_dir = {info.root_package : ''},
		  zip_safe=False,
		  **info.setup_kwargs
		  )
	

if __name__ == '__main__':
	main(sys.argv[1:])
