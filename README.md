# 合同哨兵 (Contract Sentinel)

智能合同审核、对比与法务助理平台

## 功能模块

- **合同审核**: 上传合同 → AI 风险识别 → 生成报告 → 导出修改建议
- **合同对比**: 两份合同对比 → 条款级 Redline → 风险影响分析
- **法务助理**: 智能问答 → 法规检索 → 条款建议 → 谈判要点

## 技术栈

### 后端
- Python 3.12 + FastAPI + Pydantic v2
- PostgreSQL 16 + pgvector
- Redis + arq (异步任务)
- PyMuPDF / python-docx / RapidOCR

### 前端
- Next.js 15 + React 19 + TypeScript
- Tailwind CSS 4 + shadcn/ui

## 快速开始

### 环境要求
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 16 (或使用 Docker)

### 启动项目

```powershell
# Windows
.\start.ps1

# 或手动启动
# 1. 启动数据库
docker-compose up -d postgres redis

# 2. 启动后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. 启动前端
cd frontend
npm install
npm run dev
```

### 访问地址
- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 配置

复制 `.env.example` 为 `.env` 并配置:

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/contract_sentinel

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=your-secret-key

# LLM Providers
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
```

## 项目结构

```
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/       # 路由
│   │   ├── agents/    # AI Agent 流水线
│   │   ├── models/    # 数据库模型
│   │   ├── providers/ # LLM Provider 抽象
│   │   ├── rag/       # Web-RAG 系统
│   │   └── services/  # 业务服务
│   └── configs/       # 配置文件
├── frontend/          # Next.js 前端
│   └── src/
│       ├── app/       # 页面路由
│       ├── components/# UI 组件
│       └── lib/       # 工具函数
└── docker-compose.yml
```

## License

MIT
