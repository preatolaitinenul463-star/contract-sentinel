"""Source registry - manages legal document sources."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import re


@dataclass
class LegalSource:
    """A legal document source configuration."""
    id: str
    name: str
    jurisdiction: str
    base_url: str
    allowed_patterns: List[str] = field(default_factory=list)
    seed_urls: List[str] = field(default_factory=list)
    sitemap_url: Optional[str] = None
    rate_limit: float = 1.0  # requests per second
    max_depth: int = 2  # max crawl depth from seed URL
    enabled: bool = True


class SourceRegistry:
    """Registry of legal document sources."""
    
    # Predefined sources
    DEFAULT_SOURCES = [
        # China
        LegalSource(
            id="cn_npc",
            name="国家法律法规数据库",
            jurisdiction="CN",
            base_url="https://flk.npc.gov.cn",
            allowed_patterns=[r"flk\.npc\.gov\.cn/detail"],
            seed_urls=["https://flk.npc.gov.cn/"],
            rate_limit=0.5,
        ),
        LegalSource(
            id="cn_gov",
            name="中国政府网",
            jurisdiction="CN",
            base_url="https://www.gov.cn",
            allowed_patterns=[r"www\.gov\.cn/(zhengce|xinwen)"],
            seed_urls=["https://www.gov.cn/zhengce/"],
            rate_limit=0.5,
        ),
        LegalSource(
            id="cn_court",
            name="最高人民法院",
            jurisdiction="CN",
            base_url="https://www.court.gov.cn",
            allowed_patterns=[r"www\.court\.gov\.cn/(fabu|zixun)"],
            seed_urls=["https://www.court.gov.cn/fabu.html"],
            rate_limit=0.5,
        ),
        LegalSource(
            id="cn_cac",
            name="国家互联网信息办公室",
            jurisdiction="CN",
            base_url="https://www.cac.gov.cn",
            allowed_patterns=[r"www\.cac\.gov\.cn/(xxh|zcfg)"],
            seed_urls=["https://www.cac.gov.cn/zcfg.htm"],
            rate_limit=0.5,
        ),
        
        # Hong Kong
        LegalSource(
            id="hk_eleg",
            name="电子版香港法例",
            jurisdiction="HK",
            base_url="https://www.elegislation.gov.hk",
            allowed_patterns=[r"elegislation\.gov\.hk"],
            seed_urls=["https://www.elegislation.gov.hk/"],
            rate_limit=0.5,
        ),
        
        # Singapore
        LegalSource(
            id="sg_sso",
            name="Singapore Statutes Online",
            jurisdiction="SG",
            base_url="https://sso.agc.gov.sg",
            allowed_patterns=[r"sso\.agc\.gov\.sg"],
            seed_urls=["https://sso.agc.gov.sg/"],
            rate_limit=0.5,
        ),
        
        # UK
        LegalSource(
            id="uk_leg",
            name="UK Legislation",
            jurisdiction="UK",
            base_url="https://www.legislation.gov.uk",
            allowed_patterns=[r"legislation\.gov\.uk"],
            seed_urls=["https://www.legislation.gov.uk/"],
            rate_limit=1.0,
        ),
        
        # US
        LegalSource(
            id="us_ecfr",
            name="eCFR",
            jurisdiction="US",
            base_url="https://www.ecfr.gov",
            allowed_patterns=[r"ecfr\.gov"],
            seed_urls=["https://www.ecfr.gov/"],
            rate_limit=1.0,
        ),
    ]
    
    def __init__(self):
        self.sources: Dict[str, LegalSource] = {}
        self._load_defaults()
    
    def _load_defaults(self) -> None:
        """Load default sources."""
        for source in self.DEFAULT_SOURCES:
            self.sources[source.id] = source
    
    def get_source(self, source_id: str) -> Optional[LegalSource]:
        """Get a source by ID."""
        return self.sources.get(source_id)
    
    def get_sources_by_jurisdiction(self, jurisdiction: str) -> List[LegalSource]:
        """Get all sources for a jurisdiction."""
        return [s for s in self.sources.values() if s.jurisdiction == jurisdiction and s.enabled]
    
    def is_url_allowed(self, url: str, source_id: str) -> bool:
        """Check if a URL is allowed for crawling."""
        source = self.sources.get(source_id)
        if not source:
            return False
        
        for pattern in source.allowed_patterns:
            if re.search(pattern, url):
                return True
        
        return False
    
    def add_source(self, source: LegalSource) -> None:
        """Add a custom source."""
        self.sources[source.id] = source
    
    def list_sources(self) -> List[Dict]:
        """List all sources."""
        return [
            {
                "id": s.id,
                "name": s.name,
                "jurisdiction": s.jurisdiction,
                "base_url": s.base_url,
                "enabled": s.enabled,
            }
            for s in self.sources.values()
        ]
