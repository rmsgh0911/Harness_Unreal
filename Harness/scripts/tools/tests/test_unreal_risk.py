"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class UnrealRiskTests(HarnessBaseTestCase):
    def test_unreal_risk_idempotency_hints_detects_spawn_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            py = root / "Harness/scripts/unreal/place_actors.py"
            py.parent.mkdir(parents=True)
            py.write_text("actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, loc)\n", encoding="utf-8")
            hints = idempotency_hints(root, "Harness/scripts/unreal/place_actors.py")
            self.assertIn("spawn_actor_from_class", hints)
    def test_unreal_risk_pie_only_hints_detects_addtoviewport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cpp = root / "Source/MyActor.cpp"
            cpp.parent.mkdir(parents=True)
            cpp.write_text("void AMyActor::BeginPlay() { Widget->AddToViewport(); }\n", encoding="utf-8")
            hints = pie_only_hints(root, "Source/MyActor.cpp")
            self.assertIn("AddToViewport", hints)
            self.assertIn("BeginPlay", hints)
    def test_unreal_risk_umap_and_uasset_carry_separate_messages(self) -> None:
        umap_risks = classify_path("Content/Maps/Level01.umap")
        uasset_risks = classify_path("Content/Blueprints/BP_Actor.uasset")
        umap_messages = [r["reason"] for r in umap_risks]
        uasset_messages = [r["reason"] for r in uasset_risks]
        self.assertTrue(any("level file" in m for m in umap_messages))
        self.assertTrue(any("binary asset" in m for m in uasset_messages))
        self.assertFalse(any("level file" in m for m in uasset_messages))
