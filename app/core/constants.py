"""
项目常量配置
"""
from enum import Enum


class MyEnum(Enum):
    def __get__(self, key, value):
        return self.value

class DataStatus(MyEnum):
    """
    | status | value | label |
    | --- | :---: | :---: |
    | 有效 | 1 | valid |
    | 无效 | 0 | invalid |
    """

    valid = 1
    invalid = 0

# LLM模型配置
llm_model = '0'
model_config = {
    '0': 'no_search_answer',
    '1': 'glm_no_search_answer'
}

# 性别映射
gender_map = {
    0: '男',
    1: '女',
}

# 身份映射
identity_map = {
    0: 50,
    1: 100,
    2: 150
}

# 规则ID映射
rule_id_map = {
    '问答': 1,
    '文件问答': 2
}



# Redis Key模板
email_code_redis_key = '{email}_email_code'
sms_code_redis_key = '{phone}_sms_code'
question_progress_redis_key = '{question_id}_progress'
finance_questions_processing_key = 'finance_questions_processing'  # 正在处理的金融问题数量
org_finance_questions_processing_key = 'org_{org_id}_finance_questions_processing'  # 按组织区分的正在处理金融问题数量

# 处理限制
MAX_FINANCE_QUESTIONS_PROCESSING = 200  # 最大允许同时处理的金融问题数量

