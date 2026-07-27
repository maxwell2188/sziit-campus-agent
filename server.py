"""
深信院校园办事全流程Agent - 后端服务
"""
import sqlite3
import os
import json
import uuid
import re
from datetime import datetime
from pathlib import Path

from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# ============================================================
# 0. Pydantic 请求/响应模型
# ============================================================

class LoginRequest(BaseModel):
    student_id: str
    name: str


class CreateConversationRequest(BaseModel):
    user_id: str
    scene: str
    first_message: str


class SendMessageRequest(BaseModel):
    user_id: str
    message: str

# ============================================================
# 1. 环境变量加载
# ============================================================
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    print("[WARN] DEEPSEEK_API_KEY 未设置，AI对话功能不可用。请在 .env 文件中配置或设置环境变量。")

# ============================================================
# 2. 数据库初始化
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chat.db")
# 确保 data 目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def init_db():
    """初始化数据库，创建表结构"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            scene TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
    """)

    conn.commit()
    conn.close()
    print(f"[DB] 数据库初始化完成: {DB_PATH}")


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def close_db():
    """关闭数据库连接（预留，FastAPI事件中可调用）"""
    pass


# 启动时初始化
init_db()

# ============================================================
# 3. FastAPI 应用
# ============================================================
app = FastAPI(title="深信院校园办事全流程Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 4. Prompt 文件加载
# ============================================================
PROMPTS_DIR = BASE_DIR / "prompts"


def load_prompt(filename: str) -> str:
    """从 prompts/ 目录读取 .md 文件"""
    filepath = PROMPTS_DIR / filename
    if not filepath.exists():
        print(f"[WARN] Prompt文件不存在: {filepath}")
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        print(f"[PROMPT] 已加载: {filename}")
        return content
    except Exception as e:
        print(f"[ERROR] 读取Prompt文件失败 {filepath}: {e}")
        return ""


# 全局Prompt变量
SYSTEM_PROMPT = load_prompt("system.md")
SCENE_PROMPT = {
    "scholarship": load_prompt("scholarship.md"),
    "repair": load_prompt("repair.md"),
    "academic": load_prompt("academic.md"),
    "general": load_prompt("general.md")
}

# 追加输出格式指令（代码中直接拼接，不改md文件）
OUTPUT_FORMAT_INSTRUCTION = """

## 输出格式要求（极其重要）
你可以在回复中使用以下HTML组件来结构化展示信息：

1. 给用户选项时（多轮追问）：
<div class="option-cards">
  <div class="option-card">选项1文字</div>
  <div class="option-card">选项2文字</div>
</div>

2. 展示资格判断/检查结果时：
<div class="result-card">
  <div class="rc-title">资格预审结果 <span class="badge">X/Y 基础条件</span></div>
  <ul class="check-list">
    <li class="ok"><span class="c-icon">✓</span>符合项</li>
    <li class="warn"><span class="c-icon">⚠</span>待确认项</li>
    <li class="fail"><span class="c-icon">✗</span>不符合项</li>
  </ul>
</div>

3. 展示流程进度时：
<div class="result-card">
  <div class="steps-bar">
    <div class="progress-line"><div class="progress-line-fill" style="width:XX%"></div></div>
    <div class="step active"><div class="circle">✓</div><div class="label">步骤1</div></div>
    <div class="step current"><div class="circle">2</div><div class="label">步骤2</div></div>
    <div class="step"><div class="circle">3</div><div class="label">步骤3</div></div>
  </div>
</div>

4. 展示材料清单时：使用 .material-box 组件
5. 提醒常见错误时：使用 .warning-box 组件

注意：
- 选项卡片每次最多4个，文字简洁
- 普通对话文字不要包裹在卡片中
- 不要输出完整HTML文档，只输出片段
- 不要使用Markdown格式（###、**、- 等），全部用HTML标签
"""

SYSTEM_PROMPT = SYSTEM_PROMPT + OUTPUT_FORMAT_INSTRUCTION

# 追加防幻觉指令
ANTI_HALLUCINATION = """

## 【重要】回答规则

1. 回答时优先参考上方【知识库参考内容】，其中包含了深信院的官方政策和数据
2. 所有具体金额、条件、百分比、截止日期优先使用知识库中的数据
3. 如果知识库中没有相关信息，才说"这个问题我暂时没有找到官方信息，建议咨询辅导员或学生处确认"
4. 绝不编造电话号码、办公地点、截止日期
5. 回答时要自然，不要说"根据知识库"、"参考来源"这类话
6. 如果学生问的问题不在三个场景范围内（奖助学金、宿舍报修、学业资格），礼貌说明你是校园办事助手，可以引导到这三个场景
7. 涉及数字、金额、比例时，核对知识库原文后直接引用
"""

SYSTEM_PROMPT = SYSTEM_PROMPT + ANTI_HALLUCINATION

# ============================================================
# 5. 意图识别
# ============================================================
SCENE_KEYWORDS = {
    "scholarship": [
        "奖学金", "助学金", "国家奖学金", "励志奖学金", "贫困补助",
        "助学贷款", "学费减免", "资助", "困难认定", "勤工助学", "奖金"
    ],
    "repair": [
        "报修", "宿舍", "空调", "水管", "门锁", "电灯", "马桶",
        "热水器", "维修", "漏水", "停电", "窗户", "床铺", "桌子",
        "违规电器", "电器", "吹风机", "电饭锅", "电热毯"
    ],
    "academic": [
        "学分", "成绩", "绩点", "挂科", "补考", "重修", "选课",
        "毕业", "学位", "课程", "考试", "四六级", "学籍", "转专业",
        "三好学生", "三好", "优秀学生干部", "体测", "体质测试"
    ]
}


def detect_scene(message: str) -> str:
    """关键词匹配识别用户意图场景，长词权重更高"""
    msg_lower = message.lower()
    scores = {}
    for scene, keywords in SCENE_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in msg_lower or kw in message:
                # 长关键词（3字以上）权重翻倍，避免短路匹配
                score += len(kw) if len(kw) >= 3 else 1
        scores[scene] = score

    best_scene = max(scores, key=scores.get)
    if scores[best_scene] > 0:
        return best_scene
    return "general"


# ============================================================
# 6. RAG 知识检索
# ============================================================
# 同义词映射（键为知识库中可能出现的词，值为用户可能说的同义表达）
SYNONYM_MAP = {
    "奖学金": ["国奖", "奖励", "奖金", "拿钱"],
    "助学金": ["困难补助", "补贴", "贫困补助", "钱", "资助"],
    "励志": ["立志", "立志奖学金"],
    "困难认定": ["贫困认定", "家庭经济困难", "困难学生", "困难生"],
    "助学贷款": ["生源地贷款", "国家助学贷款", "贷款"],
    "申请": ["申报", "提交", "办理", "申请流程"],
    "条件": ["资格", "要求", "标准", "门槛"],
    "材料": ["文件", "证明", "表格", "附件", "资料"],
    "学分": ["绩点", "GPA", "成绩", "分数", "课程"],
    "报修": ["维修", "坏了", "修", "修理", "坏掉", "故障", "损坏"],
    "毕业": ["结业", "拿毕业证", "学位", "毕业资格", "毕业条件"],
    "挂科": ["不及格", "没过", "补考", "重修"],
    "三好学生": ["三好", "优秀学生"],
    "体测": ["体育测试", "体质测试", "体育"],
    "违规电器": ["电器", "违章电器", "禁用电器", "不能用的电器"],
}

KNOWLEDGE_DIR = BASE_DIR / "knowledge-base"


def search_knowledge(query: str, scene: str, top_k: int = 3) -> str:
    """
    从 knowledge-base/ 目录读取对应场景的知识文件，按 ## 和 ### 标题分块，
    关键词+同义词匹配打分，返回 top_k 个最相关块的拼接内容（带来源标注）。
    """
    scene_dir = KNOWLEDGE_DIR / scene
    if not scene_dir.exists():
        return ""

    chunks = []

    try:
        for md_file in scene_dir.glob("*.md"):
            filename = md_file.name
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # 按 ## 和 ### 标题分块
            blocks = re.split(r"\n(?=#{2,3} )", content)
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                # 提取标题
                title_match = re.match(r"^#{2,3} (.+)", block)
                title = title_match.group(1) if title_match else ""
                # 块太大则再次切分
                if len(block) > 500:
                    sub_blocks = _split_chunk(block, title)
                    chunks.extend(sub_blocks)
                else:
                    chunks.append({"title": title, "content": block, "file": filename})

        if not chunks:
            return ""

        # ---- 构建查询关键词集合（含同义词扩展） ----
        query_words = _extract_keywords(query)

        # 同义词扩展：查询词 → 知识库中可能出现的词
        expanded = set(query_words)
        for qw in query_words:
            # 直接匹配同义词表的键
            if qw in SYNONYM_MAP:
                for syn in SYNONYM_MAP[qw]:
                    expanded.add(syn)
            # 反向匹配：查询词是同义词表中的某个值
            for key, values in SYNONYM_MAP.items():
                if qw in values:
                    expanded.add(key)
                    for v in values:
                        expanded.add(v)

        print(f"[RAG] 查询词(含同义词): {expanded}")

        # ---- 关键词打分 ----
        scored = []
        for chunk in chunks:
            score = 0
            for word in expanded:
                if len(word) < 2:
                    continue  # 跳过单字，避免噪音
                count = chunk["content"].count(word)
                if count > 0:
                    score += count * len(word)  # 长词匹配权重更高
            # 标题匹配加分
            if chunk["title"] and any(w in chunk["title"] for w in expanded if len(w) >= 2):
                score += 10
            if score > 0:
                scored.append((score, chunk))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored[:top_k]

        result_parts = []
        for _, chunk in top_chunks:
            result_parts.append(
                f"### 来源：{chunk['file']}\n{chunk['content']}"
            )

        result = "\n\n---\n\n".join(result_parts)
        print(f"[RAG] 检索到 {len(top_chunks)} 个相关块，场景={scene}")
        return result

    except Exception as e:
        print(f"[RAG] 检索出错: {e}")
        return ""


def _extract_keywords(text: str) -> list:
    """
    从用户查询中提取有意义的关键词（2-4字词组）。
    从长到短提取，优先匹配长词。
    """
    keywords = []
    # 去掉标点，保留中文和英文
    cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
    n = len(cleaned)
    # 从长到短提取（4字→3字→2字）
    for length in [4, 3, 2]:
        for i in range(n - length + 1):
            word = cleaned[i:i + length]
            # 过滤纯数字或纯英文短词
            if word not in keywords:
                keywords.append(word)
    return keywords


def _split_chunk(text: str, parent_title: str) -> list:
    """将过大的文本块按段落拆分成 300-500 字的小块"""
    sub_chunks = []
    paragraphs = text.split("\n\n")
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > 500 and current:
            title = parent_title or ""
            sub_chunks.append({"title": title, "content": current.strip()})
            current = para
        else:
            current += "\n\n" + para if current else para
    if current.strip():
        sub_chunks.append({"title": parent_title or "", "content": current.strip()})
    return sub_chunks


# ============================================================
# 7. DeepSeek 客户端（延迟初始化）
# ============================================================
_deepseek_client = None
_client_initialized = False


def get_deepseek_client():
    """延迟初始化并返回DeepSeek客户端实例"""
    global _deepseek_client, _client_initialized
    if not _client_initialized:
        if DEEPSEEK_API_KEY:
            _deepseek_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
                timeout=60.0
            )
            print("[AI] DeepSeek客户端初始化完成")
        else:
            print("[AI] DeepSeek客户端未初始化（缺少API Key）")
        _client_initialized = True
    return _deepseek_client

# ============================================================
# 8. DeepSeek 调用辅助函数
# ============================================================


def call_deepseek(scene: str, history: list, current_message: str) -> str:
    """构建完整Prompt并调用DeepSeek，返回Bot回复文本"""
    client = get_deepseek_client()
    if not client:
        raise HTTPException(status_code=503, detail="AI服务暂不可用，请检查API Key配置")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # 场景Prompt
    if scene != "general" and SCENE_PROMPT.get(scene):
        messages.append({"role": "system", "content": SCENE_PROMPT[scene]})

    # RAG 知识库检索
    rag_context = search_knowledge(current_message, scene)
    if rag_context:
        messages.append({"role": "system", "content": "## 深信院官方知识库（请优先参考）\n\n" + rag_context})

    # 历史消息（最近10轮 = 20条）
    recent_history = history[-20:] if len(history) > 20 else history
    if recent_history and recent_history[-1].get("content") == current_message:
        recent_history = recent_history[:-1]
    for msg in recent_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": current_message})

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            frequency_penalty=0.3,
            presence_penalty=0.2
        )
        raw = response.choices[0].message.content
        return clean_markdown(raw)
    except Exception as e:
        print(f"[AI] DeepSeek调用失败: {e}")
        raise HTTPException(status_code=500, detail="AI服务响应异常，请稍后重试")


def clean_markdown(text: str) -> str:
    """清理模型输出中的Markdown语法，转为干净HTML"""
    import re as _re

    # 去掉代码块标记
    text = _re.sub(r'```[a-zA-Z]*\n?', '', text)
    text = _re.sub(r'```', '', text)

    # 去掉标题符号 ### ## #
    text = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.MULTILINE)

    # **粗体** → <b>粗体</b>
    text = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # __粗体__ → <b>粗体</b>
    text = _re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # *斜体* → <i>斜体</i>
    text = _re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

    # _斜体_ → <i>斜体</i>
    text = _re.sub(r'_(.+?)_', r'<i>\1</i>', text)

    # 去掉分隔线 --- ***
    text = _re.sub(r'^[-*]{3,}\s*$', '', text, flags=_re.MULTILINE)

    # 去掉引用 >
    text = _re.sub(r'^>\s?', '', text, flags=_re.MULTILINE)

    # 有序列表 1. 2. → 保持数字，去掉点号后的空格中的markdown感
    # 无序列表 - * → 替换为 emoji 圆点
    text = _re.sub(r'^[\s]*[-*]\s+', '• ', text, flags=_re.MULTILINE)

    # 去掉多余的空行（超过2个连续换行压缩为2个）
    text = _re.sub(r'\n{3,}', '\n\n', text)

    # 保留的HTML标签内的换行转为<br>（但不在标签内的纯文本换行保持）
    # 注意：不要破坏已有的HTML标签
    text = text.strip()

    return text


# ============================================================
# 9. API 接口
# ============================================================

@app.post("/api/auth/login")
def api_login(req: LoginRequest):
    """模拟登录：根据学号查找/创建用户"""
    print(f"[LOGIN] 收到请求: student_id={req.student_id}, name={req.name}")
    if not req.student_id or not req.name:
        raise HTTPException(status_code=400, detail="学号和姓名不能为空")

    conn = get_db()
    try:
        cursor = conn.cursor()

        # 查找已有用户
        row = cursor.execute(
            "SELECT id, student_id, name FROM users WHERE student_id = ?",
            (req.student_id,)
        ).fetchone()

        if row:
            user_id = row["id"]
        else:
            # 创建新用户
            user_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO users (id, student_id, name) VALUES (?, ?, ?)",
                (user_id, req.student_id, req.name)
            )
            conn.commit()

        return {"user_id": user_id, "student_id": req.student_id, "name": req.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")
    finally:
        conn.close()


@app.get("/api/conversations")
def api_list_conversations(user_id: str):
    """获取用户对话列表，按更新时间倒序"""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id不能为空")

    conn = get_db()
    try:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT c.id, c.scene, c.title, c.updated_at,
                   (SELECT m.content FROM messages m
                    WHERE m.conversation_id = c.id
                    ORDER BY m.created_at DESC LIMIT 1) AS last_message
            FROM conversations c
            WHERE c.user_id = ?
            ORDER BY c.updated_at DESC
        """, (user_id,)).fetchall()

        return [
            {
                "id": row["id"],
                "scene": row["scene"],
                "title": row["title"],
                "updated_at": row["updated_at"],
                "last_message": row["last_message"]
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话列表失败: {str(e)}")
    finally:
        conn.close()


@app.post("/api/conversations")
def api_create_conversation(req: CreateConversationRequest):
    """创建新对话，发送首条消息并获取AI回复"""
    if not req.user_id or not req.scene or not req.first_message:
        raise HTTPException(status_code=400, detail="user_id、scene和first_message不能为空")

    conversation_id = str(uuid.uuid4())
    title = req.first_message[:20] + ("..." if len(req.first_message) > 20 else "")
    now = datetime.now().isoformat()

    conn = get_db()
    try:
        cursor = conn.cursor()

        # 创建对话
        cursor.execute(
            "INSERT INTO conversations (id, user_id, scene, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, req.user_id, req.scene, title, now, now)
        )

        # 保存用户消息
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, "user", req.first_message, now)
        )

        conn.commit()

        # 调用DeepSeek获取回复
        reply = call_deepseek(req.scene, [], req.first_message)

        # 保存Bot回复
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, "assistant", reply, datetime.now().isoformat())
        )
        conn.commit()

        return {"conversation_id": conversation_id, "reply": reply}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建对话失败: {str(e)}")
    finally:
        conn.close()


@app.get("/api/conversations/{conversation_id}/messages")
def api_get_messages(conversation_id: str):
    """获取对话历史消息，按时间正序"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,)
        ).fetchall()

        return [
            {"role": row["role"], "content": row["content"], "created_at": row["created_at"]}
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")
    finally:
        conn.close()


@app.post("/api/conversations/{conversation_id}/messages")
def api_send_message(conversation_id: str, req: SendMessageRequest):
    """在已有对话中发送消息并获取AI回复"""
    if not req.user_id or not req.message:
        raise HTTPException(status_code=400, detail="user_id和message不能为空")

    conn = get_db()
    try:
        cursor = conn.cursor()

        # 验证对话存在且属于该用户
        conv = cursor.execute(
            "SELECT id, scene, title FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, req.user_id)
        ).fetchone()

        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在或无权访问")

        scene = conv["scene"]

        # 保存用户消息
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, "user", req.message, now)
        )

        # 获取历史消息（用于构建上下文）
        history_rows = cursor.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,)
        ).fetchall()

        history = [{"role": r["role"], "content": r["content"]} for r in history_rows]

        # 调用DeepSeek（当前消息已在history中，call_deepseek会取最近20条）
        reply = call_deepseek(scene, history, req.message)

        # 保存Bot回复
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, "assistant", reply, datetime.now().isoformat())
        )

        # 更新对话时间和标题
        cursor.execute(
            "UPDATE conversations SET updated_at = ?, title = ? WHERE id = ?",
            (datetime.now().isoformat(), req.message[:20] + ("..." if len(req.message) > 20 else ""), conversation_id)
        )

        conn.commit()

        return {"reply": reply}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")
    finally:
        conn.close()


@app.delete("/api/conversations/{conversation_id}")
def api_delete_conversation(conversation_id: str):
    """删除对话及其所有消息"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
        return {"detail": "对话已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除对话失败: {str(e)}")
    finally:
        conn.close()


# ============================================================
# 10. 静态文件挂载（必须在最后，覆盖所有路由）
# ============================================================
app.mount("/", StaticFiles(directory=".", html=True), name="static")

print("\n" + "=" * 50)
print("  深信院校园办事全流程Agent 后端服务已启动")
print(f"  访问地址: http://localhost:8000")
print("=" * 50 + "\n")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)