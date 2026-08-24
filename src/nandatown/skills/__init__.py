"""The SkillMD registry.

A SkillMD is a short Markdown file with YAML frontmatter that any agent
deployed in the town can read and follow. The registry parses,
validates, and lists them; the bundled skills document the reference
roles and the shared town protocol.
"""

from __future__ import annotations

import importlib.resources
import re
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9._-]*$")


class Skill(BaseModel):
    name: str
    version: int
    capability: str
    role: str
    protocol: str
    summary: str
    body: str


class SkillParseError(Exception):
    pass


def parse_skill(text: str) -> Skill:
    parts = text.split("---")
    if len(parts) < 3 or parts[0].strip():
        raise SkillParseError("a SkillMD starts with YAML frontmatter"
                              " between --- lines")
    try:
        front = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise SkillParseError(f"bad frontmatter: {exc}")
    body = "---".join(parts[2:]).strip()
    try:
        return Skill(body=body, **front)
    except (ValidationError, TypeError) as exc:
        raise SkillParseError(f"invalid skill fields: {exc}")


def validate_skill(text: str) -> list[str]:
    """Returns problems; empty means valid."""
    try:
        skill = parse_skill(text)
    except SkillParseError as exc:
        return [str(exc)]
    problems = []
    if not NAME_PATTERN.match(skill.name):
        problems.append(f"name {skill.name!r} must be lowercase dotted or"
                        " dashed")
    if not skill.body:
        problems.append("the skill body is empty; an agent has nothing to"
                        " follow")
    if len(skill.summary) > 200:
        problems.append("summary longer than 200 characters")
    return problems


def _builtin_dir():
    return importlib.resources.files("nandatown.skills") / "builtin"


def builtin_skills() -> dict[str, Skill]:
    out: dict[str, Skill] = {}
    for entry in sorted(_builtin_dir().iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".md"):
            skill = parse_skill(entry.read_text())
            out[skill.name] = skill
    return out


def get_skill(name: str) -> Skill:
    skills = builtin_skills()
    if name not in skills:
        raise KeyError(f"no skill {name!r}; available: {sorted(skills)}")
    return skills[name]


def skill_source(name: str) -> str:
    path = _builtin_dir() / f"{name}.md"
    return path.read_text()
