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
from datetime import datetime
import os
import pandas as pd
from pathlib import Path
import random
import subprocess
import time

# Fuzzer modules
import file_manager as fm
import fuzzer_utils as fut
import report_manager as rm


def parse_arguments():
    parser = argparse.ArgumentParser()
    tools = parser.add_argument_group("Tools")
    problem_type = parser.add_argument_group("Problem type")
    behaviour = parser.add_argument_group("Fuzzer behaviour")
    admin = parser.add_argument_group("Admin")
    verification = parser.add_argument_group(
        "[OPTIONAL] Verification (*only* available for unweighted, unprojected model counting!)")

    # -------------------------   TOOLS   ------------------------- #
    tools.add_argument(
        "--counters", "-c", dest="counters", type=str, required=True,
        help="Path to json file with the counters and their configurations."
    )
    tools.add_argument(
        "--generators", "-g", dest="generators", type=str, required=True,
        help="Path to json file with the CNF generators and their configurations."
    )
    tools.add_argument(
        "--preprocessors", dest="preprocessors", type=str, required=False, default='',
        help="Path to json file with the preprocessors and their configurations."
    )

    # -------------------------   PROBLEM TYPE   ------------------------- #
    problem_type.add_argument(
        "--projected", dest="projected", default=False, action="store_true", required=False,
        help="If True, all specified counters are expected to do projected model counting, "
             "and all generators are expected to generate projected model counting problems. "
             "If False, all specified counters are expected to not do projected model counting, "
             "and all generators are expected to generate non-projected model counting problems"
    )
    problem_type.add_argument(
        "--weighted", dest="weighted", default=False, action="store_true", required=False,
        help="If True, all specified counters are expected to do weighted model counting, "
             "and all generators are expected to generate weighted model counting problems. "
             "If False, all specified counters are expected do unweighted model counting, "
             "and all generators are expected to generate unweighted model counting problems."
    )
    problem_type.add_argument(
        "--messyweight", dest="messy_weights", default=False, required=False,
        action="store_true", help="With this, weights are NOT fully given, and can contain negative values."
    )

    # -------------------------   BEHAVIOUR   ------------------------- #
    behaviour.add_argument(
        "--max-time", "-t", dest="max_time", type=int, default=10, required=False,
        help="Timeout time for individual runs, in seconds."
    )
    behaviour.add_argument(
        "--max-mem", "-m", dest="max_mem", type=int, default=3200, required=False,
        help="Max memory for individual runs."
    )
    behaviour.add_argument(
        "--verbosity", "-v", type=int, default=2, required=False,
        dest="verbosity", help="Specify verbosity level 1, 2 or 3"
    )
    behaviour.add_argument(
        "--seed", "-s", dest="rnd_seed", type=int, required=False,
        help="Fuzz test start seed. If unset, a random seed is picked."
    )
    behaviour.add_argument(  # TODO: Check if this is actually used
        "--keep-bugs-only", dest="keep_bugs_only", default=False, required=False,
        action="store_true",
        help="Only keep the CNFs that yield bugs, clean up all others."
    )
    behaviour.add_argument(
        "--num-iter", "-n", dest="n_iter", type=int, default=100,
        required=False, help="Specify the maximum number of iterations."
    )

    # -------------------------   ADMIN   ------------------------- #
    admin.add_argument(
        "--instance-dir", dest="cnf_dir", type=str, required=False,
        help="Specify path to directory to store generated instances. Default: /path/to/fuzzer/instances"
    )
    admin.add_argument(
        "--bug-dir", dest="bug_dir", type=str, required=False,
        help="Specify path to directory to store instances that are suspected to trigger bugs. Default: /path/to/fuzzer/bugs"
    )
    admin.add_argument(
        "--log-dir", dest="log_dir", type=str, required=False,
        help="Specify path to directory to store logs. Default: /path/to/fuzzer/logs"
    )

    # -------------------------   VERIFICATION   ------------------------- #
    verification.add_argument(
        "--verifier", dest="verifier", type=str, required=False, default=None,
        help="Path to a script that takes as argument a path to a .cnf file and then "
             "generates a verified proof of correctness of the model count.")
    verification.add_argument(
        "--verifier-timeout", dest="verifier_timeout", type=int, required=False,
        help="Specify how much time the verifier gets to obtain a verified model count. Default 10 * --max-time."
    )
    verification.add_argument(
        "--clean-up-proofs", dest="clean_up_proofs", default=False, required=False, action="store_true",
        help="Clean up all proof-related files after verified count has been obtained."
    )

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
    #

    # -------------------------   SANITY CHECKS   ------------------------- #
    parsed_args = parser.parse_args()

    if parsed_args.verifier is not None and (parsed_args.projected or parsed_args.weighted):
        rm.log_message("Verification not available for projected or weighted model counting. Aborting.")
        exit(1)

    return parsed_args


def generate_instance(generator: fut.Generator,
                      new_cnf_path: str,
                      seed: int,
                      projected=False,
                      weighted=False,
                      verbosity=1
                      ):
    # command = f"{generator.path} {generator.config} {new_cnf_path} {self._projected} {self._weighted}"
    # seed = random.randint(0, 1000000000)
    tmp_command = f"{generator.path} {generator.config}"
    type_num = fut.get_type_number(projected, weighted)
    command = fut.fstr(tmp_command, out_file=new_cnf_path, seed=seed, type_num=type_num)
    status = subprocess.call(command, shell=True)
    if status != 0:
        rm.log_message(f"Failed generator call: {command}")
        exit(-1)
    elif verbosity >= 3:
        rm.log_message(f"Called generator: {command}")
    elif verbosity >= 2:
        rm.log_message(f"Generated file {new_cnf_path}.")


def generate_instances(generators: list,
                       cnf_dir: str,
                       inst_num: int,
                       seed: int,
                       projected=False,
                       weighted=False):
    ext = fut.get_extension(projected=projected, weighted=weighted)
    new_instances = []
    for generator in generators:
        file_name = f"{cnf_dir}/base/{generator.name}_{inst_num:03}_s{seed}.{ext}"
        generate_instance(generator=generator, new_cnf_path=file_name, seed=seed, projected=projected,
                          weighted=weighted)
        new_instances.append(file_name)
    return new_instances


def run_counter(counter: fut.Counter,
                path_to_instance: str,
                log_dir: str,
                timeout=10,
                max_mem=3200,
                verbosity=1) -> dict:
    # TODO: add functionality for approximate counters
    timed_out = False
    if verbosity >= 2:
        rm.log_message(f"Running counter {counter.name} on instance {path_to_instance}.")

    counter_dir = str(Path(counter.path).parent.absolute())
    tmp_command = f"./{os.path.basename(counter.path)} {counter.config} {path_to_instance}"
    command = fut.fstr(tmp_command, STAREXEC_MAX_MEM=max_mem, STAREXEC_WALLCLOCK_LIMIT=timeout)

    if verbosity >= 2:
        rm.log_message(f"command: {command}")

    # TODO: remove the following?
    # if not counter.exact:
    #     last = toexec[len(toexec) - 1]
    #     toexec = toexec[:len(toexec) - 1]
    #     toexec.extend(["--epsilon", str(options.epsilon),
    #                    "--delta", str(options.delta),
    #                    "-s", str(seed)])
    #     toexec.extend([last])

    start_time = time.time()
    counter_output, err = fut.run(command.split(), counter_dir + '/', verbosity=verbosity)
    if err is None:
        if verbosity >= 3:
            rm.log_message("No error.")
    else:
        rm.log_message(f"Error: {err}")
    diff_time = time.time() - start_time

    # Abort if counter exceeds maximum time
    if diff_time > timeout:
        rm.log_message(
            f"Aborted! Counter {counter.name} exceeded maximum time of {timeout} s on instance {path_to_instance}.")

    # Otherwise, parse output
    success, result = fut.parse_output(counter_output, counter, path_to_instance, timed_out=timed_out)
    if not success:
        log_file = fm.store_counter_output(command, counter_output, counter, log_dir)
        rm.log_message(f"ERROR when running {counter.name}. Output written to {log_file}")

    print(result)
    return result


def get_ground_truth(
        path_to_instance: str,
        verifier_script: str,
        timeout=100,
        max_mem=3200,
        verbosity=1) -> dict:
    timed_out = False
    # TODO: figure out how to communicate time + space resources
    if verbosity >= 2:
        rm.log_message(f"Running verification script {verifier_script} on instance {path_to_instance}.")

    verification_dir = str(Path(verifier_script).parent.absolute())
    proof_dir = f"{str(Path(Path(__file__).parent.absolute()).parent.absolute())}/proofs"
    output_file = f"{proof_dir}/{os.path.basename(path_to_instance)}.output"
    tmp_command = f"./{os.path.basename(verifier_script)} {path_to_instance}"
    command = fut.fstr(tmp_command, STAREXEC_MAX_MEM=max_mem, STAREXEC_WALLCLOCK_LIMIT=timeout)

    if verbosity >= 2:
        rm.log_message(f"command: {command}")

    start_time = time.time()
    verification_output, err = fut.run(command.split(), verification_dir + '/', verbosity=verbosity)
    if err is None:
        if verbosity >= 3:
            rm.log_message("No error.")
    else:
        rm.log_message(f"Error: {err}")
    diff_time = time.time() - start_time

    # Abort if counter exceeds maximum time
    if diff_time > timeout:
        rm.log_message(
            f"Aborted! Verification script {verifier_script} exceeded maximum "
            "time of {timeout} s on instance {path_to_instance}.")

    # Otherwise, parse output
    success, result = fut.parse_verifier_output(path_to_instance, output_file, timed_out=timed_out, verbosity=verbosity)
    result['problem_type'] = 'mc'  # For now only support for ground truth of this type
    result['instance'] = path_to_instance
    if not success:
        rm.log_message(f"ERROR when running {verifier_script}. Output written to {output_file}")

    return result


def fuzz(n_iter: int,
         seed: int,
         cnf_dir: str,
         log_dir: str,
         counters: list,
         generators: list,
         preprocessors=[],
         minimisers=[],
         verifier=None,
         projected=False,
         weighted=False,
         timeout=10,
         memout=32000,
         verbosity=1,
         clean_up_proofs=False,
         ):
    # Create data structures to store summary of results
    df = pd.DataFrame(columns=[])
    path_to_csv = f"{log_dir}/{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_fuzz-results.csv"
    problem_instances = []

    # Main loop
    for i in range(n_iter):
        new_base_instances = generate_instances(
            generators=generators,
            cnf_dir=cnf_dir,
            inst_num=i,
            seed=seed + i,
            projected=projected,
            weighted=weighted,
        )
        # TODO: Handle preprocessing
        # TODO: Handle delta-debugging

        for j, instance in enumerate(new_base_instances):
            rm.log_message("")
            rm.log_message("-" * 60)
            rm.log_message("")
            rm.log_message(f"New instance: {instance}")
            rm.log_message("")
            rm.log_message("-" * 60)
            rm.log_message("")
            counts = dict()

            if verifier is not None:
                result = get_ground_truth(
                    path_to_instance=instance,
                    verifier_script=verifier,
                    timeout=timeout * 10,
                    max_mem=memout,
                    verbosity=verbosity
                )
                counts['ground_truth'] = result['verified_count']
                result['generator'] = os.path.basename(os.path.dirname(instance))
                df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)

            for counter in counters:
                result = run_counter(
                    counter=counter,
                    path_to_instance=instance,
                    log_dir=log_dir,
                    timeout=timeout,
                    max_mem=memout,
                    verbosity=verbosity
                )
                counts[counter.name] = result['count_value']
                result['generator'] = os.path.basename(os.path.dirname(instance))
                df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
            if verbosity >= 2:
                rm.log_message(f"COMPLETED iteration {i + 1}.{j + 1}")
            same_counts = fut.check_counts(counts)
            rm.print_counts(same_counts, counts)
            if same_counts:
                if clean_up_proofs:
                    fm.clean_up_proof(instance=instance)
                    if verbosity >= 2:
                        rm.log_message(f"Cleaned up proof files for instance {instance}.")
            else:
                problem_instances.append(instance)

        # Every iteration, store results:
        df.to_csv(path_to_csv)
    return path_to_csv, problem_instances


if __name__ == "__main__":
    args = parse_arguments()

    # Setup
    counters = fut.parse_counters(args.counters)
    generators = fut.parse_generators(args.generators)
    # preprocessors = fut.parse_preprocessors(args.preprocessors)

    cnf_dir = f"{Path(__file__).parent.resolve().parent.resolve()}/instances" if args.cnf_dir is None else args.cnf_dir
    log_dir = f"{Path(__file__).parent.resolve().parent.resolve()}/logs" if (
            'log_dir' not in args or args.log_dir is None) else args.log_dir
    bug_dir = f"{Path(__file__).parent.resolve().parent.resolve()}/bugs" if args.bug_dir is None else args.bug_dir
    fm.create_directories(cnf_dir=cnf_dir, bug_dir=bug_dir, log_dir=log_dir, generators=generators)

    seed = fut.get_random_seed(args.rnd_seed)
    random.seed(seed)

    os.environ['STAREXEC_WALLCLOCK_LIMIT'] = str(args.max_time)
    os.environ['STAREXEC_MAX_MEM'] = str(args.max_mem)

    path_to_results, problem_instances = fuzz(
        n_iter=args.n_iter,
        seed=seed,
        cnf_dir=cnf_dir,
        log_dir=log_dir,
        counters=counters,
        generators=generators,
        verifier=args.verifier,
        projected=args.projected,
        weighted=args.weighted,
        timeout=args.max_time,
        memout=args.max_mem,
        verbosity=args.verbosity,
        clean_up_proofs=args.clean_up_proofs
    )

    print(problem_instances)
    # this_dir = os.path.dirname(os.path.realpath(__file__))
    # save_dir = f"{this_dir}/out/bugs_{datetime.now().strftime('%Y-%m-%d')}"
    # if not os.path.isdir(f"{save_dir}"):
    #     os.makedirs(save_dir)
    # basename = os.path.basename(buggy_instance)
    # fuzzer.save_problematic_instance(buggy_instance, f"{save_dir}/{basename}")
