# -*- coding: utf-8 -*-
"""
Provide project related global information.

:note: Importing this module must not have any side effects !
"""

#{ Configuration 


# GENERAL INFORMATION
#####################
## Version Info 
# See http://docs.python.org/library/sys.html#sys.version_info for more information
#               major, minor, micro, releaselevel, serial
version = (1,     0,     0,     'Preview',        0)

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

__scripts_bin = ['bin/mrv', 'bin/imrv']
__scripts_test_bin = ['test/bin/tmrv', 'test/bin/tmrvr']
__scripts_test_bin_s = [ p.replace('test/', '') for p in __scripts_test_bin ]
__ld = """MRV is a multi-platform python development environment to ease rapid development 
of maintainable, reliable and high-performance code to be used in and around Autodesk Maya."""


# SETUP SCRIPT KWARGS
#####################
# MRV's distribution system is based on distutils. The following dictionary will 
# be passed to the setup routine of the distutils and applies additional configuration.
# Read more about the distutils: http://docs.python.org/distutils/
setup_kwargs = dict(scripts=__scripts_bin + __scripts_test_bin, 
                    long_description = __ld,
                    package_data = {   'mrv.test' : ['fixtures/ma/*', 'fixtures/maya_user_prefs/'] + __scripts_test_bin_s, 
                    					'mrv' : __scripts_bin + ['!*.gitignore'],
                    					'mrv.maya' : ['cache'],
                    					'mrv.doc' : ['source', 'makedoc', '!*source/generated/*']
                    				},   
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
					options = dict(build_py={	'exclude_from_compile' : ('*/maya/undo.py', '*/maya/nt/persistence.py'), 
												'exclude_items' : ('mrv.conf', 'mrv.dg', 'mrv.batch', 'mrv.mdp', 
																	'.automation',
																	'mrv.test.test_conf', 'mrv.test.test_dg', 
																	'mrv.test.test_batch', 'mrv.test.test_mdp', 
																	'mrv.test.test_conf') }, 
									build_scripts={ 'exclude_scripts' : ['test/bin/tmrvr']}) 
                    )
#} END configuration

