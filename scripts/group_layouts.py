"""Precompute deterministic metric communities for instant offline layout switches."""
import math
import networkx as nx
import numpy as np
from threadpoolctl import threadpool_limits


def metric_layout(data, metric):
    count = len(data['nodes'])
    graph = nx.Graph()
    graph.add_nodes_from(range(count))
    candidates = []
    for edge in data['edges']:
        value = edge.get(metric)
        if value is None or not math.isfinite(value):
            continue
        strength = abs(value) if metric == 'r' else value
        if strength > 0 and edge['s'] != edge['t']:
            candidates.append((strength, edge['s'], edge['t']))
    # Union of each household's five strongest available links: emphasize high
    # association and keep community detection bounded for the offline build.
    taken = [0] * count
    for strength, source, target in sorted(candidates, key=lambda item: (-item[0], item[1], item[2])):
        if taken[source] < 5 or taken[target] < 5:
            graph.add_edge(source, target, weight=strength**2)
        taken[source] += 1
        taken[target] += 1
    isolated = sorted(nx.isolates(graph))
    connected = graph.subgraph([i for i in graph if graph.degree(i)])
    communities = nx.community.louvain_communities(connected, weight='weight', resolution=1.4, seed=42) if connected.number_of_edges() else []
    communities = sorted((sorted(group) for group in communities), key=lambda group: (-len(group), group[0]))
    community_count = len(communities)
    print(f'Grouping {metric}: {community_count} communities, {len(isolated)} unlinked households', flush=True)
    if isolated:
        communities.append(isolated)
    positions = np.zeros((count, 2))
    labels = [-1] * count
    circles = []
    for group_id, members in enumerate(communities):
        radius = max(2.5, math.sqrt(len(members)) * 1.5)
        # Pack separate community disks without overlap; largest first.
        center = np.array([0., 0.])
        for attempt in range(1, 20000):
            if all((float(center[0])-x)**2 + (float(center[1])-y)**2 >= (radius+size+5)**2 for x,y,size in circles):
                break
            angle = attempt * 2.399963229728653
            distance = 1.5 * math.sqrt(attempt)
            center = np.array([math.cos(angle), math.sin(angle)]) * distance
        else:
            raise RuntimeError('Unable to pack community layout')
        circles.append((float(center[0]), float(center[1]), radius))
        subgraph = graph.subgraph(members)
        if len(members) > 1 and subgraph.number_of_edges():
            local = nx.spring_layout(subgraph, weight='weight', seed=42, iterations=35)
            coords = np.array([local[i] for i in members])
        else:
            coords = np.array([[math.cos(i*2.399963229728653)*math.sqrt(i+1),
                                math.sin(i*2.399963229728653)*math.sqrt(i+1)] for i in range(len(members))])
        coords -= coords.mean(axis=0)
        coords *= radius / max(float(np.linalg.norm(coords, axis=1).max()), 1e-9)
        positions[members] = coords + center
        for i in members:
            labels[i] = group_id if group_id < community_count else -1
    return {'positions': positions.round(6).tolist(), 'groups': labels,
            'groupCount': community_count, 'unlinkedCount': len(isolated),
            'method': 'Louvain, squared positive MI or squared absolute Pearson r; union of top five candidate neighbors per household; resolution 1.4; seed 42'}


def grouping_layouts(data):
    # Small community matrices are faster without competing BLAS thread pools.
    with threadpool_limits(limits=1):
        return {metric: metric_layout(data, metric) for metric in ('r', 'mi')}
