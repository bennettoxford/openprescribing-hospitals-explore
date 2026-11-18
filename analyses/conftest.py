import sys
from pathlib import Path

ANALYSES_DIR = Path(__file__).resolve().parent


def pytest_collect_file(file_path: Path, parent: object) -> None:
    if file_path.suffix != ".py" or not file_path.name.startswith("test_"):
        return
    analysis_dir = file_path.resolve().parent
    if analysis_dir.parent != ANALYSES_DIR:
        return
    _drop_modules_from_other_analyses(analysis_dir)


def _drop_modules_from_other_analyses(analysis_dir: Path) -> None:
    stale = [
        name
        for name, module in sys.modules.items()
        if _analysis_dir_of(module) not in (None, analysis_dir)
    ]
    for name in stale:
        del sys.modules[name]


def _analysis_dir_of(module: object) -> Path | None:
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return None
    path = Path(module_file).resolve()
    if ANALYSES_DIR not in path.parents:
        return None
    relative = path.relative_to(ANALYSES_DIR)
    if len(relative.parts) < 2:
        return None
    return ANALYSES_DIR / relative.parts[0]
