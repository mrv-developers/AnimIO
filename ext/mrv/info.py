# -*- coding: utf-8 -*-
"""
Provide project related global information.

:note: Importing this module must not have any side effects !
"""
import os

# GENERAL INFORMATION
#####################
## Version Info 
# See http://docs.python.org/library/sys.html#sys.version_info for more information
#               major, minor, micro, releaselevel, serial
version = (1,     0,     0,     'Preview2',        0)

# The short name for your project, important for your documentation headline as 
# well as for the name of your distribution archives and git heads.
project_name = "mrv"

# The name of your root package as used in import statements. Capitalization matters, 
# usually all lower case letters
root_package = "mrv"

# The full name of the original author(s)
author = "Sebastian Thiel"

# The author's email address(es), must be set to something for the distribution to work.
author_email = 'byronimo@gmail.com'

# URL of the project's home page, or '' if there is None
url = "http://gitorious.org/mrv"

# A short description of your project, usually not more than one line.
description ='Development Framework for Autodesk Maya'

# The name of the project's license
license = "BSD License"

# The sha belonging to the commit which created this release.
# Will only be set in actual release versions, and must never be set manually
src_commit_sha = '0'*40


# PATH INFORMATION
###################
# The distribution system offers to run regression tests automatically. For that 
# to work, it needs a hint to where to find the respective executables.
# These are assumed to be compatible to the ones provided by MRV in case 
# you provide an own implementation.
regression_test_exec = 'test/bin/tmrvr'
nosetest_exec = 'test/bin/tmrv'
# makedoc is special in that it wants to be started from within the project's doc
# directory. The path given here is relative to it
makedoc_exec = 'makedoc'


# SETUP SCRIPT KWARGS
#####################
# MRV's distribution system is based on distutils. The following dictionary will 
# be passed to the setup routine of the distutils and applies additional configuration.
# Read more about the distutils: http://docs.python.org/distutils/
__scripts_bin = ['bin/mrv', 'bin/imrv']
__scripts_test_bin = ['test/bin/tmrv', 'test/bin/tmrvr']
__scripts_test_bin_s = [ p.replace('test/', '') for p in __scripts_test_bin ]
__ld = """MRV is a multi-platform python development environment to ease rapid development 
of maintainable, reliable and high-performance code to be used in and around Autodesk Maya."""
__requires = [ 'nose', 'epydoc', 'sphinx', 'gitpython' ]
if os.name == 'posix':
	__requires.append('ipython')
# END easy_install ipython on linux + osx

setup_kwargs = dict(
					# scripts in the context of the distribution are executable python 
					# scripts that should wind up executable when installed.
					# scripts = list('path', ...)
					scripts=__scripts_bin + __scripts_test_bin,
					
					# The long description is used on pypi I presume if the commandline 
					# based upload is used. For MRV the manual upload id preferred though
					# As the distutils don't provide a way to safely store non-cleartext
					# credentials for the login
					# long_description = string
                    long_description = __ld,
                    
                    # Winds up as egg-info which informs easy-install which other packages
                    # ought to be downloaded to make this project operational
                    # requires = list(id, ...) 
                    requires=__requires,
                    
                    # Each package to be build by build_py can be enriched with data files
                    # which are copied into the build version of the respective package.
                    # MRV introduces the ability to specify directories and exclude patterns 
                    # which are prefixed with an exclamation mark (!)
                    # package_data = dict( package_name : list('pattern', ...) )
                    package_data = {   'mrv.test' : ['fixtures/ma/*', 'fixtures/maya_user_prefs/', 'maya/performance' ] + __scripts_test_bin_s, 
                    					'mrv' : __scripts_bin + ['!*.gitignore'],
                    					'mrv.maya' : ['cache'],
                    					'mrv.doc' : ['source', 'makedoc', '!*source/generated/*']
                    				},
                    				
                    # Classifiers are used exclusively by the python package index
                    # and wind up in the package info/egg info. This is important
                    # for command-line upload only, Here it serves more as general 
                    # information that is not strictly required in the distribution 
                    # process
                    # classifiers = list(classifier, ...)
                    classifiers = [
                        "Development Status :: 5 - Production/Stable",
                        "Intended Audience :: Developers",
                        "License :: OSI Approved :: BSD License",
                        "Operating System :: OS Independent",
                        "Programming Language :: Python",
                        "Programming Language :: Python :: 2.5",
                        "Programming Language :: Python :: 2.6",
                        "Topic :: Software Development :: Libraries :: Python Modules",
                        ], 
                        
                    # Options are a more interesting kwarg as it is itself a dict
                    # mapping option dicts to setup subcommand names. This allows 
                    # to pass information directly to the specified subcommand, each 
                    # of them supporting a unique set of options
                    # options = dict( subcommand = dict( option_name : option_value ) )
					options = dict(build_py={	'exclude_from_compile' : (	'*/maya/undo.py', 
																			'*/maya/nt/persistence.py', 
																			'info.py'), 
												'exclude_items' : ('mrv.conf', 'mrv.dg', 'mrv.batch', 'mrv.mdp', 
																	'.automation', '.qa',
																	'mrv.test.test_conf', 'mrv.test.test_dg', 
																	'mrv.test.test_batch', 'mrv.test.test_mdp', 
																	'mrv.test.test_conf') }, 
									build_scripts={ 'exclude_scripts' : ['test/bin/tmrvr']}) 
                    )


# EPYDOC CONFIGURATION
######################
# These values help to dynamically generate the epydoc.cfg file which will be used 
# to configure the epydoc source documentaiton generator.
doc_config = dict(
				epydoc_show_source = 'yes',
				epydoc_modules = "modules: unittest\nmodules: pydot,pyparsing\nmodules: ../,../ext/networkx/networkx",
				epydoc_exclude = "mrv.test,mrv.doc,mrv.cmd.ipythonstartup",
				)
