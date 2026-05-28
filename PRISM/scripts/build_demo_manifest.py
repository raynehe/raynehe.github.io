#!/usr/bin/env python3
"""Build the static demo manifest from asset/demo and asset/blender cases."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "asset" / "demo"
BLENDER_ROOT = ROOT / "asset" / "blender"
MANIFEST_PATH = DEMO_ROOT / "manifest.json"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def main() -> int:
    cases = []
    errors = []

    for case_dir in sorted(child for child in DEMO_ROOT.iterdir() if child.is_dir()):
        case, case_errors = build_case(case_dir, "demo")
        errors.extend(case_errors)
        if case:
            cases.append(case)

    if BLENDER_ROOT.exists():
        for case_dir in sorted(child for child in BLENDER_ROOT.iterdir() if child.is_dir()):
            case, case_errors = build_case(case_dir, "blender")
            errors.extend(case_errors)
            if case:
                cases.append(case)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    MANIFEST_PATH.write_text(json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH.relative_to(ROOT)} with {len(cases)} cases.")
    return 0


def build_case(case_dir: Path, namespace: str) -> tuple[dict | None, list[str]]:
    usd_case = build_usd_urdf_case(case_dir, namespace)
    if usd_case:
        return usd_case, []

    urdf_case, errors = build_urdf_obj_case(case_dir, namespace)
    if urdf_case or errors:
        return urdf_case, errors

    return None, [f"No supported demo assets found in {relative(case_dir)}."]


def build_usd_urdf_case(case_dir: Path, namespace: str) -> dict | None:
    export_dir = case_dir / "urdf_export"
    preview_usd = export_dir / "object_flattened.usda"
    urdf = export_dir / "object.urdf"
    if not preview_usd.exists() or not urdf.exists():
        return None

    case = base_case(case_dir, namespace)
    case.update(
        {
            "source": "usd-urdf",
            "urdf": relative(urdf),
            "previewUsd": relative(preview_usd),
        }
    )

    usd = export_dir / "object.usd"
    if usd.exists():
        case["usd"] = relative(usd)

    return case


def build_urdf_obj_case(case_dir: Path, namespace: str) -> tuple[dict | None, list[str]]:
    candidates = [
        (case_dir / "object.urdf", case_dir),
        (case_dir / "urdf_export" / "object.urdf", case_dir / "urdf_export"),
    ]

    for urdf, mesh_base in candidates:
        if not urdf.exists() or not (mesh_base / "meshes").is_dir():
            continue

        errors = validate_urdf_obj_assets(urdf, mesh_base)
        if errors:
            return None, errors

        case = base_case(case_dir, namespace)
        case.update(
            {
                "source": "urdf-obj",
                "urdf": relative(urdf),
                "meshBasePath": ensure_trailing_slash(relative(mesh_base)),
            }
        )
        return case, []

    return None, []


def base_case(case_dir: Path, namespace: str) -> dict:
    case_id = case_dir.name if namespace == "demo" else f"blender_{case_dir.name}"
    title = titleize(case_dir.name)
    if namespace == "blender":
        title = f"Blender {title}"

    case = {
        "id": case_id,
        "title": title,
    }

    thumbnail = find_thumbnail(case_dir, namespace)
    if thumbnail:
        case["thumbnail"] = thumbnail

    return case


def find_thumbnail(case_dir: Path, namespace: str) -> str | None:
    images = sorted(
        path
        for path in case_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and path.name.lower().startswith("render")
    )
    if images:
        return relative(images[0])

    if namespace == "blender":
        shared = BLENDER_ROOT / "Res1_3D.png"
        if shared.exists():
            return relative(shared)

    images = sorted(path for path in case_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if images:
        return relative(images[0])

    return None


def validate_urdf_obj_assets(urdf: Path, mesh_base: Path) -> list[str]:
    errors = []
    try:
        root = ET.parse(urdf).getroot()
    except ET.ParseError as exc:
        return [f"Could not parse {relative(urdf)}: {exc}"]

    visual_meshes = []
    for link in root.findall("link"):
        for visual in link.findall("visual"):
            mesh = visual.find("./geometry/mesh")
            filename = mesh.get("filename") if mesh is not None else None
            if filename:
                visual_meshes.append(filename)

    if not visual_meshes:
        errors.append(f"No visual mesh references found in {relative(urdf)}.")

    for filename in sorted(set(visual_meshes)):
        mesh_path = mesh_base / filename
        if not mesh_path.exists():
            errors.append(f"Missing OBJ referenced by {relative(urdf)}: {relative(mesh_path)}")
            continue

        for material_file in read_mtllibs(mesh_path):
            material_path = mesh_path.parent / material_file
            if not material_path.exists():
                errors.append(f"Missing MTL referenced by {relative(mesh_path)}: {relative(material_path)}")

    return errors


def read_mtllibs(obj_path: Path) -> list[str]:
    material_files = []
    for line in obj_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.startswith("mtllib "):
            continue
        material_files.extend(part for part in stripped[len("mtllib ") :].split() if part)
    return material_files


def titleize(value: str) -> str:
    def fix_token(token: str) -> str:
        match = re.fullmatch(r"([A-Za-z]+)(\d+)", token)
        if match:
            return f"{match.group(1).capitalize()} {match.group(2)}"
        return token.capitalize()

    return " ".join(fix_token(token) for token in value.split("_") if token)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ensure_trailing_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


if __name__ == "__main__":
    raise SystemExit(main())
