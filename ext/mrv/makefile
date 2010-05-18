
# This is a very simple make-file for now to aid keeping the commandline options
# under control. 
# There is no intention to have something like it on windows, but the commandlines
# shown here could work mostly unaltered on the windows platform as well.

.PHONY=preview

all:
	echo "Nothing to do - specify an actual target"

# Moving-Tag Preview Commit 
preview: 
	/usr/bin/python setup.py --force-git-tag  --use-git=1 --regression-tests=1 clean --all sdist --format=zip --post-testing=2011 --dist-remotes=distro,hubdistro --root-remotes=gitorious,hub docdist --zip-archive --from-build-version --dist-remotes=docdistro,hubdocdistro --root-remotes=gitorious,hub
