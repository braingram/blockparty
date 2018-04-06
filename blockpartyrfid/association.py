#!/usr/bin/env python

import networkx


def generate_association_graph(maes, show=True):
    associations = {}
    for e in maes:
        for (i, a) in enumerate(e['animals'][:-1]):
            if a not in associations:
                associations[a] = {}
            for o in e['animals'][i+1:]:
                if a == o:
                    continue
                if o not in associations[a]:
                    associations[a][o] = 0
                associations[a][o] += 1

    animals = list(associations.keys())
    g = networkx.DiGraph()
    for a in animals:
        for o in associations[a]:
            g.add_edge(hex(a), hex(o), weight=associations[a][o])

    if show:
        networkx.draw_circular(
            g, width=[d['weight'] / 50 for (u, v, d) in g.edges(data=True)],
            labels=dict(zip(g.nodes(), g.nodes())))
    return g
