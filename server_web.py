import asyncio
import html
import json
import os
from typing import AsyncGenerator, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.manus import Manus
from app.logger import logger

# 创建FastAPI应用实例
app = FastAPI(title="Manus Chat Service")

# 启用 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建静态文件目录
os.makedirs("static", exist_ok=True)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


class PromptRequest(BaseModel):
    prompt: str


class PromptResponse(BaseModel):
    message: str
    status: str


# @app.get("/", response_class=HTMLResponse)
# async def get_chat_interface():
#     """提供聊天界面的HTML页面"""
#     html_content = """
#     <!DOCTYPE html>
#     <html lang="zh-CN">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <title>Open POI DeepResearch</title>
#         <!-- 引入 Markdown 解析库 -->
#         <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
#         <!-- 引入代码高亮库 -->
#         <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11.7.0/styles/github.min.css">
#         <script src="https://cdn.jsdelivr.net/npm/highlight.js@11.7.0/lib/highlight.min.js"></script>
#         <style>
#             body {
#                 font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
#                 margin: 0;
#                 padding: 0;
#                 display: flex;
#                 flex-direction: column;
#                 height: 100vh;
#                 background-color: #f8f9fa;
#                 color: #333;
#             }
#             .chat-container {
#                 flex: 1;
#                 display: flex;
#                 flex-direction: column;
#                 max-width: 900px;
#                 margin: 0 auto;
#                 width: 100%;
#                 padding: 20px;
#                 box-sizing: border-box;
#             }
#             .chat-header {
#                 text-align: center;
#                 padding: 15px;
#                 background: #3a6ea5;
#                 color: white;
#                 border-radius: 10px 10px 0 0;
#                 box-shadow: 0 2px 4px rgba(0,0,0,0.1);
#             }
#             .chat-messages {
#                 flex: 1;
#                 overflow-y: auto;
#                 padding: 20px;
#                 background: white;
#                 border-left: 1px solid #e0e0e0;
#                 border-right: 1px solid #e0e0e0;
#                 box-shadow: 0 2px 4px rgba(0,0,0,0.05);
#             }
#             .message {
#                 margin-bottom: 20px;
#                 padding: 12px 16px;
#                 border-radius: 18px;
#                 max-width: 85%;
#                 word-wrap: break-word;
#                 position: relative;
#                 line-height: 1.5;
#             }
#             .user-message {
#                 background-color: #e1f3fb;
#                 margin-left: auto;
#                 border-bottom-right-radius: 4px;
#                 color: #0c5460;
#             }
#             .agent-message {
#                 background-color: #f8f9fa;
#                 margin-right: auto;
#                 border-bottom-left-radius: 4px;
#                 border-left: 4px solid #3a6ea5;
#                 color: #333;
#             }
#             .agent-message a {
#                 color: #2970ff;
#                 text-decoration: none;
#             }
#             .agent-message a:hover {
#                 text-decoration: underline;
#             }
#             .input-area {
#                 display: flex;
#                 padding: 15px;
#                 background: #f8f8f8;
#                 border-top: 1px solid #e0e0e0;
#                 border-left: 1px solid #e0e0e0;
#                 border-right: 1px solid #e0e0e0;
#                 border-radius: 0 0 10px 10px;
#                 box-shadow: 0 -2px 4px rgba(0,0,0,0.05);
#             }
#             #user-input {
#                 flex: 1;
#                 padding: 12px 16px;
#                 border: 1px solid #d0d0d0;
#                 border-radius: 24px;
#                 margin-right: 12px;
#                 outline: none;
#                 font-size: 16px;
#                 box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
#                 transition: border-color 0.2s;
#             }
#             #user-input:focus {
#                 border-color: #3a6ea5;
#                 box-shadow: 0 0 0 2px rgba(58, 110, 165, 0.2);
#             }
#             #send-button {
#                 padding: 12px 24px;
#                 background: #3a6ea5;
#                 color: white;
#                 border: none;
#                 border-radius: 24px;
#                 cursor: pointer;
#                 font-weight: 600;
#                 font-size: 16px;
#                 transition: background-color 0.2s;
#             }
#             #send-button:hover {
#                 background: #2c5282;
#             }
#             #send-button:active {
#                 transform: translateY(1px);
#             }
#             .typing-indicator {
#                 display: none;
#                 margin-bottom: 20px;
#                 padding: 12px 16px;
#                 background-color: #f8f9fa;
#                 border-radius: 18px;
#                 max-width: 100px;
#                 margin-right: auto;
#                 border-bottom-left-radius: 4px;
#                 border-left: 4px solid #3a6ea5;
#             }
#             .typing-dot {
#                 display: inline-block;
#                 width: 8px;
#                 height: 8px;
#                 border-radius: 50%;
#                 background-color: #3a6ea5;
#                 margin-right: 4px;
#                 animation: typing 1.5s infinite ease-in-out;
#             }
#             .typing-dot:nth-child(2) {
#                 animation-delay: 0.3s;
#             }
#             .typing-dot:nth-child(3) {
#                 animation-delay: 0.6s;
#             }
#             @keyframes typing {
#                 0%, 60%, 100% { transform: translateY(0); }
#                 30% { transform: translateY(-5px); }
#             }
#             .system-message {
#                 text-align: center;
#                 color: #666;
#                 font-style: italic;
#                 margin: 15px 0;
#                 font-size: 14px;
#             }
#             pre {
#                 background-color: #f6f8fa;
#                 padding: 16px;
#                 border-radius: 6px;
#                 overflow-x: auto;
#                 margin: 16px 0;
#                 border: 1px solid #e1e4e8;
#             }
#             code {
#                 font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
#                 font-size: 14px;
#                 padding: 2px 4px;
#                 border-radius: 3px;
#             }
#             p {
#                 margin: 8px 0;
#             }
#             blockquote {
#                 margin: 16px 0;
#                 padding-left: 16px;
#                 border-left: 4px solid #e0e0e0;
#                 color: #666;
#             }
#             .agent-message ul, .agent-message ol {
#                 padding-left: 24px;
#             }
#             table {
#                 border-collapse: collapse;
#                 width: 100%;
#                 margin: 16px 0;
#             }
#             table, th, td {
#                 border: 1px solid #e0e0e0;
#             }
#             th, td {
#                 padding: 8px 12px;
#                 text-align: left;
#             }
#             th {
#                 background-color: #f6f8fa;
#             }
#             img {
#                 max-width: 100%;
#                 height: auto;
#                 border-radius: 6px;
#                 margin: 16px 0;
#             }
#             h1, h2, h3, h4, h5, h6 {
#                 margin-top: 20px;
#                 margin-bottom: 10px;
#                 color: #333;
#             }
#             /* 响应式设计 */
#             @media (max-width: 768px) {
#                 .chat-container {
#                     padding: 10px;
#                 }
#                 .message {
#                     max-width: 90%;
#                     padding: 10px 12px;
#                 }
#                 #user-input, #send-button {
#                     padding: 10px;
#                 }
#                 .chat-header {
#                     padding: 10px;
#                 }
#                 pre {
#                     padding: 12px;
#                 }
#             }

#                         /* --- 新增样式用于结构化输出 --- */
#             .step-container {
#                 border-top: 2px solid #3a6ea5;
#                 margin-top: 20px;
#                 padding-top: 15px;
#             }
#             .step-header {
#                 font-weight: bold;
#                 color: #3a6ea5;
#                 margin-bottom: 10px;
#                 font-size: 1.2em; /* 放大字体 */
#             }
#             .step-part {
#                 border-left: 3px solid #e0e0e0;
#                 padding-left: 15px;
#                 margin-top: 10px;
#                 margin-bottom: 15px;
#             }
#             .step-part h4 {
#                 margin: 0 0 5px 0;
#                 color: #555;
#                 font-size: 1.0em; /* 调整标题大小 */
#             }
#             .step-part pre {
#                 margin: 5px 0;
#                 white-space: pre-wrap; /* 自动换行 */
#                 word-wrap: break-word;
#             }
#         </style>
#     </head>
#     <body>
#         <div class="chat-container">
#             <div class="chat-header">
#                 <h2>Open POI DeepResearch</h2>
#             </div>
#             <div class="chat-messages" id="chat-messages">
#                 <div class="message agent-message">
#                     <p>你好！我是 Open POI DeepResearch 助手。有什么我可以帮助你的吗？</p>
#                 </div>
#             </div>
#             <div class="typing-indicator" id="typing-indicator">
#                 <span class="typing-dot"></span>
#                 <span class="typing-dot"></span>
#                 <span class="typing-dot"></span>
#             </div>
#             <div class="input-area">
#                 <input type="text" id="user-input" placeholder="输入你的问题..." autocomplete="off">
#                 <button id="send-button">发送</button>
#             </div>
#         </div>

#         <script>
#             // 配置 marked 选项
#             marked.setOptions({
#                 highlight: function(code, lang) {
#                     if (lang && hljs.getLanguage(lang)) {
#                         try {
#                             return hljs.highlight(code, { language: lang }).value;
#                         } catch (e) {}
#                     }
#                     return hljs.highlightAuto(code).value;
#                 },
#                 breaks: true,
#                 gfm: true
#             });

#             const chatMessages = document.getElementById('chat-messages');
#             const userInput = document.getElementById('user-input');
#             const sendButton = document.getElementById('send-button');
#             const typingIndicator = document.getElementById('typing-indicator');
#             let eventSource = null;
#             let isProcessing = false;

#             // 发送消息函数
#             function sendMessage() {
#                 const message = userInput.value.trim();
#                 if (!message || isProcessing) return;

#                 // 添加用户消息到聊天区域
#                 addMessage(message, 'user');
#                 userInput.value = '';
#                 isProcessing = true;

#                 // 显示正在输入指示器
#                 typingIndicator.style.display = 'block';

#                 // 关闭之前的连接
#                 if (eventSource) {
#                     eventSource.close();
#                 }

#                 // 建立 SSE 连接
#                 eventSource = new EventSource(`/api/chat/stream?prompt=${encodeURIComponent(message)}`);

#                 let agentMessageContainer = null;
#                 let agentMessageContent = '';

#                 // 处理消息事件
#                 eventSource.onmessage = function(event) {
#                     // 第一条消息时，创建新的消息容器
#                     if (!agentMessageContainer) {
#                         agentMessageContainer = document.createElement('div');
#                         agentMessageContainer.className = 'message agent-message';
#                         chatMessages.appendChild(agentMessageContainer);
#                         typingIndicator.style.display = 'none';
#                     }

#                     // 累积内容
#                     agentMessageContent += JSON.parse(event.data);

#                     // 使用 marked 渲染 Markdown
#                     agentMessageContainer.innerHTML = marked.parse(agentMessageContent);

#                     // 应用代码高亮
#                     agentMessageContainer.querySelectorAll('pre code').forEach((block) => {
#                         hljs.highlightElement(block);
#                     });

#                     // 滚动到底部
#                     chatMessages.scrollTop = chatMessages.scrollHeight;
#                 };

#                 // 处理完成事件
#                 eventSource.addEventListener('complete', function(event) {
#                     typingIndicator.style.display = 'none';
#                     eventSource.close();
#                     chatMessages.scrollTop = chatMessages.scrollHeight;
#                     isProcessing = false;
#                 });

#                 // 处理错误事件
#                 eventSource.addEventListener('error', function(event) {
#                     typingIndicator.style.display = 'none';

#                     if (event.data) {
#                         try {
#                             const errorData = JSON.parse(event.data);
#                             addSystemMessage(`发生错误: ${errorData.error}`);
#                         } catch (e) {
#                             addSystemMessage('连接错误，请重试');
#                         }
#                     } else {
#                         addSystemMessage('连接错误，请重试');
#                     }

#                     eventSource.close();
#                     isProcessing = false;
#                 });
#             }

#             // 添加消息到聊天区域
#             function addMessage(message, sender) {
#                 const messageElement = document.createElement('div');
#                 messageElement.className = `message ${sender}-message`;

#                 if (sender === 'user') {
#                     // 用户消息，简单显示文本
#                     messageElement.textContent = message;
#                 } else {
#                     // AI 消息，支持 Markdown
#                     messageElement.innerHTML = marked.parse(message);

#                     // 应用代码高亮
#                     messageElement.querySelectorAll('pre code').forEach((block) => {
#                         hljs.highlightElement(block);
#                     });
#                 }

#                 chatMessages.appendChild(messageElement);
#                 chatMessages.scrollTop = chatMessages.scrollHeight;
#             }

#             // 添加系统消息
#             function addSystemMessage(message) {
#                 const messageElement = document.createElement('div');
#                 messageElement.className = 'system-message';
#                 messageElement.textContent = message;
#                 chatMessages.appendChild(messageElement);
#                 chatMessages.scrollTop = chatMessages.scrollHeight;
#             }

#             // 发送按钮点击事件
#             sendButton.addEventListener('click', sendMessage);

#             // 输入框回车键事件
#             userInput.addEventListener('keypress', function(e) {
#                 if (e.key === 'Enter') {
#                     sendMessage();
#                 }
#             });

#             // 初始聚焦到输入框
#             userInput.focus();

#             // 初始化聊天界面
#             chatMessages.scrollTop = chatMessages.scrollHeight;
#         </script>
#     </body>
#     </html>
#     """
#     return html_content

@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """提供聊天界面的HTML页面"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Open POI DeepResearch(powered by gaode)</title>
        <!-- 依赖项 highlight.js 应该在最前面 -->
        <script src="https://cdn.jsdelivr.net/npm/highlight.js@11.7.0/lib/highlight.min.js"></script>

        <!-- 引入 Markdown 解析库 -->
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <!-- 引入代码高亮库 -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11.7.0/styles/github.min.css">
        <script src="https://cdn.jsdelivr.net/npm/highlight.js@11.7.0/lib/highlight.min.js"></script>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                height: 100vh;
                background-color: #f8f9fa;
                color: #333;
            }
            .chat-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                max-width: 900px;
                margin: 0 auto;
                width: 100%;
                padding: 20px;
                box-sizing: border-box;
            }
            .chat-header {
                text-align: center;
                padding: 15px;
                background: #3a6ea5;
                color: white;
                border-radius: 10px 10px 0 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                background: white;
                border-left: 1px solid #e0e0e0;
                border-right: 1px solid #e0e0e0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            .message {
                margin-bottom: 20px;
                padding: 12px 16px;
                border-radius: 18px;
                max-width: 85%;
                word-wrap: break-word;
                position: relative;
                line-height: 1.5;
            }
            .user-message {
                background-color: #e1f3fb;
                margin-left: auto;
                border-bottom-right-radius: 4px;
                color: #0c5460;
            }
            .agent-message {
                background-color: #f8f9fa;
                margin-right: auto;
                border-bottom-left-radius: 4px;
                border-left: 4px solid #3a6ea5;
                color: #333;
            }
            .agent-message a {
                color: #2970ff;
                text-decoration: none;
            }
            .agent-message a:hover {
                text-decoration: underline;
            }
            .input-area {
                display: flex;
                padding: 15px;
                background: #f8f8f8;
                border-top: 1px solid #e0e0e0;
                border-left: 1px solid #e0e0e0;
                border-right: 1px solid #e0e0e0;
                border-radius: 0 0 10px 10px;
                box-shadow: 0 -2px 4px rgba(0,0,0,0.05);
            }
            #user-input {
                flex: 1;
                padding: 12px 16px;
                border: 1px solid #d0d0d0;
                border-radius: 24px;
                margin-right: 12px;
                outline: none;
                font-size: 16px;
                box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
                transition: border-color 0.2s;
            }
            #user-input:focus {
                border-color: #3a6ea5;
                box-shadow: 0 0 0 2px rgba(58, 110, 165, 0.2);
            }
            #send-button {
                padding: 12px 24px;
                background: #3a6ea5;
                color: white;
                border: none;
                border-radius: 24px;
                cursor: pointer;
                font-weight: 600;
                font-size: 16px;
                transition: background-color 0.2s;
            }
            #send-button:hover {
                background: #2c5282;
            }
            #send-button:active {
                transform: translateY(1px);
            }
            .typing-indicator {
                display: none;
                margin-bottom: 20px;
                padding: 12px 16px;
                background-color: #f8f9fa;
                border-radius: 18px;
                max-width: 100px;
                margin-right: auto;
                border-bottom-left-radius: 4px;
                border-left: 4px solid #3a6ea5;
            }
            .typing-dot {
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background-color: #3a6ea5;
                margin-right: 4px;
                animation: typing 1.5s infinite ease-in-out;
            }
            .typing-dot:nth-child(2) {
                animation-delay: 0.3s;
            }
            .typing-dot:nth-child(3) {
                animation-delay: 0.6s;
            }
            @keyframes typing {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-5px); }
            }
            .system-message {
                text-align: center;
                color: #666;
                font-style: italic;
                margin: 15px 0;
                font-size: 14px;
            }
            pre {
                background-color: #f6f8fa;
                padding: 16px;
                border-radius: 6px;
                overflow-x: auto;
                margin: 16px 0;
                border: 1px solid #e1e4e8;
            }
            code {
                font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
                font-size: 14px;
                padding: 2px 4px;
                border-radius: 3px;
            }
            p {
                margin: 8px 0;
            }
            blockquote {
                margin: 16px 0;
                padding-left: 16px;
                border-left: 4px solid #e0e0e0;
                color: #666;
            }
            .agent-message ul, .agent-message ol {
                padding-left: 24px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 16px 0;
            }
            table, th, td {
                border: 1px solid #e0e0e0;
            }
            th, td {
                padding: 8px 12px;
                text-align: left;
            }
            th {
                background-color: #f6f8fa;
            }
            img {
                max-width: 100%;
                height: auto;
                border-radius: 6px;
                margin: 16px 0;
            }
            h1, h2, h3, h4, h5, h6 {
                margin-top: 20px;
                margin-bottom: 10px;
                color: #333;
            }
            /* 响应式设计 */
            @media (max-width: 768px) {
                .chat-container {
                    padding: 10px;
                }
                .message {
                    max-width: 90%;
                    padding: 10px 12px;
                }
                #user-input, #send-button {
                    padding: 10px;
                }
                .chat-header {
                    padding: 10px;
                }
                pre {
                    padding: 12px;
                }
            }

            /* --- 新增样式用于结构化输出 --- */
            .step-container {
                border-top: 2px solid #3a6ea5;
                margin-top: 20px;
                padding-top: 15px;
            }
            .step-header {
                font-weight: bold;
                color: #3a6ea5;
                margin-bottom: 10px;
                font-size: 1.2em; /* 放大字体 */
            }
            .step-part {
                border-left: 3px solid #e0e0e0;
                padding-left: 15px;
                margin-top: 10px;
                margin-bottom: 15px;
            }
            .step-part h4 {
                margin: 0 0 5px 0;
                color: #555;
                font-size: 1.0em; /* 调整标题大小 */
            }
            .step-part pre {
                margin: 5px 0;
                white-space: pre-wrap; /* 自动换行 */
                word-wrap: break-word;
            }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div class="chat-header">
                <h2>Open POI DeepResearch(powered by gaode-mcp)</h2>
            </div>
            <div class="chat-messages" id="chat-messages">
                <div class="message agent-message">
                    <p>你好！我是 Open POI DeepResearch 助手。有什么我可以帮助你的吗？</p>
                </div>
            </div>
            <div class="typing-indicator" id="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
            <div class="input-area">
                <input type="text" id="user-input" placeholder="输入你的问题..." autocomplete="off">
                <button id="send-button">发送</button>
            </div>
        </div>

        <script>
            // 配置 marked 选项
            marked.setOptions({
                highlight: function(code, lang) {
                    if (lang && hljs.getLanguage(lang)) {
                        try {
                            return hljs.highlight(code, { language: lang }).value;
                        } catch (e) {}
                    }
                    return hljs.highlightAuto(code).value;
                },
                breaks: true,
                gfm: true
            });

            const chatMessages = document.getElementById('chat-messages');
            const userInput = document.getElementById('user-input');
            const sendButton = document.getElementById('send-button');
            const typingIndicator = document.getElementById('typing-indicator');
            let isProcessing = false;

            // 发送消息函数
            function sendMessage() {
                const message = userInput.value.trim();
                if (!message || isProcessing) return;

                // 添加用户消息到聊天区域
                addMessage(message, 'user');
                userInput.value = '';
                isProcessing = true;

                // 显示正在输入指示器
                typingIndicator.style.display = 'block';

                // 使用 POST 请求
                fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ prompt: message }),
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '服务器错误'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 隐藏正在输入指示器
                    typingIndicator.style.display = 'none';

                    // 添加 AI 消息
                    if (data && data.message) {
                        addMessage(data.message, 'agent');
                    } else {
                        addSystemMessage('未收到有效回复');
                    }
                    isProcessing = false;
                })
                .catch(error => {
                    // 隐藏正在输入指示器
                    typingIndicator.style.display = 'none';

                    // 显示错误信息
                    let errorMessage = '请求失败，请检查网络或联系管理员。';
                    if (error && error.message) {
                        errorMessage = `发生错误: ${error.message}`;
                    } else {
                        // 尝试从 error 对象中提取更多信息
                        try {
                            const errorStr = JSON.stringify(error);
                            if (errorStr !== '{}') {
                                errorMessage += `\\n详情: ${errorStr}`;
                            }
                        } catch(e) {}
                    }
                    addSystemMessage(errorMessage);

                    // 重置处理状态
                    isProcessing = false;
                });
            }

            // 添加消息到聊天区域
            function addMessage(message, sender) {
                const messageElement = document.createElement('div');
                messageElement.className = `message ${sender}-message`;

                if (sender === 'user') {
                    // 用户消息，简单显示文本
                    messageElement.textContent = message;
                } else {
                    // AI 消息，支持 Markdown
                    messageElement.innerHTML = marked.parse(message);

                    // 应用代码高亮
                    messageElement.querySelectorAll('pre code').forEach((block) => {
                        hljs.highlightElement(block);
                    });
                }

                chatMessages.appendChild(messageElement);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }

            // 添加系统消息
            function addSystemMessage(message) {
                const messageElement = document.createElement('div');
                messageElement.className = 'system-message';
                messageElement.textContent = message;
                chatMessages.appendChild(messageElement);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }

            // 发送按钮点击事件
            sendButton.addEventListener('click', sendMessage);

            // 输入框回车键事件
            userInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });

            // 初始聚焦到输入框
            userInput.focus();

            // 初始化聊天界面
            chatMessages.scrollTop = chatMessages.scrollHeight;
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/api/chat/stream")
async def chat_stream(prompt: str):
    """提供聊天的 SSE 流式响应端点"""
    if not prompt.strip():
        logger.warning("Empty prompt provided.")
        raise HTTPException(status_code=400, detail="Empty prompt provided")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            logger.warning(f"Processing streaming chat request: {prompt}")
            agent = Manus()

            async for chunk in agent.run_stream(prompt):
                print("chunk...", chunk)
                # 直接发送原始文本，不进行 JSON 编码
                chunk_json = json.dumps(chunk)
                yield f"data: {chunk_json}\n\n"

            # 发送处理完成事件
            complete_data = json.dumps({"status": "success"})
            yield f"event: complete\ndata: {complete_data}\n\n"

            logger.info("Streaming chat request processing completed.")
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error processing streaming chat request: {error_message}")
            error_data = json.dumps({"error": error_message})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat", response_model=PromptResponse)
async def chat(request: PromptRequest):
    """提供聊天的常规响应端点"""
    if not request.prompt.strip():
        logger.warning("Empty prompt provided.")
        raise HTTPException(status_code=400, detail="Empty prompt provided")

    try:
        logger.warning(f"Processing chat request: {request.prompt}")
        agent = Manus()
        result = await agent.run(request.prompt)

        logger.info("Chat request processing completed.")
        return PromptResponse(message=result, status="success")
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("server_web:app", host="0.0.0.0", port=8072, reload=False)
