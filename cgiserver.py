#!/usr/bin/env python3
import cgitb
cgitb.enable()
import doctor_check.server
import os
import sys
def p():
	res = ["{}={}".format(i, os.environ[i]) for i in os.environ]
	return '\n'.join(res)
	
#assert False, p()
doctor_check.server.cgi()
#print(os.environ)
#print(sys.argv)

