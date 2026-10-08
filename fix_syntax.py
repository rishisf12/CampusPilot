with open(r'C:\Users\Appex\Documents\Default Project\CampusPilot\backend\backend\features\monitoring\scan_service.py', 'r') as f:
    content = f.read()

# Find and replace the problematic section
old = """# 5. Build summary and findings for storage
    findings_json = [
        {
            "title": f.title,
            "severity": f.severity,
            "evidence": [{
                "metric": f.metric,
                "value": f.value,
                "unit": f.unit,
                "previous_value": f.previous_value,
                "change_pct": f.change_pct,
                "window": f.window,
                "source": f.source,
            }]
            for f in final_verdict.findings
        }
        for f in final_verdict.findings
    ]"""

new = """# 5. Build summary and findings for storage
    findings_json = [
        {
            "title": f.title,
            "severity": f.severity,
            "evidence": [{
                "metric": ev.metric,
                "value": ev.value,
                "unit": ev.unit,
                "previous_value": ev.previous_value,
                "change_pct": ev.change_pct,
                "window": ev.window,
                "source": ev.source,
            }]
            for ev in f.evidence
        }
        for f in final_verdict.findings
    ]"""

if old in content:
    content = content.replace(old, new)
    with open(r'C:\Users\Appex\Documents\Default Project\CampusPilot\backend\backend\features\monitoring\scan_service.py', 'w') as f:
        f.write(content)
    print('Fixed!')
else:
    print('Pattern not found')
    # Show what we're looking for
    idx = content.find('findings_json = [')
    if idx >= 0:
        print('Found at:', idx)
        print(content[idx:idx+500])