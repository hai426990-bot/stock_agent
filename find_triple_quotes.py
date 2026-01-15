with open('agents/risk_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if '"""' in line:
            print(f'Line {i}: {line.strip()[:100]}')