# -*- coding: utf-8 -*-
import logging

#{ Initialization

def _init_logging():
	"""Assure the logging is set to debug"""
	logging.basicConfig(level=logging.DEBUG)

#} END initialization

_init_logging()
