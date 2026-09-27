import bpy, sys, numpy as np
args = sys.argv[sys.argv.index('--') + 1:]
out, cols, files = args[0], int(args[1]), args[2:]
ims = []
for f in files:
    im = bpy.data.images.load(f); w, h = im.size
    ims.append(np.array(im.pixels[:], np.float32).reshape(h, w, 4))
h, w = ims[0].shape[:2]; rows = (len(ims) + cols - 1) // cols
big = np.ones((rows * h, cols * w, 4), np.float32)
for i, a in enumerate(ims):
    r, c = divmod(i, cols); big[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = a
o = bpy.data.images.new('m', cols * w, rows * h); o.pixels.foreach_set(big.ravel()); o.filepath_raw = out; o.file_format = 'PNG'; o.save()
