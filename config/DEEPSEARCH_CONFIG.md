# Deep Search Service Configuration
# 深度搜索服务配置说明

## 问题描述
当前深度搜索功能配置有误，导致404错误。原因是API端点设置不正确。

## 当前配置问题
- 错误的API地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 这个地址是阿里云通义千问的兼容模式API，不是深度搜索服务

## 解决方案

### 方案1：配置正确的深度搜索服务
如果您有专门的深度搜索服务，请在 `app/tool/deepsearch_agent.py` 中修改：

```python
_SEARCH_API_URL = "YOUR_DEEP_SEARCH_SERVICE_URL"
```

可能的服务地址格式：
- `http://your-domain.com/deep-search/api`
- `http://localhost:8080/deep-search`
- `http://ainlp.intra.xiaojukeji.com/deep-search/search`

### 方案2：使用现有搜索引擎替代
修改深度搜索逻辑，使用现有的web_search工具：

```python
# 在 execute 方法中调用 web_search
from app.tool.web_search import WebSearch
web_search = WebSearch()
result = await web_search.execute(query, num_results=10)
```

### 方案3：临时禁用功能（当前已实施）
当前已经临时禁用了深度搜索功能，返回友好的错误提示。

## 配置步骤

1. 确认您的深度搜索服务端点
2. 修改 `deepsearch_agent.py` 中的 `_SEARCH_API_URL`
3. 确保服务端点支持以下请求格式：
   ```json
   {
     "prompt": "深度搜索查询内容"
   }
   ```
4. 取消注释 `execute` 方法中的原有逻辑
5. 删除临时的禁用代码

## 测试
配置完成后，可以运行以下命令测试：
```bash
python -c "
import asyncio
from app.tool.deepsearch_agent import DeepSearchAgent
agent = DeepSearchAgent()
result = asyncio.run(agent.execute('测试查询', '用户原始查询'))
print(result)
"
```
