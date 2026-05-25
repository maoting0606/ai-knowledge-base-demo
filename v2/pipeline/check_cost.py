from model_client import quick_chat, tracker

# 做两次调用
result1 = quick_chat('用一句话介绍 Python')
print(f'回复 1: result1[\"content\"][:80]')

result2 = quick_chat('用一句话介绍 JavaScript')
print(f'回复 2: result2[\"content\"][:80]')

# 打印成本报告
tracker.report()