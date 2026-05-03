"""Tests for dataset_builder, dataset_loader, and dataset_trainer.

Run:
    pytest test_training_pipeline.py -v
"""
import json
import pytest
from pathlib import Path

from dataset_builder import DatasetBuilder
from dataset_loader import DatasetLoader


# ─── DatasetBuilder tests ──────────────────────────────────────────

class TestDatasetBuilder:
    def test_build_coding(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("coding", n=10)
        assert Path(path).exists()
        lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 10

    def test_build_math(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("math", n=8)
        lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 8

    def test_build_punjabi(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("punjabi", n=5)
        lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 5

    def test_example_is_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("coding", n=3)
        for line in Path(path).read_text().strip().splitlines():
            obj = json.loads(line)
            assert "text" in obj

    def test_chatml_format(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("math", n=3)
        for line in Path(path).read_text().strip().splitlines():
            text = json.loads(line)["text"]
            assert "<|im_start|>system" in text
            assert "<|im_start|>user" in text
            assert "<|im_start|>assistant" in text

    def test_unknown_subject_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="Unknown subject"):
            DatasetBuilder().build("chemistry", n=5)

    def test_build_all(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        paths = db.build_all(n_each=5)
        assert set(paths.keys()) == {"coding", "math", "punjabi"}
        for p in paths.values():
            assert Path(p).exists()

    def test_stats(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("coding", n=7)
        stats = db.stats(path)
        assert stats["examples"] == 7
        assert stats["avg_chars"] > 0

    def test_stats_missing_file(self):
        stats = DatasetBuilder().stats("/tmp/does_not_exist_xyz.jsonl")
        assert "error" in stats


# ─── DatasetLoader tests ──────────────────────────────────────────

class TestDatasetLoader:
    def test_load(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("coding", n=5)
        examples = DatasetLoader().load(path)
        assert len(examples) == 5
        assert all("text" in ex for ex in examples)

    def test_load_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            DatasetLoader().load("/tmp/no_such_file_abc.jsonl")

    def test_load_split_ratio(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = DatasetBuilder()
        path = db.build("math", n=10)
        train, valid = DatasetLoader().load_split(path, 0.8)
        assert len(train) == 8
        assert len(valid) == 2

    def test_save_roundtrip(self, tmp_path):
        examples = [{"text": f"example {i}"} for i in range(5)]
        out = str(tmp_path / "test.jsonl")
        DatasetLoader().save(examples, out)
        loaded = DatasetLoader().load(out)
        assert [ex["text"] for ex in loaded] == [ex["text"] for ex in examples]


# ─── DatasetTrainer (dry smoke test) ─────────────────────────────

class TestDatasetTrainerSmoke:
    def test_prepare_jsonl(self, tmp_path):
        from dataset_trainer import DatasetTrainer
        items = [{"text": f"item {i}"} for i in range(3)]
        path = str(tmp_path / "out.jsonl")
        result = DatasetTrainer().prepare_jsonl(items, path)
        assert Path(result).exists()
        lines = Path(result).read_text().strip().splitlines()
        assert len(lines) == 3

    def test_trainer_import_error_handled(self, tmp_path, monkeypatch):
        """If transformers/datasets not available, returns error dict (not crash)."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("transformers", "datasets"):
                raise ImportError(f"Mock: {name} not available")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        import asyncio
        from dataset_trainer import DatasetTrainer
        result = asyncio.run(DatasetTrainer().train("dummy.jsonl", epochs=1))
        assert result["status"] == "error"
        assert "Missing" in result["error"]
