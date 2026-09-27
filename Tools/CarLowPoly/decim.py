"""Careful edge-collapse decimator for one car part.

mode 'keep'  (version B): half-edge collapses only - every surviving vertex is an ORIGINAL vertex.
             Important vertices (corners of feature lines, seam at x=0, part outline corners) are locked,
             vertices on feature lines may only slide along that line, everything else is removed
             in order of least visual damage.
mode 'move'  (version A): full edge collapses with quadric-optimal vertex placement (vertices may move),
             same feature protection.
Features = open borders, material borders, creases sharper than `crease` degrees, the x=0 symmetry seam.
"""
import numpy as np, heapq, math

def tri_normal(a, b, c):
    n = np.cross(b - a, c - a); l = np.linalg.norm(n)
    return n / l if l > 1e-14 else n, 0.5 * l

def decimate(V, T, M, target, mode='keep', crease=38.0, seam_x=None, lock=None, quality=0.12, flip_dot=0.25, corner_dot=-0.6):
    V = np.array(V, float); T = [list(t) for t in T]; M = list(M)
    nv = len(V)
    alive_f = [True] * len(T)
    vf = [set() for _ in range(nv)]
    for fi, t in enumerate(T):
        for x in t: vf[x].add(fi)
    alive_v = np.array([len(s) > 0 for s in vf])
    def nbrs(u):
        s = set()
        for fi in vf[u]: s.update(T[fi])
        s.discard(u); return s
    def edge_faces(u, v):
        return [fi for fi in vf[u] if v in T[fi]]
    fn = {}; fa = {}
    for fi, t in enumerate(T):
        fn[fi], fa[fi] = tri_normal(V[t[0]], V[t[1]], V[t[2]])
    # ---- feature edges
    feat = set()
    edges = set()
    for t in T:
        for i in range(3):
            edges.add(frozenset((t[i], t[(i + 1) % 3])))
    cc = math.cos(math.radians(crease))
    for e in edges:
        u, v = tuple(e); ef = edge_faces(u, v)
        if len(ef) != 2 or M[ef[0]] != M[ef[1]] or np.dot(fn[ef[0]], fn[ef[1]]) < cc:
            feat.add(e)
    fdeg = np.zeros(nv, int)
    for e in feat:
        for x in e: fdeg[x] += 1
    locked = np.zeros(nv, bool)
    locked |= (fdeg == 1) | (fdeg >= 3)
    if lock is not None: locked |= lock
    # corners along feature chains: sharp turns stay
    fe_of = [[] for _ in range(nv)]
    for e in feat:
        u, v = tuple(e); fe_of[u].append(v); fe_of[v].append(u)
    for u in range(nv):
        if fdeg[u] == 2:
            a, b = fe_of[u]
            d1 = V[a] - V[u]; d2 = V[b] - V[u]
            if np.dot(d1, d2) / (np.linalg.norm(d1) * np.linalg.norm(d2) + 1e-12) > corner_dot: locked[u] = True  # turn > ~53 deg
    on_seam = np.zeros(nv, bool)
    if seam_x is not None:
        on_seam = np.abs(V[:, 0] - seam_x) < 1e-4
    # ---- quadrics
    Q = np.zeros((nv, 4, 4))
    for fi, t in enumerate(T):
        n = fn[fi]; d = -np.dot(n, V[t[0]]); p = np.append(n, d)
        K = np.outer(p, p) * fa[fi]
        for x in t: Q[x] += K
    for e in feat:        # keep feature lines in place: planes through the edge, perpendicular to the faces
        u, v = tuple(e); ed = V[v] - V[u]; L = np.linalg.norm(ed)
        if L < 1e-9: continue
        for fi in edge_faces(u, v):
            n = np.cross(ed, fn[fi]); nl = np.linalg.norm(n)
            if nl < 1e-12: continue
            n /= nl; p = np.append(n, -np.dot(n, V[u])); K = np.outer(p, p) * L * L * 4.0
            Q[u] += K; Q[v] += K
    ver = np.zeros(nv, int)
    def qcost(Qm, p):
        h = np.append(p, 1.0); return float(h @ Qm @ h)
    def check(u, v, pos_v, moved):
        """validate collapsing u into v placed at pos_v. moved: faces of v also move (full collapse)"""
        su = edge_faces(u, v)
        if not su: return None
        if len(nbrs(u) & nbrs(v)) != len(su): return None                   # link condition
        penalty = 0.0
        faces = [fi for fi in vf[u] if fi not in su]
        if moved: faces += [fi for fi in vf[v] if fi not in su]
        for fi in faces:
            t = [v if x == u else x for x in T[fi]]
            P = [pos_v if x == v else V[x] for x in t]
            n, a = tri_normal(*P)
            if a < 1e-10 or np.dot(n, fn[fi]) < flip_dot: return None
            l2 = sum(np.sum((P[i] - P[(i + 1) % 3]) ** 2) for i in range(3))
            q = 4 * math.sqrt(3) * a / l2
            if q < quality: penalty += (quality - q) * 1e-3
        return penalty
    def candidate(u, v):
        """cost + target position of collapsing edge (u -> v), or None"""
        if not (alive_v[u] and alive_v[v]) or locked[u]: return None
        e = frozenset((u, v)); isfeat = e in feat
        if fdeg[u] > 0 and not isfeat: return None             # feature vertices only slide along their line
        if on_seam[u] and not on_seam[v]: return None
        if mode == 'keep' or locked[v] or fdeg[v] > fdeg[u] or (on_seam[v] and not on_seam[u]):
            pos = V[v].copy(); moved = False; Qm = Q[u] + Q[v]
            cost = qcost(Q[u], pos)
        else:
            Qm = Q[u] + Q[v]; moved = True
            best = None
            cands = [V[u] + (V[v] - V[u]) * t for t in (0.0, 0.5, 1.0)]
            if fdeg[u] == 0 and fdeg[v] == 0 and not on_seam[u]:
                A = Qm.copy(); A[3] = [0, 0, 0, 1]
                try:
                    if abs(np.linalg.det(A)) > 1e-12:
                        p = np.linalg.solve(A, [0, 0, 0, 1])[:3]
                        if np.linalg.norm(p - (V[u] + V[v]) / 2) < np.linalg.norm(V[u] - V[v]) * 2: cands.append(p)
                except np.linalg.LinAlgError: pass
            for p in cands:
                c = qcost(Qm, p)
                if best is None or c < best[0]: best = (c, p)
            cost, pos = best
            if on_seam[u]: pos[0] = seam_x
        pen = check(u, v, pos, moved)
        if pen is None: return None
        return cost + pen, pos
    heap = []
    def push_vertex(u):
        for v in nbrs(u):
            for a, b in ((u, v), (v, u)):
                c = candidate(a, b)
                if c: heapq.heappush(heap, (c[0], a, b, ver[a], ver[b]))
    for u in range(nv):
        if alive_v[u]:
            for v in nbrs(u):
                c = candidate(u, v)
                if c: heapq.heappush(heap, (c[0], u, v, ver[u], ver[v]))
    count = int(alive_v.sum())
    while count > target and heap:
        c, u, v, vu, vv = heapq.heappop(heap)
        if not (alive_v[u] and alive_v[v]) or ver[u] != vu or ver[v] != vv: continue
        r = candidate(u, v)
        if r is None: continue
        cost, pos = r
        # collapse u -> v
        su = edge_faces(u, v)
        for fi in su:
            alive_f[fi] = False
            for x in T[fi]: vf[x].discard(fi)
        for fi in list(vf[u]):
            T[fi] = [v if x == u else x for x in T[fi]]; vf[v].add(fi)
        vf[u] = set()
        V[v] = pos
        for fi in vf[v]:
            fn[fi], fa[fi] = tri_normal(*[V[x] for x in T[fi]])
        for w in fe_of[u]:
            if w == v: continue
            feat.discard(frozenset((u, w))); feat.add(frozenset((v, w)))
            fe_of[w] = list(dict.fromkeys(v if x == u else x for x in fe_of[w]))
        fe_of[v] = [x for x in fe_of[v] if x != u] + [w for w in fe_of[u] if w != v and w not in fe_of[v]]
        fe_of[v] = list(dict.fromkeys(fe_of[v]))
        feat.discard(frozenset((u, v)))
        fdeg[v] = len(fe_of[v]); fe_of[u] = []; fdeg[u] = 0
        Q[v] += Q[u]; alive_v[u] = False; count -= 1
        touched = nbrs(v) | {v}
        for w in touched: ver[w] += 1
        for w in touched: push_vertex(w)
    # compact
    keep_f = [i for i in range(len(T)) if alive_f[i]]
    used = sorted({x for i in keep_f for x in T[i]})
    remap = {o: n for n, o in enumerate(used)}
    return V[used], np.array([[remap[x] for x in T[i]] for i in keep_f]), np.array([M[i] for i in keep_f]), locked[used]
