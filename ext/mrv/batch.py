#!/usr/bin/env python 
# -*- coding: utf-8 -*-
"""This modules contains utilities to do opeations in batch mode.
The module can be used from within python if required, but is more commonly used
from the commandline, possibly wrapped by a shell script to specialize its usae
"""
import sys,os
import signal
from collections import deque
import subprocess
import time

# module is supposed to be used as standalone program - we prevent from x import *
__all__ = None

def superviseJobs( jobs, returnIfLessThan, cmdinput, errorstream, donestream ):
	"""Check on the jobs we have and wait for finished ones. Write information
	about them into the respective streams
	:param returnIfLessThan: return once we have less than the given amount of running jobs"""
	sleeptime = 1.0		 # wait one second in the main loop before checking the processes

	if not jobs:
		return

	while True:

		jobscp = jobs[:]			# are going to alter the jobs queue
		for process in jobscp:
			# check if subprocess is done
			if process.poll() == None:
				continue

			# pop the process off the queue
			jobs.remove( process )

			# the process finished - get the stderr
			if errorstream:
				errorstream.writelines( process.stderr.readlines() )
				errorstream.flush()

			# append to the done list only if there is no error
			if donestream is not None and process.returncode == 0:
				donestream.writelines( "\n".join( cmdinput ) + "\n" )
				donestream.flush()

			# can we return ?
			if len( jobs ) < returnIfLessThan:
				return

		# END for each job

		time.sleep( sleeptime )
	# END endless loop

def killProcess( process ):
	"""Kill the given process
	:note: raises if kill is not supported by the os module"""
	if not hasattr( os, "kill" ):
		raise NotImplementedError( "os module does not support 'kill'ing of processes on your platform" )

	os.kill( process.pid, signal.SIGKILL )



def process( cmd, args, inputList, errorstream = None, donestream = None, inputsPerProcess = 1,
			 numJobs=1):
	"""Launch process at cmd with args and a list of input objects from inputList appended to args
	:param cmd: full path to tool you wish to start, like /bin/bash
	:param args: List of all argument strings to be passed to cmd
	:param inputList: list of input files to be passed as input to cmd
	:param errorstream: stream to which errors will be written to as they occour if not None
	:param donestream: stream to which items from input list will be passed once they
	have been processed if not None. Items are newline terminated
	:param inputsPerProcess: pass the given number of inputs to the cmd, or less if there
	are not enough items on the input list
	:param numJobs: number of processes we may run in parallel
	"""
	# very simple for now - just get the input together and call the cmd
	jobs = list()
	numInputs = len( inputList )
	for i in range( 0, numInputs, inputsPerProcess ):

		cmdinput = inputList[ i : i + inputsPerProcess ]	# deals with bounds
		callcmd = (cmd,)+tuple(args)+tuple(cmdinput)
		process = subprocess.Popen( callcmd,stderr=subprocess.PIPE, stdin=subprocess.PIPE, env=os.environ )

		jobs.append( process )

		# fill our input argumets additionally to stdin
		try:
			process.stdin.writelines( '\n'.join( cmdinput ) )
			process.stdin.flush()
			process.stdin.close()
		except IOError:
			pass 	# could be closed already


		# get another job ?
		if len( jobs ) < numJobs:
			continue


		if len( jobs ) != numJobs:
			raise AssertionError( "invalid job count" )

		# we have a full queue now - get a new one asap
		try:
			superviseJobs( jobs, numJobs, cmdinput, errorstream, donestream )
		except KeyboardInterrupt:
			# kill all processes - we do not know which one hangs
			for process in jobs:
				killProcess( process )
			jobs = list()
			sys.stdout.write("Aborted all running processes - continuing\n")
	# END for each chunk of inputs

	# queue is empty, finalize our pending jobs
	superviseJobs( jobs, 1, list(), errorstream, donestream )


#{ Command Line Tool

def _usageAndExit( msg = None ):
	"""Print usage"""
	sys.stdout.write("""python batch.py inputarg [inputarg ...] [-E fileForErrors|-] [-D fileForFinishedOutput|-] [-s numInputsPerProcess] -e cmd [cmdArg ...]
-E|D - 	means to use the default stream, either stderr or stdout
-I	if specified, arguments will also be read from stdin until it is depleted as
	newline separated list of names
	Its particlularly important that the pipe to stdin closes once its done as
	this command currently does not support streaming of input args
-e 	ends the parsing of commandline arguments for the batch process tool
	and uses the rest of the commandline as direct input for your command
-s	defines how many input arguments will be passed per command invocation
-j	the number of processes to keep running in parallel, default 1

	The given inputargs will be passed as arguments to the commands or into
	the standardinput of the process""")
	if msg:
		sys.stdout.write(msg+"\n")

	sys.exit(1)


def _toStream( arg, stream ):
	""":return: stream according to arg
	:param stream: stream to return if arg sais so """
	if arg == "-":
		return stream
	# stream handling

	# arg should be a file
	try:
		return open( arg, "w" )
	except IOError:
		_usageAndExit( "Stream at %s could not be opened for writing" % arg )


def _popleftchecked( argv, errmsg ):
	"""pop an arg from argv and return with an error message on error"""
	try:
		return argv.popleft()
	except IndexError:
		_usageAndExit( errmsg )


def main( *args ):
	"""Processes the arguments"""

	if not args:
		_usageAndExit( )

	inputList = list()
	streams = list( ( None, None ) )

	numJobs = 1
	inputsPerProcess = 1
	cmd = None
	cmdargs = list()
	haveReadInput = False


	# PARSE ARGUMENTS
	##################
	argv = deque( args )
	while argv:
		arg = argv.popleft()

		# COMAMND TO EXECUTE
		#####################
		if arg == "-e":
			cmd = _popleftchecked( argv, "-e must be followed by the command to execute" )

			# get cmd args
			for rarg in argv:
				cmdargs.append( rarg )

			# done processing
			break
		# END -e

		# STREAMS
		############
		flagfound = False
		for i,(flag,stream) in enumerate( ( ( "-E",sys.stderr ), ( "-D", sys.stdout ) ) ):
			if arg == flag:
				argval = _popleftchecked( argv, "%s must be followed by - or a filepath" % flag )
				streams[ i ] = _toStream( argval, stream )
				flagfound = True
				break
			# END if arg matches
		# END for each stream arg

		if flagfound: continue

		if arg == "-s":
			msg = "-s must be followed by a number > 0"
			inputsPerProcess = int( _popleftchecked( argv, msg ) )
			flagfound = True
			if inputsPerProcess < 1:
				_usageAndExit( msg )
		# END -s

		if flagfound: continue
		if arg == "-j":
			msg = "-j must be followed by a number > 0"
			numJobs = int( _popleftchecked( argv, msg ) )
			flagfound = True
			if numJobs < 1:
				_usageAndExit( msg )
		# END -s

		if flagfound: continue

		# INPUT ARGUMENTS FROM STDIN
		if arg == "-I":
			flagfound = True
			if haveReadInput:
				_usageAndExit( "-I may only be specified once" )

			haveReadInput = True
			# read stripped lines from stdin
			inputList.extend( ( l.strip() for l in  sys.stdin.readlines() ) )
		# END -s

		if flagfound: continue

		# its an input argument
		inputList.append( arg )

	# END for each argument


	if not cmd:
		_usageAndExit( "No command to execute - add it after the -e flag" )


	# have everything, transfer control to the actual batch method
	process( cmd, cmdargs, inputList, streams[0], streams[1], inputsPerProcess, numJobs )



if __name__ == "__main__":
	main( *sys.argv[1:] )

#} END command line tool
