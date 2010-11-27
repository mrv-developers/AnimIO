# -*- coding: utf-8 -*-
import os
import sys
import glob 

#{ Configuration 
# The configuration provided here is used by the template to learn more about 
# your particular project. Additionally it is used during distribution


# the minimum version of MRV that you require to work properly - usually the 
# version you used during development, its worth testing older versions though to 
# be more compatible 
mrv_min_version = (1, 0, 0)		# ( major, minor, micro )

# Information about the version of your tool
#               major, minor, micro, releaselevel, serial
version = (0,     2,     0,     'Preview',        0)

# the name of your tool or program
project_name = "AnimIO"

# The name of the rootpackage/root-directory under which all other modules are 
# located
root_package = "animio"

# Author Name
author = "Martin Freitag & Sebastian Thiel"

# Authors Email
author_email = 'not@provided.com'

# url of the project's main web presence
url = 'http://gitorious.org/animio'

# A short description of your project
description = 'Convenient Animation Export and Import'

# License Identification String
license = "BSD License"

# Will be automatically set during build to track the source version used for 
# the distribution
src_commit_sha = '0'*40



# paths to executables, relative to our project root
regression_test_exec = 'ext/mrv/test/bin/tmrvr'
nosetest_exec = 'ext/mrv/test/bin/tmrv'
makedoc_exec = '../ext/mrv/doc/makedoc'


# Additional Keyword Arguments to be passed to distutils.core.setup
# This should include the 'classifiers' keyword which is important to pipy
setup_kwargs = dict(
				package_data = {'animio.test' : ['fixtures', 'performance', 'ui']},
				options = dict(build_py={	'exclude_from_compile' : ('*/maya/undo.py', '*/maya/nt/persistence.py'), 
											'exclude_items' 		: ('mrv.doc', 'mrv.test')} )
				)


# Optionally taken into consideration by the DocGenerator implementation 
doc_config = dict(
				epydoc_show_source = 'yes', 
				epydoc_modules = "modules: unittest\nmodules: ../animio",  
				epydoc_exclude = "%s.test" % (root_package),
				)

#} END configuration
