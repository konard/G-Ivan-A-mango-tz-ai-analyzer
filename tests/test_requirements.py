from pathlib import Path


def _runtime_requirements() -> dict[str, str]:
    requirements = {}
    for raw_line in Path("requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split(";", 1)[0].split("[", 1)[0].split("=", 1)[0].split("<", 1)[0].split(">", 1)[0].strip()
        requirements[name.lower()] = line
    return requirements


def test_transformers_vision_backend_dependency_is_explicit() -> None:
    requirements = _runtime_requirements()

    assert "torchvision" in requirements
    assert requirements["torchvision"] == "torchvision>=0.18.0"
