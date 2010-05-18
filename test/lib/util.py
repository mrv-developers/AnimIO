# -*- coding: utf-8 -*-
import os
import mrv.maya as mrvmaya
from mrv.test.maya import save_for_debugging 

#{ Functions 

def fixture_base():
	return os.path.abspath(os.path.join( os.path.dirname(__file__), "../fixtures"))

def fixture_path( subpath ):
	"""@return: abspath path to fixture, it basically appends subpath to the fixture directory"""
	return os.path.join(fixture_base(), subpath)

#} END functions 

#{ Decorators
def with_scene( basename ):
	"""Loads the specified scene . the basename is supposed to be in our fixtures
	directory"""
	if not isinstance(basename, basestring):
		raise ValueError("Need basename of a scene as string, not %r" % basename)
	# END arg check
	
	def wrapper(func):
		def scene_loader(self, *args, **kwargs):
			scene_path = fixture_path(basename)
			mrvmaya.Scene.open(scene_path, force=True)
			print "Opened Scene: '%s'" % basename
			
			try:
				return func(self, *args, **kwargs)
			finally:
				mrvmaya.Scene.new(force=1)
			# END assure new scene is loaded after test
		# END internal wrapper

		scene_loader.__name__ = func.__name__
		return scene_loader
	# END wrapper
	return wrapper

#} END decorator
