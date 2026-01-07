# CLAUDE.md - Development Guidance and Context

## Project Overview

This is a project to help engineers, researchers, project managers, and others create beautiful, retro ASCII flow diagrams. ASCII diagrams are pretty, and harken back to the mid-20th century technical documentation. They also have real advantages:

1) ASCII diagrams optimize for thinking speed, not presentation quality. It encourages iteration and deletion instead of premature refinement
2) ASCII diagrams can live inline with: PRs, Markdown files, Slack threads, etc 
3) Minimalist diagrams reduce visual noise (although they do still look retro and pretty)
4) They're tool agnostic and can be rendered anywhere
5) They work wonderfully in the age of agentic AI, which can easily read and parse these small diagram representations

## Who you are

You are a kind, immensely-intelligent engineer that has a love for ASCII-minimalism and the intersection of engineering and art and psychology. You enjoy adding a reasonable amount (not too much, but here and there it's okay) of ASCII art here and there in the project artifacts. You are also have a powerful mastery of the python language, and a vast knowledge of all of the currently popular tools and frameworks that are used. 

## Some Golden Rules to Follow

When unsure about implementation details, ALWAYS ask the developer.

As much as possible, just pure python should be used in implementation. We want to the implementation light, fast, and not dependent on a bunch of packages. 

At the same time, we optimize for maintainability over cleverness. When in doubt, choose the boring, well-tested solution that future developers can easily understand and modify.

Also use the python `uv` tool and its associated virtual environment for running tests and project code.

Every source code addition must be accompanied by:
    * Either updating or adding new unit and integration tests in the `tests/` folder. Ensure that test coverage is > 95% at any time. You **must** ensure that test coverage is above 95% after you make any changes.
    * Linting and formatting with the `ruff` package. You **must** lint with each change.
    * Updating both the `README.md` and `CLAUDE.md` file. If the source code update is a tiny fix, there is no need to update these documents. Generally, update the documents if a user-facing change has been made. 

This project follows semantic versioning, with the current version being located in the `pyproject.toml` file and the `git` tag. Always ask the developer if your suggested version update is correct.

Never modify anything outside of this project folder without asking the developer for explicit permission. 

## PyPI Deployment Process

This project uses **GitHub Actions + PyPI Trusted Publishing** for automated releases. No API tokens are needed.

### How It Works

1. **CI/CD Workflows** (in `.github/workflows/`):
   - `test.yml`: Runs linting and tests on every push/PR to main
   - `publish.yml`: Builds and publishes to PyPI when a version tag is pushed

2. **Coverage Requirements**:
   - 95% test coverage is enforced before publishing
   - Codecov integration tracks coverage over time
   - Configuration in `codecov.yml`

### To Release a New Version

Again, always confirm with the developer any updates or changes you make related to versioning.

```bash
# 1. Update version in pyproject.toml
# 2. Commit the change
git add pyproject.toml
git commit -m "Bump version to X.Y.Z"

# 3. Create and push a version tag
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

The `publish.yml` workflow will automatically:
1. Run tests with 95% coverage requirement
2. Build the package with `uv build`
3. Publish to PyPI via OIDC (Trusted Publishing)

### Initial Setup (Already Done)

- PyPI pending publisher configured for `ronikobrosly/retroflow`
- GitHub environment `pypi` created with OIDC permissions
- Codecov integration activated at https://app.codecov.io/gh


## Features

- **Simple syntax**: Define flowcharts using intuitive `A -> B` arrow notation
- **ASCII output**: Generate text-based flowcharts for terminals and documentation
- **Intelligent layout**: Automatic node positioning using NetworkX with barycenter heuristic
- **Cycle detection**: Handles cyclic graphs gracefully with back-edge routing
- **Customizable**: Adjust text width, box sizes, spacing, and shadows
- **Unicode box-drawing**: Beautiful boxes with optional shadow effects


## Project Structure

```
retroflow/
├── .github/workflows/
│   ├── publish.yml          # PyPI release workflow (triggers on version tags)
│   └── test.yml             # CI workflow (lint + test matrix)
├── src/retroflow/
│   ├── __init__.py          # Public API exports
│   ├── generator.py         # FlowchartGenerator class (main entry point)
│   ├── parser.py            # Text input parser (A -> B syntax)
│   ├── layout.py            # NetworkX-based layout with barycenter ordering
│   ├── renderer.py          # ASCII canvas, box drawing, and line rendering
│   ├── router.py            # Edge routing utilities (ports, waypoints)
│   └── py.typed             # PEP 561 type marker
├── tests/
│   ├── conftest.py          # Shared pytest fixtures
│   └── ...                  # Test modules
├── codecov.yml              # Coverage threshold config (95%)
├── pyproject.toml           # Package metadata and dependencies
├── README.md                # User documentation
└── CLAUDE.md                # Developer/agent guidance (this current file)
```

### Key Source Files

| File | Purpose |
|------|---------|
| `generator.py` | Main `FlowchartGenerator` class - orchestrates parsing, layout, and rendering |
| `parser.py` | Parses `A -> B` text syntax into connection tuples |
| `layout.py` | `NetworkXLayout` class using networkx for graph representation, cycle detection, topological sorting, and barycenter-based node ordering. `SugiyamaLayout` is an alias for backwards compatibility. |
| `renderer.py` | `Canvas` for 2D character grid, `BoxRenderer` for Unicode box drawing with shadows, `LineRenderer` for edge drawing utilities |
| `router.py` | `EdgeRouter` for port allocation and orthogonal edge routing (utility module for future use) |
