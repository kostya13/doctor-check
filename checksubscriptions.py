#!/home/u63341pyl/virtualenv/kx13/3.7/bin/python3
import os
import sys
import doctor_check.watch
work_dir = os.path.dirname(sys.argv[0])
os.chdir(work_dir)
doctor_check.watch.main()

