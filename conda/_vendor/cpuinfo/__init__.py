
import sys

if sys.version_info[0] == 2:
	from conda._vendor.cpuinfo import *
else:
	from conda._vendor.cpuinfo.cpuinfo import *


