# ============================================================
# Step 1: Part Segmentation / Spatial Reasoning Analysis
# ============================================================
# Object: A compact olive-green rotating tier storage trolley/cart.
#
# Global structure:
# - A vertical white cylindrical axle/pole runs through the stack near an off-center
#   pivot point.
# - Five shallow rectangular trays are mounted at different heights and rotated
#   around the shared pole, creating a staggered spiral/tower silhouette.
# - Each tray is a shallow open-top rectangular container with non-zero wall and
#   bottom thickness. The trays have softened/rounded edges and a glossy olive
#   plastic appearance.
# - Inside each tray is a transverse raised rectangular floor/baffle panel plus two narrow
#   raised ribs, visible in the reference as horizontal inset details.
# - The central white pole is kept visually clean; artificial green inter-level
#   swivel sleeve/spacer collars have been removed because they are not visible
#   in the reference and are not required for the tray yaw joints.
# - Four small dark caster wheels sit under the lowest tray, near its corners.
#   Each caster has a dark wheel and a small fork/bracket assembly.
#
# Part list:
# 1. central_pole
#    - Category: SOLID
#    - White vertical cylinder, common rotational axis for the trays.
#
# 2. tray_01_body ... tray_05_body
#    - Category: HOLLOW_CONTAINER
#    - Open-top shallow rectangular bins with wall thickness and bottom thickness.
#    - Local origin placed on the pole axis / pivot location.
#    - Each tray is rotated around +Z by a different yaw angle.
#
# 3. tray_01_panel ... tray_05_panel
#    - Category: SOLID
#    - Thin raised rectangular inset panels inside trays.
#
# 4. tray_01_rib_A/B ... tray_05_rib_A/B
#    - Category: SOLID
#    - Narrow raised ribs on the tray floor panels.
#
# 5. caster_01_wheel ... caster_04_wheel
#    - Category: SOLID
#    - Dark horizontal cylinders under the base tray.
#
# 6. caster_01_bracket ... caster_04_bracket
#    - Category: STRUCTURAL_ASSEMBLY
#    - Small fork/yoke made from joined solid plates plus a vertical stem.
#
# Spatial relationships:
# - World up is +Z, forward is -Y.
# - The pole is at world XY = (0, 0).
# - Tray local origins coincide with the pole axis; the rectangular tray bodies are
#   offset from that origin so the pole passes through an off-center area, matching
#   the reference.
# - Trays are vertically stacked with slight gaps and alternating yaw rotations.
# - Casters are positioned beneath the lowest tray using the lowest tray's yaw and
#   local corner coordinates.
# ============================================================

import bpy
import math
from mathutils import Vector, Matrix

# ------------------------------------------------------------
# Scene cleanup
# ------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ------------------------------------------------------------
# Render / scene settings
# ------------------------------------------------------------
scene = bpy.context.scene

# EEVEE / EEVEE Next compatibility
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
except TypeError:
    scene.render.engine = 'BLENDER_EEVEE'

if hasattr(scene, "eevee"):
    eevee = scene.eevee
    if hasattr(eevee, "use_gtao"):
        eevee.use_gtao = True
    if hasattr(eevee, "gtao_distance"):
        eevee.gtao_distance = 3.0
    if hasattr(eevee, "gtao_factor"):
        eevee.gtao_factor = 1.4
    if hasattr(eevee, "use_bloom"):
        eevee.use_bloom = False
    if hasattr(eevee, "use_ssr"):
        eevee.use_ssr = False

scene.render.film_transparent = True
scene.render.resolution_x = 720
scene.render.resolution_y = 720
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '8'
scene.render.filepath = "Res1_3D.png"

# World background, no environment objects/lights are created.
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes.clear()
bg = world.node_tree.nodes.new(type="ShaderNodeBackground")
bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
bg.inputs["Strength"].default_value = 0.8
wo = world.node_tree.nodes.new(type="ShaderNodeOutputWorld")
world.node_tree.links.new(bg.outputs["Background"], wo.inputs["Surface"])

# Color management for clean transparent PNG rendering
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0

# ------------------------------------------------------------
# Materials
# ------------------------------------------------------------
def make_principled_material(name, base_color, roughness=0.45, metallic=0.0, emission_strength=0.18):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()

    bsdf = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
    out = mat.node_tree.nodes.new(type="ShaderNodeOutputMaterial")

    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = base_color
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = base_color[3]

    # Small emission makes the model visible without adding any light objects.
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = base_color
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = emission_strength

    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat.diffuse_color = base_color
    return mat

olive_mat = make_principled_material(
    "glossy_olive_green_plastic",
    (0.30, 0.42, 0.03, 1.0),
    roughness=0.34,
    metallic=0.0,
    emission_strength=0.20
)
olive_dark_mat = make_principled_material(
    "darker_olive_inside_edges",
    (0.20, 0.29, 0.02, 1.0),
    roughness=0.45,
    metallic=0.0,
    emission_strength=0.15
)
white_mat = make_principled_material(
    "matte_white_plastic_pole",
    (0.82, 0.84, 0.82, 1.0),
    roughness=0.38,
    metallic=0.0,
    emission_strength=0.28
)
wheel_mat = make_principled_material(
    "dark_rubber_wheels",
    (0.025, 0.025, 0.027, 1.0),
    roughness=0.58,
    metallic=0.0,
    emission_strength=0.10
)
bracket_mat = make_principled_material(
    "charcoal_caster_brackets",
    (0.07, 0.07, 0.075, 1.0),
    roughness=0.48,
    metallic=0.0,
    emission_strength=0.11
)

# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------
def normalize_object(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

def add_bevel_and_normals(obj, amount=0.015, segments=3):
    bevel = obj.modifiers.new("soft_rounded_edges", "BEVEL")
    bevel.width = amount
    bevel.segments = segments
    bevel.affect = 'EDGES'

    wn = obj.modifiers.new("weighted_smooth_normals", "WEIGHTED_NORMAL")
    if hasattr(wn, "keep_sharp"):
        wn.keep_sharp = True

    try:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    except Exception:
        pass

def local_to_world_xy(x, y, yaw):
    c = math.cos(yaw)
    s = math.sin(yaw)
    return Vector((c * x - s * y, s * x + c * y, 0.0))

def create_rounded_box(name, loc, dims, yaw, mat, bevel_amount=0.012, bevel_segments=3):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = (0.0, 0.0, yaw)
    normalize_object(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    add_bevel_and_normals(obj, bevel_amount, bevel_segments)
    return obj

def create_open_rect_tray(
    name,
    length,
    width,
    height,
    wall_t,
    bottom_t,
    offset_x,
    offset_y,
    z_bottom,
    yaw,
    mat
):
    # Explicit hollow container mesh:
    # outer rectangular box with open top and an inner cavity starting above bottom_t.
    ox = offset_x
    oy = offset_y
    L = length
    W = width
    H = height
    t = wall_t
    bt = bottom_t

    x0, x1 = ox - L / 2.0, ox + L / 2.0
    y0, y1 = oy - W / 2.0, oy + W / 2.0
    ix0, ix1 = x0 + t, x1 - t
    iy0, iy1 = y0 + t, y1 - t

    verts = [
        # outer bottom
        (x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0),
        # outer top
        (x0, y0, H), (x1, y0, H), (x1, y1, H), (x0, y1, H),
        # inner bottom/floor
        (ix0, iy0, bt), (ix1, iy0, bt), (ix1, iy1, bt), (ix0, iy1, bt),
        # inner top opening
        (ix0, iy0, H), (ix1, iy0, H), (ix1, iy1, H), (ix0, iy1, H),
    ]

    faces = [
        # outer bottom underside
        (0, 3, 2, 1),
        # outer side walls
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
        # top rim faces
        (4, 5, 13, 12),
        (5, 6, 14, 13),
        (6, 7, 15, 14),
        (7, 4, 12, 15),
        # inner side walls
        (8, 12, 13, 9),
        (9, 13, 14, 10),
        (10, 14, 15, 11),
        (11, 15, 12, 8),
        # inner floor
        (8, 9, 10, 11),
    ]

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (0.0, 0.0, z_bottom)
    obj.rotation_euler = (0.0, 0.0, yaw)

    if mat is not None:
        obj.data.materials.append(mat)

    normalize_object(obj)
    add_bevel_and_normals(obj, amount=0.022, segments=5)
    return obj

def create_vertical_tube(name, outer_radius, inner_radius, height, loc, mat, segments=48):
    verts = []
    faces = []

    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        co = math.cos(a)
        si = math.sin(a)
        verts.append((outer_radius * co, outer_radius * si, -height / 2.0))
        verts.append((outer_radius * co, outer_radius * si,  height / 2.0))
        verts.append((inner_radius * co, inner_radius * si, -height / 2.0))
        verts.append((inner_radius * co, inner_radius * si,  height / 2.0))

    for i in range(segments):
        j = (i + 1) % segments
        ob0, ot0, ib0, it0 = 4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3
        ob1, ot1, ib1, it1 = 4 * j, 4 * j + 1, 4 * j + 2, 4 * j + 3

        faces.append((ob0, ob1, ot1, ot0))  # outer wall
        faces.append((ib1, ib0, it0, it1))  # inner wall
        faces.append((ot0, ot1, it1, it0))  # top annulus
        faces.append((ob1, ob0, ib0, ib1))  # bottom annulus

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = loc

    if mat is not None:
        obj.data.materials.append(mat)

    normalize_object(obj)
    add_bevel_and_normals(obj, amount=0.006, segments=3)
    return obj

# ------------------------------------------------------------
# Main dimensions
# ------------------------------------------------------------
tray_L = 1.12
tray_W = 0.64
tray_H = 0.175
wall_t = 0.038
bottom_t = 0.032

# Offset of tray body relative to the central pole/pivot.
# This places the pole through an off-center zone of the tray.
tray_offset_x = 0.23
tray_offset_y = 0.00

z_bottoms = [0.14, 0.375, 0.61, 0.845, 1.08]
tray_yaws = [
    math.radians(8),
    math.radians(-62),
    math.radians(54),
    math.radians(-34),
    math.radians(18),
]

# ------------------------------------------------------------
# Central white pole
# ------------------------------------------------------------
bpy.ops.mesh.primitive_cylinder_add(
    vertices=48,
    radius=0.034,
    depth=1.34,
    location=(0.0, 0.0, 0.76)
)
central_pole = bpy.context.object
central_pole.name = "central_pole_SOLID_white_vertical_axle"
central_pole.data.materials.append(white_mat)
normalize_object(central_pole)
add_bevel_and_normals(central_pole, amount=0.003, segments=2)

# ------------------------------------------------------------
# Trays and their raised inset details
# ------------------------------------------------------------
for idx, (zb, yaw) in enumerate(zip(z_bottoms, tray_yaws), start=1):
    tray = create_open_rect_tray(
        name=f"tray_{idx:02d}_body_HOLLOW_CONTAINER",
        length=tray_L,
        width=tray_W,
        height=tray_H,
        wall_t=wall_t,
        bottom_t=bottom_t,
        offset_x=tray_offset_x,
        offset_y=tray_offset_y,
        z_bottom=zb,
        yaw=yaw,
        mat=olive_mat
    )

    # Top transverse baffle / upper board inside tray.
    # Fix v2: the reference shows this board near the tray rim, with its top
    # surface aligned to the side-wall top, not attached to the bottom floor.
    # Fix v3: the board is not centered in the tray. It occupies one side of
    # the tray interior, leaving the opposite side as an open compartment.
    # Keep the original object names so the articulation script still finds them.
    panel_thickness = 0.030
    panel_length_x = 0.43
    panel_width_y = 0.55
    panel_top_z = tray_H - 0.002
    panel_center_z = panel_top_z - panel_thickness / 2.0

    # Put the panel flush against the local -X inner wall of the tray.
    # Fix v6: remove the visible gap between this top board and the side wall.
    # A tiny overlap is intentional for visual contact after beveling.
    inner_x_min = tray_offset_x - tray_L / 2.0 + wall_t
    panel_side_overlap = 0.010
    panel_center_x = inner_x_min - panel_side_overlap + panel_length_x / 2.0

    panel_local = Vector((panel_center_x, tray_offset_y + 0.000, panel_center_z))
    panel_world_xy = local_to_world_xy(panel_local.x, panel_local.y, yaw)
    panel_loc = (
        panel_world_xy.x,
        panel_world_xy.y,
        zb + panel_local.z
    )
    create_rounded_box(
        name=f"tray_{idx:02d}_panel_SOLID_raised_floor_insert",
        loc=panel_loc,
        # Transverse footprint: the board spans across the tray width.
        dims=(panel_length_x, panel_width_y, panel_thickness),
        yaw=yaw,
        mat=olive_mat,
        bevel_amount=0.015,
        bevel_segments=4
    )

    # Two narrow top ribs on the baffle. They move together with the side panel,
    # instead of remaining around the tray center. Their top face is kept
    # approximately flush with the tray side-wall top.
    rib_thickness = 0.012
    rib_top_z = tray_H - 0.001
    rib_center_z = rib_top_z - rib_thickness / 2.0
    rib_edge_offset_x = panel_length_x / 2.0 - 0.035
    for rib_label, rib_x in [("A", -rib_edge_offset_x), ("B", rib_edge_offset_x)]:
        rib_local = Vector((panel_center_x + rib_x, tray_offset_y + 0.000, rib_center_z))
        rib_world_xy = local_to_world_xy(rib_local.x, rib_local.y, yaw)
        create_rounded_box(
            name=f"tray_{idx:02d}_rib_{rib_label}_SOLID_narrow_raised_detail",
            loc=(rib_world_xy.x, rib_world_xy.y, zb + rib_local.z),
            dims=(0.022, 0.50, rib_thickness),
            yaw=yaw,
            mat=olive_mat,
            bevel_amount=0.004,
            bevel_segments=2
        )

# ------------------------------------------------------------
# Removed artificial green swivel sleeves between trays.
# The visible/mechanical yaw axis is represented by the white central pole and
# each tray's continuous joint around that pole. No separate sleeve meshes are
# needed for the reference object.
# ------------------------------------------------------------

# Removed artificial lower green pivot collar.
# The reference image shows only the white pole and caster assemblies below the base tray;
# the extra green tube under the tray caused a visible non-reference protrusion.

# ------------------------------------------------------------
# Caster wheel assemblies
# ------------------------------------------------------------
base_yaw = tray_yaws[0]
corner_local_positions = [
    (tray_offset_x - tray_L / 2.0 + 0.13, tray_offset_y - tray_W / 2.0 + 0.11),
    (tray_offset_x + tray_L / 2.0 - 0.13, tray_offset_y - tray_W / 2.0 + 0.11),
    (tray_offset_x + tray_L / 2.0 - 0.13, tray_offset_y + tray_W / 2.0 - 0.11),
    (tray_offset_x - tray_L / 2.0 + 0.13, tray_offset_y + tray_W / 2.0 - 0.11),
]

def create_caster_bracket(index, wheel_center, yaw):
    # Bracket is a small joined structural assembly made from discrete plates
    # plus a vertical cylindrical stem.
    parts = []
    axis_half = 0.046

    # Local helper
    def world_from_local(local):
        v = local_to_world_xy(local[0], local[1], yaw)
        return (wheel_center[0] + v.x, wheel_center[1] + v.y, wheel_center[2] + local[2])

    # Two fork cheeks, placed on each side of the horizontal wheel axis.
    for side in [-1, 1]:
        loc = world_from_local((side * axis_half, 0.0, 0.032))
        obj = create_rounded_box(
            name=f"caster_{index:02d}_bracket_temp_fork_{side}",
            loc=loc,
            dims=(0.012, 0.075, 0.070),
            yaw=yaw,
            mat=bracket_mat,
            bevel_amount=0.003,
            bevel_segments=1
        )
        parts.append(obj)

    # Top yoke block
    obj = create_rounded_box(
        name=f"caster_{index:02d}_bracket_temp_top_block",
        loc=world_from_local((0.0, 0.0, 0.074)),
        dims=(0.112, 0.070, 0.018),
        yaw=yaw,
        mat=bracket_mat,
        bevel_amount=0.004,
        bevel_segments=1
    )
    parts.append(obj)

    # Vertical stem cylinder above the fork.
    # Its top is kept just under the tray bottom, so the caster no longer penetrates the tray floor.
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24,
        radius=0.016,
        depth=0.070,
        location=world_from_local((0.0, 0.0, 0.083))
    )
    stem = bpy.context.object
    stem.name = f"caster_{index:02d}_bracket_temp_vertical_stem"
    stem.data.materials.append(bracket_mat)
    normalize_object(stem)
    add_bevel_and_normals(stem, amount=0.002, segments=1)
    parts.append(stem)

    # Join plates/stem into one URDF-like structural part.
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    bracket = bpy.context.object
    bracket.name = f"caster_{index:02d}_bracket_STRUCTURAL_ASSEMBLY_fork_and_stem"
    normalize_object(bracket)
    return bracket

for i, (lx, ly) in enumerate(corner_local_positions, start=1):
    xy = local_to_world_xy(lx, ly, base_yaw)
    wheel_center = (xy.x, xy.y, 0.022)  # lowered from 0.055 to keep the wheel below tray_01 bottom

    # Horizontal wheel cylinder; cylinder default axis is Z, rotate so axis runs along local X.
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=0.052,
        depth=0.070,
        location=wheel_center,
        rotation=(0.0, math.pi / 2.0, base_yaw)
    )
    wheel = bpy.context.object
    wheel.name = f"caster_{i:02d}_wheel_SOLID_dark_rubber_cylinder"
    wheel.data.materials.append(wheel_mat)
    normalize_object(wheel)
    add_bevel_and_normals(wheel, amount=0.006, segments=3)

    create_caster_bracket(i, wheel_center, base_yaw)

# ------------------------------------------------------------
# Camera
# ------------------------------------------------------------
bpy.ops.object.camera_add(location=(1.95, -2.65, 1.55), rotation=(0.0, 0.0, 0.0))
camera = bpy.context.object
camera.name = "Camera"

target = Vector((0.17, 0.02, 0.68))
direction = target - Vector(camera.location)
camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 1.95
scene.camera = camera

# ------------------------------------------------------------
# Final render
# ------------------------------------------------------------
bpy.ops.render.render(write_still=True)