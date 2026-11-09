"""Load models.yaml, tasks, style guides, sources and facts (REQUIREMENTS.md §3, §5)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import yaml

from .schemas import FactsFile, ModelCfg, ModelsFile, Source, SourceMeta, Task

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


@dataclass(frozen=True)
class Paths:
    """All file locations derive from one root so tests and smoke can use a temp tree."""

    root: Path

    @classmethod
    def from_env(cls) -> Paths:
        return cls(Path(os.environ.get("DANEWS_ROOT", ".")).resolve())

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def sources_yaml(self) -> Path:
        return self.data / "sources.yaml"

    @property
    def sources_dir(self) -> Path:
        return self.data / "sources"

    @property
    def facts_dir(self) -> Path:
        return self.data / "facts"

    @property
    def wordlists(self) -> Path:
        return self.data / "wordlists"

    @property
    def styleguides(self) -> Path:
        return self.root / "styleguides"

    @property
    def tasks(self) -> Path:
        return self.root / "tasks"

    @property
    def prompts(self) -> Path:
        return self.root / "prompts"

    @property
    def models_yaml(self) -> Path:
        return self.root / "models.yaml"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def scores(self) -> Path:
        return self.root / "scores"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def site(self) -> Path:
        return self.root / "site"

    @property
    def cache(self) -> Path:
        return self.root / ".cache"

    @property
    def costs(self) -> Path:
        return self.root / "costs.jsonl"


def parse_source_markdown(text: str) -> Source:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        raise ValueError("missing YAML front matter")
    meta = SourceMeta.model_validate(yaml.safe_load(m.group(1)))
    return Source(meta=meta, body=m.group(2).strip() + "\n")


def render_source_markdown(source: Source) -> str:
    front = yaml.safe_dump(
        source.meta.model_dump(mode="json"), allow_unicode=True, sort_keys=False, width=1000
    )
    return f"---\n{front}---\n{source.body.strip()}\n"


class Config:
    """Lazy, cached access to everything under the repo root."""

    def __init__(self, paths: Paths | None = None):
        self.paths = paths or Paths.from_env()

    @cached_property
    def models_file(self) -> ModelsFile:
        raw = yaml.safe_load(self.paths.models_yaml.read_text())
        for m in raw.get("models", []):
            if m.get("api_base"):
                m["api_base"] = os.path.expandvars(m["api_base"])
        return ModelsFile.model_validate(raw)

    @property
    def models(self) -> list[ModelCfg]:
        return [m for m in self.models_file.models if m.enabled]

    def model(self, model_id: str) -> ModelCfg:
        return self.models_file.get(model_id)

    @cached_property
    def tasks(self) -> list[Task]:
        return [
            Task.model_validate(yaml.safe_load(p.read_text()))
            for p in sorted(self.paths.tasks.glob("t*_*.yaml"))
        ]

    def task(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise KeyError(task_id)

    @cached_property
    def styleguides(self) -> dict[str, str]:
        return {p.stem: p.read_text().strip() for p in sorted(self.paths.styleguides.glob("*.md"))}

    @cached_property
    def sources(self) -> list[Source]:
        out = []
        for p in sorted(self.paths.sources_dir.glob("*.md")):
            src = parse_source_markdown(p.read_text())
            if src.meta.needs_manual:
                continue
            out.append(src)
        return out

    def source(self, source_id: str) -> Source:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(source_id)

    @cached_property
    def facts(self) -> dict[str, FactsFile]:
        out = {}
        for p in sorted(self.paths.facts_dir.glob("*.yaml")):
            ff = FactsFile.model_validate(yaml.safe_load(p.read_text()))
            out[ff.source_id] = ff
        return out

    def prompt_template(self, name: str) -> str:
        return (self.paths.prompts / f"{name}.md").read_text()

    def wordlist_yaml(self, name: str) -> dict[str, list[str]]:
        return yaml.safe_load((self.paths.wordlists / f"{name}.yaml").read_text())

    def wordlist_txt(self, name: str) -> set[str]:
        p = self.paths.wordlists / f"{name}.txt"
        if not p.exists():
            return set()
        return {
            line.strip().lower()
            for line in p.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
