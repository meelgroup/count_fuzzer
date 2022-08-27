#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2022 Mate Soos
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 2
# of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import subprocess
import os
import sys
import time
import random
from random import choice



class PlainHelpFormatter(optparse.IndentedHelpFormatter):

    def format_description(self, description):
        if description:
            return description + "\n"
        else:
            return ""


usage = "usage: %prog [options] "
desc = """Fuzz model counter
"""


def set_up_parser():
    parser = optparse.OptionParser(
      usage=usage, description=desc,
      formatter=PlainHelpFormatter())

    parser.add_option(
      "--verbose", "-v", action="store_true", default=False,
      dest="verbose", help="Print more output")

    parser.add_option(
      "--seed", dest="fuzz_seed_start",
      help="Fuzz test start seed. Otherwise, random seed is picked"
      " (printed to console)", type=int)

    parser.add_option(
      "--novalgrind", dest="dovalgrind", default=True,
      action="store_false", help="Use valgrind")

    parser.add_option(
      "--valgrindfreq", dest="valgrind_freq", type=int,
      default=10, help="1 out of X times valgrind will be used. Default: %default in 1")

    parser.add_option(
      "--tout", "-t", dest="maxtime", type=int, default=25,
      help="Max time to run. Default: %default")

    parser.add_option(
      "--textra", dest="maxtimediff", type=int, default=5,
      help="Extra time on top of timeout for processing."
      " Default: %default")

    return parser




if __name__ == "__main__":
    if not os.path.isdir("out"):
        print("Directory for outputs, 'out' not present, creating it.")
        os.mkdir("out")

    # parse options
    parser = set_up_parser()
    (options, args) = parser.parse_args()
    if options.valgrind_freq <= 0:
        print("Valgrind Frequency must be at least 1")
        exit(-1)

    fuzzers_frat = fuzzers_noxor
    fuzzers_nofrat = fuzzers_noxor + fuzzers_xor

    print_version()
    tester = Tester()
    tester.needDebugLib = False
    num = 0
    rnd_seed = options.fuzz_seed_start
    if rnd_seed is None:
        rnd_seed = random.randint(0, 1000*1000*100)





