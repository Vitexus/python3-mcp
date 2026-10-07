#!/usr/bin/env python3
"""Statically pin a hatchling/uv-dynamic-versioning pyproject.toml for a Debian build.

Debian builds run without a git checkout's tag history and without the
uv-dynamic-versioning hatch plugin installed, so the dynamic version (and,
for the root mcp package, the dynamic dependency list rendered by the
uv-dynamic-versioning hatch metadata hook) must be replaced with static
values before hatchling runs.
"""

import re
import sys

MARKER_RE = re.compile(r"\s*;\s*(python_version|sys_platform)\b.*$")


def inline_dependencies(text: str, version: str) -> str:
    match = re.search(
        r"\[tool\.hatch\.metadata\.hooks\.uv-dynamic-versioning\]\ndependencies = \[\n(.*?)\n\]\n",
        text,
        re.DOTALL,
    )
    if not match:
        raise SystemExit("could not find the uv-dynamic-versioning dependencies block")

    seen = set()
    resolved = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        spec = line.strip(",")
        spec = spec[1:-1] if spec[:1] in "\"'" else spec  # strip quotes
        # Markers that can never hold on a Debian system Python: skip the
        # requirement entirely rather than mis-render it as unconditional.
        if "sys_platform == 'win32'" in spec or "sys_platform == \"win32\"" in spec:
            continue
        spec = MARKER_RE.sub("", spec)
        spec = spec.replace("{{ version }}", version)
        name = re.split(r"[><=\[]", spec, maxsplit=1)[0]
        if name in seen:
            continue
        seen.add(name)
        resolved.append(spec)

    deps_literal = "dependencies = [\n" + "".join(f'    "{d}",\n' for d in resolved) + "]"

    text = text.replace('dynamic = ["version", "dependencies"]', deps_literal + f'\nversion = "{version}"')
    return text


def strip_dynamic_versioning(text: str) -> str:
    text = re.sub(r'requires = \["hatchling", "uv-dynamic-versioning"\]', 'requires = ["hatchling"]', text)
    text = re.sub(r"\[tool\.hatch\.version\]\nsource = \"uv-dynamic-versioning\"\n\n", "", text)
    text = re.sub(r"\[tool\.uv-dynamic-versioning\]\n(?:.+\n)*?\n", "", text)
    text = re.sub(r"\[tool\.hatch\.metadata\.hooks\.uv-dynamic-versioning\]\ndependencies = \[\n(?:.*?\n)*?\]\n\n", "", text)
    return text


def main() -> None:
    path, version = sys.argv[1], sys.argv[2]
    inline_deps = "--inline-dependencies" in sys.argv[3:]

    with open(path) as f:
        text = f.read()

    if inline_deps:
        text = inline_dependencies(text, version)
    else:
        text = text.replace('dynamic = ["version"]', f'version = "{version}"')

    text = strip_dynamic_versioning(text)
    # Older hatchling (e.g. Ubuntu noble) rejects classifiers it does not know.
    text = text.replace('    "Programming Language :: Python :: 3.14",\n', '')

    with open(path, "w") as f:
        f.write(text)


if __name__ == "__main__":
    main()
