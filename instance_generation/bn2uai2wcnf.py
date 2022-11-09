# encoding: utf-8
"""
@author: anna
@contact: a.l.d.latour@liacs.leidenuniv.nl
@time: 3/15/21 1:07 PM
@file: net2uai2wcnf.py
@desc:
"""

import enum
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

class ReadingState(enum.Enum):
    """ The different reading states for reading out a BN network in .net format.
    """
    Nothing = 0
    Node = 1
    Conditionals = 2
    Data = 3


@dataclass
class BayesianNetworkNode:
    """
    Attributes:
        label (str): The label of the Bayesian Network node in the .net input file.
        root (Bool): Is the Bayesian Network node parentless?
        idx (int): Node ID
        states (tuple):
    """
    label: str = ''
    """The label of the Bayesian Network node in the .net input file."""
    root: bool = False
    idx: int = -1
    states: tuple = tuple()
    parents: list = field(default_factory=list)
    cpt: list = field(default_factory=list)
    indicator_vars: list = field(default_factory=list)
    parameter_vars: list = field(default_factory=list)


@dataclass
class WCNF:
    n_vars: int = 0
    n_clauses: int = 0
    clauses: list = field(default_factory=list)
    evidence_clauses: list = field(default_factory=list)


def _get_clauses_string(clauses):
    return '\n'.join(['{cl} 0'.format(cl=' '.join([str(lit) for lit in cl]))
                     for cl in clauses]) + '\n'


class Net2UAI2WCNF:

    def __init__(self, net_file=None, evi_files=None):
        self._net_file = net_file
        self._evi_files = evi_files

        self._uai_file = None
        self._uai_evi_file = None

        self._cnf_filename = None
        self._wmap_filename = None
        self._vmap_filename = None

        self._wcnf_filename = None

        self._bn = dict()
        self._evidence = dict()

        self._bnvarstate2cnfvars = dict()
        self._uaivar2cnf_states = dict()
        self._cnfidx2weight = []

        self._states_pat = re.compile(r'\s*states\s*=\s*\(\s*(?P<states>((\"\w+\")\s*)+)\)\s*;', re.DOTALL)
        self._conditional_pat = re.compile(
            r'\s*potential\s*\(\s*(?P<label>\w+)\s*(\|\s*(?P<conditionals>(\w+\s+)*\w+)\s*)?\)\s*', re.DOTALL)
        self._root_data_pat = re.compile(r'\s*data = \(\s*(?P<data>([01]\.\d+\s*)+)\)\s*;.*', re.DOTALL)
        self._internal_node_data_pat = re.compile(r'\s*(data = \()?\s*\(\s*(?P<data>([10]\.\d+\s*)+)\).*', re.DOTALL)
        self._evi_pat = re.compile(r'<inst\s*id=\"(?P<label>\w+)\"\s*value=\"(?P<value>\w+)\"/>', re.DOTALL)
        self._vmap_pat = re.compile(r'(?P<uai_var>\d+)\s*=\s*(?P<cnf_lits>[\d\[\],\s\-]+)\s*', re.DOTALL)
        if self._net_file is not None:
            self._parse_net_file()
        if self._evi_files is not None:
            self._parse_evidence_files()

        self._cmd = []

    def _read_state_info(self, line) -> tuple:
        """
        Extracts the different state labels associated with Bayesian Network
        node in an input .net file.

        :param line: line from the .net Bayesian Network file, of the form:
            'states = ("label1" "label2" ...)'
        :return: tuple with state labels
        """
        m = re.match(self._states_pat, line)
        assert m is not None, "Found no states match for line \"{l}\"".format(l=line)
        states = tuple(state.replace('"', '') for state in m.group('states').split())
        return states

    def _read_conditional_info(self, line) -> tuple:
        m = re.match(self._conditional_pat, line)
        assert m is not None, "Found no conditionals match for line \"{l}\"".format(l=line)
        label = m.group('label')
        conditionals = [c for c in m.group('conditionals').split()] \
            if m.group('conditionals') is not None else []
        return label, conditionals

    def _read_data_info(self, line, is_root) -> tuple:
        pat = self._root_data_pat if is_root else self._internal_node_data_pat
        m = re.match(pat, line)
        assert m is not None, "Found no data match for line \"{l}\"".format(l=line)
        data = tuple(float(elt) for elt in m.group('data').split())
        return data

    def _parse_net_file(self):
        with open(self._net_file, 'r') as netfile:
            new_node = BayesianNetworkNode()
            state = ReadingState.Nothing
            current_cpt = ''
            for line in netfile.readlines():
                print(line)
                print(state)
                if (state == ReadingState.Nothing
                        and line.startswith('node')):
                    state = ReadingState.Node
                    label = line.split()[1]
                    new_node = BayesianNetworkNode(label=label, idx=len(self._bn))
                    continue
                if (state == ReadingState.Node
                        and line.lstrip().startswith('states')):
                    new_node.states = self._read_state_info(line)
                    self._bn[new_node.label] = new_node
                    state = ReadingState.Nothing
                    continue
                if (state == ReadingState.Nothing
                        and line.startswith('potential')):
                    state = ReadingState.Conditionals
                    label, conditionals = self._read_conditional_info(line)
                    current_cpt = label
                    self._bn[label].parents.extend(conditionals)
                    self._bn[label].root = len(conditionals) == 0
                if (state == ReadingState.Conditionals
                        and line.lstrip().startswith('data')):
                    is_root = len(self._bn[current_cpt].parents) == 0
                    data = self._read_data_info(line, is_root)
                    print('data:', data)
                    self._bn[current_cpt].cpt.append((tuple(p for p in data)))
                    # state = ReadingState.Nothing
                    state = ReadingState.Nothing if is_root else ReadingState.Data
                    continue
                if state == ReadingState.Data:
                    if line.strip() == ');':
                        state = ReadingState.Nothing
                        continue
                    data = self._read_data_info(line, False)
                    print('data:', data)
                    self._bn[current_cpt].cpt.append(tuple(p for p in data))
                    if line.strip().endswith(');'):
                        state = ReadingState.Nothing
                        continue
                    continue

    def _read_evidence(self, line) -> tuple:
        m = re.match(self._evi_pat, line)
        if m is not None:
            label = m.group('label')
            state = m.group('value')
            return label, state
        return None, None

    def _parse_evidence_files(self):
        """
        Each evidence file contains the label of a node in the Bayesian Network
        and the label of the state on which it is conditioned.
        :return: None
        """
        for evi_filename in self._evi_files:
            with open(evi_filename, 'r') as evi_file:
                for line in evi_file.readlines():
                    label, state = self._read_evidence(line)
                    if label is not None:
                        self._evidence[label] = state

    def print_bn(self):
        for label, node in self._bn.items():
            print('node:', label)
            print('states:', node.states)
            print('conditioned on:', node.parents)
            print('cpt:')
            for p in node.cpt:
                print(p)
            print('')

    def save2uai(self, out_dir=None):
        basename = os.path.basename(self._net_file)
        if out_dir is None:
            out_dir = os.path.dirname(self._net_file)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        self._uai_file = out_dir + '/' + basename.replace('.net', '.uai')
        self._uai_evi_file = self._uai_file + '.evid'

        label2idx = {node.label: node.idx for node in self._bn.values()}
        idx2label = {node.idx: node.label for node in self._bn.values()}
        with open(self._uai_file, 'w') as uai_file:
            # Type of network:
            uai_file.write("BAYES\n")
            # Number of variables:
            uai_file.write("%i\n" % len(self._bn))
            # Number of states for each node (domain of each variable):
            uai_file.write(
                ' '.join([str(len(node.states)) for node in sorted(self._bn.values(), key=lambda x: x.idx)]) + '\n')
            # Number of functions (CPTs):
            uai_file.write("%i\n" % len(self._bn))
            uai_file.write('\n')

            # Specify for each variable how many lines their CPTs have and
            # which variable indices are involved in each CPT.
            for idx in range(len(self._bn)):
                parents = self._bn[idx2label[idx]].parents
                parent_idx = [label2idx[parent] for parent in parents]
                n_function_elts = len(parents) + 1
                uai_file.write('{n} {p} {c}\n'.format(
                    n=n_function_elts,
                    p=' '.join([str(p_idx) for p_idx in parent_idx]),
                    c=idx))
            uai_file.write('\n')

            # Specify CPTs
            for node_label, node in self._bn.items():
                n_cpt_elts = len(node.cpt) * len(node.cpt[0])
                uai_file.write("%i\n" % n_cpt_elts)

                for row in node.cpt:
                    uai_file.write("\t{row}\n".format(row=' '.join([str(p) for p in row])))

        # Add evidence
        with open(self._uai_evi_file, 'w') as uai_evi_file:
            # Specify number of variables that are fixed in the evidence:
            uai_evi_file.write('{n_evi}\n'.format(n_evi=len(self._evidence)))
            # Specify the values to which they have been fixed:
            for var_label, state_label in self._evidence.items():
                uai_evi_file.write('\t{var_idx} {state_idx}\n'.format(
                    var_idx=self._bn[var_label].idx,
                    state_idx=self._bn[var_label].states.index(state_label)
                ))

    def convert2cnf(self, out_dir=None, bn2cnf_dir=None,
                    enc='DIRECT', implicit=False, prime=False):
        basename = os.path.basename(self._net_file)
        if out_dir is None:
            out_dir = os.path.dirname(self._net_file)
        self._cnf_filename = out_dir + '/' + basename.replace('.net', '.cnf')
        self._wmap_filename = out_dir + '/' + basename.replace('.net', '.wmap')
        self._vmap_filename = out_dir + '/' + basename.replace('.net', '.vmap')

        if bn2cnf_dir is None:
            bn2cnf_dir = '../bins/'

        cmd = [bn2cnf_dir + 'bn2cnf_linux',
               '-i', self._uai_file,
               '-o', self._cnf_filename,
               '-w', self._wmap_filename,
               '-v', self._vmap_filename,
               '-e', enc]
        if implicit:
            cmd.append('-implicit')
        if prime:
            cmd.extend(['-s', 'prime'])
        self._cmd = cmd
        output = subprocess.run(cmd, capture_output=True)
        print(output)

    def _parse_weight_map(self):
        assert self._wmap_filename is not None, "Make sure to run save2uai() and convert2cnf() first."
        with open(self._wmap_filename, 'r') as wmap_file:
            for line in wmap_file.readlines():
                if line.startswith('-') or line.startswith('0'):  # TODO: implement scaling
                    continue
                cnf_var_idx = int(line.split()[0])
                cnf_var_weight = line.split()[1]
                self._cnfidx2weight[cnf_var_idx] = cnf_var_weight

    def _read_variable_map(self, line):
        """
        Reads a line in the variable map to extract the index of the Bayesian
        variable and the states, expressed as CNF literals, associated with it.

        :param line: line in variable map (.vmap) file
        :return: tuple with in the first position the index of the Bayes
                 variable, and in the second position a list of states,
                 expressed either as tuples or singlets of CNF literals.
        """
        m = re.match(self._vmap_pat, line)
        if m is not None:
            uai_var = int(m.group('uai_var'))
            cnf_lits = m.group('cnf_lits')
            states = []

            # This is an ugly hack until I've thought of something better:

            # multiple cnf variables for one uai variable:
            if ',' in cnf_lits:
                states = [tuple([int(lit) for lit in state.split(',')])
                          for state in cnf_lits[2:-3].split('][')]
            # one cnf variable for one uai variable:
            else:
                states = [int(lit) for lit in cnf_lits[2:-3].split('][')]
            return uai_var, states

    def _parse_variable_map(self):
        """
        Parses the variable map (.vmap) file, to extract for each Bayesian
        variable a list of states expressed in terms of CNF literals.
        These are stored in self._uaivar2cnf_states.

        :return: None
        """
        assert self._vmap_filename is not None, "Make sure to run save2uai() and convert2cnf() first."
        with open(self._vmap_filename, 'r') as vmap_file:
            for line in vmap_file.readlines():
                uai_var, states = self._read_variable_map(line)
                self._uaivar2cnf_states[uai_var] = states

    def _add_evidence_clauses(self):
        """
        The .vmap file specifies which (sets of) literals are associated with
        each state of each Bayesian Network node. By adding unit clauses that
        force those literals to be set to `True', we add the appropriate query
        to the WCNF. These unit clauses are added to self._wcnf.evidence_clauses.

        :return: None
        """
        assert self._evi_files is not None and len(self._evidence) > 0, "If you have specified evidence files, make sure to have run "
        for var_label, state_label in self._evidence.items():
            state_idx = self._bn[var_label].states.index(state_label)
            uai_var = self._bn[var_label].idx
            state_literals = self._uaivar2cnf_states[uai_var][state_idx]
            if isinstance(state_literals, int):
                self._wcnf.evidence_clauses.append([state_literals])
                self._wcnf.n_clauses += 1
            else:
                for lit in state_literals:
                    self._wcnf.evidence_clauses.append([lit])
                    self._wcnf.n_clauses += 1

    def _parse_cnf_file(self):
        assert self._cnf_filename is not None, "Make sure to run save2uai() and convert2cnf() first."
        with open(self._cnf_filename, 'r') as cnf_file:
            for line in cnf_file.readlines():
                if line.startswith('p'):
                    _, _, n_vars, n_clauses = line.split()
                    self._cnfidx2weight = [-1] * (int(n_vars) + 1)
                    self._wcnf = WCNF(n_vars=int(n_vars), n_clauses=int(n_clauses))
                else:
                    self._wcnf.clauses.append([int(elt) for elt in line.split()[:-1]])

    def _write_wcnf_2_file(self):
        clean_cmd = ['bn2cnf_linux'] + [os.path.basename(elt)
                                        if os.path.isfile(elt) else elt
                                        for elt in self._cmd[1:]]
        header = 'c ' + '=' * 78 + '\nc\n'
        header += 'c Weighted CNF\n' \
                  'c ------------\n' \
                  'c format:    DIMACS\n' \
                  'c weights:   A weight of -1 indicates that the weight of that variable does not\n' \
                  'c            contribute to the weighted model count. For all other variables,\n' \
                  'c            only the weight of the positive literal is given, and it is assumed\n' \
                  'c            that the weights of the positive and negative literal are non-\n' \
                  'c            negative and sum up to 1.\n' \
                  'c date:      ' + datetime.now().strftime('%d-%m-%Y\n') + \
                  'c input net: ' + os.path.basename(self._net_file) + '\n' \
                  'c command:   ' + ' '.join(clean_cmd) + '\n' \
                  'c \n' \
                  'c ' + 78 * '=' + '\nc\n'
        with open(self._wcnf_filename, 'w') as wcnf_file:
            wcnf_file.write(header)
            wcnf_file.write('p cnf {nvars} {nclauses}\n'.format(
                nvars=self._wcnf.n_vars, nclauses=self._wcnf.n_clauses
            ))
            wcnf_file.write('c\nc Weights\nc\n')
            for i, w in enumerate(self._cnfidx2weight):
                if i == 0:
                    continue
                wcnf_file.write('w {idx} {weight}\n'.format(idx=i, weight=w))
            wcnf_file.write('c\nc Network clauses\nc\n')
            wcnf_file.write(_get_clauses_string(self._wcnf.clauses))
            wcnf_file.write('c\nc Query clauses (evidence)\nc\n')
            wcnf_file.write(_get_clauses_string(self._wcnf.evidence_clauses))

    def convert2wcnf(self, out_dir=None):
        basename = os.path.basename(self._net_file)
        if out_dir is None:
            out_dir = os.path.dirname(self._net_file)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        self._wcnf_filename = out_dir + '/' + basename.replace('.net', '.wcnf')

        self._parse_cnf_file()
        self._parse_weight_map()
        self._parse_variable_map()
        self._add_evidence_clauses()
        self._write_wcnf_2_file()

