# Runs nose - to be called by the mayarv python wrapper which assures the environment 
# is setup properly

if __name__ == "__main__":
	import sys
	import site
	# assure all sitelibs are available, important for OSX
	for syspath in sys.path[:]:
		if syspath.endswith('site-packages'):
			site.addsitedir(syspath, set(sys.path))
	# END for each syspath
	import nose
	nose.main()

