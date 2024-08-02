#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Short description.

Author:     Anna L.D. Latour
Authors:    [Anna L.D. Latour, And another one, etc]
Contact:    a.l.d.latour@tudelft.nl
Date:       2024-07-21
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

import argparse
from datetime import datetime
import json
from operator import countOf
import numpy as np
import os
import pandas as pd
from pathlib import Path
import re
import subprocess

import fuzzer_utils as fut

pat_prefix = re.compile(r'(?P<path>.*\/)(?P<prefix>\d{4}-\d{2}-\d{2}_\d{6}_s\d+_).*\.\w+', re.DOTALL)

PROJECT_DIR = Path(os.path.dirname(__file__)).parent.absolute()


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--csv", dest="csv", type=str, required=True,
        help="Path to .csv file with solver output."
    )
    parser.add_argument(
        "--outdir", "-o", dest="outdir", type=str, required=False, default=f"{PROJECT_DIR}/latex_out",
        help="Path to directory for storing results.")
    parser.add_argument(
        "--pdflatex", "-p", dest="pdflatex", required=False, action='store_true', default=False,
        help="Generate .pdf from LaTeX file."
    )

    # parser.add_argument(
    #     "--latex", dest="latex", type=str, required=True,
    #     help="Path to .tex file with results report."
    # )
    # parser.add_argument(
    #     "--txt", dest="txt", type=str, required=True,
    #     help="Path to .txt file with results report."
    # )

    return parser.parse_args()


def latex_underscore(elt) -> str:
    if not type(elt) == str:
        return elt
    return elt.replace('_', '\_')


def latex_sf(string: str) -> str:
    return "{\\sf " + latex_underscore(string) + "}"


def latex_verb(string: str) -> str:
    return f"\\verb|{latex_underscore(string)}|"


def latex_lst_inline(string: str) -> str:
    return f"\\lstinline|{string}|"


def to_short_sat(string: str) -> str:
    if string == "UNSATISFIABLE":
        return 'UNSAT'
    elif string == 'SATISFIABLE':
        return 'SAT'
    return string


def latex_int(number) -> str:
    number = int(number)
    tmp = f"{number:,}"
    return tmp.replace(',', '\\:')


def get_counters(df) -> list:
    return sorted(list(set(df.counter.to_list())))


def get_generators(df) -> list:
    return sorted(list(set(df.generator.to_list())))


def get_instances(df) -> list:
    return sorted(list(set(df.instance.to_list())))


def get_param_file(csv_file: str) -> str:
    m = re.match(pat_prefix, csv_file)
    return f"{m.group('path')}{m.group('prefix')}parameters.json"


def create_table_with_fuzzing_parameters(param_dict: dict) -> str:
    latex_table = ('\\begin{tabular}{lr}\n'
                   '\\toprule\n' +
                   'parameter & value\\\\ \\midrule\n')
    for (key, value) in param_dict.items():
        if key in ['counter_configs', 'generator_configs', 'verifier']:
            continue
        latex_table += f'{latex_lst_inline(key)} & {latex_lst_inline(value)}\\\\\n'
    latex_table += "\\bottomrule\n" \
                   "\\end{tabular}"
    return latex_table


def create_list_with_tool_info(tools: list) -> str:
    latex_list = '\\begin{itemize}\n'
    for tool in tools:
        counter_dir = str(Path(tool.path).parent.absolute())
        executable = os.path.basename(tool.path)
        latex_list += (
                f"\t\\item {latex_sf(tool.name)}\n" +
                "\t\\begin{compactitems}\n" +
                f"\t\t\\item dir: {latex_lst_inline(counter_dir)}\n" +
                f"\t\t\\item cmd: {latex_lst_inline(executable + tool.config)}\n" +
                "\t\\end{compactitems}\n"
        )
    latex_list += "\\end{itemize}\n"
    return latex_list


def get_sat_info(generator_names: list, df):
    sat_results = []
    if 'verifier' in set(df.counter):
        for generator in generator_names:
            for instance in sorted(set(df.instance)):
                if generator not in instance:
                    continue
                satisfiability = df[(df.generator == generator) & (df.instance == instance) & (df.counter == 'verifier')]['satisfiability'].iloc[0]
                if satisfiability not in ['SATISFIABLE', 'UNSATISFIABLE', 'UNKNOWN']:
                    satisfiability = 'UNKNOWN'
                sat_results.append({'generator': generator, 'instance': instance, 'satisfiability': satisfiability})
    else:
        for generator in generator_names:
            for instance in set(df.instance):
                if generator not in instance:
                    continue
                sat_vals = pd.unique(df[(df.instance == instance) & (df.generator == generator)]['satisfiability'])
                if 'SATISFIABLE' in sat_vals and 'UNSATISFIABLE' not in sat_vals:
                    satisfiability = 'SATISFIABLE'
                elif 'SATISFIABLE' not in sat_vals and 'UNSATISFIABLE' in sat_vals:
                    satisfiability = 'UNSATISFIABLE'
                else:
                    print(instance, sat_vals)
                    satisfiability = 'UNKNOWN'
                # TODO: add functionality for making verified result leading here.

                sat_results.append({'generator': generator, 'instance': instance, 'satisfiability': satisfiability})
    return pd.DataFrame.from_records(sat_results)


def create_table_with_generator_satisfiability(generator_names: list, sat_df) -> str:
    table = []
    for generator in generator_names:
        new_dict = {
            'generator': generator,
            'SAT': sat_df[sat_df.generator == generator].groupby('satisfiability').size()['SATISFIABLE'],
            'UNSAT': sat_df[sat_df.generator == generator].groupby('satisfiability').size().get('UNSATISFIABLE',
                                                                                                default=0),
            'unknown': sat_df[sat_df.generator == generator].groupby('satisfiability').size().get('UNKNOWN', default=0)
        }
        new_dict['total'] = new_dict['SAT'] + new_dict['UNSAT'] + new_dict['unknown']
        table.append(new_dict)
    df_table = pd.DataFrame.from_records(table)
    latex_table = ('\\begin{tabular}{lrrr|r}\n'
                   '\\toprule\n' +
                   ' & '.join(df_table.head()) + '\\\\ \\midrule\n')
    for row in df_table.iterrows():
        elts = row[1].to_list()
        latex_table += f'{latex_sf(elts[0])} & ' + ' & '.join([str(elt) for elt in elts[1:]])
        latex_table += '\\\\\n'
    latex_table += "\\midrule\n"
    sums = df_table.sum(axis=0)
    latex_table += f"total & {sums['SAT']} & {sums['UNSAT']} & {sums['unknown']} & {sums['total']} \\\\\n" \
                   "\\bottomrule\n" \
                   "\\end{tabular}"
    return latex_table


def create_list_with_unsat_instances(sat_df) -> str:
    unsat_instances = sorted(sat_df[sat_df.satisfiability == 'UNSATISFIABLE']['instance'].to_list())
    if not unsat_instances:
        return "There are no unsatisfiable instances in this experiment."
    latex_list = "\\begin{compactitems}\n"
    for instance in unsat_instances:
        latex_list += f"\\item {latex_lst_inline(os.path.basename(instance))}\n"
    latex_list += "\\end{compactitems}"
    return latex_list


def create_list_with_unknown_instances(sat_df) -> str:
    unknown_instances = sorted(sat_df[sat_df.satisfiability == 'UNKNOWN']['instance'].to_list())
    if not unknown_instances:
        return "There are no instances with unknown satisfiability in this experiment."
    latex_list = "\\begin{compactitems}\n"
    for instance in unknown_instances:
        latex_list += f"\\item {latex_lst_inline(os.path.basename(instance))}\n"
    latex_list += "\\end{compactitems}"
    return latex_list

    print(unsat_instances)
    unknown_instances = sorted(df_sat[df_sat.satisfiability == 'UNKNOWN']['instance'].to_list())
    print(unknown_instances)


def get_counter_result(df, counter_name: str, instance: str):
    count_field = 'count_value'
    if counter_name == 'verifier':
        count_field = 'verified_count'
    count = df[(df.instance == instance) & (df.counter == counter_name)][count_field].iloc[0]
    timed_out = df[(df.instance == instance) & (df.counter == counter_name)]['timed_out'].iloc[0]
    error = df[(df.instance == instance) & (df.counter == counter_name)]['error'].iloc[0]
    satisfiability = df[(df.instance == instance) & (df.counter == counter_name)]['satisfiability'].iloc[0]

    # satisfiability = 'UNKNOWN' if (satisfiability not in ['SATISFIABLE', 'UNSATISFIABLE']) else satisfiability
    if not timed_out and not error and satisfiability in ['SATISFIABLE', 'UNSATISFIABLE', 'UNKNOWN']:
        count = 0.0 if (counter_name == 'verifier' and np.isnan(count)) else count
        return True, satisfiability, count
    elif satisfiability in ['SATISFIABLE', 'UNSATISFIABLE', 'UNKNOWN']:
        return False, satisfiability, count
    else:
        return False, 'None', count


# def get_count(df):
#     if df.size == 1 and df.isnull().iloc[0]:
#
#     elif df.size == 1
#         print("NaN")
#     return int(df.fillna(-1))


def get_result_summary(counter_names: list, instances: list, df):
    """ There are basically five scenarios:
        1. counter and verifier agree on count of a given instance
        2. counter fails, verifier fails
        3. counter fails, verifier returns verified count for given instance
        4. counter returns count for given instance, verifier fails
        5. counter and verifier disagree on count of given instance
    By 'fail' we mean timeout, memout, assertion errors, etc. Hence, model
    counter bugs are probably going to be found in scenarios 2, 3 and 5.
    This function processes the raw data to collect the above information for
    further processing.
    """
    results = []
    for instance in instances:
        if 'verifier' in counter_names:
            v_success, v_satisfiability, verified_count = get_counter_result(df, 'verifier', instance)
            for counter in counter_names:
                if counter == 'verifier':
                    continue
                c_success, c_satisfiability, count = get_counter_result(df, counter, instance)
                results.append(
                    {'instance': instance, 'counter': counter,
                     'counter_success': c_success, 'counter_satisfiability': c_satisfiability,
                     'verifier_success': v_success, 'verifier_satisfiability': v_satisfiability,
                     'count': count, 'verified_count': count,
                     'agree': c_success and v_success and (v_satisfiability == c_satisfiability) and (count == verified_count),
                     'disagree': c_success and v_success and ((v_satisfiability != c_satisfiability) or (count != verified_count)),
                     })
        else:
            # TODO: Implement
            print("TODO: Implement function for when user didn't use a verifier.")

    df_results = pd.DataFrame.from_records(results)
    return df_results


def create_table_with_counter_verifier_status_summary(counter_names: list, df):
    rows = []
    for counter in counter_names:
        if counter == 'verifier':
            continue
        selection = df[df.counter == counter]
        n_counter_and_verifier_agree = selection['agree'].value_counts()[True] if True in selection['agree'].to_list() else 0
        n_counter_and_verifier_disagree = selection['disagree'].value_counts()[True] if True in selection['disagree'].to_list() else 0
        n_counter_fails_verifier_succeeds = selection[(selection['counter_success'] == False) & selection['verifier_success']].shape[0]
        n_counter_succeeds_verifier_fails = selection[(selection['verifier_success'] == False) & selection['counter_success']].shape[0]
        n_counter_fails_verifier_fails = selection[(selection['counter_success'] == False) & (selection['verifier_success'] == False)].shape[0]
        rows.append({
            'counter': counter,
            'agree': n_counter_and_verifier_agree,
            'disagree': n_counter_and_verifier_disagree,
            'counter fails': n_counter_fails_verifier_succeeds,
            'verifier fails': n_counter_succeeds_verifier_fails,
            'both fail': n_counter_fails_verifier_fails})
    df_table = pd.DataFrame.from_records(rows)
    sums = df_table[['agree', 'disagree', 'counter fails', 'verifier fails', 'both fail']].sum(axis=1)
    latex_table = ('\\begin{tabular}{lrrrrr|r}\n'
                   '\\toprule\n' +
                   ' & '.join(list(df_table.head()) + ['total']) + '\\\\ \\midrule\n')
    for i, row in enumerate(df_table.iterrows()):
        elts = row[1].to_list()
        latex_table += f'{latex_sf(elts[0])} & ' + ' & '.join([str(elt) for elt in elts[1:]] + [str(sums[i])])
        latex_table += '\\\\\n'
    latex_table += "\\bottomrule\n" \
                   "\\end{tabular}"
    return latex_table


def get_failure_type(res_dict):
    if res_dict['timed_out'][0] and not res_dict['error'][0]:
        return 't/o'
    elif not res_dict['timed_out'][0] and res_dict['error'][0]:
        return 'error'
    elif res_dict['timed_out'][0] and res_dict['error'][0]:
        return 't/o and error'
    else:
        return 'unknown'


def create_table_with_detailed_results(counter_names: list, df_results, df_summary):
    rows = []
    # # results = df_results.to_dict(orient='index_names')
    # summary = df_summary.to_dict(orient='tight')
    # for key, val in summary.items():
    #     print(key, val)

    for counter in counter_names:
        if counter == 'verifier':
            continue
        for instance in sorted(set(df_results.instance)):
            selection = df_summary[(df_summary.counter == counter) & (df_summary.instance == instance)]
            selection_dict = selection.to_dict(orient='list')
            agree = selection_dict['agree'][0]
            if agree:
                continue
            disagree = selection_dict['disagree'][0]
            counter_fails = (not selection_dict['counter_success'][0] and selection_dict['verifier_success'][0])
            verifier_fails = (selection_dict['counter_success'][0] and not selection_dict['verifier_success'][0])
            both_fail = (not selection_dict['counter_success'][0] and not selection_dict['verifier_success'][0])
            problem = ''
            details = ''


            result_dict = df_results[(df_results.counter == counter) & (df_results.instance == instance)].to_dict(orient='list')
            verifier_dict = df_results[(df_results.counter == 'verifier') & (df_results.instance == instance)].to_dict(orient='list')
            if disagree:
                problem = 'disagree'
            elif counter_fails:
                problem = 'counter fails'
                details = get_failure_type(result_dict)
            elif verifier_fails:
                problem = 'verifier fails'
                details = get_failure_type(verifier_dict)
            elif both_fail:
                problem = 'both fail'
                details = f"counter: {get_failure_type(result_dict)}; verifier: {get_failure_type(verifier_dict)}"
            rows.append({
                'counter': counter,
                'instance': os.path.splitext(os.path.basename(instance))[0],
                'problem': problem,
                'details': details,
                'sat? (counter)': to_short_sat(result_dict['satisfiability'][0]),
                'sat? (verifier)': to_short_sat(verifier_dict['satisfiability'][0]),
                'count (counter)': latex_int(result_dict['count_value'][0]) if not np.isnan(result_dict['count_value'][0]) else result_dict['count_value'][0],      # TODO: make this depend on counting type
                'count (verifier)': latex_int(verifier_dict['verified_count'][0]) if not np.isnan(verifier_dict['verified_count'][0]) else verifier_dict['verified_count'][0] # TODO: make this depend on counting type
            })
    df_table = pd.DataFrame.from_records(rows)
    latex_table = (
            '{\\footnotesize\n'
            '\\begin{longtable}{lrR{2cm}R{2.5cm}R{1.25cm}R{1.25cm}R{1.5cm}R{1.5cm}}\n'
            '\\toprule\n' +
            ' & '.join(list(df_table.head())) + '\\\\ \\midrule\n')
    old_counter = counter_names[0]
    for i, row in enumerate(df_table.iterrows()):
        elts = row[1].to_list()
        if elts[0] != old_counter:
            old_counter = elts[0]
            latex_table += '\\midrule\n'
        latex_table += f'{latex_sf(elts[0])} & {latex_lst_inline(elts[1])} & ' + ' & '.join([str(elt) for elt in elts[2:]])
        latex_table += '\\\\\n'

    latex_table += "\\bottomrule\n" \
                   "\\end{longtable}\n" \
                   "}\n"
    return latex_table


def run_latex(path_to_tex_file):
    cmd = ['pdflatex', path_to_tex_file]
    return_value = subprocess.call(cmd, shell=False)
    # print(return_value)
    # console_output, err = fut.run(cmd, f'{latex_dir}')


if __name__ == "__main__":

    args = parse_arguments()

    df_results = pd.read_csv(args.csv, delimiter=',')

    counter_names = get_counters(df_results)
    generator_names = get_generators(df_results)
    instances = get_instances(df_results)

    param_file = get_param_file(args.csv)
    params = json.load(open(param_file, 'r'))
    table_fuzzing_parameters = create_table_with_fuzzing_parameters(params)

    list_generator_info = create_list_with_tool_info(fut.parse_generators(params['generators']))
    list_counter_info = create_list_with_tool_info(fut.parse_generators(params['counters']))

    df_sat = get_sat_info(generator_names, df_results)
    table_generator_satisfiability = create_table_with_generator_satisfiability(generator_names, df_sat)

    list_unsat_instances = create_list_with_unsat_instances(df_sat)
    list_unknown_instances = create_list_with_unknown_instances(df_sat)

    df_summary = get_result_summary(counter_names, instances, df_results)
    table_counter_verifier_status_summary = create_table_with_counter_verifier_status_summary(counter_names, df_summary)

    table_counter_verifier_status_details = create_table_with_detailed_results(counter_names, df_results, df_summary)

    os.makedirs(f"{args.outdir}", exist_ok=True)
    with open(f"{PROJECT_DIR}/latex_generator/report_template.tex", 'r') as infile:
        text = str(infile.read())
        text = text.replace("@@count_type@@", "mc")
        text = text.replace("@@table_fuzzing_parameters@@", table_fuzzing_parameters)
        text = text.replace("@@list_generator_info@@", list_generator_info)
        text = text.replace("@@list_counter_info@@", list_counter_info)
        text = text.replace("@@table_generator_satisfiability@@", table_generator_satisfiability)
        text = text.replace("@@list_unsatisfiable_instances@@", list_unsat_instances)
        text = text.replace("@@list_unknown_instances@@", list_unknown_instances)
        text = text.replace("@@table_counter_verifier_status_summary@@", table_counter_verifier_status_summary)
        text = text.replace("@@table_counter_verifier_status_details@@", table_counter_verifier_status_details)
        with open(f"{args.outdir}/report.tex", 'w') as outfile:
            outfile.write(text)

    if args.pdflatex:
        run_latex(f"{args.outdir}/report.tex")
