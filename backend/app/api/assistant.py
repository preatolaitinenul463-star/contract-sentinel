"""法律助手 API — 四模式结构化报告 + 联网搜索 + 验证闭环 + 导出。

Modes:
  qa              — 法律问答
  case_analysis   — 案件深度分析
  contract_review — 合同条款审查
  doc_draft       — 法律文书起草

Pipeline: Orchestrator → RetrievalAgent → AnalysisAgent → ReasoningAgent
          → FormattingAgent → ComplianceAgent → VerificationEngine → Persist
"""

import json
import io
import traceback
import time
from typing import AsyncGenerator, Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db, async_session_maker
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage as ChatMessageModel, ContextType
from app.schemas.chat import ChatRequest, ChatResponse
from app.api.deps import get_current_user, get_current_user_optional
from app.providers import get_provider_registry, ChatMessage
from app.pipeline.context import PipelineContext
from app.pipeline.verification import verify_assistant_output, get_verification_decision
from app.policy.jurisdiction import get_disclaimer, get_compliance_rules
from app.telemetry import record_counter

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# Mode definitions (prompt templates & expected JSON keys)
# ═══════════════════════════════════════════════════════════

MODE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "qa": {
        "label": "法律问答",
        "expected_keys": [],
        "prompt_suffix": """## 回答格式要求（必须遵守）
- 使用 Markdown 格式输出，不要输出 JSON
- 用 ## / ### 分级标题组织内容
- 用 **加粗** 标注关键法条和重要结论
- 用编号列表（1. 2. 3.）分条论述
- 引用法条格式：**《xxx法》第xxx条** [S#]
- 每个关键结论后用 [S#] 标注来源
- 结尾加"---"分割线后附免责声明""",
    },
    "case_analysis": {
        "label": "案件分析",
        "expected_keys": [],
        "prompt_suffix": """## 回答格式要求（必须遵守）
- 使用 Markdown 格式输出，不要输出 JSON
- 必须包含以下章节：
  ## 案情摘要
  ## 争议焦点
  ## 法律适用
  ## 裁判分析
  ## 实务建议
- 用 **加粗** 标注关键法条，每处引用法条后加 [S#]
- 精准引用真实法条，不编造不存在的法律条文
- 涉及案例名称时，确保案例名称和案情事实的准确性
- 结尾加"---"分割线后附免责声明""",
    },
    "contract_review": {
        "label": "合同审查",
        "expected_keys": [],
        "prompt_suffix": """## 回答格式要求（必须遵守）
- 使用 Markdown 格式输出，不要输出 JSON
- 必须包含以下章节：
  ## 审查概要
  ## 风险条款分析（逐条列出，标注风险等级）
  ## 修改建议
  ## 整体评估
- 每条风险标注 **【高风险】**/**【中风险】**/**【低风险】**
- 引用的法条用 [S#] 标注来源
- 结尾加"---"分割线后附免责声明""",
    },
    "doc_draft": {
        "label": "文书起草",
        "expected_keys": [],
        "prompt_suffix": """## 回答格式要求（必须遵守）
- 使用 Markdown 格式输出，不要输出 JSON
- 直接输出完整的法律文书内容
- 必要处引用法条并加 [S#] 来源标注
- 结尾附免责声明""",
    },
}


# ═══════════════════════════════════════════════════════════
# 文件解析工具
# ═══════════════════════════════════════════════════════════

def parse_uploaded_file(content: bytes, filename: str) -> str:
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        try:
            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            text = "".join(page.get_text() for page in doc)
            doc.close()
            return text.strip() or "[PDF 内容为空]"
        except Exception as e:
            return f"[PDF 解析失败: {e}]"
    elif filename_lower.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs).strip() or "[Word 内容为空]"
        except Exception as e:
            return f"[Word 解析失败: {e}]"
    elif filename_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        try:
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR()
            result, _ = ocr(content)
            if result:
                return "\n".join([line[1] for line in result]).strip()
            return "[图片中未识别到文字]"
        except ImportError:
            return "[图片 OCR 功能需要 rapidocr-onnxruntime 依赖]"
        except Exception as e:
            return f"[图片识别失败: {e}]"
    elif filename_lower.endswith(".txt"):
        try:
            return content.decode("utf-8").strip()
        except Exception:
            return content.decode("gbk", errors="ignore").strip()
    else:
        try:
            return content.decode("utf-8").strip()
        except Exception:
            return f"[不支持的文件格式: {filename}]"


# ═══════════════════════════════════════════════════════════
# 联网搜索 → 结构化 sources
# ═══════════════════════════════════════════════════════════

async def search_and_build_sources(query: str, jurisdiction: str = "CN") -> tuple:
    """Return (sources_list, sources_prompt_text, citations_for_frontend)."""
    sources: List[Dict[str, Any]] = []
    prompt_text = ""
    try:
        from app.rag.agent_search import AgentSearch
        agent = AgentSearch()
        results = await agent.search_laws(custom_query=query, jurisdiction=jurisdiction)
        if results:
            parts = []
            for i, r in enumerate(results[:6]):
                sid = f"S{i+1}"
                source = {
                    "source_id": sid,
                    "trusted": r.get("trusted", False),
                    "kind": r.get("kind", "other"),
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "excerpt": r.get("text", "")[:500],
                    "institution": r.get("institution", ""),
                }
                sources.append(source)
                label = "官方" if source["trusted"] else "参考"
                parts.append(f"[{sid}]【{label}】{source['title']}\n{source['excerpt'][:300]}\n链接: {source['url']}")
            prompt_text = "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"Legal context search failed: {e}")
    return sources, prompt_text, sources


# ═══════════════════════════════════════════════════════════
# JSON 解析助手
# ═══════════════════════════════════════════════════════════

def _extract_json(text: str) -> Optional[dict]:
    """Try to extract JSON from model output."""
    # Try ```json ... ```
    if "```json" in text:
        try:
            block = text.split("```json")[1].split("```")[0]
            return json.loads(block)
        except Exception:
            pass
    if "```" in text:
        try:
            block = text.split("```")[1].split("```")[0]
            return json.loads(block)
        except Exception:
            pass
    # Try raw JSON
    try:
        # Find first { and last }
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════
# 流式问答核心
# ═══════════════════════════════════════════════════════════

async def legal_assistant_stream(
    user_message: str,
    mode: str = "qa",
    jurisdiction: str = "CN",
    file_text: str = "",
    history: Optional[list] = None,
    session_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """法律助手流式问答：编排 → 检索 → 推理 → 验证 → 持久化。"""

    # Create pipeline context
    pctx = PipelineContext(
        feature="assistant",
        user_id=user_id,
        mode=mode,
        jurisdiction=jurisdiction,
        input_text=user_message + file_text,
    )

    mode_config = MODE_SCHEMAS.get(mode, MODE_SCHEMAS["qa"])

    try:
        yield _sse({"type": "start", "run_id": pctx.run_id})

        # ── Stage 1: 联网搜索 ──
        yield _sse({"type": "status", "message": "正在搜索相关法规..."})
        pctx.add_event("retrieval", "running", 10, "开始联网检索")
        t0 = time.time()

        sources, search_prompt, _ = await search_and_build_sources(user_message, jurisdiction)

        retrieval_ms = int((time.time() - t0) * 1000)
        pctx.add_event("retrieval", "completed", 20, f"检索到 {len(sources)} 条来源", duration_ms=retrieval_ms)

        # Register sources in pipeline context
        for s in sources:
            pctx.add_source(**s)

        if search_prompt:
            yield _sse({"type": "status", "message": f"已检索到 {len(sources)} 条相关法规"})
        else:
            yield _sse({"type": "status", "message": "未命中官方源，将基于通用规则分析"})

        # ── Stage 2: 构建 Prompt → 推理 ──
        yield _sse({"type": "status", "message": "正在生成分析报告..."})
        pctx.add_event("reasoning", "running", 30, "开始 LLM 推理")

        registry = get_provider_registry()
        chat_client = registry.get_chat_client("deepseek", "deepseek-reasoner")

        compliance_rules = get_compliance_rules(jurisdiction)
        disclaimer = get_disclaimer(jurisdiction)

        system_prompt = f"""你是"合同哨兵"平台的法律助手，当前模式：{mode_config['label']}。

## 你的能力
1. 法律问题解答：基于中国法律法规（及用户指定法域）解答各类法律问题
2. 案件深度分析：分析案情，梳理法律关系，评估各方责任和胜诉可能性
3. 合同条款审查：识别合同风险、不公平条款，给出修改意见
4. 法律文书辅助：辅助起草法律意见书、答辩状、合同条款等

## 引用规则（必须遵守）
- 你收到的搜索来源标记为 [S1] [S2] ... 等
- 在你的回答中，每个关键结论、法条依据后面都必须用 [S#] 标注来源
- 法条/法规依据只能引用标有"官方"的来源
- 标有"参考"的来源只能用于背景/观点/案例分析，不得作为法条依据
- 如果没有任何官方来源，明确标注"未命中官方法规源，以下为通用规则分析"

## 准确性要求（极其重要）
- 对于用户提到的具体案件名称、当事人姓名，必须确保准确
- 不得混淆不同案件的当事人、案情或判决结果
- 如果对某个案件的细节不确定，必须明确标注"该案件细节有待核实"
- 宁可说"不确定"也不编造虚假案情
- 搜索到的来源中如有相关案例，优先使用搜索结果中的信息

## 合规要求
{chr(10).join('- ' + r for r in compliance_rules)}

## 免责声明（必须在末尾输出）
{disclaimer}
"""
        if search_prompt:
            system_prompt += f"\n\n## 联网检索到的法规来源\n{search_prompt[:4000]}"

        if file_text:
            system_prompt += f"\n\n## 用户上传的文件内容\n{file_text[:8000]}"

        system_prompt += f"\n\n## 输出格式\n{mode_config['prompt_suffix']}"

        messages = [ChatMessage(role="system", content=system_prompt)]
        if history:
            for h in history[-6:]:
                messages.append(ChatMessage(role=h.get("role", "user"), content=h.get("content", "")))
        messages.append(ChatMessage(role="user", content=user_message))

        # ── Stage 3: 流式输出（含思考阶段 keepalive） ──
        yield _sse({"type": "status", "message": "AI 正在深度思考中..."})
        full_response = ""
        first_token_received = False
        thinking_tick = 0
        async for token in chat_client.chat_stream(messages, temperature=0.3, max_tokens=4096):
            if not first_token_received:
                first_token_received = True
                yield _sse({"type": "status", "message": "开始输出分析结果..."})
            full_response += token
            yield _sse({"type": "token", "content": token})

        reasoning_ms = int((time.time() - t0) * 1000) - retrieval_ms
        pctx.add_event("reasoning", "completed", 70, "LLM 推理完成", duration_ms=reasoning_ms)

        # ── Stage 4: 清理输出（如果模型仍输出了 JSON 代码块，提取文本内容） ──
        cleaned_response = full_response
        report_json = _extract_json(full_response)
        is_structured = False  # 我们现在期望 Markdown，不做结构化渲染

        pctx.add_event("formatting", "completed", 80, "Markdown 输出")

        # ── Stage 5: Verification ──
        pctx.add_event("verification", "running", 85, "开始验证")
        verify_assistant_output(
            text=full_response,
            report_json=None,
            sources=[{"source_id": s["source_id"], "trusted": s["trusted"]} for s in sources],
            ctx=pctx,
            expected_keys=None,
        )
        decision = get_verification_decision(pctx)
        pctx.add_event("verification", "completed", 90, f"验证结果: {decision}")

        # ── Stage 6: 持久化 ──
        pctx.result_summary = {
            "mode": mode,
            "structured": is_structured,
            "verification_decision": decision,
            "sources_count": len(sources),
            "official_count": sum(1 for s in sources if s.get("trusted")),
        }

        saved_session_id = session_id
        if user_id:
            try:
                saved_session_id = await _save_chat_messages(
                    user_id=user_id,
                    session_id=session_id,
                    user_message=user_message,
                    assistant_response=full_response,
                    citations=[
                        {"source": s.get("source_id", ""), "text": s.get("excerpt", "")[:150],
                         "url": s.get("url", ""), "trusted": s.get("trusted", False)}
                        for s in sources
                    ] if sources else None,
                )
            except Exception as e:
                logger.warning(f"Failed to persist chat: {e}")

        # Persist pipeline run
        await pctx.persist()

        # ── Stage 7: 完成 ──
        done_data: Dict[str, Any] = {
            "type": "done",
            "run_id": pctx.run_id,
            "full_content": full_response,
            "mode": mode,
            "structured": is_structured,
            "verification_decision": decision,
        }
        if report_json and is_structured:
            done_data["report_json"] = report_json
        if sources:
            done_data["sources"] = [
                {
                    "source_id": s["source_id"],
                    "trusted": s["trusted"],
                    "kind": s.get("kind", "other"),
                    "title": s.get("title", ""),
                    "url": s.get("url", ""),
                    "excerpt": s.get("excerpt", "")[:200],
                    "institution": s.get("institution", ""),
                }
                for s in sources
            ]
        if saved_session_id:
            done_data["session_id"] = saved_session_id

        yield _sse(done_data)

    except Exception as e:
        logger.error(f"Legal assistant error: {e}\n{traceback.format_exc()}")
        pctx.status = "failed"
        pctx.add_event("error", "error", 0, str(e))
        try:
            await pctx.persist()
        except Exception:
            pass
        yield _sse({"type": "error", "error": str(e)})


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _save_chat_messages(
    user_id: int, session_id: Optional[int],
    user_message: str, assistant_response: str,
    citations: Optional[list] = None,
) -> int:
    async with async_session_maker() as db:
        if session_id:
            result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            )
            session = result.scalar_one_or_none()
        else:
            session = None

        if not session:
            title = user_message[:30] + ("..." if len(user_message) > 30 else "")
            session = ChatSession(user_id=user_id, title=title, context_type=ContextType.GENERAL)
            db.add(session)
            await db.flush()

        db.add(ChatMessageModel(session_id=session.id, role="user", content=user_message))
        db.add(ChatMessageModel(
            session_id=session.id, role="assistant", content=assistant_response,
            citations=citations, model_used="deepseek-reasoner",
        ))
        await db.commit()
        return session.id


# ═══════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════

@router.get("/chat/stream")
async def stream_chat(
    message: str = Query(...),
    mode: str = Query(default="qa"),
    jurisdiction: str = Query(default="CN"),
    session_id: Optional[int] = Query(default=None),
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """流式法律问答（GET，支持 query param token 认证）。"""
    if not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    user_id = None
    if token:
        try:
            from jose import jwt, JWTError
            from app.config import settings
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = int(payload.get("sub", 0)) or None
        except Exception:
            pass

    history = []
    if session_id and user_id:
        result = await db.execute(
            select(ChatMessageModel).where(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at.asc())
        )
        msgs = result.scalars().all()
        history = [{"role": m.role, "content": m.content} for m in msgs]

    return StreamingResponse(
        legal_assistant_stream(
            user_message=message, mode=mode, jurisdiction=jurisdiction,
            history=history if history else None,
            session_id=session_id, user_id=user_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/upload")
async def stream_chat_with_file(
    message: str = Form(...),
    mode: str = Form(default="qa"),
    jurisdiction: str = Form(default="CN"),
    file: Optional[UploadFile] = File(default=None),
    session_id: Optional[int] = Form(default=None),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """带文件上传的流式法律问答（POST multipart）。"""
    if not message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    file_text = ""
    if file:
        content = await file.read()
        file_text = parse_uploaded_file(content, file.filename or "file")

    return StreamingResponse(
        legal_assistant_stream(
            user_message=message, mode=mode, jurisdiction=jurisdiction,
            file_text=file_text, session_id=session_id,
            user_id=current_user.id if current_user else None,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/chat")
async def send_message(request: ChatRequest):
    """非流式法律问答（兼容旧接口）。"""
    try:
        registry = get_provider_registry()
        chat_client = registry.get_chat_client("deepseek", "deepseek-reasoner")
        system_prompt = """你是"合同哨兵"的法律助手。基于中国法律法规回答问题，引用具体法条。"""
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=request.message),
        ]
        response = await chat_client.chat(messages, temperature=0.4, max_tokens=2000)
        return {"response": response.content, "model": response.model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════
# 报告导出
# ═══════════════════════════════════════════════════════════

@router.get("/export/{run_id}")
async def export_assistant_report(
    run_id: str,
    format: str = Query(default="docx"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出法律助手报告为 DOCX 或 PDF。"""
    from app.models.pipeline import PipelineRun
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.sources), selectinload(PipelineRun.approval))
        .where(PipelineRun.run_id == run_id, PipelineRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    # Get the last assistant message for this run's session
    # For now, get from chat messages by searching recent
    from app.services.export_service import ExportService
    from urllib.parse import quote

    export_service = ExportService()

    sources_data = [
        {
            "source_id": s.source_id,
            "trusted": s.trusted,
            "title": s.title or "",
            "url": s.url or "",
            "excerpt": (s.excerpt or "")[:300],
            "institution": s.institution or "",
        }
        for s in (run.sources or [])
    ]

    mode_label = MODE_SCHEMAS.get(run.mode or "qa", {}).get("label", "法律分析")
    download_name = f"法律助手_{mode_label}_{run.run_id[:8]}"

    if format == "pdf":
        output_path = await export_service.export_assistant_report_pdf(
            run=run, sources=sources_data, mode_label=mode_label,
        )
        media_type = "application/pdf"
        download_name += ".pdf"
    else:
        output_path = await export_service.export_assistant_report_docx(
            run=run, sources=sources_data, mode_label=mode_label,
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        download_name += ".docx"

    encoded = quote(download_name)
    return FileResponse(
        path=output_path, media_type=media_type, filename="report.docx",
        headers={"Content-Disposition": f"attachment; filename=report.docx; filename*=UTF-8''{encoded}"},
    )


# ═══════════════════════════════════════════════════════════
# 会话管理（保持兼容）
# ═══════════════════════════════════════════════════════════

@router.post("/sessions")
async def create_session(
    title: str = "新对话",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(user_id=current_user.id, title=title, context_type=ContextType.GENERAL)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None}


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc()).limit(50)
    )
    sessions = result.scalars().all()
    return [
        {"id": s.id, "title": s.title,
         "created_at": s.created_at.isoformat() if s.created_at else None,
         "updated_at": s.updated_at.isoformat() if s.updated_at else None,
         "message_count": len(s.messages) if s.messages else 0}
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")
    msg_result = await db.execute(
        select(ChatMessageModel).where(ChatMessageModel.session_id == session_id)
        .order_by(ChatMessageModel.created_at.asc())
    )
    messages = msg_result.scalars().all()
    return [
        {"id": m.id, "role": m.role, "content": m.content, "citations": m.citations,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in messages
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.execute(sa_delete(ChatMessageModel).where(ChatMessageModel.session_id == session_id))
    await db.delete(session)
    await db.commit()
