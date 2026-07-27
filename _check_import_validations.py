"""Check which import_ functions use validate_excel_size/extension."""
import re

with open('/workspace/app/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all import_ function positions
import_funcs = []
for m in re.finditer(r"^def\s+(import_\w+)\(", content, re.MULTILINE):
    name = m.group(1)
    pos = m.start()
    # Get the next 2000 chars body
    end_pattern = re.search(r"^def\s+\w+\(", content[m.end():], re.MULTILINE)
    end = m.end() + (end_pattern.start() if end_pattern else 2000)
    body = content[m.end():end]
    import_funcs.append((name, pos, body))

# Filter out non-import
actual_imports = [(n, p, b) for n, p, b in import_funcs if not n.startswith('import_max')]
print(f"Total actual import_ functions: {len(actual_imports)}")

for name, pos, body in actual_imports:
    has_size = 'validate_excel_size' in body
    has_ext = 'validate_excel_extension' in body
    status = 'PASS' if (has_size and has_ext) else ('PARTIAL' if has_size or has_ext else 'FAIL')
    print(f"  {name:35s} size={has_size} ext={has_ext} [{status}]")
