import logging
from typing import Optional

logger = logging.getLogger(__name__)

LEVEL1_INDUSTRIES = [
    "农林牧渔", "煤炭", "石油石化", "有色金属", "钢铁",
    "基础化工", "建筑材料", "机械设备", "电力设备", "电子",
    "通信", "计算机", "国防军工", "汽车", "家用电器",
    "纺织服饰", "轻工制造", "食品饮料", "美容护理", "医药生物",
    "建筑装饰", "公用事业", "环保", "交通运输", "房地产",
    "商贸零售", "社会服务", "传媒", "银行", "非银金融", "综合"
]

INDUSTRY_MAPPING = {
    "游戏": "传媒",
    "网络游戏": "传媒",
    "游戏行业": "传媒",
    "手游": "传媒",
    "新能源汽车": "汽车",
    "新能源车": "汽车",
    "电动车": "汽车",
    "新能源": "电力设备",
    "光伏": "电力设备",
    "风电": "电力设备",
    "锂电池": "电力设备",
    "锂电": "电力设备",
    "储能": "电力设备",
    "医疗器械": "医药生物",
    "医疗设备": "医药生物",
    "生物医药": "医药生物",
    "创新药": "医药生物",
    "中药": "医药生物",
    "半导体": "电子",
    "芯片": "电子",
    "集成电路": "电子",
    "IC": "电子",
    "人工智能": "计算机",
    "AI": "计算机",
    "大模型": "计算机",
    "云计算": "计算机",
    "数据要素": "计算机",
    "元宇宙": "传媒",
    "虚拟现实": "传媒",
    "VR": "传媒",
    "AR": "传媒",
    "数字经济": "计算机",
    "软件": "计算机",
    "信息安全": "计算机",
    "卫星导航": "国防军工",
    "航天军工": "国防军工",
    "航空军工": "国防军工",
    "船舶": "国防军工",
    "稀土": "有色金属",
    "黄金": "有色金属",
    "铜": "有色金属",
    "铝": "有色金属",
    "锂": "有色金属",
    "钴": "有色金属",
    "镍": "有色金属",
    "化工": "基础化工",
    "新材料": "基础化工",
    "碳纤维": "基础化工",
    "食品": "食品饮料",
    "饮料": "食品饮料",
    "白酒": "食品饮料",
    "啤酒": "食品饮料",
    "乳制品": "食品饮料",
    "调味品": "食品饮料",
    "休闲食品": "食品饮料",
    "化妆品": "美容护理",
    "医美": "美容护理",
    "眼科": "医药生物",
    "牙科": "医药生物",
    "口腔": "医药生物",
    "血液制品": "医药生物",
    "疫苗": "医药生物",
    "检测": "医药生物",
    "体外诊断": "医药生物",
    "原料药": "医药生物",
    "工程机械": "机械设备",
    "机器人": "机械设备",
    "自动化": "机械设备",
    "激光": "机械设备",
    "高端装备": "机械设备",
    "输配电": "电力设备",
    "电网": "电力设备",
    "电机": "电力设备",
    "电池设备": "电力设备",
    "消费电子": "电子",
    "面板": "电子",
    "LED": "电子",
    "光学": "电子",
    "半导体材料": "电子",
    "通信设备": "通信",
    "通信服务": "通信",
    "电信": "通信",
    "5G": "通信",
    "物联网": "通信",
    "PCB": "电子",
    "被动元件": "电子",
    "集成电路制造": "电子",
    "封测": "电子",
    "分立器件": "电子",
    "城投": "房地产",
    "地产": "房地产",
    "物业管理": "房地产",
    "建筑": "建筑装饰",
    "基建": "建筑装饰",
    "园林": "建筑装饰",
    "装修": "建筑装饰",
    "钢铁行业": "钢铁",
    "煤炭开采": "煤炭",
    "动力煤": "煤炭",
    "焦煤": "煤炭",
    "油气": "石油石化",
    "炼化": "石油石化",
    "农药": "基础化工",
    "化肥": "基础化工",
    "纯碱": "基础化工",
    "氯碱": "基础化工",
    "钛白粉": "基础化工",
    "氟化工": "基础化工",
    "有机硅": "基础化工",
    "MDI": "基础化工",
    "TDI": "基础化工",
    "养殖": "农林牧渔",
    "种植": "农林牧渔",
    "种子": "农林牧渔",
    "饲料": "农林牧渔",
    "畜牧": "农林牧渔",
    "农业": "农林牧渔",
    "造纸": "轻工制造",
    "包装": "轻工制造",
    "印刷": "轻工制造",
    "家居": "轻工制造",
    "家具": "轻工制造",
    "纺织": "纺织服饰",
    "服装": "纺织服饰",
    "鞋帽": "纺织服饰",
    "家电": "家用电器",
    "空调": "家用电器",
    "冰箱": "家用电器",
    "洗衣机": "家用电器",
    "厨卫": "家用电器",
    "小家电": "家用电器",
    "环保工程": "环保",
    "水务": "环保",
    "固废": "环保",
    "大气治理": "环保",
    "污水处理": "环保",
    "航运": "交通运输",
    "港口": "交通运输",
    "公路": "交通运输",
    "铁路": "交通运输",
    "航空": "交通运输",
    "机场": "交通运输",
    "物流": "交通运输",
    "快递": "交通运输",
    "公路货运": "交通运输",
    "公交": "交通运输",
    "旅游": "社会服务",
    "景区": "社会服务",
    "酒店": "社会服务",
    "餐饮": "社会服务",
    "教育": "社会服务",
    "体育": "社会服务",
    "演艺": "社会服务",
    "出版": "传媒",
    "影视": "传媒",
    "院线": "传媒",
    "动漫": "传媒",
    "广告": "传媒",
    "数字媒体": "传媒",
    "电视": "传媒",
    "广播": "传媒",
    "银行": "银行",
    "国有银行": "银行",
    "股份制银行": "银行",
    "城商行": "银行",
    "农商行": "银行",
    "保险": "非银金融",
    "证券": "非银金融",
    "信托": "非银金融",
    "租赁": "非银金融",
    "期货": "非银金融",
    "资产管理": "非银金融",
    "多元金融": "非银金融",
    "金控": "非银金融",
    "零售": "商贸零售",
    "百货": "商贸零售",
    "超市": "商贸零售",
    "电商": "商贸零售",
    "跨境电商": "商贸零售",
    "商贸": "商贸零售",
    "燃气": "公用事业",
    "电力": "公用事业",
    "火电": "公用事业",
    "水电": "公用事业",
    "核电": "公用事业",
    "光伏发电": "公用事业",
    "风力发电": "公用事业",
    "综合": "综合",
}


def normalize_to_level1(industry: str) -> str:
    """将任意行业名称标准化为一级行业"""
    if not industry:
        return ""
    
    industry = industry.strip()
    
    if not industry:
        return ""
    
    if industry in LEVEL1_INDUSTRIES:
        return industry
    
    if industry in INDUSTRY_MAPPING:
        return INDUSTRY_MAPPING[industry]
    
    for level1 in LEVEL1_INDUSTRIES:
        if level1 in industry or industry in level1:
            return level1
    
    cleaned = industry.replace("行业", "").strip()
    if cleaned in LEVEL1_INDUSTRIES:
        return cleaned
    
    for level1 in LEVEL1_INDUSTRIES:
        if level1 in cleaned or cleaned in level1:
            return level1
    
    logger.warning(f"行业未能标准化为一级: {industry}")
    return industry


async def get_stock_industry_from_db(ts_code: str) -> Optional[str]:
    """从 stock_list 表查询股票所属行业并标准化"""
    try:
        from app.core.database import dbm
        from sqlalchemy import text
        
        async with dbm.session('report_db') as db:
            result = await db.execute(
                text("SELECT industry FROM stock_list WHERE ts_code = :ts_code"),
                {"ts_code": ts_code}
            )
            row = result.fetchone()
            
            if row and row[0]:
                stock_industry = row[0]
                normalized = normalize_to_level1(stock_industry)
                logger.info(f"股票 {ts_code} 行业: {stock_industry} -> {normalized}")
                return normalized
            
    except Exception as e:
        logger.warning(f"查询股票行业失败 {ts_code}: {e}")
    
    return None


async def get_industry_from_report(report_type: str, report_id: int) -> Optional[str]:
    """从研报记录获取行业并标准化"""
    try:
        from app.core.database import dbm
        from app.models.chunk import StockResearchReportRecord, IndustryResearchReportRecord
        from sqlalchemy import select
        
        async with dbm.session() as db:
            if report_type == "stock":
                result = await db.execute(
                    select(StockResearchReportRecord.industry_name).where(
                        StockResearchReportRecord.report_id == report_id
                    )
                )
            else:
                result = await db.execute(
                    select(IndustryResearchReportRecord.industry_name).where(
                        IndustryResearchReportRecord.report_id == report_id
                    )
                )
            
            row = result.fetchone()
            
            if row and row[0]:
                industry = row[0]
                normalized = normalize_to_level1(industry)
                logger.info(f"研报 {report_type}:{report_id} 行业: {industry} -> {normalized}")
                return normalized
            
    except Exception as e:
        logger.warning(f"查询研报行业失败 {report_type}:{report_id}: {e}")
    
    return None


async def resolve_industry(
    report_type: str,
    report_id: int,
    ts_code: Optional[str] = None,
    existing_industry: Optional[str] = None
) -> str:
    """解析行业名称，按优先级获取并标准化为一级行业"""
    
    if existing_industry:
        normalized = normalize_to_level1(existing_industry)
        if normalized in LEVEL1_INDUSTRIES:
            return normalized
    
    if report_type == "stock":
        industry_from_report = await get_industry_from_report(report_type, report_id)
        if industry_from_report:
            return industry_from_report
        
        if ts_code:
            industry_from_stock = await get_stock_industry_from_db(ts_code)
            if industry_from_stock:
                return industry_from_stock
    
    return ""
