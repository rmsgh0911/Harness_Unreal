import json
from pathlib import Path

import unreal


def project_dir():
    return Path(unreal.Paths.project_dir())


def load_config():
    path = project_dir() / "Harness" / "config" / "project.json"
    if not path.exists():
        raise RuntimeError(f"Missing Harness config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def add_actor(actor_class, location, rotation=None, label=None):
    rotation = rotation or unreal.Rotator(0.0, 0.0, 0.0)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actor_subsystem.spawn_actor_from_class(actor_class, location, rotation)
    if label:
        actor.set_actor_label(label)
    return actor


def add_cube(label, location, scale):
    actor = add_actor(unreal.StaticMeshActor, location, label=label)
    actor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube.Cube"))
    actor.set_actor_scale3d(scale)
    return actor


def set_world_game_mode(config):
    class_path = config.get("default_game_mode_class", "")
    if not class_path:
        return

    game_mode = unreal.load_class(None, class_path)
    if not game_mode:
        unreal.log_warning(f"Could not load default_game_mode_class: {class_path}")
        return

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", game_mode)


def create_level():
    config = load_config()
    level_path = config.get("harness_level_path", "/Game/Harness/HarnessTestLevel")

    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    set_world_game_mode(config)

    add_actor(
        unreal.PlayerStart,
        unreal.Vector(-400.0, 0.0, 120.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        "PlayerStart_Harness",
    )

    add_cube("Floor_Harness", unreal.Vector(250.0, 0.0, -10.0), unreal.Vector(16.0, 12.0, 0.2))
    add_cube("Harness_Target_01", unreal.Vector(700.0, 0.0, 100.0), unreal.Vector(0.6, 0.6, 1.8))
    add_cube("Harness_Target_02", unreal.Vector(700.0, -260.0, 100.0), unreal.Vector(0.6, 0.6, 1.8))
    add_cube("Harness_Target_03", unreal.Vector(700.0, 260.0, 100.0), unreal.Vector(0.6, 0.6, 1.8))

    key_light = add_actor(
        unreal.DirectionalLight,
        unreal.Vector(0.0, 0.0, 900.0),
        unreal.Rotator(-45.0, -35.0, 0.0),
        "Harness_KeyLight",
    )
    key_light.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 4.0)

    add_actor(unreal.SkyLight, unreal.Vector(0.0, 0.0, 400.0), label="Harness_SkyLight")

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.EditorLoadingAndSavingUtils.save_map(world, level_path)
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    unreal.log(f"Harness level saved: {level_path}")


create_level()
