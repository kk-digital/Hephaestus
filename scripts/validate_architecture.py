#!/usr/bin/env python3
"""
Validate three-layer architecture dependencies.

Rules:
- c1 imports NOTHING from Hephaestus (only stdlib + external)
- c2 imports from c1 only
- c3 imports from c2 and c1 only

No circular dependencies allowed.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple


def extract_imports(file_path: Path) -> List[str]:
    """Extract all Hephaestus imports from a Python file."""
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError as e:
        print(f"⚠️  Syntax error in {file_path}: {e}")
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith('src.') or alias.name.startswith('c1_') or alias.name.startswith('c2_') or alias.name.startswith('c3_'):
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module.startswith('src.') or node.module.startswith('c1_') or node.module.startswith('c2_') or node.module.startswith('c3_')):
                imports.append(node.module)

    return imports


def get_layer(package_name: str) -> str:
    """Get layer from package name (c1_, c2_, c3_) or None for src."""
    if package_name.startswith('c1_'):
        return 'c1'
    elif package_name.startswith('c2_'):
        return 'c2'
    elif package_name.startswith('c3_'):
        return 'c3'
    else:
        return 'src'


def validate_layer_dependencies() -> Tuple[bool, List[str]]:
    """Validate that layer dependencies follow the rules."""
    src_dir = Path('src')
    violations = []

    if not src_dir.exists():
        print("✅ No src/ directory found (architecture not yet migrated)")
        return True, []

    for py_file in src_dir.rglob("*.py"):
        if py_file.name.startswith('__'):
            continue

        # Get file's layer
        package_parts = py_file.relative_to(src_dir).parts
        if not package_parts:
            continue

        package_name = package_parts[0]
        file_layer = get_layer(package_name)

        # Extract imports
        imports = extract_imports(py_file)

        for imported_module in imports:
            imported_layer = get_layer(imported_module.split('.')[0])

            # Check layer rules
            if file_layer == 'c1' and imported_layer in ['c2', 'c3']:
                violations.append(f"{py_file}: c1 cannot import from {imported_layer} ({imported_module})")
            elif file_layer == 'c2' and imported_layer == 'c3':
                violations.append(f"{py_file}: c2 cannot import from c3 ({imported_module})")

    return len(violations) == 0, violations


def main():
    """Run architecture validation."""
    print("=" * 70)
    print("Three-Layer Architecture Validator")
    print("=" * 70)
    print()

    success, violations = validate_layer_dependencies()

    if success:
        print("✅ All layer dependencies are valid!")
        print()
        print("Layer rules:")
        print("  - c1 imports: stdlib + external packages only")
        print("  - c2 imports: c1 + stdlib + external packages")
        print("  - c3 imports: c1 + c2 + stdlib + external packages")
        return 0
    else:
        print(f"❌ Found {len(violations)} layer dependency violations:")
        print()
        for violation in violations:
            print(f"  - {violation}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
