# -*- coding: utf-8 -*-
""" Contains all exceptions used by the mrv package in general """
__docformat__ = "restructuredtext"

class MRVError( Exception ):
	""" Base Class for all exceptions that the mrv framework throws"""
	def __init__(self, *args, **kwargs):
		self._message = ""
		if args and isinstance(args[0], basestring):
			self._message = args[0]
			args = args[1:]
		# END args and message handling
		Exception.__init__(self,*args, **kwargs)
	
	def _get_message(self): 
		return self._message
	def _set_message(self, message): 
		self._message = message
	message = property(_get_message, _set_message)


