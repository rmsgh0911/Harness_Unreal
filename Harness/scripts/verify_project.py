import json
from pathlib import Path

import unreal


def fail(message):
    raise RuntimeError(message)


def project_dir():
    return Path(unreal.Paths.project_dir())


def config_path():
    return project_dir() / "Harness" / "config" / "project.json"


def load_config():
    path = config_path()
    if not path.exists():
        fail(f"Missing Harness config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_file(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_text_relative(relative_path):
    path = project_dir() / relative_path
    if not path.exists():
        fail(f"Missing file: {relative_path}")
    return path.read_text(encoding="utf-8")


def require_asset(asset_path):
    if asset_path and not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        fail(f"Missing asset: {asset_path}")


def require_class(class_path):
    if class_path and not unreal.load_class(None, class_path):
        fail(f"Missing class: {class_path}")


def require_text_markers(relative_path, markers):
    text = read_text_relative(relative_path)
    for marker in markers:
        if marker not in text:
            fail(f"Missing marker in {relative_path}: {marker}")


def verify_startup_map(config):
    startup_map = config.get("editor_startup_map", "")
    if not startup_map:
        return

    engine_ini = project_dir() / "Config" / "DefaultEngine.ini"
    if not engine_ini.exists():
        fail("Missing Config/DefaultEngine.ini")

    text = engine_ini.read_text(encoding="utf-8-sig")
    map_name = startup_map.rsplit("/", 1)[-1]
    accepted_values = {
        startup_map,
        f"{startup_map}.{map_name}",
    }

    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "EditorStartupMap" and value.strip() in accepted_values:
            return

    if not any(f"EditorStartupMap={value}" in text for value in accepted_values):
        fail(f"EditorStartupMap is not {startup_map}")


def verify_uproject(config):
    uproject_file = config.get("uproject_file", "")
    if not uproject_file:
        candidates = list(project_dir().glob("*.uproject"))
        if len(candidates) != 1:
            fail("Set uproject_file in Harness/config/project.json")
        uproject_path = candidates[0]
    else:
        uproject_path = project_dir() / uproject_file

    if not uproject_path.exists():
        fail(f"Missing uproject file: {uproject_path.name}")

    uproject = load_json_file(uproject_path)
    project_name = config.get("project_name", "")
    if project_name and uproject_path.stem != project_name:
        unreal.log_warning(f"Project name does not match uproject file name: {project_name}")

    plugins = {plugin.get("Name") for plugin in uproject.get("Plugins", [])}
    for plugin_name in config.get("required_uproject_plugins", []):
        if plugin_name not in plugins:
            fail(f"Missing plugin in uproject: {plugin_name}")


def verify_harness_level(config):
    level_path = config.get("harness_level_path", "")
    required_labels = config.get("harness_level_required_actor_labels", [])
    if not level_path or not required_labels:
        return

    if not unreal.EditorAssetLibrary.does_asset_exist(level_path):
        unreal.log_warning(
            f"Harness level has not been created yet: {level_path}. "
            "Run Harness/scripts/create_level.py if level validation is needed."
        )
        return

    unreal.EditorLoadingAndSavingUtils.load_map(level_path)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {actor.get_actor_label() for actor in actor_subsystem.get_all_level_actors()}
    for label in required_labels:
        if label not in labels:
            fail(f"Missing Harness level actor: {label}")


def main():
    config = load_config()

    verify_uproject(config)
    verify_startup_map(config)

    for class_path in config.get("required_classes", []):
        require_class(class_path)

    for asset_path in config.get("required_assets", []):
        require_asset(asset_path)

    for relative_path, markers in config.get("required_source_markers", {}).items():
        require_text_markers(relative_path, markers)

    for relative_path, markers in config.get("required_config_markers", {}).items():
        if markers:
            require_text_markers(relative_path, markers)

    verify_harness_level(config)
    unreal.log("Harness project verification passed.")


main()
