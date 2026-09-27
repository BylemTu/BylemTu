# Helpers shared by the pipeline: DFF frames -> world transforms, material -> category mapping.
import numpy as np, dff
PAINT, GLASS, BLACK, METAL, HEAD, TAIL, PLATE = 1, 2, 3, 4, 5, 6, 7
r = dff.parse('bullet.dff')
F = r['frames']
def world(i):
    M = np.eye(4)
    while i >= 0:
        f = F[i]; L = np.eye(4); L[:3,:3] = np.array(f['rot']).reshape(3,3).T; L[:3,3] = f['pos']
        M = L @ M; i = f['parent']
    return M
skip = {'interior','interior__parts','interior_decals','interior_glass','steeringwheel_glow','steeringwheel_ok','enginemesh','suspension','wheel'}
def cat(atom, m):
    t = (m['tex'] or '').lower(); c = m['color'][:3]
    if atom == 'lights_glass0': return HEAD
    if atom in ('tail_lights0',): return TAIL
    if atom == 'boot_ok' and t in ('glass_d', 'light_d', 'shader_rear_0'): return TAIL
    if 'steklo' in t: return GLASS
    if t == 'remap_body' or c == (60,255,0): return PAINT
    if t == 'vehiclelights128': return HEAD if c in ((255,175,0),(0,255,200)) else TAIL
    if atom == 'lights' and (t.startswith('shader') or t == 'light_d'): return HEAD
    if atom == 'bump_rear_ok' and t == 'light_d': return TAIL
    if t == 'nomer': return PLATE
    if t in ('metal_d',): return METAL
    return BLACK
def components(tris, nv):
    p = np.arange(nv)
    def find(a):
        while p[a] != a:
            p[a] = p[p[a]]; a = p[a]
        return a
    for a, b, c in tris:
        ra, rb, rc = find(a), find(b), find(c)
        p[rb] = ra; p[find(rc)] = ra
    return np.array([find(i) for i in range(nv)])
