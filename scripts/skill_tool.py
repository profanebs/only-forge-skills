#!/usr/bin/env python3
"""Validate, scan, and package agent skills.

Usage:
  python skill_tool.py validate <skill-dir> [--public] [--strict] [--json]
  python skill_tool.py scan <skill-dir> [--skills-root PATH ...] [--threshold 0.35] [--top 5] [--json]
  python skill_tool.py package <skill-dir> <out-dir> [--public] [--strict] [--dry-run]

The tool is intentionally dependency-light. If PyYAML is installed it is used;
otherwise a small parser handles the flat frontmatter used by skills.
"""

import argparse
import ast
import json
import re
import sys
import zipfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[A-Za-z0-9_]+")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TRIGGER_RE = re.compile(
    r"(?i)\b(use when|when the user|load before|use this skill|trigger|"
    r"should be used|when creating|when upgrading|when auditing)\b|"
    r"\u9002\u7528|\u7528\u4e8e|\u5f53"
)
NEGATIVE_RE = re.compile(
    r"(?i)\b(do not use|don't use|not for|avoid using)\b|"
    r"\u4e0d\u9002\u7528|\u4e0d\u8981\u7528"
)
CODE_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".ps1",
    ".bat", ".cmd", ".json", ".yaml", ".yml", ".toml", ".sh",
}
EXCLUDE_DIRS = {
    "__pycache__", "node_modules", ".git", ".svn", "evals",
    "dist", "secrets", "__MACOSX", "trial-with", "trial-baseline",
    "evidence", "fixtures",
}
EXCLUDE_NAMES = {".DS_Store", ".env", "report.md"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}
EXTRA_DOCS = {
    "CHANGELOG.md", "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md",
    "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
}
STOPWORDS = set(
    "a an the and or for to of in on with when where which who what this that "
    "these those use used using skill skills it its is are be as at by from you "
    "your we our they their can will should may not no do does done if then than "
    "so such into over under about after before while during without within".split()
)


class Finding:
    def __init__(self, level, code, message, path=None, line=None):
        self.level = level
        self.code = code
        self.message = message
        self.path = str(path) if path else None
        self.line = line

    def as_dict(self):
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "line": self.line,
        }

    def render(self):
        where = ""
        if self.path:
            where = " [" + self.path
            if self.line:
                where += ":" + str(self.line)
            where += "]"
        return self.level + " " + self.code + ": " + self.message + where


def read_text(path):
    data = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def strip_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def simple_yaml(text):
    """Parse the flat frontmatter used by skills.

    Handles flat key/value pairs, one nested map, and folded/literal block
    scalars. It is deliberately not a full YAML parser. If PyYAML is present,
    the caller uses PyYAML instead.
    """
    result = {}
    current = None
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index].rstrip()
        index += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[:1].isspace() and current:
            key, sep, value = raw.strip().partition(":")
            if sep and key and value:
                if not isinstance(result.get(current), dict):
                    result[current] = {}
                result[current][key.strip()] = strip_quotes(value.strip())
            continue
        key, sep, value = raw.partition(":")
        if not sep:
            continue
        key = key.strip()
        current = key
        value = value.strip()
        if value in (">", ">-", ">+", "|", "|-", "|+"):
            block = []
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() and not candidate[:1].isspace():
                    break
                block.append(candidate.strip())
                index += 1
            if value.startswith("|"):
                result[key] = "\n".join(block).strip()
            else:
                result[key] = " ".join(part for part in block if part).strip()
        elif value == "":
            result[key] = {}
        else:
            result[key] = strip_quotes(value)
    return result


def parse_yaml(text):
    if yaml is not None:
        return yaml.safe_load(text)
    return simple_yaml(text)


def split_frontmatter(text):
    match = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if not match:
        return None, text, 1
    body = text[match.end():]
    body_line = text[:match.end()].count("\n") + 1
    return match.group(1), body, body_line


def load_skill_file(md_path):
    md_path = Path(md_path).resolve()
    skill_dir = md_path.parent
    if not md_path.is_file():
        return {
            "dir": skill_dir,
            "md": md_path,
            "text": "",
            "frontmatter": {},
            "fm_error": "SKILL.md not found",
            "body": "",
            "body_line": 1,
        }
    md = md_path
    text = read_text(md)
    fm_text, body, body_line = split_frontmatter(text)
    fm = {}
    fm_error = None
    if fm_text is None:
        fm_error = "No YAML frontmatter found"
    else:
        try:
            fm = parse_yaml(fm_text)
            if not isinstance(fm, dict):
                fm_error = "Frontmatter must be a YAML mapping"
                fm = {}
        except Exception as exc:  # noqa: BLE001
            fm_error = "Invalid YAML: " + str(exc)
            fm = {}
    return {
        "dir": skill_dir,
        "md": md,
        "text": text,
        "frontmatter": fm,
        "fm_error": fm_error,
        "body": body,
        "body_line": body_line,
    }


def load_skill(skill_dir):
    skill_dir = Path(skill_dir).resolve()
    return load_skill_file(skill_dir / "SKILL.md")


def estimate_tokens(text):
    cjk = len(CJK_RE.findall(text))
    words = len(WORD_RE.findall(text))
    return int(cjk + words * 1.3 + len(text) * 0.02)


def add(findings, level, code, message, path=None, line=None):
    findings.append(Finding(level, code, message, path, line))


PATH_RE = re.compile(r"`((?:references|scripts|assets)/[^`\s]+)`")


def check_links_in_file(skill_dir, path, text, findings, line_offset=0):
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0].strip()
        if not target:
            continue
        if re.match(r"^[A-Za-z]:[\\/]", target) or target.startswith("/"):
            continue
        candidates = [
            (path.parent / target).resolve(),
            (skill_dir / target).resolve(),
        ]
        if not any(candidate.exists() for candidate in candidates):
            line = line_offset + text[:match.start()].count("\n") + 1
            add(findings, "FAIL", "link.broken",
                "Broken local link: " + target, path, line)
    for match in PATH_RE.finditer(text):
        target = match.group(1).strip().rstrip(".,;:)")
        if "*" in target or "?" in target:
            continue
        resolved = (skill_dir / target).resolve()
        if not resolved.exists():
            line = line_offset + text[:match.start()].count("\n") + 1
            add(findings, "FAIL", "path.broken",
                "Broken path reference: " + target, path, line)


def check_all_links(skill, findings):
    skill_dir = skill["dir"]
    check_links_in_file(
        skill_dir, skill["md"], skill["body"], findings,
        skill["body_line"] - 1,
    )
    refs = skill_dir / "references"
    if refs.is_dir():
        for ref in sorted(refs.rglob("*.md")):
            check_links_in_file(skill_dir, ref, read_text(ref), findings, 0)


def check_scripts(skill_dir, findings):
    scripts = skill_dir / "scripts"
    if not scripts.is_dir():
        return 0
    count = 0
    for path in sorted(scripts.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".py":
            count += 1
            try:
                ast.parse(read_text(path))
            except SyntaxError as exc:
                add(findings, "FAIL", "script.syntax",
                    "Python syntax error: " + str(exc), path, exc.lineno)
            except Exception as exc:  # noqa: BLE001
                add(findings, "FAIL", "script.read",
                    "Cannot read Python script: " + str(exc), path)
        elif path.suffix in {".js", ".mjs", ".cjs", ".ts", ".ps1", ".bat", ".cmd", ".sh"}:
            count += 1
            if path.stat().st_size == 0:
                add(findings, "FAIL", "script.empty",
                    "Script is empty", path)
    return count


def check_ascii(skill_dir, findings):
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES:
            continue
        data = path.read_bytes()
        if any(byte > 127 for byte in data):
            add(findings, "WARN", "code.non_ascii",
                "Non-ASCII byte in a code or config file; move the text to a "
                ".md/.txt data file and read it at runtime", path)


def check_extraneous(skill_dir, public, findings):
    readme = skill_dir / "README.md"
    if readme.is_file() and not public:
        add(findings, "WARN", "file.readme_internal",
            "README.md in an internal skill; keep it in the build output or use --public",
            readme)
    if public and not readme.is_file():
        add(findings, "FAIL", "file.public_readme",
            "Public skill must have README.md at the skill root", skill_dir)
    for name in sorted(EXTRA_DOCS):
        path = skill_dir / name
        if path.is_file():
            add(findings, "WARN", "file.extra_doc",
                "Extraneous documentation in a skill: " + name, path)
    for name, level, code in (
        ("__pycache__", "WARN", "file.cache"),
        ("node_modules", "WARN", "file.modules"),
        (".git", "WARN", "file.git"),
        (".env", "FAIL", "file.env"),
        ("secrets", "FAIL", "file.secrets"),
    ):
        for path in skill_dir.rglob(name):
            add(findings, level, code,
                "Forbidden or build-only path: " + name, path)


def normalized_lines(text):
    for index, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"\s+", " ", raw.strip())
        if len(line) >= 40 and not line.startswith(("#", "```")):
            yield line, index


def check_duplicates(skill_dir, body, findings, body_line=1):
    seen = {}
    offset = max(0, body_line - 1)
    for line, index in normalized_lines(body):
        full_line = index + offset
        if line in seen:
            add(findings, "WARN", "content.duplicate",
                "Repeated line in SKILL.md (also line " + str(seen[line]) + ")",
                skill_dir / "SKILL.md", full_line)
        else:
            seen[line] = full_line
    refs = skill_dir / "references"
    if not refs.is_dir():
        return
    for ref in sorted(refs.glob("*.md")):
        for line, index in normalized_lines(read_text(ref)):
            if line in seen:
                add(findings, "WARN", "content.duplicate_ref",
                    "Line duplicates SKILL.md line " + str(seen[line])
                    + "; keep one source", ref, index)


def iter_text_files(skill_dir):
    suffixes = {
        ".md", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".ps1",
        ".bat", ".cmd", ".json", ".yaml", ".yml", ".toml", ".sh", ".txt",
    }
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path, read_text(path)


def check_secrets(skill_dir, findings):
    patterns = [
        ("FAIL", "secret.private_key",
         re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "Private key block"),
        ("FAIL", "secret.token",
         re.compile(r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|"
                    r"github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b"),
         "Token-like string"),
        ("WARN", "secret.assignment",
         re.compile(r"(?i)\b(api[_-]?key|password|secret|token)\s*[:=]\s*"
                    r"[\"']?[A-Za-z0-9_\-]{12,}"),
         "Possible credential assignment"),
    ]
    for path, text in iter_text_files(skill_dir):
        for level, code, pattern, label in patterns:
            for match in pattern.finditer(text):
                line = text[:match.start()].count("\n") + 1
                add(findings, level, code, label + " detected", path, line)


def load_extra_patterns(path):
    patterns = []
    if not path:
        return patterns
    source = Path(path)
    if not source.is_file():
        return patterns
    for line in read_text(source).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line))
        except re.error:
            continue
    return patterns


def check_pii(skill_dir, public, allow_local_paths, extra_patterns, findings):
    patterns = [
        ("path.windows", re.compile(r"\b[A-Za-z]:\\"), "path"),
        ("path.profile", re.compile(r"\bC:\\Users\\", re.I), "path"),
        ("path.macos", re.compile(r"/Users/[A-Za-z0-9._-]+"), "path"),
        ("pii.email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "pii"),
    ]
    for path, text in iter_text_files(skill_dir):
        for code, pattern, kind in patterns:
            for match in pattern.finditer(text):
                line = text[:match.start()].count("\n") + 1
                if kind == "path" and allow_local_paths:
                    level = "WARN"
                elif public:
                    level = "FAIL"
                else:
                    level = "WARN"
                add(findings, level, code,
                    "Local path or email; desensitize before publishing", path, line)
        for pattern in extra_patterns:
            for match in pattern.finditer(text):
                line = text[:match.start()].count("\n") + 1
                level = "FAIL" if public else "WARN"
                add(findings, level, "pii.custom",
                    "Custom site-specific identifier; desensitize before publishing",
                    path, line)


def validate_skill(skill_dir, public=False, strict=False, allow_local_paths=False,
                   pii_patterns=None):
    skill = load_skill(skill_dir)
    findings = []
    skill_dir = skill["dir"]
    extra_patterns = load_extra_patterns(pii_patterns)
    if skill["fm_error"]:
        add(findings, "FAIL", "frontmatter", skill["fm_error"], skill["md"])
        fm = {}
    else:
        fm = skill["frontmatter"]
        if yaml is None:
            add(findings, "WARN", "frontmatter.fallback",
                "PyYAML is not installed; using the fallback parser. "
                "Complex frontmatter may not validate the same way.", skill["md"])

    name = fm.get("name")
    description = fm.get("description")
    if not isinstance(name, str) or not name.strip():
        add(findings, "FAIL", "name.missing", "Missing or non-string name", skill["md"])
        name = ""
    else:
        name = name.strip()
        if not NAME_RE.match(name):
            add(findings, "FAIL", "name.format",
                "Name must be lowercase kebab-case: " + name, skill["md"])
        if len(name) > 64:
            add(findings, "FAIL", "name.length",
                "Name is longer than 64 characters", skill["md"])
        if name != skill_dir.name:
            add(findings, "FAIL", "name.directory",
                "Name does not match directory: " + skill_dir.name, skill["md"])

    if not isinstance(description, str) or not description.strip():
        add(findings, "FAIL", "description.missing",
            "Missing or non-string description", skill["md"])
        description = ""
    else:
        description = description.strip()
        if len(description) > 1024:
            add(findings, "FAIL", "description.length",
                "Description is longer than 1024 characters", skill["md"])
        if len(description) < 20:
            add(findings, "WARN", "description.short",
                "Description is short; add what it does and when to load it", skill["md"])
        if "<" in description or ">" in description:
            add(findings, "FAIL", "description.angle",
                "Description must not contain angle brackets", skill["md"])
        if not TRIGGER_RE.search(description):
            add(findings, "WARN", "description.trigger",
                "Description has no clear trigger cue (e.g. 'Use when ...')", skill["md"])
        if not NEGATIVE_RE.search(description):
            add(findings, "WARN", "description.negative",
                "Description has no 'do not use for ...' boundary", skill["md"])
        desc_tokens = estimate_tokens(description)
        if desc_tokens > 150:
            add(findings, "WARN", "description.tokens",
                "Description is about " + str(desc_tokens) + " tokens; target is 150",
                skill["md"])

    if not skill["body"].strip():
        add(findings, "FAIL", "body.empty", "SKILL.md body is empty", skill["md"])
    body_lines = skill["body"].count("\n") + 1
    if body_lines > 500:
        add(findings, "FAIL", "body.lines",
            "Body is " + str(body_lines) + " lines; hard cap is 500", skill["md"])
    elif body_lines > 300:
        add(findings, "WARN", "body.lines_warn",
            "Body is " + str(body_lines) + " lines; target is 300 or fewer", skill["md"])
    body_tokens = estimate_tokens(skill["body"])
    if body_tokens > 8000:
        add(findings, "WARN", "body.tokens",
            "Body is about " + str(body_tokens) + " tokens; target is 8k or fewer",
            skill["md"])

    if fm.get("license") is None:
        add(findings, "WARN", "license.missing",
            "No license field; public skills need one", skill["md"])
    compatibility = fm.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or len(compatibility) > 500
    ):
        add(findings, "WARN", "compatibility.format",
            "Compatibility should be a string of at most 500 characters", skill["md"])

    check_all_links(skill, findings)
    script_count = check_scripts(skill_dir, findings)
    check_ascii(skill_dir, findings)
    check_extraneous(skill_dir, public, findings)
    check_duplicates(skill_dir, skill["body"], findings, skill["body_line"])
    check_secrets(skill_dir, findings)
    check_pii(skill_dir, public, allow_local_paths, extra_patterns, findings)

    refs = skill_dir / "references"
    ref_count = len(list(refs.glob("*.md"))) if refs.is_dir() else 0
    if script_count > 3:
        add(findings, "WARN", "budget.scripts",
            "Script count is " + str(script_count) + "; target is 3 or fewer", skill_dir)
    if ref_count > 3:
        add(findings, "WARN", "budget.references",
            "Reference count is " + str(ref_count) + "; target is 3 or fewer", skill_dir)

    placeholder_words = ["TO" + "DO", "TB" + "D", "FIX" + "ME", "XX" + "X"]
    placeholders = re.compile(
        r"\b(" + "|".join(placeholder_words) + r")\b|"
        r"\[place" + r"holder\]"
    )
    for path, text in iter_text_files(skill_dir):
        for match in placeholders.finditer(text):
            line = text[:match.start()].count("\n") + 1
            add(findings, "WARN", "content.placeholder",
                "Placeholder text: " + match.group(0), path, line)

    errors = [f for f in findings if f.level == "FAIL"]
    warnings = [f for f in findings if f.level == "WARN"]
    status = "fail" if errors else ("warn" if warnings else "pass")
    if strict and warnings:
        status = "fail"

    file_count = sum(1 for p in skill_dir.rglob("*") if p.is_file())
    total_bytes = sum(p.stat().st_size for p in skill_dir.rglob("*") if p.is_file())
    metrics = {
        "name": name,
        "description_chars": len(description),
        "description_tokens": estimate_tokens(description),
        "body_lines": body_lines,
        "body_tokens": estimate_tokens(skill["body"]),
        "scripts": script_count,
        "references": ref_count,
        "files": file_count,
        "bytes": total_bytes,
        "status": status,
    }
    return {
        "skill": str(skill_dir),
        "status": status,
        "errors": [f.as_dict() for f in errors],
        "warnings": [f.as_dict() for f in warnings],
        "findings": [f.as_dict() for f in findings],
        "metrics": metrics,
    }


def collect_skills(roots):
    seen = set()
    skills = []
    for root in roots:
        root = Path(root).expanduser()
        if not root.exists():
            continue
        resolved_root = root.resolve()
        candidates = list(root.rglob("SKILL.md")) + list(root.glob("*.md"))
        for path in candidates:
            if path.name.lower() == "readme.md":
                continue
            resolved = path.resolve()
            try:
                relative_parts = resolved.relative_to(resolved_root).parts
            except ValueError:
                relative_parts = resolved.parts
            if any(part.startswith(".") or part in ("node_modules", "__pycache__")
                   for part in relative_parts):
                continue
            if path.name != "SKILL.md":
                try:
                    head = read_text(path)[:4]
                except Exception:  # noqa: BLE001
                    head = ""
                if not head.startswith("---"):
                    continue
            if resolved in seen:
                continue
            seen.add(resolved)
            skills.append(resolved)
    return skills


def default_skills_roots():
    home = Path.home()
    candidates = [
        home / ".config" / "opencode" / "skills",
        home / ".claude" / "skills",
        home / ".agents" / "skills",
    ]
    current = Path.cwd()
    for base in (current, *current.parents):
        for name in (".opencode/skills", ".claude/skills", ".agents/skills"):
            candidates.append(base / name)
        if (base / ".git").exists():
            break
    result = []
    seen = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def skill_id(path):
    return path.parent.name if path.name == "SKILL.md" else path.stem


def stem(word):
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ing") and len(word) > 5:
        return word[:-3]
    if word.endswith("ed") and len(word) > 4:
        return word[:-2]
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if (word.endswith("s") and not word.endswith(("ss", "us", "is"))
            and len(word) > 3):
        return word[:-1]
    return word


def description_tokens(text):
    tokens = set()
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) >= 3 and word not in STOPWORDS:
            tokens.add(stem(word))
    cjk = "".join(CJK_RE.findall(text))
    for index in range(len(cjk) - 1):
        tokens.add(cjk[index:index + 2])
    return tokens


def jaccard(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def scan_skill(skill_dir, roots, threshold=0.35, top=5, ignore_invalid=False):
    skill_dir = Path(skill_dir).resolve()
    target = load_skill(skill_dir)
    target_id = skill_id(skill_dir / "SKILL.md")
    target_name = (target["frontmatter"].get("name") or target_id)
    target_desc = target["frontmatter"].get("description") or ""
    if not isinstance(target_desc, str):
        target_desc = ""
    if not isinstance(target_name, str):
        target_name = target_id
    target_tokens = description_tokens(target_desc)

    collisions = []
    similar = []
    invalid = []
    all_skills = collect_skills(roots)
    for path in all_skills:
        if path == (skill_dir / "SKILL.md").resolve():
            continue
        other = load_skill_file(path)
        if other["fm_error"]:
            invalid.append({"path": str(path), "error": other["fm_error"]})
            continue
        fm = other["frontmatter"]
        other_id = skill_id(path)
        other_name = fm.get("name") or other_id
        other_desc = fm.get("description") or ""
        if not isinstance(other_name, str):
            other_name = other_id
        if not isinstance(other_desc, str):
            other_desc = ""
        problems = []
        if other_id.lower() == target_id.lower():
            problems.append("same directory id: " + other_id)
        if str(other_name).lower() == str(target_name).lower():
            problems.append("same frontmatter name: " + str(other_name))
        if other_desc and other_desc == target_desc:
            problems.append("identical description")
        if problems:
            collisions.append({"path": str(path), "id": other_id,
                               "name": other_name, "problems": problems})
        score = jaccard(target_tokens, description_tokens(other_desc))
        if score >= threshold:
            shared = sorted(target_tokens & description_tokens(other_desc))
            similar.append({"path": str(path), "id": other_id,
                            "name": other_name, "score": round(score, 3),
                            "shared": shared[:12]})

    similar.sort(key=lambda item: item["score"], reverse=True)
    similar = similar[:top]
    invalid_blocks = bool(invalid) and not ignore_invalid
    status = "fail" if collisions else (
        "warn" if similar or invalid_blocks else "pass"
    )
    return {
        "skill": str(skill_dir),
        "status": status,
        "collisions": collisions,
        "similar": similar,
        "invalid": invalid,
        "invalid_count": len(invalid),
        "threshold": threshold,
        "scanned": len(all_skills),
    }


def package_skill(skill_dir, out_dir, public=False, strict=False, dry_run=False,
                  scan=True, include_evals=False, pii_patterns=None):
    skill_dir = Path(skill_dir).resolve()
    result = validate_skill(skill_dir, public=public, strict=strict,
                            pii_patterns=pii_patterns)
    if result["status"] == "fail":
        for finding in result["findings"]:
            if finding["level"] == "FAIL":
                print(Finding(**finding).render())
        print("Packaging blocked: validation failed.")
        return 1
    for finding in result["findings"]:
        if finding["level"] == "WARN":
            print(Finding(**finding).render())

    if scan:
        roots = default_skills_roots()
        if roots:
            scan_result = scan_skill(skill_dir, roots)
            for item in scan_result["collisions"]:
                print("FAIL collision: " + item["path"] + " -> "
                      + "; ".join(item["problems"]))
            for item in scan_result["similar"]:
                print("WARN similar (" + str(item["score"]) + "): " + item["path"])
            if scan_result["invalid_count"]:
                print("WARN invalid: " + str(scan_result["invalid_count"])
                      + " skill(s) skipped; collisions may be missed")
            if scan_result["status"] == "fail":
                print("Packaging blocked: conflict scan failed.")
                return 1
        else:
            print("INFO scan skipped: no skills roots found")

    exclude_dirs = set(EXCLUDE_DIRS)
    if include_evals:
        exclude_dirs.discard("evals")
    announced_evals = False
    announced_dist = False
    files = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir)
        if any(part in exclude_dirs for part in rel.parts):
            if "evals" in rel.parts and not include_evals and not announced_evals:
                print("Excluded: evals (use --include-evals to keep)")
                announced_evals = True
            if "dist" in rel.parts and not announced_dist:
                print("Excluded: dist (package output directory)")
                announced_dist = True
            continue
        if path.name in EXCLUDE_NAMES or path.suffix in EXCLUDE_SUFFIXES:
            continue
        if path.name.startswith("~$"):
            continue
        files.append(path)

    if dry_run:
        print("Files to package (" + str(len(files)) + "):")
        for path in files:
            print("  " + str(path.relative_to(skill_dir)))
        return 0

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / (skill_dir.name + ".skill")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            arcname = Path(skill_dir.name) / path.relative_to(skill_dir)
            archive.write(path, str(arcname))
    print("Packaged " + str(target) + " (" + str(len(files)) + " files, "
          + str(target.stat().st_size) + " bytes)")
    return 0


def print_validation(result, as_json):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("Skill: " + result["skill"])
    for finding in result["findings"]:
        print(Finding(**finding).render())
    metrics = result["metrics"]
    print("Status: " + result["status"])
    print("Metrics: " + ", ".join(
        key + "=" + str(value) for key, value in metrics.items()))


def main():
    parser = argparse.ArgumentParser(description="Validate, scan, and package agent skills")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("skill_dir")
    validate.add_argument("--public", action="store_true")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")
    validate.add_argument("--allow-local-paths", action="store_true")
    validate.add_argument("--pii-patterns", default=None)

    scan = sub.add_parser("scan")
    scan.add_argument("skill_dir")
    scan.add_argument("--skills-root", action="append", default=[])
    scan.add_argument("--threshold", type=float, default=0.35)
    scan.add_argument("--top", type=int, default=5)
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--strict", action="store_true")
    scan.add_argument("--ignore-invalid", action="store_true")

    package = sub.add_parser("package")
    package.add_argument("skill_dir")
    package.add_argument("out_dir")
    package.add_argument("--public", action="store_true")
    package.add_argument("--strict", action="store_true")
    package.add_argument("--dry-run", action="store_true")
    package.add_argument("--skip-scan", action="store_true")
    package.add_argument("--include-evals", action="store_true")
    package.add_argument("--pii-patterns", default=None)

    args = parser.parse_args()
    if args.command == "validate":
        result = validate_skill(
            args.skill_dir, public=args.public, strict=args.strict,
            allow_local_paths=args.allow_local_paths,
            pii_patterns=args.pii_patterns,
        )
        print_validation(result, args.json)
        return 1 if result["status"] == "fail" else 0
    if args.command == "scan":
        roots = args.skills_root or default_skills_roots()
        result = scan_skill(args.skill_dir, roots, args.threshold, args.top,
                            args.ignore_invalid)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Skill: " + result["skill"])
            print("Scanned: " + str(result["scanned"]))
            for item in result["collisions"]:
                print("FAIL collision: " + item["path"] + " -> " + "; ".join(item["problems"]))
            for item in result["similar"]:
                print("WARN similar (" + str(item["score"]) + "): " + item["path"]
                      + " shared=" + ", ".join(item["shared"]))
            for item in result["invalid"]:
                print("INFO skipped: " + item["path"] + " (" + item["error"] + ")")
            if result["invalid_count"]:
                print("WARN invalid: " + str(result["invalid_count"])
                      + " skill(s) skipped; collisions may be missed")
            print("Status: " + result["status"])
        failed = result["status"] == "fail"
        if args.strict and result["status"] == "warn":
            failed = True
        return 1 if failed else 0
    return package_skill(
        args.skill_dir, args.out_dir, public=args.public,
        strict=args.strict, dry_run=args.dry_run,
        scan=not args.skip_scan, include_evals=args.include_evals,
        pii_patterns=args.pii_patterns,
    )


if __name__ == "__main__":
    sys.exit(main())
