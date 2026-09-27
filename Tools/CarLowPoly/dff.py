import struct, sys, json
import numpy as np

def chunks(data, off, end):
    while off + 12 <= end:
        t, s, v = struct.unpack_from('<III', data, off)
        yield t, off + 12, s
        off += 12 + s

def parse(path):
    d = open(path, 'rb').read()
    out = {'frames': [], 'geoms': [], 'atomics': []}
    for t, o, s in chunks(d, 0, len(d)):
        if t != 0x10: continue
        for t2, o2, s2 in chunks(d, o, o + s):
            if t2 == 0x0E:  # frame list
                sub = list(chunks(d, o2, o2 + s2))
                st = sub[0]
                n = struct.unpack_from('<I', d, st[1])[0]
                p = st[1] + 4
                for i in range(n):
                    rot = struct.unpack_from('<9f', d, p); pos = struct.unpack_from('<3f', d, p + 36)
                    parent, flags = struct.unpack_from('<iI', d, p + 48)
                    out['frames'].append({'rot': rot, 'pos': pos, 'parent': parent, 'name': ''})
                    p += 56
                for i, (t3, o3, s3) in enumerate(sub[1:]):
                    for t4, o4, s4 in chunks(d, o3, o3 + s3):
                        if t4 == 0x253F2FE:
                            out['frames'][i]['name'] = d[o4:o4 + s4].split(b'\0')[0].decode('latin1')
            elif t2 == 0x1A:
                for t3, o3, s3 in list(chunks(d, o2, o2 + s2))[1:]:
                    if t3 == 0x0F:
                        out['geoms'].append(parse_geom(d, o3, s3))
            elif t2 == 0x14:
                st = next(chunks(d, o2, o2 + s2))
                fi, gi, fl, _ = struct.unpack_from('<4I', d, st[1])
                out['atomics'].append({'frame': fi, 'geom': gi, 'flags': fl})
    return out

def parse_geom(d, o, s):
    sub = list(chunks(d, o, o + s))
    t, p, ss = sub[0]
    fmt, ntri, nv, nmt = struct.unpack_from('<4I', d, p); p += 16
    nuv = (fmt >> 16) & 0xFF
    if nuv == 0: nuv = 2 if fmt & 0x80 else (1 if fmt & 0x04 else 0)
    g = {'fmt': fmt}
    if fmt & 0x08:
        g['col'] = np.frombuffer(d, np.uint8, nv * 4, p).reshape(-1, 4); p += nv * 4
    uvs = []
    for i in range(nuv):
        uvs.append(np.frombuffer(d, np.float32, nv * 2, p).reshape(-1, 2)); p += nv * 8
    g['uv'] = uvs[0] if uvs else None
    tri = np.frombuffer(d, np.uint16, ntri * 4, p).reshape(-1, 4); p += ntri * 8
    g['tris'] = tri[:, [1, 0, 3]].astype(np.int64); g['mat'] = tri[:, 2].astype(np.int64)
    p += 16
    hv, hn = struct.unpack_from('<II', d, p); p += 8
    g['v'] = np.frombuffer(d, np.float32, nv * 3, p).reshape(-1, 3).copy() if hv else None; p += nv * 12 * hv
    # materials
    mats = []
    for t, o2, s2 in sub[1:]:
        if t == 0x08:
            for t3, o3, s3 in list(chunks(d, o2, o2 + s2))[1:]:
                if t3 == 0x07:
                    m = {'tex': None}
                    msub = list(chunks(d, o3, o3 + s3))
                    m['color'] = tuple(d[msub[0][1] + 4: msub[0][1] + 8])
                    for t4, o4, s4 in msub[1:]:
                        if t4 == 0x06:
                            tsub = list(chunks(d, o4, o4 + s4))
                            m['tex'] = d[tsub[1][1]:tsub[1][1] + tsub[1][2]].split(b'\0')[0].decode('latin1')
                    mats.append(m)
    g['mats'] = mats
    return g

if __name__ == '__main__':
    r = parse(sys.argv[1])
    for i, f in enumerate(r['frames']):
        print(i, f['name'], f['parent'], [round(x, 3) for x in f['pos']])
    for a in r['atomics']:
        g = r['geoms'][a['geom']]
        v = g['v']
        print('ATOM', r['frames'][a['frame']]['name'], 'nv', len(v), 'ntri', len(g['tris']), 'min', v.min(0).round(2), 'max', v.max(0).round(2), 'mats', len(g['mats']))
