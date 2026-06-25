import re

def main():
    with open('charts.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Update _cfg margin
    # original: "margin": {"t": 50, "b": 80, "l": 50, "r": 30}
    content = re.sub(
        r'\"margin\":\s*\{\"t\":\s*\d+,\s*\"b\":\s*\d+,\s*\"l\":\s*\d+,\s*\"r\":\s*\d+\}',
        '"margin": {"t": 50, "b": 20, "l": 20, "r": 20}',
        content
    )

    # Strip l= and b= from margin=dict(...)
    def fix_margin(m):
        inner = m.group(1)
        parts = inner.split(',')
        new_parts = [p.strip() for p in parts if not p.strip().startswith('l=') and not p.strip().startswith('b=')]
        return 'margin=dict(' + ', '.join(new_parts) + ')'

    content = re.sub(r'margin=dict\(([^)]+)\)', fix_margin, content)

    # Add automargin=True to update_xaxes and update_yaxes
    def add_auto(m):
        inner = m.group(1)
        if 'automargin=True' in inner:
            return m.group(0)
        return inner + ', automargin=True' + m.group(2)

    content = re.sub(r'(\.update_xaxes\([^)]*)(\))', add_auto, content)
    content = re.sub(r'(\.update_yaxes\([^)]*)(\))', add_auto, content)

    with open('charts.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print('Done updating margins in charts.py')

if __name__ == "__main__":
    main()
