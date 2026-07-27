import requests, json, sys

BASE = "http://localhost:8000"
USER_ID = "test-verify-rag"

tests = [
    {"q": "国家奖学金多少钱", "scene": "scholarship", "expect": ["10000", "万"]},
    {"q": "学业奖学金有几个等级", "scene": "scholarship", "expect": ["特等", "12000", "4000", "2500", "1500"]},
    {"q": "挂科了补考通过绩点怎么算", "scene": "academic", "expect": ["绩点", "0"]},
    {"q": "宿舍违规电器有哪些", "scene": "repair", "expect": ["吹风机", "电饭锅", "电热毯"]},
    {"q": "三好学生成绩要求", "scene": "academic", "expect": ["30%", "20%", "体测", "合格"]},
    {"q": "优秀学生干部奖金多少", "scene": "academic", "expect": ["1000"]},
    {"q": "校长电话多少", "scene": "general", "expect": ["没有", "找不到", "官方", "辅导员", "确认"]},
    {"q": "今天吃什么", "scene": "general", "expect": ["奖助学金", "报修", "学业", "办事", "场景"]},
]

with open("d:/VueProject/maxAgentDemo/test_result.txt", "w", encoding="utf-8") as f:
    f.write("RAG验收测试结果\n" + "="*60 + "\n")
    
    for i, test in enumerate(tests):
        f.write(f"\n[{i+1}/{len(tests)}] 问题: {test['q']}\n")
        try:
            resp = requests.post(f"{BASE}/api/conversations", json={
                "user_id": USER_ID,
                "scene": test["scene"],
                "first_message": test["q"]
            }, timeout=60)
            data = resp.json()
            reply = data.get("reply", "")
            
            matched = [kw for kw in test["expect"] if kw in reply]
            missed = [kw for kw in test["expect"] if kw not in reply]
            
            if test["q"] in ["校长电话多少", "今天吃什么"]:
                status = "PASS" if any(kw in reply for kw in test["expect"]) else "FAIL"
            else:
                status = "PASS" if len(matched) >= len(test["expect"]) * 0.5 else "FAIL"
            
            f.write(f"结果: {status} | 匹配: {matched} | 未匹配: {missed}\n")
            f.write(f"回复: {reply[:300]}...\n")
        except Exception as e:
            f.write(f"错误: {e}\n")

print("done - see test_result.txt")