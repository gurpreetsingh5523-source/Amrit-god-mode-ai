"""File Operations — Safe read/write/search/copy within workspace."""
import shutil
import json
from pathlib import Path
from logger import setup_logger
logger = setup_logger("FileOps")


class FileOps:
    """Safe file operations scoped to a workspace directory."""

    def __init__(self, workspace: str = "workspace"):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe(self, path: str) -> Path:
        """Resolve path inside workspace. Raises PermissionError if outside."""
        p = (self.workspace / path).resolve()
        if not str(p).startswith(str(self.workspace)):
            raise PermissionError(f"Path outside workspace: {path}")
        return p

    def read(self, path: str) -> str:
        p = self._safe(path)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {path}")
        return p.read_text(errors="ignore")

    def write(self, path: str, content: str, append: bool = False) -> int:
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        logger.info(f"{'Appended' if append else 'Wrote'} {len(content)} chars to {path}")
        return len(content)

    def delete(self, path: str) -> bool:
        p = self._safe(path)
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
        return True

    def copy(self, src: str, dst: str) -> str:
        s, d = self._safe(src), self._safe(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        return str(d)

    def list_dir(self, path: str = "") -> list:
        p = self._safe(path)
        if not p.is_dir():
            return []
        return sorted(str(x.relative_to(self.workspace)) for x in p.iterdir())

    def exists(self, path: str) -> bool:
        try:
            return self._safe(path).exists()
        except PermissionError:
            return False

    def search_text(self, query: str, extension: str = ".py") -> list:
        """
        Search for query string in all files with given extension.
        Returns list of {file, line, content} matches.
        """
        matches = []
        for fp in self.workspace.rglob(f"*{extension}"):
            try:
                for i, line in enumerate(fp.read_text(errors="ignore").splitlines(), 1):
                    if query.lower() in line.lower():
                        matches.append({
                            "file": str(fp.relative_to(self.workspace)),
                            "line": i,
                            "content": line.strip()[:200]
                        })
                        if len(matches) >= 50:  # cap results
                            return matches
            except Exception:
                pass
        return matches

    def read_json(self, path: str) -> dict:
        return json.loads(self.read(path))

    def write_json(self, path: str, data) -> int:
        return self.write(path, json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    fo = FileOps()
    fo.write("test_file_ops.txt", "FileOps is working!\n")
    print(fo.read("test_file_ops.txt"))
    fo.delete("test_file_ops.txt")
    print("FileOps OK")
