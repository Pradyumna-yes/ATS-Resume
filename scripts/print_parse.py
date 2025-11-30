from app.services.resume_parser import parse_resume_text
import json
text = """
Experience
Role A — CoA
2018 - 2020
- Worked on projects

Role B — CoB
2019 - 2021
- Overlapping role
"""
print(json.dumps(parse_resume_text(text), indent=2))
