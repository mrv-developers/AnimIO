
.PHONY=docs release clean

# CONFIGURATION
# python 2.6
MAYA_VERSION=2011
PYVERSION_ARGS=--maya-version=$(MAYA_VERSION)
REG_ARGS=--regression-tests=$(MAYA_VERSION)
DOC_ARGS=--zip-archive --coverage=0 --epydoc=1
SDIST=sdist

PYTHON_SETUP=/usr/bin/python setup.py

all:
	echo "Nothing to do - specify an actual target"
	exit 1

clean:
	$(PYTHON_SETUP) clean --all
	$$(cd doc; ../animio/ext/mrv/doc/makedoc --clean --package=animio)
	
docs:
	$(PYTHON_SETUP) $(PYVERSION_ARGS) docdist $(DOC_ARGS)
	
release:
	$(PYTHON_SETUP) $(PYVERSION_ARGS) $(REG_ARGS) clean --all $(SDIST)
