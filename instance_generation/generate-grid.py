#!/usr/bin/env python3
# encoding: utf-8
"""
@author: anna
@contact: a.l.d.latour@liacs.leidenuniv.nl
@time: 5/28/21 4:56 PM
@file: generate-grid.py
@desc: Script to generate a GRID-like Bayesian Network with a fraction of the
nodes deterministic, and one query node. Also creates associated evidence file.
"""

import argparse
from datetime import datetime
import itertools as it
import numpy as np
import os

parser = argparse.ArgumentParser(description='Generate GRID instances in .net format.')
parser.add_argument_group('Mandatory arguments')
parser.add_argument('--size', type=int, help='The grid has size x size nodes.')
parser.add_argument('--det', type=float, help='Fraction of nodes that is to be deterministic.')
parser.add_argument('--seed', type=int, help='Random seed.')
parser.add_argument('--outdir', type=str, help='Path to where to write the file.')
parser.add_argument('--outfile', type=str, help='Filename for outfile.')
args = parser.parse_args()

PROJECT_HOME = os.environ.get('PROJECT_HOME')
OUT_DIR = args.outdir

# Create outdirs
for outdir in ['/net', '/evidence']:
    if not os.path.exists(OUT_DIR + outdir):
        os.makedirs(OUT_DIR + outdir)

# Initialise random seed
np.random.seed = args.seed

# Define outfiles
net_outfile = args.outfile if args.outfile.endswith('.net') else args.outfile + '.net'
evi_outfile = args.outfile.replace('.net', '.inst') if args.outfile.endswith('.net') else args.outfile + '.inst'


def make_grid(size_, det_):
    """
    Create a string that describes a GRID Bayesian Network.
    :param size_: Number of nodes on one size of the grid (grid is size x size)
    :param det_: Fraction of nodes that is deterministic
    :return: tuple (str: bn, str: q_node) that represents the Bayesian
    Network and the node ID of the query node.
    """
    string = "net\n{\n}\n"

    # NODES
    nodes = []
    for i, j in it.product(range(size_), repeat=2):
        nodeId = "v_{}_{}".format(i + 1, j + 1)
        # Seems like the first state means "v_{i+1}_{j+1} == true", and the second means "v_{i+1}_{j+1} == false"
        string += "node " + nodeId + "\n{\n\t states = (\"" + nodeId + "a\" \"" + nodeId + "b\");\n}\n"
        nodes.append(nodeId)
    q_node = nodes[-1]

    deterministic = np.zeros(len(nodes), dtype=bool)
    deterministic[np.random.permutation(range(len(nodes)))[:int(len(nodes) * det_)]] = True;

    # EDGES
    for index, (i, j) in enumerate(it.product(range(size_), repeat=2)):
        input_nodes = []
        if i > 0:
            input_nodes.append(size_ * (i - 1) + j)
        if j > 0:
            input_nodes.append(size_ * i + j - 1)

        string += "potential ( {}".format(nodes[index])
        if len(input_nodes) > 0:
            string += " | "
            string += " ".join([nodes[ii] for ii in input_nodes])
        string += " )\n{\n\t data = ("

        for _ in range(2 ** (len(input_nodes))):
            if len(input_nodes) > 0:
                string += "\t("
            # prob = np.random.rand()
            prob = np.random.randint(1, 10) / 10.0
            if deterministic[index]:
                prob = 1 if prob > .5 else 0
            if np.random.choice([True, False]):
                string += "{0:.2f} {1:.1f}".format(round(prob, 1), round(1 - prob, 1))
            else:
                string += "{0:.2f} {1:.1f}".format(round(1 - prob, 1), round(prob, 1))
            if len(input_nodes) > 0:
                string += ")\n"
        if string.endswith('\n'):
            string = string[:-1] + ");\n}\n"
        else:
            string += ");\n}\n"
    return string, q_node


def create_evidence(q_node):
    """ Create an evidence file for the query node.
    :param q_node: string that represent the id of the node that we want to query.
    :return: string of the evidence file.
    """
    s = '<?xml version="1.0" encoding="UTF-8"?>\n'
    s += '<instantiation date="{date}">\n'.format(date=datetime.now().strftime("%d %B %Y, %H:%M:%S"))
    s += '<inst id="{nodeID}" value="{nodeID}{choice}"/>\n'.format(nodeID=q_node, choice=np.random.choice(['a', 'b']))
    s += '</instantiation>'
    return s


grid, query_node = make_grid(args.size, args.det)
with open(OUT_DIR + '/net/' + net_outfile, "w") as fh:
    fh.write(grid)
    fh.close()
evi = create_evidence(query_node)
with open(OUT_DIR + '/evidence/' + evi_outfile, "w") as fh:
    fh.write(evi)
    fh.close()

