from __future__ import annotations
import hashlib, math, time
import networkx as nx

class AdvancedKnowledgeGraph:
    """Ontology-aware, semantic, freshness-aware capability/knowledge graph."""
    def __init__(self, half_life_seconds=30*86400):
        self.g = nx.MultiDiGraph()
        self.half_life = half_life_seconds

    def add_concept(self, name, kind='knowledge', aliases=None, parents=None, metadata=None):
        n = f'{kind}:{name.lower()}'
        self.g.add_node(n, kind=kind, name=name.lower(), updated_at=time.time(), **(metadata or {}))
        for alias in aliases or []:
            x = f'{kind}:{alias.lower()}'
            self.g.add_node(x, kind=kind, name=alias.lower())
            self.g.add_edge(x, n, relation='alias_of', weight=1.0, updated_at=time.time())
        for parent in parents or []:
            x = f'{kind}:{parent.lower()}'
            self.g.add_node(x, kind=kind, name=parent.lower())
            self.g.add_edge(n, x, relation='is_a', weight=.9, updated_at=time.time())
        return n

    def add_relationship(self, source, target, *, kind='knowledge', relation='related_to', weight=.7, bidirectional=False):
        a = self.add_concept(source, kind)
        b = self.add_concept(target, kind)
        self.g.add_edge(a, b, relation=relation, weight=float(weight), updated_at=time.time())
        if bidirectional:
            self.g.add_edge(b, a, relation=relation, weight=float(weight), updated_at=time.time())
        return a, b

    def add_contradiction(self, left, right, *, kind='knowledge'):
        return self.add_relationship(left, right, kind=kind, relation='contradicts', weight=-1.0, bidirectional=True)

    def contradictions(self, concept, *, kind='knowledge'):
        node = f'{kind}:{concept.lower()}'
        if node not in self.g:
            return []
        out = []
        for _, target, data in self.g.out_edges(node, data=True):
            if data.get('relation') == 'contradicts':
                out.append(self.g.nodes[target].get('name', target))
        return sorted(set(out))

    def add_agent(self, agent):
        self.g.add_node(agent.agent_id, kind='agent', updated_at=time.time())
        for cap in agent.capabilities:
            c = self.add_concept(cap.name, 'capability')
            self.g.add_edge(agent.agent_id, c, relation='has_capability', weight=cap.proficiency, validated=cap.validated, updated_at=time.time())
        for knowledge in agent.knowledge:
            c = self.add_concept(knowledge, 'knowledge')
            self.g.add_edge(agent.agent_id, c, relation='knows', weight=1.0, updated_at=time.time())

    def inherit(self, child, parent, kind='capability', weight=.85):
        a = self.add_concept(child, kind)
        b = self.add_concept(parent, kind)
        self.g.add_edge(a, b, relation='is_a', weight=weight, updated_at=time.time())

    def freshness(self, updated_at, now=None):
        age = max(0, (now or time.time()) - float(updated_at or 0))
        return math.pow(.5, age / max(1, self.half_life))

    def semantic_similarity(self, a, b, vectorizer=None):
        if a.lower() == b.lower():
            return 1.0
        if vectorizer:
            va, vb = vectorizer(a), vectorizer(b)
            dot = sum(x*y for x, y in zip(va, vb))
            na = math.sqrt(sum(x*x for x in va)); nb = math.sqrt(sum(x*x for x in vb))
            return dot / max(1e-12, na*nb)
        def vector(text):
            out = [0.0] * 128
            tokens = text.lower().replace('-', ' ').replace('_', ' ').split()
            for token in tokens:
                digest = int(hashlib.sha256(token.encode()).hexdigest(), 16)
                out[digest % len(out)] += 1
                out[(digest >> 8) % len(out)] += .35
            return out
        return self.semantic_similarity(a, b, vector)

    def import_ontology(self, records, *, kind='knowledge'):
        """Import normalized ontology records.

        Each record can contain ``name``, ``aliases``, ``parents``, ``related`` and
        ``contradicts``. This format is intentionally simple so SKOS/RDF/OWL
        loaders can normalize into it without changing the graph core.
        """
        count = 0
        for record in records:
            name = record['name']
            self.add_concept(name, kind, aliases=record.get('aliases'), parents=record.get('parents'), metadata=record.get('metadata'))
            for related in record.get('related', []):
                self.add_relationship(name, related, kind=kind, relation='related_to', bidirectional=True)
            for opposite in record.get('contradicts', []):
                self.add_contradiction(name, opposite, kind=kind)
            count += 1
        return count

    def import_rdf(self, path_or_url, *, kind='knowledge'):
        try:
            import rdflib
            from rdflib.namespace import SKOS, RDFS
        except ImportError as exc:
            raise RuntimeError('Install agentweave[ontology]') from exc
        graph = rdflib.Graph()
        graph.parse(path_or_url)
        records = {}
        for subject, _, label in graph.triples((None, SKOS.prefLabel, None)):
            records.setdefault(str(subject), {'name': str(label), 'aliases': [], 'parents': [], 'related': []})
        for subject, _, label in graph.triples((None, SKOS.altLabel, None)):
            records.setdefault(str(subject), {'name': str(subject), 'aliases': [], 'parents': [], 'related': []})['aliases'].append(str(label))
        for subject, predicate, parent in graph:
            if predicate in {SKOS.broader, RDFS.subClassOf} and str(subject) in records:
                parent_name = records.get(str(parent), {}).get('name', str(parent).rsplit('/', 1)[-1])
                records[str(subject)]['parents'].append(parent_name)
            elif predicate == SKOS.related and str(subject) in records:
                related_name = records.get(str(parent), {}).get('name', str(parent).rsplit('/', 1)[-1])
                records[str(subject)]['related'].append(related_name)
        return self.import_ontology(records.values(), kind=kind)

    def retrieve(self, query, *, kind='knowledge', limit=10, vectorizer=None, include_stale=True):
        rows = []
        now = time.time()
        for node, data in self.g.nodes(data=True):
            if data.get('kind') != kind:
                continue
            name = data.get('name', '')
            similarity = self.semantic_similarity(query, name, vectorizer)
            fresh = self.freshness(data.get('updated_at', now), now)
            if not include_stale and fresh < .25:
                continue
            rows.append({'node': node, 'name': name, 'similarity': similarity, 'freshness': fresh, 'score': similarity * (.6 + .4*fresh)})
        return sorted(rows, key=lambda x: x['score'], reverse=True)[:limit]

    def agent_score(self, agent_id, required: list[str], kind='capability', semantic_threshold=.35, vectorizer=None):
        if not self.g.has_node(agent_id):
            return 0.0
        edges = [(v, d) for _, v, d in self.g.out_edges(agent_id, data=True) if self.g.nodes[v].get('kind') == kind]
        if not required:
            return 1.0
        scores = []
        for req in required:
            best = 0.0
            for node, data in edges:
                name = self.g.nodes[node].get('name', '')
                sim = self.semantic_similarity(req, name, vectorizer)
                if sim >= semantic_threshold:
                    best = max(best, sim * float(data.get('weight', 1)) * self.freshness(data.get('updated_at', time.time())))
                for _, parent, parent_data in self.g.out_edges(node, data=True):
                    if parent_data.get('relation') == 'is_a':
                        inherited = self.semantic_similarity(req, self.g.nodes[parent].get('name', ''), vectorizer) * float(parent_data.get('weight', .8))
                        best = max(best, inherited)
            scores.append(best)
        return sum(scores) / len(scores)

    def stats(self):
        kinds = {}
        relations = {}
        for _, data in self.g.nodes(data=True):
            kinds[data.get('kind', 'unknown')] = kinds.get(data.get('kind', 'unknown'), 0) + 1
        for _, _, data in self.g.edges(data=True):
            rel = data.get('relation', 'unknown')
            relations[rel] = relations.get(rel, 0) + 1
        return {'nodes': self.g.number_of_nodes(), 'edges': self.g.number_of_edges(), 'kinds': kinds, 'relations': relations}
