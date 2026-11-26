#!/usr/bin/env python3
"""ATS score check for generated resumes (heuristic rubric, not a certified scorer).

Mirrors what commercial ATS scorers measure mechanically: parseability of the
text layer, standard section headers, literal contact details, date coverage,
and exact keyword coverage against target role families.

Usage: python3 tools/check_ats_score.py cv/prep_resume/<file>.pdf
"""
import re
import subprocess
import sys

CONTACT = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone": r"\+?\d[\d ()-]{8,}\d",
    "location": r"Bangkok",
}
SECTIONS = ["summary", "skills", "professional experience", "education"]
DATE_RX = re.compile(r"\b(0?[1-9]|1[0-2])/20\d{2}\b")

# Target role families = the titles actually applied to (CLAUDE.md, 2026-11-10).
FAMILIES = {
    "DevOps": [
        "devops", "ci/cd", "terraform", "ansible", "docker", "kubernetes",
        "aws", "gitlab ci", "github actions", "linux", "monitoring",
        "ec2", "s3", "vpc", "cloudfront", "dynamodb", "helm", "infrastructure as code",
    ],
    "SRE": [
        "sre", "site reliability", "slo", "on-call", "incident response",
        "postmortem", "runbook", "prometheus", "grafana", "reliability",
    ],
    "Platform/DevEx": [
        "platform", "developer experience", "internal tooling", "ci/cd",
        "developer productivity", "tooling",
    ],
    "AI/LLMOps": [
        "ai integration", "llm", "rag", "mcp", "ai agents", "claude",
        "openai", "groq", "litellm", "pgvector", "prompt", "ollama",
    ],
    "Backend": [
        "node.js", "python", "php", "postgresql", "api", "microservices",
        "rest", "sql",
    ],
}


def extract(path: str) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", path, "-"], capture_output=True, text=True
    )
    if r.returncode != 0:
        sys.exit(f"pdftotext failed: {r.stderr.strip()}")
    return r.stdout


def main(path: str) -> int:
    text = extract(path)
    low = text.lower()
    # ATS parsers normalize whitespace before matching; do the same for keywords.
    norm = re.sub(r"\s+", " ", low)
    findings, score = [], 0.0

    # Parseability (40)
    pages = 1 + low.count("\f") if "\f" in low else 1
    info = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", info)
    pages = int(m.group(1)) if m else pages
    if pages == 2:
        score += 10
    else:
        findings.append(f"pages={pages}, want exactly 2")
    bad = len(re.findall(r"\(cid:|\ufffd", text))
    if bad == 0:
        score += 10
    else:
        findings.append(f"{bad} broken glyphs in text layer")
    for name, rx in CONTACT.items():
        if re.search(rx, text, re.I):
            score += 6
        else:
            findings.append(f"contact {name} not literal in text layer")

    # Section headers (15)
    for s in SECTIONS:
        if re.search(rf"^\s*{s}\s*$", low, re.M):
            score += 15 / len(SECTIONS)
        else:
            findings.append(f"missing standard section header: {s!r}")

    # Date coverage (10): one MM/YYYY per experience role, >=6 total
    dates = len(DATE_RX.findall(text))
    score += min(dates, 8) / 8 * 10
    if dates < 6:
        findings.append(f"only {dates} MM/YYYY dates found")

    # Keyword families (35)
    per_family = {}
    for fam, kws in FAMILIES.items():
        hit = sum(
            1 for k in kws if re.search(rf"\b{re.escape(k)}(?:es|s)?\b", norm)
        )
        per_family[fam] = (hit, len(kws))
        score += hit / len(kws) * (35 / len(FAMILIES))
        if hit < len(kws):
            missing = [k for k in kws if not re.search(rf"\b{re.escape(k)}\b", low)]
            findings.append(f"{fam} keywords missing: {', '.join(missing)}")

    print(f"ATS score: {score:.1f}/100  ({path})")
    for fam, (hit, total) in per_family.items():
        print(f"  {fam:15} {hit}/{total}")
    for f in findings:
        print(f"  ! {f}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
