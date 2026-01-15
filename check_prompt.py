with open('C:/Users/j/Documents/GitHub/stock_agent/agents/risk_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    # 检查第 127 行（prompt 开始）
    print(f'Line 127: {repr(lines[126])}')
    print(f'Line 286: {repr(lines[285])}')
    print(f'Total lines: {len(lines)}')
    
    # 检查从第 127 行开始的三引号
    in_prompt = False
    for i in range(126, len(lines)):
        line = lines[i]
        if '"""' in line:
            print(f'Line {i+1}: {repr(line.strip())}')
            in_prompt = not in_prompt