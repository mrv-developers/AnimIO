__author__ = """Aric Hagberg (hagberg@lanl.gov)\nDan Schult (dschult@colgate.edu)"""
#    Copyright (C) 2004-2008 by 
#    Aric Hagberg <hagberg@lanl.gov>
#    Dan Schult <dschult@colgate.edu>
#    Pieter Swart <swart@lanl.gov>
#    All rights reserved.
#    BSD license.

__all__ = ['read_gpickle', 'write_gpickle']


import codecs
import locale
import string
import sys
import time

from networkx.utils import is_string_like,_get_fh

import cPickle as pickle

def write_gpickle(G, path):
    fh=_get_fh(path,mode='wb')        
    pickle.dump(G,fh,pickle.HIGHEST_PROTOCOL)
    fh.close()

def read_gpickle(path):
    fh=_get_fh(path,'rb')
    return pickle.load(fh)
