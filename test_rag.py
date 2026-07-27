"""RAG 验收测试脚本 - 测试6个核心问题 + 超纲/闲聊兜底"""
import requests
import json
import time

BASE = "http://localhost:8000"
USER_ID = "test-verify-rag"

# 测试问题列表
tests = [
    # 6个核心RAG问题
    {"q": "国家奖学金多少钱", "scene": "scholarship", "expect": ["10000", "万"]},
    {"q": "学业奖学金有几个等级", "scene": "scholarship", "expect": ["特等", "12000", "4000", "2500", "1500"]},
    {"q": "挂科了补考通过绩点怎么算", "scene": "academic", "expect": ["绩点", "0"]},
    {"q": "宿舍违规电器有哪些", "scene": "repair", "expect": ["吹风机", "电饭锅", "电热毯"]},
    {"q": "三好学生成绩要求", "scene": "academic", "expect": ["30%", "20%", "体测", "合格"]},
    {"q": "优秀学生干部奖金多少", "scene": "academic", "expect": ["1000"]},
    # 超纲兜底
    {"q": "校长电话多少", "scene": "general", "expect": ["没有", "找不到", "官方", "辅导员", "确认"]},
    # 闲聊兜底
    {"q": "今天吃什么", "scene": "general", "expect": ["奖助学金", "报修", "学业", "办事", "场景"]},
]

results = []

for i, test in enumerate(tests):
    print(f"\n{'='*50}")
    print(f"[{i+1}/{len(tests)}] 问题: {test['q']}")
    print(f"场景: {test['scene']}")
    
    try:
        # 创建新对话
        resp = requests.post(f"{BASE}/api/conversations", json={
            "user_id": USER_ID,
            "scene": test["scene"],
            "first_message": test["q"]
        }, timeout=60)
        data = resp.json()
        reply = data.get("reply", "")
        
        # 检查期望关键词
        matched = []
        missed = []
        for kw in test["expect"]:
            if kw in reply:
                matched.append(kw)
            else:
                missed.append(kw)
        
        status = "PASS" if len(matched) >= len(test["expect"]) * 0.5 else "FAIL"
        if test["q"] in ["校长电话多少", "今天吃什么"]:
            # 兜底问题：只要没编造具体信息就算通过
            status = "PASS" if any(kw in reply for kw in test["expect"]) else "FAIL"
        
        print(f"结果: {status}")
        print(f"匹配: {matched}")
        if missed:
            print(f"未匹配: {missed}")
        print(f"回复摘要: {reply[:200]}...")
        
        results.append({
            "q": test["q"],
            "status": status,
            "matched": matched,
            "missed": missed,
            "reply_preview": reply[:200]
        })
        
    except Exception as e:
        print(f"错误: {e}")
        results.append({"q": test["q"], "status": "ERROR", "error": str(e)})
    
    time.sleep(1)

# 汇总
print(f"\n{'='*50}")
print("验收结果汇总:")
passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
print(f"通过: {passed}/{len(results)}")
print(f"失败: {failed}/{len(results)}")
for r in results:
    icon = "✅" if r["status"] == "PASS" else "❌"
    print(f"  {icon} {r['q']}")