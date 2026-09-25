from pathlib import Path
p=Path(__file__).resolve().parent/'repair_dashboard_views.py'
s=p.read_text(encoding='utf-8')
old='pattern = rf"function {name}\\(\\)\\{{.*?\\n        \\}}\\n\\n        function {next_name}"'
new='pattern = rf"function {name}\\(\\)\\s*\\{{.*?(?=\\n\\s*function {next_name}\\s*\\(\\))"'
if old not in s:
    raise SystemExit('expected regex line not found')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('regex relaxed')
