# app/services/resume_parser.py
"""
Deterministic resume parser + suspicious-claim heuristics.

Exports:
- parse_resume_text(text: str, original_layout: dict = None) -> dict
  Returns Stage C schema:
  {
    "contact": {...},
    "skills": [...],
    "experience": [{company, title, start, end, bullets, metrics: [...]}, ...],
    "education": [...],
    "certs": [...],
    "suspicious_claims": [...],
    "original_layout": {...},
    "confidence": 0.0-1.0
  }
"""

import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from dateutil import parser as dateutil_parser  # lightweight date parsing
import math

# Useful taggers & patterns
YEAR_RE = re.compile(r'(?P<start>\d{4})(?:\s*[-–—]\s*(?P<end>\d{4}|Present|present|Now|now|Current))?')
PERCENT_RE = re.compile(r'(\d+(?:\.\d+)?%)')
MONEY_RE = re.compile(r'(\$\s?\d{1,3}(?:[,\d{3}])*(?:\.\d+)?)')
NUMBER_RE = re.compile(r'(\d+(?:\+|k|M)?(?:\.\d+)?)\b')
DURATION_YEARS_RE = re.compile(r'(\d+)\s+years?')

# Section heading keywords
SECTION_ALIASES = {
    "experience": ["experience", "work experience", "professional experience", "employment history", "work history"],
    "skills": ["skills", "technical skills", "skills & tools", "core skills"],
    "education": ["education", "academic", "qualifications"],
    "certifications": ["certifications", "certificates", "licenses"],
    "projects": ["projects", "selected projects"],
    "summary": ["summary", "professional summary", "profile", "about me"]
}

def _normalize_heading(h: str) -> str:
    s = h.strip().lower()
    # remove punctuation
    s = re.sub(r'[^a-z0-9 &]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    for key, aliases in SECTION_ALIASES.items():
        for a in aliases:
            if a in s:
                return key
    return s

def split_into_sections(text: str) -> Dict[str, str]:
    """
    Split text into sections using common headings. Returns dict mapping normalized_heading -> section_text.
    If no headings found, returns {"body": text}.
    """
    lines = [l.rstrip() for l in text.splitlines()]
    headings = []
    # detect lines that look like headings (short, often uppercase or titlecase)
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        # skip obvious bullet lines — they are not section headings
        if line.strip().startswith(('-', '•', '*')):
            continue
        # heuristics: short line (<=5 words), contains keyword, or all caps
        words = line.strip().split()
        low = line.strip().lower()
        is_heading = False
        if len(words) <= 6 and (line.strip().isupper() or any(keyword in low for group in SECTION_ALIASES.values() for keyword in group)):
            is_heading = True
        # also headings that end with ":" or are underlined by === or ---
        next_line = lines[idx+1] if idx+1 < len(lines) else ""
        if line.strip().endswith(':') or re.match(r'^[\-=_]{3,}$', next_line.strip()):
            is_heading = True
        if is_heading:
            headings.append((idx, line.strip()))
    if not headings:
        return {"body": text}

    sections = {}
    # build ranges
    for i, (idx, head) in enumerate(headings):
        start = idx + 1
        end = headings[i+1][0] if i+1 < len(headings) else len(lines)
        sec_text = "\n".join(lines[start:end]).strip()
        normalized = _normalize_heading(head)
        if normalized in sections:
            # append if repeated heading
            sections[normalized] += "\n\n" + sec_text
        else:
            sections[normalized] = sec_text
    return sections

def extract_contact(text: str) -> Dict[str, Optional[str]]:
    """
    Try to extract name, email, phone, location heuristically from top of resume.
    """
    email_re = re.compile(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')
    phone_re = re.compile(r'(\+?\d[\d\s\-\(\)]{6,}\d)')
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return {"name": None, "email": None, "phone": None, "location": None}
    # assume header is first 8 lines
    header = "\n".join(lines[:8])
    email = email_re.search(header)
    phone = phone_re.search(header)
    # avoid mistaking date ranges for phone numbers
    if phone and YEAR_RE.search(phone.group(1)):
        phone = None
    # heuristic name: first non-empty line that is not email or phone
    name = None
    for l in lines[:4]:
        if '@' in l or re.search(r'\d', l):
            continue
        # skip common section headings (Experience, Skills, Education, etc.)
        if _normalize_heading(l) in SECTION_ALIASES:
            continue
        # skip common words
        if len(l.split()) <= 6 and len(l) > 1:
            name = l
            break
    # location heuristic: last line in header without digits and not an email
    location = None
    for l in reversed(lines[:6]):
        if '@' in l or re.search(r'\d', l):
            continue
        if len(l.split()) <= 5:
            location = l
            break
    return {
        "name": name,
        "email": email.group(1) if email else None,
        "phone": phone.group(1) if phone else None,
        "location": location
    }

def extract_skills_from_section(skills_text: str) -> List[str]:
    """
    Split skills section by commas/lines and normalize.
    """
    if not skills_text:
        return []
    # Often skills are comma-separated or newline separated or bullet lists
    parts = re.split(r'[\n•\u2022\-•]+', skills_text)
    tokens = []
    for p in parts:
        for tok in re.split(r'[,\|;/]+', p):
            s = tok.strip()
            if not s:
                continue
            # normalize multiple spaces
            s = re.sub(r'\s+', ' ', s)
            tokens.append(s)
    # dedupe preserving order
    seen = set()
    out = []
    for t in tokens:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out

def split_experience_entries(exp_text: str) -> List[str]:
    """
    Heuristic splitting of experience section into entries.
    Splits on double-newline or lines that look like company + date patterns.
    """
    if not exp_text:
        return []
    # first try splitting on double newlines
    blocks = [b.strip() for b in re.split(r'\n{2,}', exp_text) if b.strip()]
    # further split blocks that contain multiple entries by seeing lines with year ranges
    entries = []
    for block in blocks:
        # find all indexes of lines that contain year patterns
        lines = [l for l in block.splitlines() if l.strip()]
        split_idxs = []
        for i, l in enumerate(lines):
            if YEAR_RE.search(l):
                split_idxs.append(i)
        if split_idxs and len(split_idxs) > 1:
            # cut into chunks at each split idx
            for i, idx in enumerate(split_idxs):
                start = idx
                end = split_idxs[i+1] if i+1 < len(split_idxs) else len(lines)
                chunk = "\n".join(lines[start:end]).strip()
                if chunk:
                    entries.append(chunk)
        else:
            entries.append(block)
    return [e for e in entries if e]

def parse_experience_entry(text: str) -> Dict[str, any]:
    """
    Parse a single experience chunk into company, title, start, end, bullets, metrics.
    Uses heuristics:
      - first line may contain "Title at Company (dates)" or "Company — Title (dates)"
      - bullets are lines starting with '-' or '•' or plain lines following the header
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    header = lines[0] if lines else ""
    # try to extract dates from header or second line
    start = end = None
    # search for YEAR_RE in header or anywhere in first two lines
    for l in lines[:2]:
        m = YEAR_RE.search(l)
        if m:
            start = m.group('start')
            end = m.group('end') or None
            break
    # try to extract company/title
    company = None
    title = None
    # common patterns: "Title — Company", "Company — Title", "Title, Company"
    if ' at ' in header:
        parts = header.split(' at ', 1)
        title, company = parts[0].strip(), parts[1].strip()
    elif ' - ' in header or ' — ' in header:
        parts = re.split(r'\s+[-—–]\s+', header)
        if len(parts) >= 2:
            # decide which is company by presence of 'Inc' 'LLC' or capitalized words
            left, right = parts[0].strip(), parts[1].strip()
            if any(x in right for x in ['Inc', 'LLC', 'Ltd', 'GmbH']):
                title, company = left, right
            else:
                # heuristic: longer segment is company
                if len(left) < len(right):
                    title, company = left, right
                else:
                    company, title = left, right
    elif ',' in header:
        parts = [p.strip() for p in header.split(',')]
        if len(parts) >= 2:
            title, company = parts[0], parts[1]
    else:
        # fallback: company might be second line
        if len(lines) >= 2 and YEAR_RE.search(lines[1]):
            company = lines[0]
            # title attempt in second line
            title = None
        elif len(lines) >= 2:
            title = lines[0]
            company = lines[1]
        else:
            title = header
            company = None

    # bullets: following lines that start with bullet chars or that are sentences
    bullets = []
    for l in lines[1:]:
        if l.startswith(('-', '•', '*')):
            bullets.append(l.lstrip('-•* ').strip())
        else:
            # treat as bullet if it's a sentence and not a date line
            if YEAR_RE.search(l):
                # skip date-only lines
                continue
            bullets.append(l)

    # metrics extraction
    metrics = []
    for b in bullets:
        found = []
        for m in PERCENT_RE.finditer(b):
            found.append({'type': 'percent', 'raw': m.group(1)})
        for m in MONEY_RE.finditer(b):
            found.append({'type': 'money', 'raw': m.group(1)})
        for m in NUMBER_RE.finditer(b):
            found.append({'type': 'number', 'raw': m.group(1)})
        metrics.extend(found)

    return {
        "company": company,
        "title": title,
        "start": start,
        "end": end if end and end.lower() not in ('present','now','current') else (None if (end and end.lower() in ('present','now','current')) else None),
        "bullets": bullets,
        "metrics": metrics
    }

def detect_suspicious_claims(experiences: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """
    Heuristics:
    - overlapping date ranges among full-time (if start/end present)
    - impossible durations (e.g., degree durations unrealistic could be derived from education but we have only experiences)
    - suspicious aggregate years > plausible (e.g., claimed 20 years but resume indicates < 10)
    Returns list of suspects with reason and confidence (0-1).
    """
    claims = []
    # build ranges [ (start_year, end_year, idx) ]
    ranges = []
    for i, e in enumerate(experiences):
        s = e.get("start")
        eend = e.get("end")
        if s and s.isdigit():
            syear = int(s)
            if eend and eend.isdigit():
                eyear = int(eend)
            else:
                eyear = datetime.utcnow().year
            if syear <= eyear:
                ranges.append((syear, eyear, i))
    # check overlaps
    ranges_sorted = sorted(ranges, key=lambda x: x[0])
    for i in range(len(ranges_sorted)-1):
        s1, e1, idx1 = ranges_sorted[i]
        s2, e2, idx2 = ranges_sorted[i+1]
        if s2 <= e1:
            claims.append({
                "text": f"Overlapping dates between experiences index {idx1} and {idx2}",
                "reason": f"Ranges {s1}-{e1} and {s2}-{e2} overlap",
                "confidence": 0.7
            })
    # unrealistic quick progressions (e.g., many promotions in very short time)
    # count average tenure
    if ranges:
        total_years = sum((r[1]-r[0]+1) for r in ranges)
        avg = total_years / len(ranges)
        if avg < 0.5:
            claims.append({
                "text": "Average job tenure suspiciously low",
                "reason": f"Average tenure ~{avg:.2f} years",
                "confidence": 0.6
            })
    return claims

def compute_confidence(parsed: Dict[str, any]) -> float:
    """
    Heuristic confidence: fraction of sections found, presence of contact and at least 1 experience/skill.
    Returns between 0 and 1.
    """
    score = 0.0
    if parsed.get("contact") and (parsed["contact"].get("email") or parsed["contact"].get("name")):
        score += 0.3
    if parsed.get("skills"):
        score += 0.25
    if parsed.get("experience"):
        score += 0.3
    if parsed.get("education"):
        score += 0.05
    # cap
    return min(1.0, score)

def parse_resume_text(text: str, original_layout: Optional[Dict] = None) -> Dict[str, any]:
    """
    Main entry for parsing resume text.
    """
    if not text:
        return {
            "contact": {},
            "skills": [],
            "experience": [],
            "education": [],
            "certs": [],
            "suspicious_claims": [],
            "original_layout": original_layout or {},
            "confidence": 0.0
        }

    sections = split_into_sections(text)

    # contact: prefer the top-of-document header (first lines) for name/email extraction.
    # If that yields nothing, fall back to the 'summary' section or the body.
    header_text = "\n".join(text.splitlines()[:8])
    contact = extract_contact(header_text)
    if (not contact.get("email") and not contact.get("name")):
        # try summary first, then body
        if "summary" in sections:
            contact = extract_contact(sections.get("summary", ""))
        elif "body" in sections:
            contact = extract_contact("\n".join(sections.get("body", "").splitlines()[:8]))

    # skills
    skills = []
    if "skills" in sections:
        skills = extract_skills_from_section(sections["skills"])
    else:
        # attempt to find inline "Skills:" tokens in body
        m = re.search(r'(Skills[:\s]+)(.+)', text, flags=re.IGNORECASE)
        if m:
            skills = extract_skills_from_section(m.group(2))

    # experience
    experiences = []
    if "experience" in sections:
        exp_text = sections["experience"]
        entries = split_experience_entries(exp_text)
        for e in entries:
            experiences.append(parse_experience_entry(e))
    else:
        # try to heuristically extract by looking for years
        # find chunks separated by two newlines containing a year
        candidates = re.split(r'\n{2,}', text)
        for c in candidates:
            if YEAR_RE.search(c):
                experiences.append(parse_experience_entry(c))

    # education
    education = []
    if "education" in sections:
        # simple split on lines
        ed_lines = [l.strip() for l in sections["education"].splitlines() if l.strip()]
        for l in ed_lines:
            education.append({"text": l})
    # certs
    certs = []
    if "certifications" in sections:
        cert_lines = [l.strip() for l in sections["certifications"].splitlines() if l.strip()]
        for l in cert_lines:
            certs.append({"text": l})

    # suspicious claims
    suspicious = detect_suspicious_claims(experiences)

    parsed = {
        "contact": contact,
        "skills": skills,
        "experience": experiences,
        "education": education,
        "certs": certs,
        "suspicious_claims": suspicious,
        "original_layout": original_layout or {},
    }
    parsed["confidence"] = compute_confidence(parsed)
    return parsed
