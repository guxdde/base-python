# 基于的基础镜像
FROM python:3.10

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置app文件夹是工作目录
WORKDIR /app

# 先将依赖文件拷贝到项目中
COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
# 执行指令，安装依赖
RUN pip install -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 拷贝当前目录的项目文件和代码
COPY . /app

# 执行命令
CMD uvicorn main:app --host 0.0.0.0 --port 8099
