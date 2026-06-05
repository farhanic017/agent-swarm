"""Generate a lightweight animated coffee coin asset in Blender.

Run:
  blender --background --python examples/blender_coin.py
"""

from __future__ import annotations

from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
OUT_GLB = ROOT / "coffee_coin.glb"
OUT_BLEND = ROOT / "coffee_coin.blend"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def create_coin() -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=0.12, location=(0, 0, 0))
    coin = bpy.context.object
    coin.name = "lightweight_coffee_coin"
    coin.data.name = "coffee_coin_mesh"

    material = bpy.data.materials.new("warm_gold")
    material.diffuse_color = (1.0, 0.64, 0.22, 1.0)
    coin.data.materials.append(material)

    bevel = coin.modifiers.new("soft_edge", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 1
    coin.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return coin


def add_bean_mark() -> None:
    material = bpy.data.materials.new("espresso_mark")
    material.diffuse_color = (0.20, 0.09, 0.035, 1.0)
    for x in (-0.18, 0.18):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.18, location=(x, 0, 0.071))
        bean = bpy.context.object
        bean.name = "coffee_bean_emboss"
        bean.scale = (0.55, 1.25, 0.08)
        bean.rotation_euler[2] = 0.45 if x < 0 else -0.45
        bean.data.materials.append(material)


def add_animation(coin: bpy.types.Object) -> None:
    coin.rotation_euler = (0, 0, 0)
    coin.keyframe_insert(data_path="rotation_euler", frame=1)
    coin.rotation_euler = (0, 0, 6.283185307)
    coin.keyframe_insert(data_path="rotation_euler", frame=96)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 96


def add_camera_and_light() -> None:
    bpy.ops.object.light_add(type="AREA", location=(0, -2.5, 3.2))
    light = bpy.context.object
    light.name = "softbox"
    light.data.energy = 350
    light.data.size = 3.5

    bpy.ops.object.camera_add(location=(0, -3.2, 1.8), rotation=(1.1, 0, 0))
    bpy.context.scene.camera = bpy.context.object


def main() -> None:
    clear_scene()
    coin = create_coin()
    add_bean_mark()
    add_animation(coin)
    add_camera_and_light()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB")
    print(f"wrote {OUT_GLB}")


if __name__ == "__main__":
    main()
