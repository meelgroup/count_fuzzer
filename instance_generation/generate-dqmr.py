#!/usr/bin/env python3
# encoding: utf-8
"""
@author: anna
@contact: a.l.d.latour@liacs.leidenuniv.nl
@time: 9/29/21 3:50 PM
@file: generate-dqmr.py
@desc: Script to generate a DQMR-like bipartite Bayesian Network according to
the specifications of [Sang et al. 2005]:
    "An abstract version of the QMR-DT medical diagnosis Bayesian networks
    (Shwe et al. 1991). Each problem is given by a two layer bipartite network
    in which the top layer consists of diseases and the bottom layer consists of
    symptoms. If a disease may result a symptom, there is an edge from the
    disease to the symptom. In the CPTs for DQMR (unlike those of QMR-DT) a
    symptom is completely determined by the diseases that cause it; i.e., it is
    modeled as an OR rather than a noisy OR of its inputs. As in QMR-DT, every
    disease has an independent prior probability.
    For our experiments, we varied the numbers of diseases and symptoms from 50
    to 100 and chose the edges of the bipartite graph randomly, with each
    symptom caused by four randomly chosen diseases. The problem was to compute
    the marginal probabilities for all the diseases given a set of consistent
    observations of symptoms. The size of the observation set varied between
    10% to 30% of all symptoms."
Also creates associated evidence file.

It takes as input the number of diseases, number of symptoms, and the fraction
of observed symptoms. The output is a .net file and an evidence file. The net
represents the Bayesian Network, the evidence contains all observed symptoms and
the query disease.

Note that we're departing a little bit from the original brief of computing the
marginal probabilities of all diseases. Instead, we're computing the joint
probability of observing the symptoms and having the disease. We could compute
the marginal probability of having the disease given the observed symptoms by
simply computing the probability of the observed symptoms, by removing the
disease query. Then, we could divide the joint probability by the symptom
probability.

"""

import argparse
from datetime import datetime
import itertools as it
import numpy as np
import os

parser = argparse.ArgumentParser(description='Generate DQMR instances in .net format.')
parser.add_argument_group('Mandatory arguments')
parser.add_argument('--diseases', type=int, choices=range(5, 101, 5),
                    help='The number of diseases')
parser.add_argument('--symptoms', type=int, choices=range(5, 101, 5),
                    help='The number of symptoms')
parser.add_argument('--obs', type=float,
                    help='Fraction of symptoms that are observed.')
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

def make_network(n_diseases: int, n_symptoms: int):
    """
    Create a string that described a DQMR Bayesian Network.
    :param n_diseases: Number of diseases.
    :param n_symptoms: Number of symptoms.
    :return: triple (str: bn,
                     list: [d_node_1, ..., d_node_n_diseases],
                     list: [s_node_1, ..., s_node_n_symptoms]) that represents
                     the Bayesian Network and a list of query node IDs.
    """

    string = "net\n{\n}\n"

    # NODES
    disease_nodes_ = []
    symptom_nodes_ = []

    # DISEASES
    for i in range(n_diseases):
        nodeId_disease = "d{0:03d}".format(i+1)
        string += "node " + nodeId_disease + "\n{\n\t states = (\"" + \
                  nodeId_disease + "_true\" \"" + nodeId_disease + "_false\");\n}\n"
        disease_nodes_.append(nodeId_disease)

    # SYMPTOMS
    for i in range(n_symptoms):
        nodeId_symptom = "s{0:03d}".format(i+1)
        string += "node " + nodeId_symptom + "\n{\n\t states = (\"" + \
                  nodeId_symptom + "_true\" \"" + nodeId_symptom + "_false\");\n}\n"
        symptom_nodes_.append(nodeId_symptom)

    # EDGES
    edge_sources = [sorted(np.random.choice(disease_nodes_, 4, replace=False)) for _ in range(n_symptoms)]
    for disease_node in disease_nodes_:
        prob = np.random.rand()
        string += "potential ( {}".format(disease_node) + \
                  " )\n{\n\t data = " + "({0:.2f} {1:.2f})".format(round(prob, 2), round(1-prob, 2)) + \
                  ";\n}\n"

    for symptom_node, parents in zip(symptom_nodes_, edge_sources):
        string += "potential ( {} | ".format(symptom_node)
        string += " ".join(parents)
        string += " )\n"
        string += "{\ndata = (\t"
        string += (4**2-1)*"(1.00 0.00)\n\t"    # at least one disease -> symptom present (OR)
        string += "(0.00 1.00)\n\t"             # no disease -> no symptom
        string += ");\n}\n"

    return string, disease_nodes_, symptom_nodes_


def create_evidence(symptom_nodes_, observed, q_node_):
    """ Create an evidence file for the query node.
    :param evi_nodes: list of
    :param q_node: string that represent the id of the node that we want to query.
    :return: string of the evidence file.
    """

    observed_symptoms_ = np.random.choice(symptom_nodes_, int(observed*len(symptom_nodes_)), replace=False)

    s = '<?xml version="1.0" encoding="UTF-8"?>\n'
    s += '<instantiation date="{date}">\n'.format(date=datetime.now().strftime("%d %B %Y, %H:%M:%S"))
    # Observed symptoms are always true, so we can guarantee that they are
    # consistent. Because the symptoms are modelled as ORs, not noisy ORs,
    # we cannot have observed absence of symptoms.
    s += '\n'.join(['<inst id="{nodeID}" value="{nodeID}_true"/>'.format(nodeID=node_id)
                    for node_id in observed_symptoms_])
    # The disease query is also positive.
    s += '<inst id="{nodeID}" value="{nodeID}_true"/>\n'.format(nodeID=q_node_)
    s += '</instantiation>'
    return s


grid, disease_nodes, symptom_nodes = make_network(args.diseases, args.symptoms)
with open(OUT_DIR + '/net/' + net_outfile, "w") as fh:
    fh.write(grid)
    fh.close()
q_node = np.random.choice(disease_nodes, 1)[0]
evi = create_evidence(symptom_nodes, args.obs, q_node)
with open(OUT_DIR + '/evidence/' + evi_outfile, "w") as fh:
    fh.write(evi)
    fh.close()

