"""Contract comparison API routes - 真实 AI 对比流水线."""
import asyncio
import hashlib
import json
import traceback
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_maker
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.models.comparison import ComparisonResult
from app.schemas.comparison import CompareRequest, CompareResponse
from app.api.deps import get_current_user, get_current_user_optional
from app.providers import get_provider_registry, ChatMessage
from app.config import settings

router = APIRouter()


def _sse(data: dict) -> str:
    """Format as SSE event."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_json(text: str) -> dict:
    """从文本中提取 JSON"""
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text)
    except Exception:
        return {}


def _parse_file_text(content: bytes, filename: str) -> str:
    """解析上传文件为纯文本"""
    if filename.endswith(".pdf"):
        try:
            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            return f"[PDF解析失败: {e}]"
    elif filename.endswith(".docx"):
        try:
            import io
            from docx import Document
            doc = Document(io.BytesIO(content))
            return "\n".join(para.text for para in doc.paragraphs)
        except Exception as e:
            return f"[DOCX解析失败: {e}]"
    else:
        try:
            return content.decode("utf-8")
        except Exception:
            return content.decode("gbk", errors="ignore")


async def real_compare_stream(
    text_a: str,
    text_b: str,
    filename_a: str,
    filename_b: str,
    ctx: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """
    真实 AI 对比流水线 - 流式返回对比进度和结果

    Pipeline:
      Stage 1: DocIngest A & B (文档解析) → 已完成(上传时)
      Stage 2: ClauseStruct (条款结构化) → DeepSeek
      Stage 3: LLM Compare (AI 深度对比) → DeepSeek
      Stage 4: Complete (汇总结果)
    """
    registry = get_provider_registry()
    all_changes = []

    try:
        # ============================================
        # Stage 1: 文档解析 (已完成)
        # ============================================
        yield _sse({
            "stage": "doc_ingest",
            "status": "completed",
            "progress": 10,
            "message": "文档解析完成",
            "agent": "文档解析",
            "detail": f"原合同: {len(text_a)} 字符, 新合同: {len(text_b)} 字符",
        })
        await asyncio.sleep(0.3)

        # ============================================
        # Stage 2: 条款结构化 (ClauseStructAgent)
        # ============================================
        yield _sse({
            "stage": "clause_struct",
            "status": "running",
            "progress": 15,
            "message": "正在提取两份合同的结构...",
            "agent": "条款结构化",
        })

        # 条款结构化用 MiniMax（简单提取任务，节省 DeepSeek 额度）
        struct_client = registry.get_chat_client("minimax", "abab6.5s-chat")

        struct_prompt = f"""分别提取以下两份合同的关键信息，返回JSON：
{{
  "contract_a": {{
    "parties": ["甲方名称", "乙方名称"],
    "key_clauses": ["付款条款", "违约条款", "保密条款", ...]
  }},
  "contract_b": {{
    "parties": ["甲方名称", "乙方名称"],
    "key_clauses": ["付款条款", "违约条款", "保密条款", ...]
  }}
}}

原合同（前2000字）：
{text_a[:2000]}

新合同（前2000字）：
{text_b[:2000]}"""

        struct_response = await struct_client.chat(
            [ChatMessage(role="user", content=struct_prompt)],
            temperature=0.1, max_tokens=1000,
        )

        structures = _parse_json(struct_response.content)

        yield _sse({
            "stage": "clause_struct",
            "status": "completed",
            "progress": 30,
            "message": "结构提取完成",
            "agent": "条款结构化",
            "detail": json.dumps(structures, ensure_ascii=False),
            "tokens": struct_response.tokens_input + struct_response.tokens_output,
        })
        await asyncio.sleep(0.3)

        # ============================================
        # Stage 3: AI 深度对比 (LLM Compare) - 流式
        # ============================================
        # AI 深度对比用 DeepSeek Reasoner（核心推理任务）
        chat_client = registry.get_chat_client("deepseek", "deepseek-reasoner")

        yield _sse({
            "stage": "llm_compare",
            "status": "running",
            "progress": 35,
            "message": "AI 正在逐条对比...",
            "agent": "智能对比",
        })

        compare_prompt = f"""你是一位资深法务合同对比专家。请逐条对比以下两份合同的差异，并分析每处变更的风险影响。

## 对比要求
1. 逐条对比，识别所有新增、删除和修改的条款
2. 分析每处变更对合同当事人的影响
3. 评估风险变化方向（上升/下降/中性）

## 输出格式
逐条输出每个差异，格式：
===CHANGE_START===
change_type: added/removed/modified
clause_type: 条款类型（如付款条款、违约责任等）
original_text: 原文（修改/删除时填写，新增则留空）
new_text: 新文（新增/修改时填写，删除则留空）
risk_impact: increased/decreased/neutral
analysis: 变更影响分析
===CHANGE_END===

所有差异分析完毕后，输出总结：
===SUMMARY_START===
主要变更摘要和整体风险评估
===SUMMARY_END===

===KEY_CHANGES_START===
关键变更点1
关键变更点2
关键变更点3
===KEY_CHANGES_END===

## 原合同
{text_a[:5000]}

## 新合同
{text_b[:5000]}"""

        full_response = ""
        async for token in chat_client.chat_stream(
            [ChatMessage(role="user", content=compare_prompt)],
            temperature=0.2, max_tokens=4096,
        ):
            full_response += token

            yield _sse({
                "stage": "llm_compare",
                "status": "streaming",
                "progress": 40 + min(40, len(full_response) // 80),
                "message": "AI 正在分析差异...",
                "agent": "智能对比",
                "token": token,
            })

            # 检查是否有完整的变更项
            while "===CHANGE_END===" in full_response:
                change_block, full_response = full_response.split("===CHANGE_END===", 1)
                if "===CHANGE_START===" in change_block:
                    change_text = change_block.split("===CHANGE_START===")[1]
                    change = _parse_change_block(change_text, len(all_changes))
                    if change:
                        all_changes.append(change)
                        yield _sse({
                            "stage": "llm_compare",
                            "status": "found_change",
                            "progress": 50,
                            "message": f"发现差异: {change['clause_type']}",
                            "agent": "智能对比",
                            "change_item": change,
                        })

        # 提取总结
        summary = ""
        if "===SUMMARY_START===" in full_response:
            parts = full_response.split("===SUMMARY_START===")
            if len(parts) > 1:
                summary = parts[1].split("===SUMMARY_END===")[0].strip()

        # 提取关键变更
        key_changes = []
        if "===KEY_CHANGES_START===" in full_response:
            parts = full_response.split("===KEY_CHANGES_START===")
            if len(parts) > 1:
                kc_text = parts[1].split("===KEY_CHANGES_END===")[0].strip()
                key_changes = [line.strip() for line in kc_text.split("\n") if line.strip()]

        yield _sse({
            "stage": "llm_compare",
            "status": "completed",
            "progress": 90,
            "message": f"对比完成 - 发现 {len(all_changes)} 处差异",
            "agent": "智能对比",
        })
        await asyncio.sleep(0.3)

        # ============================================
        # Stage 4: 完成 - 持久化结果
        # ============================================
        added = sum(1 for c in all_changes if c["change_type"] == "added")
        removed = sum(1 for c in all_changes if c["change_type"] == "removed")
        modified = sum(1 for c in all_changes if c["change_type"] == "modified")
        risk_increased = sum(1 for c in all_changes if c["risk_impact"] == "increased")

        comparison_id = None
        if ctx is not None:
            try:
                comparison_id = await _save_comparison_result(
                    ctx=ctx,
                    all_changes=all_changes,
                    summary=summary,
                    key_changes=key_changes,
                    added=added,
                    removed=removed,
                    modified=modified,
                    risk_increased=risk_increased,
                )
            except Exception as e:
                from loguru import logger
                logger.warning(f"Failed to persist comparison result: {e}")

        yield _sse({
            "stage": "complete",
            "status": "completed",
            "progress": 100,
            "message": "对比完成",
            "summary": summary,
            "key_changes": key_changes,
            "comparison_id": comparison_id,
            "stats": {
                "added": added,
                "removed": removed,
                "modified": modified,
                "risk_increased": risk_increased,
                "total": len(all_changes),
            },
            "all_changes": all_changes,
        })

    except Exception as e:
        yield _sse({
            "stage": "error",
            "status": "error",
            "progress": 0,
            "message": f"对比失败: {str(e)}",
            "detail": traceback.format_exc(),
        })


def _parse_change_block(text: str, index: int) -> dict | None:
    """解析变更块"""
    try:
        lines = text.strip().split("\n")
        change = {"id": f"compare_{index}"}
        for line in lines:
            line = line.strip()
            if line.startswith("change_type:"):
                change["change_type"] = line.split(":", 1)[1].strip()
            elif line.startswith("clause_type:"):
                change["clause_type"] = line.split(":", 1)[1].strip()
            elif line.startswith("original_text:"):
                val = line.split(":", 1)[1].strip()
                change["original_text"] = val if val and val != "无" else None
            elif line.startswith("new_text:"):
                val = line.split(":", 1)[1].strip()
                change["new_text"] = val if val and val != "无" else None
            elif line.startswith("risk_impact:"):
                change["risk_impact"] = line.split(":", 1)[1].strip()
            elif line.startswith("analysis:"):
                change["analysis"] = line.split(":", 1)[1].strip()

        if change.get("change_type") and change.get("clause_type"):
            # Ensure defaults
            change.setdefault("risk_impact", "neutral")
            change.setdefault("analysis", "")
            return change
    except Exception:
        pass
    return None


async def _save_comparison_result(
    ctx: dict,
    all_changes: list,
    summary: str,
    key_changes: list,
    added: int,
    removed: int,
    modified: int,
    risk_increased: int,
) -> Optional[int]:
    """Persist Contract A/B + ComparisonResult to database."""
    async with async_session_maker() as db:
        user_id = ctx.get("user_id") or 0

        # Create Contract A record
        content_a = ctx.get("content_a", b"")
        hash_a = hashlib.sha256(content_a).hexdigest() if content_a else "none"
        contract_a = Contract(
            user_id=user_id,
            filename=ctx.get("filename_a", "contract_a"),
            file_hash=hash_a,
            file_path="in-memory",
            file_size=len(content_a),
            mime_type="application/octet-stream",
            raw_text=ctx.get("text_a", "")[:50000],
            status=ContractStatus.PARSED,
        )
        db.add(contract_a)

        # Create Contract B record
        content_b = ctx.get("content_b", b"")
        hash_b = hashlib.sha256(content_b).hexdigest() if content_b else "none"
        contract_b = Contract(
            user_id=user_id,
            filename=ctx.get("filename_b", "contract_b"),
            file_hash=hash_b,
            file_path="in-memory",
            file_size=len(content_b),
            mime_type="application/octet-stream",
            raw_text=ctx.get("text_b", "")[:50000],
            status=ContractStatus.PARSED,
        )
        db.add(contract_b)
        await db.flush()

        comparison = ComparisonResult(
            user_id=user_id,
            contract_a_id=contract_a.id,
            contract_b_id=contract_b.id,
            changes=all_changes,
            added_count=added,
            removed_count=removed,
            modified_count=modified,
            risk_increased_count=risk_increased,
            summary=summary,
            key_changes=key_changes,
            model_used="deepseek-reasoner",
            tokens_used=0,
        )
        db.add(comparison)
        await db.commit()
        await db.refresh(comparison)
        return comparison.id


@router.post("/upload-and-compare")
async def upload_and_compare(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """上传两份合同并直接开始对比（流式返回），结果持久化到数据库"""
    content_a = await file_a.read()
    content_b = await file_b.read()

    filename_a = file_a.filename or "contract_a"
    filename_b = file_b.filename or "contract_b"

    text_a = _parse_file_text(content_a, filename_a)
    text_b = _parse_file_text(content_b, filename_b)

    if not text_a.strip():
        text_a = "[原合同内容为空或无法解析]"
    if not text_b.strip():
        text_b = "[新合同内容为空或无法解析]"

    ctx = {
        "user_id": current_user.id if current_user else None,
        "filename_a": filename_a,
        "filename_b": filename_b,
        "content_a": content_a,
        "content_b": content_b,
        "text_a": text_a,
        "text_b": text_b,
    }

    return StreamingResponse(
        real_compare_stream(
            text_a=text_a,
            text_b=text_b,
            filename_a=filename_a,
            filename_b=filename_b,
            ctx=ctx,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=CompareResponse, status_code=status.HTTP_201_CREATED)
async def compare_contracts(
    request: CompareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare two contracts (non-streaming, uses CompareService)."""
    from app.services.compare_service import CompareService

    # Get contract A
    result_a = await db.execute(
        select(Contract).where(
            Contract.id == request.contract_a_id,
            Contract.user_id == current_user.id,
        )
    )
    contract_a = result_a.scalar_one_or_none()

    if not contract_a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原合同不存在",
        )

    # Get contract B
    result_b = await db.execute(
        select(Contract).where(
            Contract.id == request.contract_b_id,
            Contract.user_id == current_user.id,
        )
    )
    contract_b = result_b.scalar_one_or_none()

    if not contract_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="新合同不存在",
        )

    service = CompareService(db)
    comparison = await service.compare_contracts(
        contract_a=contract_a,
        contract_b=contract_b,
        analyze_risk=request.analyze_risk_impact,
    )
    return comparison


@router.get("/{comparison_id}", response_model=CompareResponse)
async def get_comparison_result(
    comparison_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get comparison result."""
    result = await db.execute(
        select(ComparisonResult).where(
            ComparisonResult.id == comparison_id,
            ComparisonResult.user_id == current_user.id,
        )
    )
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对比结果不存在",
        )

    return comparison


@router.get("", response_model=list[CompareResponse])
async def list_comparisons(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's comparison results."""
    query = (
        select(ComparisonResult)
        .where(ComparisonResult.user_id == current_user.id)
        .order_by(ComparisonResult.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    comparisons = result.scalars().all()

    return comparisons
