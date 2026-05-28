# ============================================================
# Export rotating tier trolley mesh + URDF for Isaac Sim
# Run after fixed_model_rotating_trolley.py in Blender 4.x.
#
# Example:
# blender --background \
#   --python fixed_model_rotating_trolley.py \
#   --python export_rotating_trolley_urdf.py \
#   -- --out_dir /tmp/rotating_trolley_urdf
# ============================================================

import bpy
import math
import json
import argparse
import sys
from pathlib import Path
from mathutils import Matrix, Vector, Euler

# ---------------------------
# CLI / output directory
# ---------------------------
def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", type=str, default=None,
                        help="Output directory. If omitted, writes ./rotating_trolley_urdf")
    return parser.parse_args(argv)

args = parse_args()
if args.out_dir:
    out_dir = Path(args.out_dir).expanduser().resolve()
else:
    out_dir = (Path.cwd() / "rotating_trolley_urdf").resolve()

# Avoid accidentally writing to root-owned paths.
if str(out_dir) == "/" or str(out_dir).startswith("/rotating_trolley_urdf"):
    out_dir = (Path.home() / "rotating_trolley_urdf").resolve()

mesh_dir = out_dir / "meshes"
mesh_dir.mkdir(parents=True, exist_ok=True)

# ---------------------------
# Scene constants from model
# ---------------------------
TRAY_Z_BOTTOMS = [0.14, 0.375, 0.61, 0.845, 1.08]
TRAY_YAWS = [
    math.radians(8),
    math.radians(-62),
    math.radians(54),
    math.radians(-34),
    math.radians(18),
]
TRAY_L = 1.12
TRAY_W = 0.64
TRAY_OFFSET_X = 0.23
TRAY_OFFSET_Y = 0.0
TRAY_H = 0.175
BASE_YAW = TRAY_YAWS[0]

CORNER_LOCAL_POSITIONS = [
    (TRAY_OFFSET_X - TRAY_L / 2.0 + 0.13, TRAY_OFFSET_Y - TRAY_W / 2.0 + 0.11),
    (TRAY_OFFSET_X + TRAY_L / 2.0 - 0.13, TRAY_OFFSET_Y - TRAY_W / 2.0 + 0.11),
    (TRAY_OFFSET_X + TRAY_L / 2.0 - 0.13, TRAY_OFFSET_Y + TRAY_W / 2.0 - 0.11),
    (TRAY_OFFSET_X - TRAY_L / 2.0 + 0.13, TRAY_OFFSET_Y + TRAY_W / 2.0 - 0.11),
]
WHEEL_Z = 0.022
CASTER_STEM_ABOVE_WHEEL = 0.083

# ---------------------------
# Transform helpers
# ---------------------------
def tf_xyz_rpy(xyz, rpy=(0.0, 0.0, 0.0)):
    return Matrix.Translation(Vector(xyz)) @ Euler(rpy, 'XYZ').to_matrix().to_4x4()

def rpy_string(rpy):
    return f"{rpy[0]:.9g} {rpy[1]:.9g} {rpy[2]:.9g}"

def xyz_string(xyz):
    return f"{xyz[0]:.9g} {xyz[1]:.9g} {xyz[2]:.9g}"

def obj_required(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise RuntimeError(f"Required object not found: {name}. Run the fixed modeling script first.")
    return obj

def mat_color(obj):
    if obj.data and obj.data.materials and obj.data.materials[0]:
        c = obj.data.materials[0].diffuse_color
        return tuple(float(v) for v in c)
    return (0.65, 0.65, 0.65, 1.0)

# ---------------------------
# Link frames and object groups
# Link frame convention:
# - Each tray link frame lies on the central pole at its tray bottom Z, with rest yaw in rpy.
# - Mesh vertices are exported into their link frame to avoid double offsets.
# ---------------------------
links = []

def add_link(name, objects, frame_matrix, inertial_mass=0.2):
    links.append({
        "name": name,
        "objects": objects,
        "frame_matrix": frame_matrix,
        "mesh": f"meshes/{name}.obj",
        "mass": inertial_mass,
    })

add_link(
    "base_link",
    [
        "central_pole_SOLID_white_vertical_axle",
    ],
    tf_xyz_rpy((0.0, 0.0, 0.0)),
    inertial_mass=1.0,
)

for i, (zb, yaw) in enumerate(zip(TRAY_Z_BOTTOMS, TRAY_YAWS), start=1):
    add_link(
        f"tray_{i:02d}_link",
        [
            f"tray_{i:02d}_body_HOLLOW_CONTAINER",
            f"tray_{i:02d}_panel_SOLID_raised_floor_insert",
            f"tray_{i:02d}_rib_A_SOLID_narrow_raised_detail",
            f"tray_{i:02d}_rib_B_SOLID_narrow_raised_detail",
        ],
        tf_xyz_rpy((0.0, 0.0, zb), (0.0, 0.0, yaw)),
        inertial_mass=0.35,
    )

# Artificial green inter-level swivel sleeve meshes were removed from the model.
# Therefore no sleeve links are exported.

# Caster links are children of tray_01. Their link frames are defined in tray_01 local coordinates.
T_tray1 = tf_xyz_rpy((0.0, 0.0, TRAY_Z_BOTTOMS[0]), (0.0, 0.0, BASE_YAW))
for i, (lx, ly) in enumerate(CORNER_LOCAL_POSITIONS, start=1):
    stem_local = (lx, ly, WHEEL_Z + CASTER_STEM_ABOVE_WHEEL - TRAY_Z_BOTTOMS[0])
    wheel_local = (lx, ly, WHEEL_Z - TRAY_Z_BOTTOMS[0])
    T_stem = T_tray1 @ tf_xyz_rpy(stem_local)
    T_wheel = T_tray1 @ tf_xyz_rpy(wheel_local)
    add_link(
        f"caster_{i:02d}_bracket_link",
        [f"caster_{i:02d}_bracket_STRUCTURAL_ASSEMBLY_fork_and_stem"],
        T_stem,
        inertial_mass=0.04,
    )
    add_link(
        f"caster_{i:02d}_wheel_link",
        [f"caster_{i:02d}_wheel_SOLID_dark_rubber_cylinder"],
        T_wheel,
        inertial_mass=0.03,
    )

# ---------------------------
# OBJ + MTL export
# ---------------------------
def sanitize_material_name(name):
    return ''.join(ch if ch.isalnum() or ch in ['_', '-'] else '_' for ch in name)

def export_link_obj(link):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_path = mesh_dir / f"{link['name']}.obj"
    mtl_path = mesh_dir / f"{link['name']}.mtl"
    inv_link = link["frame_matrix"].inverted()

    verts = []
    faces = []
    face_materials = []
    materials = {}

    for obj_name in link["objects"]:
        obj = obj_required(obj_name)
        if obj.type != 'MESH':
            continue
        mat_name = sanitize_material_name(obj.data.materials[0].name if obj.data.materials else obj_name + "_mat")
        materials[mat_name] = mat_color(obj)
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        try:
            base = len(verts)
            for v in mesh.vertices:
                world_v = obj_eval.matrix_world @ v.co
                link_v = inv_link @ world_v
                verts.append((link_v.x, link_v.y, link_v.z))
            for poly in mesh.polygons:
                faces.append([base + idx + 1 for idx in poly.vertices])
                face_materials.append(mat_name)
        finally:
            obj_eval.to_mesh_clear()

    with mtl_path.open('w') as f:
        for mat_name, color in materials.items():
            r, g, b, a = color
            f.write(f"newmtl {mat_name}\n")
            f.write(f"Kd {r:.6f} {g:.6f} {b:.6f}\n")
            f.write(f"Ka {r:.6f} {g:.6f} {b:.6f}\n")
            f.write(f"Ks 0.100000 0.100000 0.100000\n")
            f.write(f"d {a:.6f}\n")
            f.write("Ns 30.0\n\n")

    with obj_path.open('w') as f:
        f.write(f"mtllib {mtl_path.name}\n")
        f.write(f"o {link['name']}\n")
        for x, y, z in verts:
            f.write(f"v {x:.9g} {y:.9g} {z:.9g}\n")
        current_mat = None
        for face, mat_name in zip(faces, face_materials):
            if mat_name != current_mat:
                f.write(f"usemtl {mat_name}\n")
                current_mat = mat_name
            f.write("f " + " ".join(str(i) for i in face) + "\n")
    return obj_path

for link in links:
    export_link_obj(link)

# ---------------------------
# URDF writing
# ---------------------------
joints = []

def add_joint(name, joint_type, parent, child, xyz, rpy, axis):
    joints.append({
        "name": name,
        "type": joint_type,
        "parent": parent,
        "child": child,
        "xyz": xyz,
        "rpy": rpy,
        "axis": axis,
    })

for i, (zb, yaw) in enumerate(zip(TRAY_Z_BOTTOMS, TRAY_YAWS), start=1):
    add_joint(
        f"tray_{i:02d}_yaw_joint",
        "continuous",
        "base_link",
        f"tray_{i:02d}_link",
        (0.0, 0.0, zb),
        (0.0, 0.0, yaw),
        (0.0, 0.0, 1.0),
    )

# No sleeve spin joints: the removed sleeves are only artificial visual spacers.

for i, (lx, ly) in enumerate(CORNER_LOCAL_POSITIONS, start=1):
    stem_local = (lx, ly, WHEEL_Z + CASTER_STEM_ABOVE_WHEEL - TRAY_Z_BOTTOMS[0])
    add_joint(
        f"caster_{i:02d}_swivel_joint",
        "continuous",
        "tray_01_link",
        f"caster_{i:02d}_bracket_link",
        stem_local,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    add_joint(
        f"caster_{i:02d}_wheel_roll_joint",
        "continuous",
        f"caster_{i:02d}_bracket_link",
        f"caster_{i:02d}_wheel_link",
        (0.0, 0.0, -CASTER_STEM_ABOVE_WHEEL),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    )

urdf_path = out_dir / "rotating_tier_trolley.urdf"
with urdf_path.open('w') as f:
    f.write('<?xml version="1.0"?>\n')
    f.write('<robot name="rotating_tier_trolley">\n')
    f.write('  <!-- Generated for Isaac Sim. Units: meters. Coordinate system: Z-up, right-handed. -->\n')
    for link in links:
        name = link['name']
        mesh = link['mesh']
        mass = link['mass']
        f.write(f'  <link name="{name}">\n')
        f.write('    <inertial>\n')
        f.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
        f.write(f'      <mass value="{mass:.6g}"/>\n')
        f.write('      <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>\n')
        f.write('    </inertial>\n')
        f.write('    <visual>\n')
        f.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
        f.write(f'      <geometry><mesh filename="{mesh}" scale="1 1 1"/></geometry>\n')
        f.write('    </visual>\n')
        f.write('    <collision>\n')
        f.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
        f.write(f'      <geometry><mesh filename="{mesh}" scale="1 1 1"/></geometry>\n')
        f.write('    </collision>\n')
        f.write('  </link>\n')
    for joint in joints:
        f.write(f'  <joint name="{joint["name"]}" type="{joint["type"]}">\n')
        f.write(f'    <parent link="{joint["parent"]}"/>\n')
        f.write(f'    <child link="{joint["child"]}"/>\n')
        f.write(f'    <origin xyz="{xyz_string(joint["xyz"])}" rpy="{rpy_string(joint["rpy"])}"/>\n')
        f.write(f'    <axis xyz="{xyz_string(joint["axis"])}"/>\n')
        f.write('    <dynamics damping="0.05" friction="0.0"/>\n')
        f.write('  </joint>\n')
    f.write('</robot>\n')

# ---------------------------
# JSON metadata
# ---------------------------
info = {
    "name": "rotating_tier_trolley",
    "units": "meter",
    "coordinate_system": {"up_axis": "Z", "handedness": "right-handed"},
    "fixes_applied": [
        "Rotated/swapped each tray floor insert and rib footprint so the baffle runs transversely across the tray instead of lengthwise.",
        "Raised each transverse baffle to align with the tray side-wall/rim height.",
        "Shifted each baffle to one side of the tray interior rather than the center.",
        "Lowered caster wheel/bracket placement to avoid penetrating the bottom tray.",
        "Removed artificial green inter-level swivel sleeve meshes and their URDF links/joints."
    ],
    "links": [
        {
            "name": link["name"],
            "mesh": link["mesh"],
            "source_objects": link["objects"],
        }
        for link in links
    ],
    "joints": joints,
}
json_path = out_dir / "model_and_joint_info.json"
json_path.write_text(json.dumps(info, indent=2))

print(f"[OK] Wrote URDF: {urdf_path}")
print(f"[OK] Wrote meshes under: {mesh_dir}")
print(f"[OK] Wrote metadata: {json_path}")