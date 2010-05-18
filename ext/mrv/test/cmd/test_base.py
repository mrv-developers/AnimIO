# -*- coding: utf-8 -*-
"""Test for commands - the funny thing here is that it needs itself to be working in order
to run the tests"""
from mrv.test.lib import *
from mrv.cmd.base import *

import os
import optparse

class TestBase( unittest.TestCase ):
	def test_base( self ):
		valid_versions = (8.5, 2008, 2009.0, 2010, 2011.0)
		
		# supported version
		for ver in valid_versions:
			assert is_supported_maya_version(ver)
			assert isinstance(python_version_of(ver), float)
		# END check valid versions on methods
		
		for ver in ("hello", 7.0):
			assert not is_supported_maya_version(ver)
			
		# parse versions
		for ver in valid_versions:
			parsed, version = parse_maya_version(str(ver), 8.5)
			assert parsed and version == ver
		# END for each version to check
		
		parsed, version = parse_maya_version('-c', 8.5)
		assert not parsed
		
		# python_version raises
		self.failUnlessRaises(EnvironmentError, python_version_of, 2050)
		
		
		# test maya location - find one, or raise environment error
		for ver in valid_versions:
			try:
				mayalocatiion = maya_location(ver)
			except EnvironmentError:
				pass
			else:
				assert os.path.isdir(mayalocatiion)
			# END exception handling
		# END for each valid version
		
		self.failUnlessRaises(EnvironmentError, maya_location, 2050)
		
		# at least one version should be found
		versions = available_maya_versions()
		assert versions == sorted(versions)
		assert versions and isinstance(versions[0], (float, int))
		
		
		# misc
		assert isinstance(python_executable(), basestring)
		assert isinstance(python_executable(2.6), basestring)
		
		assert isinstance(find_mrv_script('mrv'), Path)
		self.failUnlessRaises(EnvironmentError, find_mrv_script, 'something')
