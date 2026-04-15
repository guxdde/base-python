import re
import logging

logger = logging.getLogger(__name__)

CHUNK_TYPE_CONTENT = "content"
CHUNK_TYPE_RISK = "risk"
CHUNK_TYPE_RATING = "rating"
CHUNK_TYPE_CONTACT = "contact"

ANALYST_DECLARATION_PATTERNS = [
    r"执业证书编号",
    r"SAC\s*:?\s*[A-Z0-9]+",
    r"分析师承诺",
    r"执业资质",
    r"证券投资咨询执业资格",
    r"S\d{8,}",
]

RATING_PATTERNS = [
    r"投资评级[说明]?",
    r"买入|增持|减持|卖出|中性",
    r"强于大市|弱于大市|同步大市",
    r"评级\s*(?:标准|定义|说明)",
    r"相对.*涨幅",
    r"未来.*个月内",
]

CONTACT_PATTERNS = [
    r"联系地址",
    r"邮编\d{6}",
    r"电话[：:]?\s*\d{3,4}[-\s]?\d{3,4}[-\s]?\d{3,4}",
    r"传真[：:]?\s*\d{3,4}[-\s]?\d{3,4}[-\s]?\d{3,4}",
    r"官网",
    r"mailto:",
    r"电子邮箱",
    r"客服电话",
    r"客服热线",
    r"公司地址",
    r"[^\s]{20,}大道\d+号",
    r"[^\s]{10,}大厦",
]

RISK_PATTERNS = [
    r"风险提示",
    r"免责声明",
    r"本报告仅供",
    r"不构成.*投资建议",
    r"投资风险",
    r"市场风险",
    r"政策风险",
    r"原料?风险",
    r"技术风险",
    r"经营风险",
    r"行业周期波动风险",
    r"下游需求波动风险",
    r"证券交易.*风险",
    r"请投资者.*风险",
]

PAGE_NUM_PATTERN = r"[-‐‑‒–——边际]*\d+[-‐‑‒–——边际]*\s*(?:页|/|of|P)"

COMPILED_PATTERNS = {
    "analyst": [re.compile(p, re.IGNORECASE) for p in ANALYST_DECLARATION_PATTERNS],
    "rating": [re.compile(p, re.IGNORECASE) for p in RATING_PATTERNS],
    "contact": [re.compile(p, re.IGNORECASE) for p in CONTACT_PATTERNS],
    "risk": [re.compile(p, re.IGNORECASE) for p in RISK_PATTERNS],
}


def is_noise_chunk(text: str) -> tuple[bool, str]:
    """判断是否为噪声块
    
    Args:
        text: 文本内容
        
    Returns:
        (是否为噪声, 噪声类型)
    """
    if not text or len(text.strip()) < 50:
        return False, ""
    
    text_lower = text.lower()
    text_length = len(text)
    
    for pattern in COMPILED_PATTERNS["analyst"]:
        if pattern.search(text):
            return True, CHUNK_TYPE_RISK
    
    for pattern in COMPILED_PATTERNS["rating"]:
        if pattern.search(text):
            return True, CHUNK_TYPE_RATING
    
    for pattern in COMPILED_PATTERNS["contact"]:
        if pattern.search(text):
            return True, CHUNK_TYPE_CONTACT
    
    for pattern in COMPILED_PATTERNS["risk"]:
        if pattern.search(text):
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                if len(matched_text) > 4:
                    return True, CHUNK_TYPE_RISK
    
   Analyst_count = sum(1 for p in COMPILED_PATTERNS["analyst"] if p.search(text))
    risk_count = sum(1 for p in COMPILED_PATTERNS["risk"] if p.search(text))
    
    density_threshold = 0.03
    if text_length < 1000:
        if Analyst_count >= 1 or risk_count >= 2:
            if "分析师" in text or "声明" in text or "承诺" in text:
                return True, CHUNK_TYPE_RISK
    
    if re.search(r"^\s*#+\s*", text):
        if len(text.strip()) < 100:
            return True, CHUNK_TYPE_RISK
    
    return False, ""


def classify_chunk(text: str) -> str:
    """分类块类型
    
    Args:
        text: 文本内容
        
    Returns:
        chunk_type: content/risk/rating/contact
    """
    is_noise, noise_type = is_noise_chunk(text)
    
    if is_noise:
        return noise_type
    
    return CHUNK_TYPE_CONTENT


def filter_chunks(chunks: list) -> tuple[list, dict]:
    """过滤噪声块
    
    Args:
        chunks: 分块列表
        
    Returns:
        (过滤后的分块, 过滤统计)
    """
    stats = {
        "total": len(chunks),
        "content": 0,
        "risk": 0,
        "rating": 0,
        "contact": 0,
    }
    
    filtered = []
    for chunk in chunks:
        text = chunk.get("content", "")
        chunk_type = classify_chunk(text)
        
        chunk_type_key = chunk_type if chunk_type else "content"
        if chunk_type_key == "risk":
            chunk_type_key = "risk"
        
        stats[chunk_type_key] = stats.get(chunk_type_key, 0) + 1
        
        filtered.append({
            "content": text,
            "metadata": {
                **chunk.get("metadata", {}),
                "chunk_type": chunk_type or CHUNK_TYPE_CONTENT,
            }
        })
    
    logger.info(f"分块过滤: {stats}")
    return filtered, stats


def should_include_noise(query: str) -> bool:
    """判断查询是否需要包含噪声内容
    
    Args:
        query: 用户查询
        
    Returns:
        是否包含噪声
    """
    noise_keywords = [
        "风险", "评级", "声明", "免责声明", 
        "分析师", "执业", "联系方式", "地址",
        "电话", "传真"
    ]
    
    for kw in noise_keywords:
        if kw in query:
            return True
    
    return False