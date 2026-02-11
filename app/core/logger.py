import os
import logging
import json
import time
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from functools import wraps

# 确保日志目录存在
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
MAIN_LOG_FILE = os.path.join(LOG_DIR, 'app.log')
QUERY_LOG_FILE = os.path.join(LOG_DIR, 'query.log')
ERROR_LOG_FILE = os.path.join(LOG_DIR, 'error.log')

# 默认日志格式 - 修改为包含question_openid和更多详细信息
DEFAULT_LOG_FORMAT = '%(asctime)s [%(levelname)s] [qid:%(question_openid)s] %(module)s:%(lineno)d - %(message)s'
DETAILED_LOG_FORMAT = '%(asctime)s [%(levelname)s] [qid:%(question_openid)s] %(module)s:%(funcName)s:%(lineno)d - %(message)s'
JSON_LOG_FORMAT = '%(message)s'

class QuestionLogFilter(logging.Filter):
    """确保日志包含question_openid"""
    def filter(self, record):
        # 如果没有question_openid字段，添加默认值
        if not hasattr(record, 'question_openid'):
            record.question_openid = 'unknown'
        return True

class JsonFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""
    def format(self, record):
        log_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'level': record.levelname,
            'module': record.module,
            'line': record.lineno,
            'question_openid': getattr(record, 'question_openid', 'unknown')
        }
        
        # 添加其他额外字段
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            # 确保对列表和字典进行适当处理
            extra_data = {}
            for k, v in record.extra.items():
                if isinstance(v, (list, dict)):
                    # 对于列表和字典，保留原始结构但确保可序列化
                    extra_data[k] = self._ensure_serializable(v)
                else:
                    extra_data[k] = v
            log_data.update(extra_data)
            
        # 处理消息
        if isinstance(record.msg, dict):
            log_data['message'] = record.msg
        else:
            log_data['message'] = record.getMessage()
            
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data, ensure_ascii=False)
    
    def _ensure_serializable(self, obj):
        """确保对象可JSON序列化"""
        if isinstance(obj, dict):
            return {k: self._ensure_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._ensure_serializable(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            # 将不可序列化的对象转换为字符串
            return str(obj)

class DailyFileHandler(logging.FileHandler):
    """每日日志文件处理器，在日期变化时自动切换到新文件"""
    def __init__(self, base_filename, mode='a', encoding='utf-8'):
        self.base_filename = base_filename
        self.base_name, self.ext = os.path.splitext(os.path.basename(base_filename))
        self.log_dir = os.path.dirname(base_filename)
        self.encoding = encoding
        self.mode = mode
        self.today = datetime.now().date()
        
        # 生成当前的日志文件名
        current_filename = self._get_current_filename()
        
        # 初始化父类
        super().__init__(current_filename, mode, encoding)
        print(f"创建日志处理器: {current_filename}")
    
    def _get_current_filename(self):
        """基于当前日期获取日志文件名"""
        today_str = self.today.strftime('%Y-%m-%d')
        return os.path.join(self.log_dir, f"{self.base_name}-{today_str}{self.ext}")
    
    def emit(self, record):
        """发出日志记录，检查日期是否发生变化"""
        today = datetime.now().date()
        if today != self.today:
            # 日期已变化，关闭旧文件并打开新文件
            if self.stream is not None:
                self.stream.close()
            self.today = today
            self.baseFilename = self._get_current_filename()
            self.stream = self._open()
            print(f"日志日期已变化，切换到新文件: {self.baseFilename}")
            
            # 添加日期变更标记
            self.stream.write(f"\n--- 日期变更，日志继续于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        
        # 调用父类方法发出日志
        super().emit(record)

# 更新设置日志记录器函数以使用自定义处理器
def setup_logger(name, log_file, level=logging.INFO, formatter=None):
    """设置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除已有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 使用自定义的DailyFileHandler
    file_handler = DailyFileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(level)
    
    # 写入日志开始标记
    with open(file_handler.baseFilename, 'a', encoding='utf-8') as f:
        f.write(f"\n--- 日志开始于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    
    # 设置格式
    if formatter:
        file_handler.setFormatter(formatter)
    else:
        file_handler.setFormatter(logging.Formatter(DETAILED_LOG_FORMAT))
    
    # 添加过滤器确保包含question_openid
    file_handler.addFilter(QuestionLogFilter())
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(DETAILED_LOG_FORMAT))
    console_handler.addFilter(QuestionLogFilter())
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 输出诊断信息
    print(f"日志设置完成: {name}")
    print(f"  - 日志级别: {logging.getLevelName(level)}")
    print(f"  - 当前文件: {file_handler.baseFilename}")
    
    return logger

# 添加日志管理函数
def clean_old_logs(log_dir=LOG_DIR, days_to_keep=30):
    """清理旧的日志文件，保留最近N天的日志"""
    # 使用文件标记来防止重复执行
    cleaning_marker = os.path.join(log_dir, '.cleaning_done')
    
    # 获取当前日期的字符串表示
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 检查今天是否已经执行过清理
    if os.path.exists(cleaning_marker):
        with open(cleaning_marker, 'r') as f:
            marker_date = f.read().strip()
            if marker_date == today_str:
                print(f"日志清理已经在今天({today_str})执行过，跳过")
                return
    
    print(f"开始清理日志目录: {log_dir}")
    try:
        # 获取当前日期
        current_date = datetime.now().date()
        
        # 查找日志目录中的所有文件
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            
            # 跳过目录和标记文件
            if os.path.isdir(file_path) or filename.startswith('.'):
                continue
                
            # 检查文件是否为日志文件
            base_name, ext = os.path.splitext(filename)
            if ext != '.log':
                continue
                
            # 检查文件是否包含日期
            date_part = None
            if '-' in base_name:
                parts = base_name.split('-')
                # 尝试解析最后一部分作为日期
                try:
                    date_str = parts[-1]
                    if len(date_str) == 10 and date_str.count('-') == 2:  # YYYY-MM-DD格式
                        date_part = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            # 如果找到日期部分并且日期早于保留天数，删除文件
            if date_part and (current_date - date_part).days > days_to_keep:
                try:
                    os.remove(file_path)
                    print(f"已删除旧日志文件: {filename}")
                except Exception as e:
                    print(f"删除日志文件失败 {filename}: {str(e)}")
        
        # 记录今天已经执行了清理
        with open(cleaning_marker, 'w') as f:
            f.write(today_str)
            
    except Exception as e:
        print(f"清理日志目录失败: {str(e)}")

# 确保日志系统初始化时清理旧日志
clean_old_logs()

# 创建主应用日志记录器
main_logger = setup_logger('app', MAIN_LOG_FILE)

# 创建查询专用日志记录器（JSON格式）
query_logger = setup_logger(
    'query', 
    QUERY_LOG_FILE, 
    formatter=JsonFormatter()
)

# 创建错误日志记录器
error_logger = setup_logger(
    'error', 
    ERROR_LOG_FILE, 
    level=logging.ERROR
)

# 输出诊断信息
print(f"当前日志文件:")
print(f"  - 主日志: {[h.baseFilename for h in main_logger.handlers if isinstance(h, logging.FileHandler)]}")
print(f"  - 查询日志: {[h.baseFilename for h in query_logger.handlers if isinstance(h, logging.FileHandler)]}")
print(f"  - 错误日志: {[h.baseFilename for h in error_logger.handlers if isinstance(h, logging.FileHandler)]}")

# 输出初始化信息
main_logger.info("日志系统初始化完成", extra={'question_openid': 'system'})
query_logger.info("查询日志系统初始化完成", extra={'question_openid': 'system'})
error_logger.info("错误日志系统初始化完成", extra={'question_openid': 'system'})

# 日志记录装饰器
def log_operation(logger=main_logger):
    """记录函数操作的装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 获取question_openid
            question_openid = kwargs.get('question_openid') or 'unknown'
            
            # 记录开始执行
            logger.info(
                f"Started {func.__name__}", 
                extra={
                    'question_openid': question_openid, 
                    'extra': {'operation': func.__name__, 'status': 'started'}
                }
            )
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                
                # 记录成功完成
                execution_time = time.time() - start_time
                logger.info(
                    f"Completed {func.__name__}", 
                    extra={
                        'question_openid': question_openid, 
                        'extra': {
                            'operation': func.__name__, 
                            'status': 'completed',
                            'execution_time': f"{execution_time:.4f}s"
                        }
                    }
                )
                return result
            except Exception as e:
                # 记录异常
                execution_time = time.time() - start_time
                error_logger.error(
                    f"Error in {func.__name__}: {str(e)}", 
                    exc_info=True,
                    extra={
                        'question_openid': question_openid, 
                        'extra': {
                            'operation': func.__name__, 
                            'status': 'error',
                            'execution_time': f"{execution_time:.4f}s",
                            'error_type': type(e).__name__
                        }
                    }
                )
                raise
        return wrapper
    return decorator

# 流程日志函数
def log_process(question_openid='unknown', **kwargs):
    """记录处理流程的函数"""
    # 确保额外信息存储在extra字段中
    extra_data = {'extra': kwargs} if kwargs else {}
    extra_data['question_openid'] = question_openid
    
    # 构建日志消息
    stage = kwargs.get('stage', 'unknown')
    status = kwargs.get('status', 'unknown')
    message = f"Process question_openid: {question_openid}, stage: {stage}"
    
    # 记录到查询日志
    query_logger.info(message, extra=extra_data)

# 错误日志函数
def log_error(question_openid='unknown', error_message='Error occurred', exception=None, **kwargs):
    """记录错误的函数"""
    # 准备额外信息
    extra_data = {'extra': kwargs} if kwargs else {}
    extra_data['question_openid'] = question_openid
    
    # 如果提供了异常对象，添加异常详情
    if exception:
        extra_data['extra']['error_type'] = type(exception).__name__
        extra_data['extra']['error_details'] = str(exception)
    
    # 记录到错误日志
    error_logger.error(error_message, exc_info=bool(exception), extra=extra_data)

# 性能日志函数
def log_performance(question_openid='unknown', operation='unknown', execution_time=0, **kwargs):
    """记录性能数据的函数"""
    # 准备额外信息
    extra_data = {'extra': kwargs} if kwargs else {}
    extra_data['question_openid'] = question_openid
    extra_data['extra']['operation'] = operation
    extra_data['extra']['execution_time'] = f"{execution_time:.4f}s"
    
    # 记录到主日志
    main_logger.info(f"Performance: {operation} took {execution_time:.4f}s", extra=extra_data)

# 计时上下文管理器
class TimingContext:
    """用于测量代码块执行时间的上下文管理器"""
    def __init__(self, operation_name, question_openid='unknown', **kwargs):
        self.operation_name = operation_name
        self.question_openid = question_openid
        self.kwargs = kwargs
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        log_process(
            question_openid=self.question_openid,
            stage=self.operation_name,
            **self.kwargs
        )
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time
        
        if exc_type is not None:
            # 发生异常
            log_error(
                question_openid=self.question_openid,
                error_message=f"Error in {self.operation_name}: {exc_val}",
                exception=exc_val,
                execution_time=execution_time,
                **self.kwargs
            )
        else:
            # 正常完成
            log_process(
                question_openid=self.question_openid,
                stage=self.operation_name,
                execution_time=execution_time,
                **self.kwargs
            )
            
            # 记录性能数据
            log_performance(
                question_openid=self.question_openid,
                operation=self.operation_name,
                execution_time=execution_time,
                **self.kwargs
            )
        
        # 不抑制异常
        return False