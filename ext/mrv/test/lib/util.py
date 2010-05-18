# -*- coding: utf-8 -*-
import os
from mrv.path import Path

def fixture_path( name ):
	""":return:
		path to fixture file with ``name``, you can use a relative path as well, like
		subfolder/file.ext"""
	return Path(os.path.abspath( os.path.join( os.path.dirname( __file__ ), "../fixtures/%s" % name ) ))
	
def get_maya_file( filename ):
	""":return: path to specified maya ( test ) file """
	return fixture_path( "ma/"+filename )

