import os
import sys
import doctor_check.server


sys.path.insert(0, os.path.dirname(__file__))

application = doctor_check.server.application


