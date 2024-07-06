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

# See https://mccompetition.org/assets/files/2021/competition2021.pdf for input format info

from collections import namedtuple
from datetime import datetime
from functools import partial
import glob
import json
import os
from pathlib import Path
import random
import re
import resource
import shutil
import subprocess
import sys
import time

# Johannes' scripts:
# sys.path.insert(1, '/Users/aldlatour/research-software/mc_experiments-johannes/eval/scripts/count_replication')
# sys.path.insert(1, '/Users/aldlatour/research-software/mc_experiments-johannes/eval/scripts')
# sys.path.insert(1, '/Users/aldlatour/research-software/mc_experiments-johannes/eval')
from parse_counts_util import log10cnt


SCRIPT_NAME = os.path.basename(__file__)

Counter = namedtuple("Counter", "name path config regex exact",
                     defaults=[None, None, None, None, True])
Generator = namedtuple("Generator", "name path config",
                       defaults=[None, None, None])
Preprocessor = namedtuple("Preprocessor", "name path config",
                       defaults=[None, None, None])
DeltaDebugger = namedtuple("DeltaDebugger", "name path config",
                       defaults=[None, None, None])

Count = namedtuple("Count", "solver preproc count", defaults=[None, None, -1])
maxtimediff = 1


def log_message(message: str):
    print(f'[{SCRIPT_NAME}], {datetime.now().strftime("%Y-%m-%d, %Hh%Mm%Ss")}: {message}')
    sys.stdout.flush()


def get_file_number(file_dir, extension):
    return len(glob.glob1(file_dir, f"*.{extension}")) + 1


def set_limits(t):
    # Set maximum CPU time to 1 second in child process, after fork() but before exec()
    log_message(f"Setting resource limit in child (pid {os.getpid()})")
    resource.setrlimit(resource.RLIMIT_CPU, (t, t))


def run(command: str, dir: str, verbose=True, max_time=4):
    log_message(f'--> Executing: {command} in dir {dir}')
    if verbose:
        log_message(f'CPU limit of parent (pid {os.getpid()}): {resource.getrlimit(resource.RLIMIT_CPU)}')

    p = subprocess.Popen(command, stderr=subprocess.STDOUT, shell=True,
                         stdout=subprocess.PIPE, universal_newlines=True, cwd=dir,
                         preexec_fn=partial(set_limits, max_time))

    console_output, err = p.communicate()
    if verbose:
        log_message(f"CPU limit of parent (pid {os.getpid()}) after child finished executing: {resource.getrlimit(resource.RLIMIT_CPU)}")
    return console_output, err


def fstr(template, **kwargs):
    return eval(f"f'{template}'", kwargs)


class CountFuzzer():
    """ A class to manage the fuzzing of model counters

    Attributes:
        _projected (bool):  True iff doing projected counting.
        _weighted (bool):   True iff doing weighted counting.

    """

    def __init__(self,
                 counter_config_file: str,
                 generator_config_file: str,
                 preprocessor_config_file=None,
                 projected=False,
                 weighted=False,
                 verbosity=2,
                 counter_timeout=4,
                 counter_memout=32000,
                 seed=None):

        # Type of counting
        self._projected = projected
        self._weighted = weighted

        self._counter_timeout = -1
        self._counter_memout = -1

        self._verbosity = -1
        self._seed = -1

        self._generated_instances = []
        # TODO: Come up with reliable way to read and process model counts for different output formats
        self._result_pat = re.compile(r'c s (exact|approx) (arb|single|double|quadruple) -?\d+\.?\d*')

        self._counters = []
        self._generators = []
        self._preprocessors = []
        self._delta_debuggers = []

        self._create_directories()
        self._set_random_seed()

        self.add_counters(counter_config_file=counter_config_file)
        self.add_generators(generator_config_file=generator_config_file)
        self.add_preprocessors(preprocessor_config_file=preprocessor_config_file)

        self.set_counter_timeout(timeout=counter_timeout)
        self.set_counter_memout(memout=counter_memout)

        self.set_seed(seed=seed)
        self.set_verbosity(verbosity=verbosity)

    def reset_counters(self):
        """Remove all counters from memory."""
        self._counters = []

    def add_counters(self, counter_config_file: str):
        """Append counters from a given json file with the counter configurations.

        Parameters:
            counter_config_file (str): Path to json file with counter configuration
        """
        counters = json.load(open(counter_config_file))
        for name in counters:
            new_counter = Counter(
                name,
                counters[name]["path"],
                counters[name]["config"],
                counters[name]["result_regex"],
                bool(counters[name]["exact"]))
            self._counters.append(new_counter)
        assert len(self._counters) > 1, "Aborting. Please specify at least two counters."

    def print_counter_info(self):
        log_message("Test the following solvers:")
        log_message("\n")
        # TODO: print counter info in a nicely readable format

    def reset_generators(self):
        """Remove all generators from memory."""
        self._generators = []

    def add_generators(self, generator_config_file: str):
        """Append instance generators from a given json file with the generator configurations.

        Parameters:
            generator_config_file (str): Path to json file with generator configuration
        """
        generators = json.load(open(generator_config_file))
        for name in generators:
            new_generator = Generator(name, generators[name]["path"], generators[name]["config"])
            self._generators.append(new_generator)
        assert self._generators, "Aborting. Please specify at least one CNF generator."

    def print_generator_info(self):
        log_message("Generate test instances with:")
        log_message("\n")
        # TODO: print generator info in a nicely readable format

    def reset_preprocessors(self):
        """Remove all preprocessors from memory."""
        self._preprocessors = []

    def add_preprocessors(self, preprocessor_config_file: str):
        """Append preprocessors from a given json file with the preprocessor configurations.

        Parameters:
            preprocessor_config_file (str): Path to json file with preprocessor configuration
        """
        if preprocessor_config_file is not None:
            preprocessors = json.load(open(preprocessor_config_file))
            for name in preprocessors:
                new_preprocessor = Preprocessor(name, preprocessors[name]["path"], preprocessors[name]["config"])
                self._preprocessors.append(new_preprocessor)

    def print_preprocessor_info(self):
        log_message("Preprocess test instances with:")
        log_message("\n")
        # TODO: print preprocessor info in a nicely readable format

    def set_counter_timeout(self, timeout: int):
        """Set timeout time in seconds for one run of one counter on one instance.

        Parameters:
            timeout (int): timeout time in seconds.
        """
        assert timeout > 0, "Please specify timeout in seconds."
        self._counter_timeout = timeout

    def set_counter_memout(self, memout: int): #TODO: check memory units
        """Set maximum allowed memory in MBs for one run of one counter on one instance.

        Parameters:
            memout (int): maximum allowed memory in MBs.
        """
        assert memout > 0, "Please specify max memory in MBs."
        self._counter_memout = memout

    def set_seed(self, seed: int):
        self._seed = seed

    def set_verbosity(self, verbosity: int):
        assert 1 <= verbosity <= 3, "Please specify verbosity level 1, 2, or 3"
        self._verbosity = verbosity
        
    def write_report(self, path_to_report):
        return

    def _create_directories(self):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        assert self._generators, "Aborting, must specify a generator config file."

        # Generate all directories for storing CNFs:
        if not os.path.isdir("cnf"):
            log_message(f"Creating directory to store generated CNFs: {this_dir}/cnf.")
            os.makedirs("cnf", exist_ok=True)
        for generator in self._generators:
            generator_dir = f"{this_dir}/cnf/{generator.name}/original"
            if not os.path.isdir(generator_dir):
                if self._verbosity >= 3:
                    log_message(f"Creating directory to store CNFs generated by {generator.name}: {generator_dir}.")
                os.makedirs(generator_dir, exist_ok=True)
            if self._do_preprocess:
                for preprocessor in self._preprocessors:
                    preprocessor_dir = f"{this_dir}/cnf/{generator.name}/{preprocessor.name}"
                    if not os.path.isdir(preprocessor_dir):
                        if self._verbosity >= 3:
                            log_message(f"Creating directory to store CNFs generated by {generator.name} and preprocessed by {preprocessor.name}: {preprocessor_dir}.")
                    os.makedirs(preprocessor_dir, exist_ok=True)
        if not os.path.isdir("bug"):
            log_message(f"Creating directory to store CNFs that trigger possibly buggy behaviour: {this_dir}/bug.")
            os.makedirs("bug", exist_ok=True)

    def _set_random_seed(self):
        if self._seed is None:
            b = os.urandom(8)
            self._seed = int.from_bytes(b)
        log_message(f"Using seed: {self._seed}")
        random.seed(self._seed)

    def _get_random_generator(self):
        return random.choice(self._generators)

    def _get_random_preprocessor(self):
        return random.choice(self._preprocessors)

    def _get_path_to_new_instance(self, generator):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        cnf_dir = f"{this_dir}/cnf/{generator.name}/original"
        instance_number = get_file_number(cnf_dir, "cnf")
        new_cnf_path = f"{cnf_dir}/fuzz_{instance_number:>03}.cnf" # TODO: check if we need to create wcnf or pcnf extensions
        return new_cnf_path

    def _get_type_number(self, projected, weighted):
        ty = "0"
        if projected and not weighted: ty = "1"
        if not projected and weighted: ty = "2"
        if projected and weighted: ty = "3"
        return ty

    def generate_instance(self, generator, new_cnf_path):
        # command = f"{generator.path} {generator.config} {new_cnf_path} {self._projected} {self._weighted}"
        seed = random.randint(0, 1000000000)
        tmp_command = f"{generator.path} {generator.config}"
        type_num = self._get_type_number(self._projected, self._weighted)
        command = fstr(tmp_command, out_file=new_cnf_path, seed=seed, type_num=type_num)

        status = subprocess.call(command, shell=True)
        if status != 0:
            log_message(f"Failed generator call: {command}")
            exit(-1)
        else:
            log_message(f"Called generator: {command}")
            log_message(f"Generated file {new_cnf_path}.")
            self._generated_instances.append(new_cnf_path)

    def _parse_output(self, counter_output, counter, path_to_instance) -> (bool, int):
        num = None
        unsat = False
        unknown = False
        count = -1

        pat = re.compile(counter.regex)
        if self._verbosity >= 3:
            log_message("OUTPUT")

        for l in counter_output.split("\n"):
            l = l.strip()

            # Print each line of the counter's output, if verbosity level is high enough
            if self._verbosity >= 3:
                log_message(l)

            # Check if this is the line in which the count is reported
            m = re.match(pat, l)
            if m is not None:
                count = int(m.group("count"))

            # Check if instance is found to be unsatisfiable
            if "s UNSATISFIABLE" in l:
                unsat = True
                if self._verbosity >= 2:
                    log_message(f"Counter {counter.name} found {path_to_instance} to be UNSAT.")

            if "s UNKOWN" in l:
                unknown = True
                if self._verbosity >= 2:
                    log_message(f"Counter {counter.name} found the satisfiability of {path_to_instance} to be unknown.")

            if "Assertion " in l and "failed" in l:
                if self._verbosity >= 2:
                    log_message(f"Counter {counter.name} reports assertion fail: {l}")  # TODO: come up with better error message
                return False, None
            if "ERROR Memory out!" in l:
                if self._verbosity >= 2:
                    log_message(f"Counter {counter.name} ran out of memory on {path_to_instance}.")
                return True, None
            if "ERROR" in l:    # TODO: check if this is a reliable way to detect errors
                log_message(f"ERROR found in counter {counter.name} on instance {path_to_instance}!")
                log_message(f"ERROR in output: {l}")
                log_message("Full output:")
                for line in counter_output.split("\n"):
                    log_message(line.strip())
                return False, None

            if len(l) < 4:      # TODO: this seems super arbitrary
                continue
            if l[0] == 'c' and l[:3] != "c s": # TODO: find out what this is about?
                continue
            # TODO: the following seems super hacky; see if I can come up with something better.
            if l[:4] == "s mc" or l[:13] == "c s exact arb" or l[:5] == "s pmc" or "s exact double prec-sci" in l or " s approx arb int" in l:
                if num is not None:
                    print("ERROR: Two 's mc' lines in output!!")
                    # TODO: print command that got executed
                    exit(-1)
                if l[:4] == "s mc" or l[:5] == "s pmc":
                    num = int(l.split()[2])
                elif "c s exact arb float " in l:
                    num = float(l.split()[5])
                elif "c s exact arb int" in l:
                    num = float(l.split()[5])
                elif " s approx arb int" in l:
                    num = float(l.split()[5])
                elif l[:13] == "c s exact arb":
                    num = int(l.split()[5])
                elif "s exact double prec-sci" in l:
                    num = float(l.split()[5])
                else:
                    print("ERROR")
                    exit(-1)
        if unsat:
            return True, 0
        if unknown:
            return True, -1 # TOOD: Figure out what to return here
        if count > 0:
            return True, count


        # TODO: again, the following is super hacky, come up with something better.
        if num is None:
            print("ERROR, could not find 's mc', 'c s exact arb int', or 'c s approx arb int' in output")
            for l in counter_output.split("\n"):
                print(l.strip())
            if ("ganak" in counter.path or "approx" in counter.path):
                return False, None
            else:
                print("Not erroring out, it's not our solver")
                return True, None

    def _run_counter(self, counter, path_to_instance):
        # TODO: add functionality for approximate counters
        log_message(f"Running counter {counter.name} on instance {path_to_instance}.")

        counter_dir = str(Path(counter.path).parent.absolute())
        command = f"{os.path.basename(counter.path)} {counter.config} {path_to_instance}"
        tmp_command = f"{counter.path} {counter.config} {path_to_instance}"


        command = fstr(tmp_command, STAREXEC_MAX_MEM=self._max_mem, STAREXEC_WALLCLOCK_LIMIT=self._counter_timeout)

        if self._verbosity >= 2:
            log_message(f"command: {command}")

        # TODO: remove the following?
        # if not counter.exact:
        #     last = toexec[len(toexec) - 1]
        #     toexec = toexec[:len(toexec) - 1]
        #     toexec.extend(["--epsilon", str(options.epsilon),
        #                    "--delta", str(options.delta),
        #                    "-s", str(seed)])
        #     toexec.extend([last])

        start_time = time.time()
        counter_output, err = run(command, counter_dir +'/', verbose=(self._verbosity>=3))
        if err is None:
            if self._verbosity >= 2:
                log_message("No error.")
        else:
            log_message(f"Error: {err}")
        diff_time = time.time() - start_time

        # Abort if counter exceeds maximum time
        if diff_time > self._counter_timeout - maxtimediff:
            log_message(f"Aborted! Counter {counter.name} exceeded maximum time of {self._counter_timeout} s on instance {path_to_instance}.")
            return True, None

        # Otherwise, parse output
        result = self._parse_output(counter_output, counter, path_to_instance)
        print(result)
        return result

    def _check_counts(self, counts: dict) -> bool:
        # TODO: Add functionality for approximate counters
        # TODO: Add functionality for weighted & projected counters

        # If all counts agree, return True
        if len(set(counts.values())) == 1:
            return True
        return False

    def _print_counting_results(self, same_counts: bool, counts: dict):
        if same_counts:
            log_message(f"All counters agree on count: {list(counts.values())[0]}.")
        else:
            log_message("ATTENTION: at least one counter disagrees with the others.")
            name_width = max(len(max(counts.keys(), key=len)), 6) + 1
            count_width = len(max([str(count) for count in counts.values()], key=len)) + 1
            log_message(f"{'counter':<{name_width}}|{'count':>{count_width}}")
            log_message("-" * (name_width + 1 + count_width))
            for counter, count in counts.items():
                log_message(f"{counter:<{name_width}}|{str(count):>{count_width}}")

    def save_problematic_instance(self, old_path, new_path):
        if os.path.isfile(new_path):
            filename, ext = os.path.splitext(new_path)
            new_new_path = f"{filename}_{datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")}.{ext}"
            if self._verbosity >= 2:
                log_message(f"WARNING: File {new_path} already exists. Copying to {new_new_path}, instead.")
            new_path = new_new_path
        shutil.copy2(old_path, new_path)
        if self._verbosity >= 3:
            log_message(f"Copied file {old_path} to {new_path}.")


    def clean_up(self):
        for path_to_instance in self._generated_instances:
            os.remove(path_to_instance)
        self._generated_instances = []
        if self._verbosity >= 3:
            log_message("Cleaned up all generated instances.")


    def fuzz(self):

        while True:
            generator = self._get_random_generator()
            preprocessor = None
            if self._do_preprocess:
                preprocessor = self._get_random_preprocessor()
            path_to_instance = self._get_path_to_new_instance(generator)

            self.generate_instance(generator, path_to_instance)

            counts = dict()
            for counter in self._counters:
                success, count = self._run_counter(counter, path_to_instance)
                counts[counter.name] = count if success else -1

            same_counts = self._check_counts(counts)
            self._print_counting_results(same_counts, counts)
            if not same_counts:
                return path_to_instance

            













