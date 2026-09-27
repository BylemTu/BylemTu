"""BMW E36 sedan (1990-1998, non-M) reference dimensions and profile curves.

Car frame used throughout the generator:
    x  lateral, +x = car's left side (driver side on LHD)
    s  longitudinal, +s = forward
    z  up, z = 0 is the ground plane
Origin: ground level, midway between the axles.
Converted to Blender as (x, -s, z) so the car faces -Y (glTF +Z forward).

Numbers come from the factory spec (length 4433, width 1698, height 1393,
wheelbase 2700, track 1418/1431) and were traced from the side/plan blueprint.
"""
from .curves import Curve

LENGTH = 4.433
WIDTH = 1.698
HEIGHT = 1.393
WHEELBASE = 2.700
S_FA = WHEELBASE / 2          # front axle
S_RA = -WHEELBASE / 2         # rear axle
TRACK_F = 1.418
TRACK_R = 1.431
S_FRONT = 2.101               # front bumper tip  (overhang 763 mm)
S_REAR = S_FRONT - LENGTH     # rear bumper tip   (overhang 970 mm)

# 185/65 R15 tyre on 6.5Jx15 steel wheel
TYRE_W = 0.185
RIM_R = 15 * 0.0254 / 2
TYRE_R = RIM_R + 0.65 * TYRE_W
WHEEL_Z = TYRE_R - 0.012      # slightly loaded tyre
ARCH_R = 0.365
ARCH_DZ = 0.069      # front; rear arch sits a bit higher (factory rake)
ARCH_DZ_R = 0.098


def arch_z(front):
    return WHEEL_Z + (ARCH_DZ if front else ARCH_DZ_R)

HALF_W = WIDTH / 2

# ---------------------------------------------------------------- lower body
# plan-view half width at the widest waterline (rub strip height)
W_PLAN = Curve([(S_REAR, 0.80), (-2.1, 0.815), (-1.9, 0.826), (-1.7, 0.836), (-1.5, 0.845), (0.0, HALF_W), (1.3, 0.849), (1.5, 0.845), (1.7, 0.83), (S_FRONT, 0.80)])
# underside of the body (sill / bumper bottoms)
Z_BOTTOM = Curve([(S_REAR, 0.32), (-2.1, 0.29), (-1.75, 0.225), (-1.2, 0.195), (0.0, 0.19), (1.2, 0.195), (1.75, 0.205), (1.95, 0.215), (S_FRONT, 0.235)])
# side character line (runs through the door handles, top of lamps)
Z_CREASE = Curve([(S_REAR, 0.84), (-1.6, 0.80), (0.0, 0.745), (1.5, 0.64), (S_FRONT, 0.58)])
# top edge of the body side: hood edge / belt line / trunk edge
Z_DECK = Curve([(S_REAR, 0.99), (-2.1, 1.0), (-1.9, 1.01), (-1.7, 0.967), (-1.5, 0.961), (-1.2, 0.955),
                (-0.6, 0.942), (0.0, 0.929), (0.6, 0.915), (0.85, 0.89), (1.0, 0.85), (1.2, 0.82),
                (1.4, 0.79), (1.6, 0.747), (1.8, 0.69), (1.9, 0.64), (S_FRONT, 0.60)])
# centre crown of hood / trunk lid over the deck edge
Z_CROWN = Curve([(S_REAR, 0.06), (-2.0, 0.085), (-1.86, 0.085), (-1.74, 0.0), (0.72, 0.0),
                 (0.86, 0.03), (1.0, 0.07), (1.5, 0.065), (1.9, 0.06), (S_FRONT, 0.05)])
Z_RUB = 0.57                 # side rub strip / widest waterline

# end faces (centre line) : s of the face as a function of height z
S_FRONT_Z = Curve([(0.20, S_FRONT - 0.06), (0.28, S_FRONT), (0.40, S_FRONT - 0.005),
                   (0.45, S_FRONT - 0.035), (0.47, S_FRONT - 0.04), (0.60, S_FRONT - 0.06),
                   (0.64, S_FRONT - 0.09), (0.67, S_FRONT - 0.14)])
S_REAR_Z = Curve([(0.30, S_REAR + 0.12), (0.40, S_REAR + 0.08), (0.50, S_REAR + 0.025),
                  (0.60, S_REAR + 0.012), (0.64, S_REAR + 0.05), (0.66, S_REAR + 0.10),
                  (0.90, S_REAR + 0.108), (0.97, S_REAR + 0.10), (1.01, S_REAR + 0.09),
                  (1.035, S_REAR + 0.12)])
FRONT_BULGE, FRONT_RHO, FRONT_PHI = 0.13, 0.26, 72.0   # plan-view nose shape
REAR_BULGE, REAR_RHO, REAR_PHI = 0.05, 0.15, 80.0

# ---------------------------------------------------------------- greenhouse
GH_S0, GH_S1 = -1.74, 0.66      # greenhouse ends (buried in the deck)
S_COWL = 0.62                  # windshield base, centre line
S_ROOF_F = 0.12                 # windshield top
S_ROOF_R = -1.15                # rear window top
S_RW = -1.70                    # rear window base
Z_TOP = Curve([(-1.74, 1.08), (-1.70, 1.105), (-1.55, 1.17), (-1.40, 1.24), (-1.26, 1.30),
               (-1.12, 1.345), (-0.90, 1.378), (-0.50, 1.393), (-0.10, 1.386), (0.06, 1.37), (0.14, 1.345),
               (0.30, 1.215), (0.45, 1.09), (0.62, 0.945), (0.66, 0.925)])
ROOF_CROWN = Curve([(-1.74, 0.02), (-1.15, 0.05), (0.12, 0.05), (0.66, 0.03)])
X_ROOF = Curve([(-1.74, 0.64), (-1.70, 0.635), (-1.15, 0.585), (-0.5, 0.60), (0.12, 0.59), (0.62, 0.70), (0.66, 0.705)])
X_BELT = Curve([(-1.74, 0.70), (-1.62, 0.735), (-1.4, 0.765), (-0.5, 0.772), (0.4, 0.765), (0.62, 0.745), (0.66, 0.74)])
WRAP_F = Curve([(0.02, 0.0), (0.14, 0.08), (0.66, 0.10)])   # windshield plan wrap
WRAP_R = Curve([(-1.74, 0.10), (-1.17, 0.09), (-1.02, 0.0)])  # rear window plan wrap
