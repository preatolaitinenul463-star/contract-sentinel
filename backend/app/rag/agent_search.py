"""Agent Search — 实时从官方法律网站搜取最新法条。

升级版：
  1. DuckDuckGo 搜索获取候选 URL
  2. 并发抓取候选页面正文（而非仅依赖 snippet）
  3. 用 Extractor 抽取正文 + 选取与 query 最相关段落
  4. 输出结构化 sources（含 trusted/kind/excerpt/institution 等）

策略（推荐混合）：
  - 法条/法规依据 → 优先官方白名单（trusted=true）
  - 案例/新闻/观点 → 允许"网络参考"（trusted=false），但强制标注
  - 官方源 snippet 也保留作为 fallback（防抓取失败）
"""

import asyncio
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import quote, unquote, parse_qs, urlparse

import httpx
from loguru import logger

from app.telemetry import record_counter, record_histogram


# ═══════════════════════════════════════════════════════════
# 白名单域名 —— 只信任这些官方源
# ═══════════════════════════════════════════════════════════

TRUSTED_DOMAINS: Dict[str, List[Dict[str, str]]] = {
    "CN": [
        {"domain": "flk.npc.gov.cn", "name": "国家法律法规数据库"},
        {"domain": "www.npc.gov.cn", "name": "全国人大"},
        {"domain": "npc.gov.cn", "name": "全国人大"},
        {"domain": "www.gov.cn", "name": "中国政府网"},
        {"domain": "court.gov.cn", "name": "最高人民法院"},
        {"domain": "gongbao.court.gov.cn", "name": "最高法公报"},
        {"domain": "ipc.court.gov.cn", "name": "最高法知产庭"},
        {"domain": "www.cac.gov.cn", "name": "网信办"},
        {"domain": "www.moj.gov.cn", "name": "司法部"},
        {"domain": "www.samr.gov.cn", "name": "市场监管总局"},
        {"domain": "htsfwb.samr.gov.cn", "name": "合同示范文本库"},
    ],
    "HK": [
        {"domain": "www.elegislation.gov.hk", "name": "电子版香港法例"},
        {"domain": "elegislation.gov.hk", "name": "电子版香港法例"},
    ],
    "SG": [
        {"domain": "sso.agc.gov.sg", "name": "Singapore Statutes Online"},
    ],
    "UK": [
        {"domain": "www.legislation.gov.uk", "name": "UK Legislation"},
        {"domain": "legislation.gov.uk", "name": "UK Legislation"},
    ],
    "US": [
        {"domain": "www.ecfr.gov", "name": "eCFR"},
        {"domain": "ecfr.gov", "name": "eCFR"},
    ],
}

GOV_CN_SUFFIX = ".gov.cn"


def _build_site_filter(jurisdiction: str) -> str:
    domains = TRUSTED_DOMAINS.get(jurisdiction, TRUSTED_DOMAINS.get("CN", []))
    core_domains = [d["domain"] for d in domains[:5]]
    return " OR ".join(f"site:{d}" for d in core_domains)


def _is_trusted_url(url: str, jurisdiction: str) -> tuple:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return False, ""
    domains = TRUSTED_DOMAINS.get(jurisdiction, []) + TRUSTED_DOMAINS.get("CN", [])
    for d in domains:
        trusted = d["domain"]
        if hostname == trusted or hostname.endswith(f".{trusted}"):
            return True, d["name"]
    if hostname.endswith(GOV_CN_SUFFIX):
        return True, "政府官网"
    return False, ""


# ═══════════════════════════════════════════════════════════
# 合同类型 → 搜索关键词
# ═══════════════════════════════════════════════════════════

CONTRACT_TYPE_KEYWORDS = {
    "general": "民法典 合同编 违约责任 合同效力",
    "labor": "劳动合同法 劳动者权益 解除劳动合同 经济补偿",
    "tech": "民法典 技术合同 知识产权 保密义务 竞业限制",
    "sales": "民法典 买卖合同 产品质量法 交付验收 违约赔偿",
    "lease": "民法典 租赁合同 租金 押金退还 合同解除",
    "service": "民法典 服务合同 委托合同 违约责任",
    "nda": "反不正当竞争法 商业秘密 保密协议 竞业禁止",
}


# ═══════════════════════════════════════════════════════════
# 正文段落相关性选择
# ═══════════════════════════════════════════════════════════

def _select_relevant_excerpts(full_text: str, query: str, max_excerpts: int = 3, max_len: int = 600) -> str:
    """从全文中选取与 query 最相关的段落作为 excerpt。"""
    if not full_text or not query:
        return full_text[:max_len] if full_text else ""

    # 按段落切分
    paragraphs = [p.strip() for p in re.split(r'\n{2,}|\r\n{2,}', full_text) if p.strip() and len(p.strip()) > 30]
    if not paragraphs:
        # 按句子切分
        paragraphs = [s.strip() for s in re.split(r'[。！？\n]', full_text) if s.strip() and len(s.strip()) > 15]
    if not paragraphs:
        return full_text[:max_len]

    # 简单关键词匹配评分
    keywords = set(re.findall(r'[\u4e00-\u9fff]+', query))
    scored = []
    for p in paragraphs:
        score = sum(1 for kw in keywords if kw in p)
        # 法条格式加分
        if re.search(r'第.{1,5}条', p):
            score += 2
        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    selected = [p for _, p in scored[:max_excerpts]]
    result = "\n\n".join(selected)
    return result[:max_len * max_excerpts]


class AgentSearch:
    """实时从官方法律网站搜取法条。支持全文抓取与摘录提取。"""

    def __init__(self, max_fetch_concurrency: int = 3, fetch_timeout: float = 15.0):
        self._max_concurrency = max_fetch_concurrency
        self._fetch_timeout = fetch_timeout

    async def search_laws(
        self,
        contract_type: str = "general",
        jurisdiction: str = "CN",
        key_clauses: Optional[List[str]] = None,
        custom_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """搜索法条并返回结构化 sources。"""
        start = time.time()

        if custom_query:
            query = custom_query
        else:
            base_keywords = CONTRACT_TYPE_KEYWORDS.get(contract_type, "民法典 合同 违约")
            raw_clauses = (key_clauses or [])[:3]
            clause_strs = [
                str(c.get("name", c)) if isinstance(c, dict) else str(c)
                for c in raw_clauses if c
            ]
            clause_keywords = " ".join(clause_strs)
            query = f"{base_keywords} {clause_keywords}".strip()

        results = []

        # Check cache first
        from app.pipeline.cache import cache_get, cache_set
        cache_key = f"{query}:{jurisdiction}"
        cached = await cache_get("search", cache_key, ttl=900)
        if cached:
            logger.info(f"Agent Search cache hit for '{query[:30]}...'")
            return cached

        # 策略1: 官方源搜索
        try:
            official = await self._search_official(query, jurisdiction)
            results.extend(official)
        except Exception as e:
            logger.warning(f"Agent Search official failed: {e}")

        # 策略2: 开放搜索
        try:
            open_results = await self._search_open(query, jurisdiction)
            results.extend(open_results)
        except Exception as e:
            logger.warning(f"Agent Search open failed: {e}")

        # 去重
        seen = set()
        unique = []
        for r in results:
            key = r.get("url", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(r)

        # 并发抓取全文并提取摘录
        unique = await self._enrich_with_fulltext(unique, query)

        elapsed = time.time() - start
        official_count = sum(1 for r in unique if r.get("trusted"))
        open_count = sum(1 for r in unique if not r.get("trusted"))

        record_counter("sentinel_search_official_hits_total", official_count)
        record_counter("sentinel_search_open_hits_total", open_count)
        record_histogram("sentinel_search_duration_seconds", elapsed, {"jurisdiction": jurisdiction})

        logger.info(
            f"Agent Search: query='{query[:40]}...' "
            f"jurisdiction={jurisdiction} "
            f"results={len(unique)} (official={official_count}, open={open_count}) "
            f"in {elapsed:.1f}s"
        )
        final = unique[:8]
        # Cache results
        await cache_set("search", cache_key, final, ttl=900)
        return final

    async def _search_official(self, query: str, jurisdiction: str) -> List[Dict[str, Any]]:
        site_filter = _build_site_filter(jurisdiction)
        full_query = f"{query} {site_filter}"
        raw_results = await self._duckduckgo_search(full_query)
        trusted_results = []
        for r in raw_results:
            is_trusted, source_name = _is_trusted_url(r["url"], jurisdiction)
            if is_trusted:
                r["source"] = f"{source_name}（官方）"
                r["trusted"] = True
                r["kind"] = "statute"
                r["institution"] = source_name
                trusted_results.append(r)
        return trusted_results

    async def _search_open(self, query: str, jurisdiction: str) -> List[Dict[str, Any]]:
        raw_results = await self._duckduckgo_search(query)
        labeled = []
        seen_urls = set()
        for r in raw_results:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            is_trusted, source_name = _is_trusted_url(url, jurisdiction)
            if is_trusted:
                r["source"] = f"{source_name}（官方）"
                r["trusted"] = True
                r["kind"] = "statute"
                r["institution"] = source_name
            else:
                r["source"] = "网络参考"
                r["trusted"] = False
                r["kind"] = "other"
                r["institution"] = ""
            labeled.append(r)
        return labeled

    async def _enrich_with_fulltext(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """并发抓取 URL 正文，用 Extractor 提取，并选取相关段落作为 excerpt。"""
        if not results:
            return results

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def fetch_one(r: Dict[str, Any]) -> Dict[str, Any]:
            url = r.get("url", "")
            if not url or not url.startswith("http"):
                return r
            async with semaphore:
                try:
                    async with httpx.AsyncClient(timeout=self._fetch_timeout, follow_redirects=True) as client:
                        resp = await client.get(url, headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                        })
                        if resp.status_code != 200:
                            record_counter("sentinel_fetch_failure_total", 1)
                            return r

                    from app.rag.extractor import Extractor
                    extractor = Extractor()
                    doc = extractor.extract(resp.text, url, "agent_search")
                    if doc.content and len(doc.content) > 50:
                        excerpt = _select_relevant_excerpts(doc.content, query)
                        if excerpt:
                            r["text"] = excerpt
                            r["fulltext_fetched"] = True
                        if doc.title and doc.title != "Untitled":
                            r["title"] = doc.title
                        if doc.institution:
                            r["institution"] = doc.institution
                        if doc.published_date:
                            r["published_date"] = doc.published_date.isoformat()
                        # detect kind
                        if doc.doc_type in ("law", "regulation", "interpretation"):
                            r["kind"] = "statute"
                        elif doc.doc_type == "notice":
                            r["kind"] = "commentary"
                    record_counter("sentinel_fetch_success_total", 1)
                except httpx.TimeoutException:
                    logger.debug(f"Fetch timeout: {url[:60]}")
                    record_counter("sentinel_fetch_failure_total", 1)
                except Exception as e:
                    logger.debug(f"Fetch error {url[:60]}: {e}")
                    record_counter("sentinel_fetch_failure_total", 1)
            return r

        enriched = await asyncio.gather(*[fetch_one(r) for r in results])
        return list(enriched)

    async def _duckduckgo_search(self, query: str) -> List[Dict[str, Any]]:
        results = []
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    },
                )
                if response.status_code != 200:
                    logger.warning(f"DuckDuckGo returned {response.status_code}")
                    return results

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "lxml")
                for item in soup.select(".result")[:10]:
                    title_elem = item.select_one(".result__a")
                    snippet_elem = item.select_one(".result__snippet")
                    if not title_elem or not snippet_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    snippet = snippet_elem.get_text(strip=True)
                    if not snippet or len(snippet) < 15:
                        continue
                    raw_url = title_elem.get("href", "")
                    url = self._extract_real_url(raw_url)
                    results.append({
                        "source": "搜索结果",
                        "title": title,
                        "text": snippet,
                        "url": url,
                        "trusted": False,
                        "kind": "other",
                        "institution": "",
                        "fulltext_fetched": False,
                    })
        except httpx.TimeoutException:
            logger.warning("DuckDuckGo search timed out")
        except Exception as e:
            logger.warning(f"DuckDuckGo search error: {e}")
        return results

    @staticmethod
    def _extract_real_url(ddg_url: str) -> str:
        if "uddg=" in ddg_url:
            try:
                parsed = urlparse(ddg_url)
                qs = parse_qs(parsed.query)
                real = qs.get("uddg", [ddg_url])[0]
                return unquote(real)
            except Exception:
                return ddg_url
        return ddg_url
