# 🎓 深信院校园办事全流程Agent

> 深圳信息职业技术大学校园办事智能助手 · 2026火山杯Agent创新大赛参赛作品

## 📖 项目简介

为解决深信院学生办事流程分散、信息不对称、材料准备易错等痛点，基于火山引擎Trae平台和DeepSeek大模型打造的专属校园办事智能助手。覆盖三大高频办事场景，提供全流程智能指引、资格智能预判、材料清单生成、避坑提醒等核心能力。

**核心价值：**
- 🎯 资格预判：根据学生个人情况智能判断是否符合申请条件，避免白跑
- 📋 材料清单：自动生成个性化材料清单，标注易错点
- ⚠️ 避坑提醒：基于往届学生真实驳回原因，提前预警
- 📱 移动端优先：对话式交互，降低使用门槛
- 💾 历史记录：对话持久化，办事进度可追溯

## 🛠️ 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 前端 | 原生 HTML5 + CSS3 + JavaScript | 零依赖，移动端优先，单页应用 |
| 后端 | FastAPI (Python) | 高性能异步框架，自动生成API文档 |
| 大模型 | DeepSeek Chat | 国产大模型，性价比高，中文理解能力强 |
| 数据库 | SQLite | 轻量级文件数据库，零配置 |
| RAG检索 | 关键词匹配+同义词扩展 | 基于官方文件的精准知识库检索 |
| 部署 | Docker / Render | 支持容器化部署和免费云托管 |

## ✨ 核心功能

### 1. 🎓 奖助学金/补贴申请全指引
- 覆盖国家奖学金、国家励志奖学金、国家助学金、学业奖学金等全部项目
- 智能资格预审：输入年级、绩点、排名、困难认定情况，即时判断是否符合条件
- 自动生成申请材料清单
- 标注互斥规则（如国奖与励志不可兼得）
- 时间节点提醒

### 2. 🔧 宿舍后勤报修助手
- 自助排查引导（30%问题可自行解决）
- 报修单智能生成
- 维修人员进入宿舍安全规定说明
- 违规电器清单提醒
- 服务时效告知

### 3. 📋 学业资格与评奖评优自查
- 绩点计算（官方规则：60分=1.0，每分+0.1，满分5.0）
- 奖学金资格评估（特等/一等/二等/三等）
- 三好学生、优秀学生干部条件自查
- 挂科影响分析（补考通过绩点记为0等关键规则）
- 毕业资格评估

## 🚀 快速开始

### 方式一：本地运行（推荐开发）

**环境要求：** Python 3.9+

```bash
# 1. 克隆项目
git clone https://github.com/你的用户名/campus-agent.git
cd campus-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 DEEPSEEK_API_KEY

# 4. 启动服务
python server.py

# 5. 访问
# 浏览器打开 http://localhost:8000
```

### 方式二：Docker运行

```bash
# 构建镜像
docker build -t campus-agent .

# 运行容器（替换your_api_key）
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=your_api_key campus-agent

# 访问 http://localhost:8000
```

### 方式三：免费云部署（公网访问）

详见下方【部署指南】章节，使用Render免费层一键部署。

## 📁 项目结构

```
campus-agent/
├── index.html                    # 前端单页应用
├── server.py                     # FastAPI后端服务
├── requirements.txt              # Python依赖
├── Dockerfile                    # Docker构建配置
├── .env.example                  # 环境变量模板
├── .gitignore                    # Git忽略配置
├── prompts/                      # System Prompt
│   ├── system_prompt.md          # 全局Agent指令
│   ├── scene_scholarship.md      # 场景一：奖助学金
│   ├── scene_repair.md           # 场景二：宿舍报修
│   └── scene_academic.md         # 场景三：学业自查
└── knowledge-base/               # RAG知识库
    ├── 场景一-奖助学金补贴申请/
    ├── 场景二-宿舍后勤报修/
    └── 场景三-学业资格与评奖评优自查/
```

## 🧪 测试验证

项目包含18个标准测试用例，覆盖登录、三大场景对话、兜底问答、历史记录等功能。详见开发文档。

## 🎯 赛事亮点

| 评审维度 | 对应能力 |
|---------|---------|
| 实用价值与落地性（30%） | 解决真实校园痛点，100%基于官方文件，可直接上线使用 |
| 技术实现（30%） | 前后端分离架构、RAG知识库、SQLite持久化、Docker部署 |
| 创新性与创意度（20%） | 资格智能预判（非简单问答而是推理决策）、结构化结果卡片、自助排查前置 |
| 用户体验（20%） | 移动端优先对话式UI、选项卡片减少输入、避坑提醒、历史记录 |

## 📊 API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/auth/login` | 用户登录/注册 |
| GET | `/api/conversations` | 获取对话列表 |
| POST | `/api/conversations` | 创建新对话 |
| GET | `/api/conversations/{id}/messages` | 获取对话历史消息 |
| POST | `/api/conversations/{id}/messages` | 发送消息 |
| DELETE | `/api/conversations/{id}` | 删除对话 |

API文档：启动服务后访问 `http://localhost:8000/docs` 查看自动生成的Swagger文档。

## 🤝 开发团队

深圳信息职业技术大学 · 计算机与软件学院

## 📄 许可证

MIT License

---

**注意：** 本项目为参赛作品，知识库内容基于深圳信息职业技术大学公开官方文件整理，仅供学习交流使用。