#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2024  Anna Latour
#                     Mate Soos
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

import argparse
from count_fuzzer import CountFuzzer
from datetime import datetime
import os


def parse_arguments():
    parser = argparse.ArgumentParser()
    tools = parser.add_argument_group("Tools")
    problem_type = parser.add_argument_group("Problem type")
    behaviour = parser.add_argument_group("Fuzzer behaviour")

    tools.add_argument(
        "--counters", "-c", dest="counters", type=str, required=True,
        help="Path to json file with the counters and their configurations.")

    tools.add_argument(
        "--generators", "-g", dest="generators", type=str, required=True,
        help="Path to json file with the CNF generators and their configurations.")

    tools.add_argument(
        "--preprocessors", dest="preprocessors", type=str, required=False, default='',
        help="Path to json file with the preprocessors and their configurations.")

    problem_type.add_argument(
      "--projected", dest="projected", default=False, action="store_true", required=False,
      help="If True, all specified counters are expected to do projected model counting, "
           "and all generators are expected to generate projected model counting problems. "
           "If False, all specified counters are expected to not do projected model counting, "
           "and all generators are expected to generate non-projected model counting problems")

    problem_type.add_argument(
      "--weighted", dest="weighted", default=False, action="store_true", required=False,
      help="If True, all specified counters are expected to do weighted model counting, "
           "and all generators are expected to generate weighted model counting problems. "
           "If False, all specified counters are expected do unweighted model counting, "
           "and all generators are expected to generate unweighted model counting problems")

    problem_type.add_argument(
      "--messyweight", dest="messy_weights", default=False, required=False,
      action="store_true", help="With this, weights are NOT fully given, and can contain negative values.")

    behaviour.add_argument(
      "--max-time", "-t", dest="max_time", type=int, default=4, required=False,
      help="Max time to run, in seconds. Default: %default")

    behaviour.add_argument(
      "--max-mem", "-m", dest="max_mem", type=int, default=32000, required=False,
      help="Max memory per run.")

    behaviour.add_argument(
      "--verbosity", "-v", type=int, default=2, required=False,
      dest="verbosity", help="Specify verbosity level 1, 2 or 3")

    behaviour.add_argument(
      "--seed", "-s", dest="rnd_seed", type=int, required=False,
      help="Fuzz test start seed. Otherwise, random seed is picked")

    behaviour.add_argument( # TODO: Check if this is actually used
      "--keep-bugs-only", dest="keep_bugs_only", default=True, required=False,
        action="store_true",
        help="Only keep the CNFs that yield bugs, clean up the others. Default: %default")


    # behaviour.add_option(
    #   "--delta", dest="delta", type=float, default="0.2",
    #   help="TODO. Default: %default")
    #
    # optional.add_option(
    #   "--epsilon", dest="epsilon", type=float, default="0.2",
    #   help="TODO. Default: %default")


    # # sandbox, sampling ,etc
    # optional.add_option( # TODO: Check what this means
    #   "--sandbox", dest="sandbox", default=False,
    #   action="store_true", help="Do experiments in the sandbox")

    # optional.add_option( # TODO: See if we can generalise this
    #   "--sample-approxmc", dest="sample_approxmc", default=False,
    #     action="store_true",
    #     help="Query ApproxMC for different seeds and store the counts. Default: %default")
    #
    # optional.add_option(
    #     "--num-samples", dest="num_samples", type=int, default=3,
    #     help="How many samples to take for approximate counters. Default: %default")

    return parser.parse_args()


if __name__ == "__main__":

    args = parse_arguments()

    os.environ['STAREXEC_WALLCLOCK_LIMIT'] = str(args.max_time)
    os.environ['STAREXEC_MAX_MEM'] = str(args.max_mem)

    fuzzer = CountFuzzer(
        counter_config_file=args.counters,
        generator_config_file=args.generators,
        preprocessor_config_file=(args.preprocessors if args.preprocessors else None),
        projected=args.projected,
        weighted=args.weighted,
        verbosity=args.verbosity,
        max_time=args.max_time,
        max_mem=args.max_mem,
        seed=args.rnd_seed
    )
    buggy_instance = fuzzer.fuzz()

    this_dir = os.path.dirname(os.path.realpath(__file__))
    save_dir = f"{this_dir}/out/bugs_{datetime.now().strftime('%Y-%m-%d')}"
    if not os.path.isdir(f"{save_dir}"):
        os.makedirs(save_dir)
    basename = os.path.basename(buggy_instance)
    fuzzer.save_problematic_instance(buggy_instance, f"{save_dir}/{basename}")




