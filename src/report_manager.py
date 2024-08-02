#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Short description.

Author:     Anna L.D. Latour
Authors:    [Anna L.D. Latour, And another one, etc]
Contact:    a.l.d.latour@tudelft.nl
Date:       2024-07-06
Maintainer: Anna L.D. Latour
Version:    0.0.1
Credits:    [One developer, And another one, etc]
Copyright:  (C) 2024, Anna L.D. Latour
License:    GPLv3
    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; version 3
    of the License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
    02110-1301, USA.
    
Description: Long description.

"""

from datetime import datetime
import json
import sys


def log_message(message: str):
    print(f'[sharp-fuzz], {datetime.now().strftime("%Y-%m-%d, %Hh%Mm%Ss")}: {message}')
    sys.stdout.flush()


def print_counts(same_counts: bool, counts: dict):
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


def save_parameters(args, seed, log_dir, output_prefix):
    args_dict = dict(vars(args))
    print(args_dict)
    args_dict['rnd_seed'] = seed
    args_dict['generator_configs'] = json.load(open(args.generators))
    args_dict['counter_configs'] = json.load(open(args.counters))
    param_file = f"{log_dir}/{output_prefix}_parameters.json"
    with open(param_file, 'w') as out_file:
        json.dump(args_dict, out_file, indent=4)


def save_problem_instances(problem_instances, log_dir, output_prefix):
    with open(f"{log_dir}/{output_prefix}_problem_instances.txt", 'w') as out_file:
        out_file.write("\n".join(problem_instances))