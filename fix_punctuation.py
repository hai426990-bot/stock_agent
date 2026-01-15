# 修复中文标点符号
import re

# 读取文件
with open('agents/risk_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换中文标点符号
content = content.replace('、', ',')  # 顿号
content = content.replace('。', '.')  # 句号
content = content.replace('？', '?')  # 问号
content = content.replace('！', '!')  # 感叹号
content = content.replace('，', ',')  # 逗号
content = content.replace('；', ';')  # 分号
content = content.replace('：', ':')  # 冒号

# 写回文件
with open('agents/risk_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ 已替换所有中文标点符号')