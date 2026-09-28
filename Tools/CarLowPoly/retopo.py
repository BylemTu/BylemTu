"""Panel-by-panel retopology of one car part.

1. Feature lines = open borders, material borders, creases sharper than `crease` deg (and the x=0 seam).
2. Feature lines are cut into chains between corners and simplified (Douglas-Peucker on the ORIGINAL
   vertices, max segment length `lmax`) - the same simplified chain is shared by both sides, so
   neighbouring regions stay welded.
3. The surface is split into regions along the feature lines; each region is flattened (LSCM),
   re-triangulated with a constrained quality Delaunay (Triangle, min angle 25-28 deg) and refined
   only where the new triangles deviate from the original surface by more than `tol`.
4. New points are mapped back onto the original surface (barycentric), so the shape is kept.
Returns vertices, faces (triangles), material per face, and the list of regions that fell back.
"""
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import triangle as tr
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
import decim


def _normals(V, T):
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    a = np.linalg.norm(n, axis=1)
    return n / np.maximum(a, 1e-15)[:, None], 0.5 * a


def _dp(P, tol):
    """Douglas-Peucker on a 3D polyline, returns kept indices"""
    keep = {0, len(P) - 1}
    st = [(0, len(P) - 1)]
    while st:
        a, b = st.pop()
        if b <= a + 1:
            continue
        seg = P[b] - P[a]; L = np.linalg.norm(seg)
        Q = P[a + 1:b] - P[a]
        if L < 1e-12:
            d = np.linalg.norm(Q, axis=1)
        else:
            d = np.linalg.norm(np.cross(Q, seg / L), axis=1)
        i = int(np.argmax(d))
        if d[i] > tol:
            m = a + 1 + i; keep.add(m); st += [(a, m), (m, b)]
    return sorted(keep)


def _lscm(V, T):
    """least-squares conformal map of a triangle patch (local vertex ids). returns uv or None"""
    nv = len(V)
    rows, cols, vals = [], [], []
    r = 0
    for (a, b, c) in T:
        p1, p2, p3 = V[a], V[b], V[c]
        e1 = p2 - p1; l1 = np.linalg.norm(e1)
        n = np.cross(e1, p3 - p1); ln = np.linalg.norm(n)
        if l1 < 1e-12 or ln < 1e-14:
            continue
        e1 /= l1; n /= ln; e2 = np.cross(n, e1)
        q = [np.array([0.0, 0.0]), np.array([l1, 0.0]), np.array([np.dot(p3 - p1, e1), np.dot(p3 - p1, e2)])]
        s = 1.0 / math.sqrt(ln)
        W = [q[2] - q[1], q[0] - q[2], q[1] - q[0]]
        for j, vid in enumerate((a, b, c)):
            wr, wi = W[j] * s
            rows += [r, r, r + 1, r + 1]; cols += [vid, nv + vid, vid, nv + vid]; vals += [wr, -wi, wi, wr]
        r += 2
    if r == 0:
        return None
    A = sp.csr_matrix((vals, (rows, cols)), shape=(r, 2 * nv))
    # pin the two vertices that are farthest apart
    i0 = int(np.argmax(np.linalg.norm(V - V.mean(0), axis=1)))
    i1 = int(np.argmax(np.linalg.norm(V - V[i0], axis=1)))
    if i0 == i1:
        return None
    d = np.linalg.norm(V[i1] - V[i0])
    pins = {i0: (0.0, 0.0), i1: (d, 0.0)}
    fixed = np.zeros(2 * nv, bool); x0 = np.zeros(2 * nv)
    for k, (u, v) in pins.items():
        fixed[k] = fixed[nv + k] = True; x0[k] = u; x0[nv + k] = v
    Af = A[:, ~fixed]; b = -A[:, fixed] @ x0[fixed]
    try:
        sol = spla.spsolve((Af.T @ Af).tocsc(), Af.T @ b)
    except Exception:
        return None
    x = x0.copy(); x[~fixed] = sol
    uv = np.stack([x[:nv], x[nv:]], 1)
    if not np.all(np.isfinite(uv)):
        return None
    return uv


def remesh(V, T, M, tol=0.01, lmax=0.4, crease=35.0, corner=45.0, seam_x=None, min_angle=22, fill=0.03, cut=None,
           hard_dot=0.6, hard_dev=0.012, hard_min_area=2e-5, bend_cos=-1.0, soft_crease=12.0, soft_min_len=0.15, outline_tol=0.003):
    V = np.asarray(V, float); T = np.asarray(T, int); M = np.asarray(M, int)
    nv = len(V)
    FN, FA = _normals(V, T)
    # ---------------- edges & features
    ef = {}
    for fi, t in enumerate(T):
        for k in range(3):
            a, b = int(t[k]), int(t[(k + 1) % 3])
            ef.setdefault((min(a, b), max(a, b)), []).append(fi)
    cc = math.cos(math.radians(crease))
    feat = set()
    sc_ = math.cos(math.radians(soft_crease))
    soft = []
    for e, fs in ef.items():
        if len(fs) != 2 or M[fs[0]] != M[fs[1]] or abs(np.dot(FN[fs[0]], FN[fs[1]])) < cc:
            feat.add(e)
        elif abs(np.dot(FN[fs[0]], FN[fs[1]])) < sc_:
            soft.append(e)
    # character lines: gentle creases (> soft_crease deg per edge) that form LONG connected lines
    # (hood creases, shoulder line, the edge above the tail lights) become feature lines too;
    # short scattered bends on curved surfaces are ignored
    par = {}
    def fnd(a):
        while par.setdefault(a, a) != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for a, b in soft:
        par[fnd(a)] = fnd(b)
    comp_len = {}
    for a, b in soft:
        r0 = fnd(a); comp_len[r0] = comp_len.get(r0, 0.0) + float(np.linalg.norm(V[a] - V[b]))
    for a, b in soft:
        if comp_len[fnd(a)] >= soft_min_len:
            feat.add((a, b))
    adj = [[] for _ in range(nv)]
    for a, b in feat:
        adj[a].append(b); adj[b].append(a)
    node = np.array([len(x) not in (0, 2) for x in adj])
    cco = math.cos(math.radians(180 - corner))
    for u in range(nv):
        if len(adj[u]) == 2:
            d1 = V[adj[u][0]] - V[u]; d2 = V[adj[u][1]] - V[u]
            if np.dot(d1, d2) / (np.linalg.norm(d1) * np.linalg.norm(d2) + 1e-15) > cco:
                node[u] = True
    if seam_x is not None:
        on = np.abs(V[:, 0] - seam_x) < 1e-5
        for u in range(nv):   # seam ends are corners
            if on[u] and len(adj[u]) == 2 and sum(on[w] for w in adj[u]) < 2:
                node[u] = True
    # ---------------- chains
    used = set(); chains = []
    def walk(start, nxt):
        ch = [start, nxt]; used.add((min(start, nxt), max(start, nxt)))
        prev, cur = start, nxt
        while not node[cur]:
            cand = [w for w in adj[cur] if w != prev and (min(cur, w), max(cur, w)) not in used]
            if not cand:
                break
            prev, cur = cur, cand[0]; used.add((min(prev, cur), max(prev, cur))); ch.append(cur)
            if cur == start:
                break
        return ch
    for u in range(nv):
        if node[u]:
            for w in adj[u]:
                if (min(u, w), max(u, w)) not in used:
                    chains.append(walk(u, w))
    for (a, b) in feat:           # closed loops without any corner
        if (a, b) not in used:
            node[a] = True
            chains.append(walk(a, b))
    keep = np.zeros(nv, bool)
    segs = []                     # simplified feature segments (original vertex ids)
    # adaptive tolerance: a chain may deviate at most `near` x the distance to the closest OTHER chain,
    # so the borders of narrow strips (roof rail, window trims, panel gaps) never cross after simplification
    from scipy.spatial import cKDTree
    cv = np.concatenate([np.array(ch) for ch in chains]) if chains else np.zeros(0, int)
    cid = np.concatenate([np.full(len(ch), i) for i, ch in enumerate(chains)]) if chains else np.zeros(0, int)
    kd = cKDTree(V[cv]) if len(cv) else None
    near = 0.4
    # chains that are only a cut where hidden faces were removed (zig-zag under an overlapping layer):
    # simplified generously and ignored as neighbours - they are not real edges of the car
    is_cut = np.array([cut is not None and all(cut[u] for u in ch) and
                       all(len(ef[(min(a, b), max(a, b))]) == 1 for a, b in zip(ch[:-1], ch[1:])) for ch in chains], bool)
    # open outlines of a part meet ANOTHER part (lens vs bonnet, fender vs arch liner ...): simplify them
    # tightly, otherwise a wedge-shaped gap opens between the two parts
    is_outline = np.array([all(len(ef[(min(a, b), max(a, b))]) == 1 for a, b in zip(ch[:-1], ch[1:])) for ch in chains], bool)
    def chain_tol(i, ch):
        if is_cut[i]:              # follow the (hidden) cut exactly - a chord across it may show up in the open
            return outline_tol
        if is_outline[i] and not (seam_x is not None and all(abs(V[u][0] - seam_x) < 1e-5 for u in ch)):
            return outline_tol
        ends = V[[ch[0], ch[-1]]]
        dmin = tol / near
        for u in ch[1:-1]:
            for d, j in zip(*kd.query(V[u], k=16)):
                if j >= len(cv) or cid[j] == i or cv[j] in (ch[0], ch[-1]) or is_cut[cid[j]]:
                    continue
                # ignore neighbours that are just around a shared corner
                if np.min(np.linalg.norm(ends - V[cv[j]], axis=1)) < 1.5 * d:
                    continue
                dmin = min(dmin, d); break
        return max(0.0015, min(tol, near * dmin))
    for ci, ch in enumerate(chains):
        P = V[ch]
        k = _dp(P, chain_tol(ci, ch))
        # split long segments along the chain
        out = [k[0]]
        for a, b in zip(k[:-1], k[1:]):
            L = np.linalg.norm(np.diff(P[a:b + 1], axis=0), axis=1).sum()
            n = int(L // lmax)
            if n > 0:
                cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P[a:b + 1], axis=0), axis=1))])
                for s in range(1, n + 1):
                    j = a + int(np.searchsorted(cum, L * s / (n + 1)))
                    if out[-1] < j < b:
                        out.append(j)
            out.append(b)
        ids = [ch[i] for i in out]
        keep[ids] = True
        segs += [(ids[i], ids[i + 1]) for i in range(len(ids) - 1) if ids[i] != ids[i + 1]]
    # ---------------- regions (flood fill across non-feature edges)
    reg = -np.ones(len(T), int); nreg = 0
    for f0 in range(len(T)):
        if reg[f0] >= 0:
            continue
        st = [f0]; reg[f0] = nreg
        while st:
            f = st.pop()
            t = T[f]
            for k in range(3):
                a, b = int(t[k]), int(t[(k + 1) % 3]); e = (min(a, b), max(a, b))
                if e in feat:
                    continue
                for g in ef[e]:
                    if reg[g] < 0:
                        reg[g] = nreg; st.append(g)
        nreg += 1
    # ---------------- remesh each region
    remesh.dbg = []
    outV = []; vid = {}           # original vertex id -> output id (shared across regions)
    outF = []; outM = []; fallback = []
    def ov(orig):
        if orig not in vid:
            vid[orig] = len(outV); outV.append(V[orig].copy())
        return vid[orig]
    seg_by_vert = {}
    for s in segs:
        seg_by_vert.setdefault(s[0], []).append(s); seg_by_vert.setdefault(s[1], []).append(s)
    for r in range(nreg):
        fids = np.where(reg == r)[0]
        RT = T[fids]
        rv = np.unique(RT); loc = {g: i for i, g in enumerate(rv)}
        LT = np.vectorize(loc.get)(RT)
        mat = int(np.bincount(M[fids]).argmax())
        # segments that belong to this region: a feature edge adjacent to one of its faces
        rset = set(fids.tolist())
        rsegs = []
        region_keep = set()
        for ch in chains:
            e = (min(ch[0], ch[1]), max(ch[0], ch[1]))
            if any(f in rset for f in ef[e]):
                region_keep.update(g for g in ch if keep[g])
        region_keep = sorted(region_keep)
        rk = set(region_keep)
        rsegs = sorted({s for g in region_keep for s in seg_by_vert.get(g, []) if s[0] in rk and s[1] in rk})
        def orig_faces():
            """fallback: careful decimation of the region; its border keeps only the simplified-chain vertices,
            so it still welds to the neighbouring regions"""
            RV = V[rv]; RM = M[fids]
            is_keep = keep[rv]
            bnd = set()
            for t in LT:
                for k in range(3):
                    a, b = rv[t[k]], rv[t[(k + 1) % 3]]
                    if (min(a, b), max(a, b)) in feat: bnd.update((t[k], t[(k + 1) % 3]))
            interior = np.ones(len(rv), bool); interior[list(bnd)] = False
            try:
                # pass 1: remove the non-kept border vertices (they slide along their border)
                V1, T1, M1, L1 = decim.decimate(RV, LT, RM, 0, mode='keep', crease=179.0, lock=is_keep | interior, corner_dot=1.1, quality=0.0)
                # map back which vertices are original ids
                def ident(Vx):
                    return [int(np.argmin(np.linalg.norm(RV - x, axis=1))) for x in Vx]
                id1 = ident(V1)
                lock2 = np.array([is_keep[i] or not interior[i] for i in id1])
                V2, T2, M2, L2 = decim.decimate(V1, T1, M1, max(3, int(lock2.sum() + (~lock2).sum() * 0.25)), mode='keep', crease=179.0, lock=lock2, corner_dot=1.1)
                id2 = ident(V2)
                for t, m in zip(T2, M2):
                    outF.append([ov(int(rv[id2[x]])) for x in t]); outM.append(int(m))
            except Exception:
                for t in RT:
                    outF.append([ov(int(x)) for x in t]); outM.append(mat)
        if len(fids) < 4 or len(region_keep) < 3:
            if len(fids) >= 4: fallback.append((r, 'fewkeep', len(fids), len(region_keep)))
            orig_faces(); continue
        uv = _lscm(V[rv], LT)
        if uv is None:
            fallback.append((r, 'lscm', len(fids))); orig_faces(); continue
        a = (uv[LT[:, 1]] - uv[LT[:, 0]]); b = (uv[LT[:, 2]] - uv[LT[:, 0]])
        sa = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
        if (sa < 0).sum() > 0.01 * len(sa) and (sa > 0).sum() > 0.01 * len(sa):
            fallback.append((r, 'flip', len(fids))); orig_faces(); continue
        if (sa < 0).sum() > (sa > 0).sum():
            uv[:, 1] *= -1; sa = -sa
        s3 = FA[fids].sum(); s2 = np.abs(sa).sum() * 0.5
        uv *= math.sqrt(s3 / max(s2, 1e-15))
        bvh = BVHTree.FromPolygons([(u, v, 0.0) for u, v in uv], LT.tolist(), all_triangles=True)
        def lift(p):
            """uv point -> (3d point, inside?)"""
            co, n, fi, dist = bvh.find_nearest(Vector((p[0], p[1], 0.0)))
            if fi is None:
                return None, False
            t = LT[fi]
            q = barycentric_transform(co, *[Vector((uv[k][0], uv[k][1], 0.0)) for k in t], *[Vector(V[rv[k]]) for k in t])
            return np.array(q), dist < 1e-6
        pv = np.array([uv[loc[g]] for g in region_keep])
        pidx = {g: i for i, g in enumerate(region_keep)}
        S = np.array([[pidx[s0], pidx[s1]] for s0, s1 in rsegs]) if rsegs else np.zeros((0, 2), int)
        if len(S) < 3:
            fallback.append((r, 'segs', len(fids))); orig_faces(); continue
        try:
            base = tr.triangulate({'vertices': pv, 'segments': S}, 'pYQn')
        except Exception:
            fallback.append((r, 'base', len(fids))); orig_faces(); continue
        # components of the base triangulation separated by the (simplified) feature segments;
        # a component is a hole when most of it lies outside the original region
        BT = base['triangles']; NB = base['neighbors']; BV = base['vertices']
        segset = {(min(a, b), max(a, b)) for a, b in base.get('segments', S)}
        comp = -np.ones(len(BT), int); nc = 0
        for t0 in range(len(BT)):
            if comp[t0] >= 0: continue
            st = [t0]; comp[t0] = nc
            while st:
                t = st.pop(); tri = BT[t]
                for k in range(3):
                    nb = NB[t][k]
                    if nb < 0 or comp[nb] >= 0: continue
                    a, b = tri[(k + 1) % 3], tri[(k + 2) % 3]      # edge opposite vertex k
                    if (min(a, b), max(a, b)) in segset: continue
                    comp[nb] = nc; st.append(nb)
            nc += 1
        holes = []
        for c in range(nc):
            ts = np.where(comp == c)[0]
            cen = BV[BT[ts]].mean(1)
            w = 0.5 * np.abs(np.cross(BV[BT[ts, 1]] - BV[BT[ts, 0]], BV[BT[ts, 2]] - BV[BT[ts, 0]]))
            ins = np.array([lift(q)[1] for q in cen])
            if (w * ins).sum() < 0.5 * w.sum():
                holes.append(cen[int(np.argmax(w))])
        inp = {'vertices': pv, 'segments': S}
        if holes:
            inp['holes'] = np.array(holes)
        # vertex budget of the region: its border/feature points + a share of the original interior density
        budget = len(region_keep) + max(4, int(fill * (len(rv) - len(region_keep))))
        cur = None
        for qa in (min_angle, 20, 15, 10, None):          # relax the angle quality until the region fits its budget
            try:
                c = tr.triangulate(inp, 'pYQ' + (f'q{qa}' if qa else ''))
            except Exception:
                continue
            if 'triangles' in c and len(c['triangles']):
                cur, qual = c, qa
                if len(c['vertices']) <= budget:
                    break
        if cur is None:
            fallback.append((r, 'tri', len(fids))); orig_faces(); continue
        init_n = len(cur.get('vertices', []))
        if 'triangles' not in cur or len(cur['triangles']) == 0:
            fallback.append((r, 'empty', len(fids), len(holes), len(base.get('triangles', [])))); orig_faces(); continue
        def face_normal_at(p):
            co, _, fi, _ = bvh.find_nearest(Vector((p[0], p[1], 0.0)))
            return FN[fids[fi]] if fi is not None else None
        W7 = ((1/3, 1/3, 1/3), (.5, .5, 0), (0, .5, .5), (.5, 0, .5), (2/3, 1/6, 1/6), (1/6, 2/3, 1/6), (1/6, 1/6, 2/3))
        def evaluate(TV, TT):
            """per triangle: (soft error?, hard error?) - hard = folded / tilted against the surface or far off it"""
            P3 = np.array([lift(p)[0] for p in TV])
            soft = np.zeros(len(TT), bool); hard = np.zeros(len(TT), bool)
            crease_under = np.zeros(len(TT), bool); evaluate.crease = crease_under
            for i, t in enumerate(TT):
                A3 = P3[t]
                n = np.cross(A3[1] - A3[0], A3[2] - A3[0]); ln = np.linalg.norm(n)
                if ln < 1e-14:
                    continue
                n /= ln
                err = 0.0
                for w in W7:
                    q, _ = lift(np.dot(w, TV[t]))
                    err = max(err, abs(np.dot(q - A3[0], n)))
                elen = max(np.linalg.norm(A3[k] - A3[(k + 1) % 3]) for k in range(3))
                soft[i] = err > tol or elen > lmax
                if 0.5 * ln > hard_min_area:
                    dmin = 1.0; ns = []
                    for w in W7:
                        fnn = face_normal_at(np.dot(w, TV[t]))
                        if fnn is not None:
                            dmin = min(dmin, float(np.dot(fnn, n))); ns.append(fnn)
                    # the surface under the triangle bends (character line / tight radius) -> follow it with smaller triangles
                    if len(ns) > 1:
                        ns = np.array(ns); spread = float(np.min(ns @ ns.mean(0) / max(np.linalg.norm(ns.mean(0)), 1e-9)))
                        crease_under[i] = spread < bend_cos
                    hard[i] = dmin < hard_dot or err > hard_dev
            return soft, hard
        ok = True
        for it in range(14):
            TV = cur['vertices']; TT = cur['triangles']
            soft, hard = evaluate(TV, TT)
            under = len(TV) < budget
            # hard errors are refined even over the budget; bends under a triangle up to 2.5x the budget
            ref = hard | (soft & under) | (evaluate.crease & (len(TV) < 2.5 * budget))
            if not ref.any():
                break
            a2 = 0.5 * np.abs(np.cross(TV[TT[:, 1]] - TV[TT[:, 0]], TV[TT[:, 2]] - TV[TT[:, 0]]))
            areas = np.where(ref, a2 * np.where(hard, 0.3, 0.4), 1e9)
            try:
                nxt = tr.triangulate({'vertices': TV, 'triangles': TT, 'segments': cur.get('segments', S),
                                      'triangle_max_area': areas}, 'rpYQa' + (f'q{qual}' if qual else ''))
            except Exception:
                ok = False; break
            if 'triangles' not in nxt:
                break
            if len(nxt['vertices']) > 4 * budget + 60:  # runaway guard
                break
            if not hard.any() and not evaluate.crease.any() and len(nxt['vertices']) > budget:
                break
            cur = nxt
        if ok:
            _, hard = evaluate(cur['vertices'], cur['triangles'])
            if hard.any():
                ok = False
        if not ok:
            fallback.append((r, 'refine', len(fids))); orig_faces(); continue
        TV = cur['vertices']; TT = cur['triangles']
        remesh.dbg.append((r, len(fids), len(rv), len(region_keep), len(TV) - len(region_keep), init_n - len(region_keep)))
        ids = []
        for i, p in enumerate(TV):
            if i < len(region_keep):
                ids.append(ov(region_keep[i]))
            else:
                q, _ = lift(p); ids.append(len(outV)); outV.append(q)
        for t in TT:
            f = [ids[k] for k in t]
            # keep the original winding: compare with the original surface normal at the centroid
            A3 = np.array([outV[k] for k in f]); n = np.cross(A3[1] - A3[0], A3[2] - A3[0])
            co, _, fi, _ = bvh.find_nearest(Vector((*TV[t].mean(0), 0.0)))
            if fi is not None and np.dot(n, FN[fids[fi]]) < 0:
                f = f[::-1]
            outF.append(f); outM.append(mat)
    remesh.stats = dict(keep=int(keep.sum()), regions=nreg, chains=len(chains))
    return np.array(outV), outF, np.array(outM), fallback
