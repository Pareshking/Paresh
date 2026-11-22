"""GitHub refuses a workflow with a key written twice in one mapping; Python's YAML reader quietly keeps the last
one, so a check that only loads the file passes it (found 21 Nov 2026: a second `concurrency:` in nse_indices.yml
made every run of that workflow fail before starting)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS = sorted((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml"))


class _Strict(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    keys = [loader.construct_object(k, deep=deep) for k, _ in node.value]
    dup = sorted({str(k) for k in keys if keys.count(k) > 1})
    if dup:
        raise yaml.constructor.ConstructorError(None, None, f"key written twice: {dup}", node.start_mark)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_workflow_writes_a_key_twice(path):
    yaml.load(path.read_text(encoding="utf-8"), Loader=_Strict)
