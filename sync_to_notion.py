#!/usr/bin/env python3
"""
AI联盟 Notion 同步脚本
Markdown 文件同步到 Notion Database

功能：
- 读取本地 Markdown 文件
- 解析 frontmatter 元数据
- 创建/更新 Notion 页面
- 支持 GitHub Action 自动运行
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# 加载 .env 文件
from pathlib import Path
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# ============================================================
# 配置区域 - 请根据实际情况修改
# ============================================================

# 文档类型映射到 Notion Database ID（暂时都使用默认数据库）
DEFAULT_DB = os.getenv("NOTION_DATABASE_DEFAULT", "")
DATABASE_MAPPING = {
    "memory": DEFAULT_DB,
    "agents": DEFAULT_DB,
    "projects": DEFAULT_DB,
    "flows": DEFAULT_DB,
    "knowledge": DEFAULT_DB,
    "default": DEFAULT_DB,
}

# 默认 Database ID
DEFAULT_DATABASE_ID = DEFAULT_DB

# ============================================================
# 日志配置
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sync.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# 数据结构
# ============================================================

@dataclass
class MarkdownDoc:
    """Markdown 文档结构"""
    file_path: Path
    title: str
    content: str
    metadata: Dict[str, any] = field(default_factory=dict)
    doc_type: str = "default"
    tags: List[str] = field(default_factory=list)
    importance: int = 3
    source: str = "local"
    status: str = "未处理"

@dataclass
class NotionPage:
    """Notion 页面结构"""
    page_id: Optional[str] = None
    title: str = ""
    content: str = ""
    properties: Dict[str, any] = field(default_factory=dict)
    database_id: str = ""

# ============================================================
# Markdown 解析器
# ============================================================

class MarkdownParser:
    """Markdown 文件解析器"""
    
    # 支持的文档类型
    DOC_TYPES = {
        "系统架构": "knowledge",
        "记忆库": "memory",
        "节点库": "agents",
        "项目系统": "projects",
        "流程系统": "flows",
        "知识库": "knowledge",
        "仪表盘": "knowledge",
        "README": "knowledge",
    }
    
    # 重要性映射
    IMPORTANCE_MAP = {
        "MVP": 5,
        "关键": 5,
        "重要": 4,
        "一般": 3,
        "普通": 2,
        "实验": 1,
    }
    
    @staticmethod
    def parse_frontmatter(content: str) -> Tuple[Dict, str]:
        """解析 YAML frontmatter"""
        frontmatter_pattern = r'^---\s*\n([\s\S]*?)\n---\s*\n'
        match = re.match(frontmatter_pattern, content)
        
        if match:
            yaml_content = match.group(1)
            body = content[match.end():]
            
            # 简单 YAML 解析
            metadata = {}
            for line in yaml_content.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip().strip('"\'')
            
            return metadata, body
        
        return {}, content
    
    @staticmethod
    def extract_title(content: str) -> str:
        """提取文档标题"""
        # 尝试从第一行 # 标题
        match = re.match(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        # 如果没有标题，使用文件名
        return "Untitled"
    
    @staticmethod
    def extract_tags(content: str) -> List[str]:
        """提取文档中的标签"""
        tags = []
        
        # 匹配 #标签 格式
        tag_pattern = r'#(\w+)'
        tags.extend(re.findall(tag_pattern, content))
        
        return list(set(tags))  # 去重
    
    @staticmethod
    def determine_doc_type(file_path: Path, content: str, metadata: Dict) -> str:
        """确定文档类型"""
        # 优先使用 frontmatter 中的 type
        if 'type' in metadata:
            return metadata['type']
        
        # 根据文件路径判断
        filename = file_path.stem
        for keyword, doc_type in MarkdownParser.DOC_TYPES.items():
            if keyword in filename or keyword in content[:500]:
                return doc_type
        
        return "default"
    
    @staticmethod
    def parse_importance(metadata: Dict) -> int:
        """解析重要性"""
        if 'importance' in metadata:
            value = metadata['importance']
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
            return MarkdownParser.IMPORTANCE_MAP.get(value, 3)
        
        return 3
    
    def parse(self, file_path: Path) -> MarkdownDoc:
        """解析单个 Markdown 文件"""
        logger.info(f"解析文件: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 frontmatter
            metadata, body = self.parse_frontmatter(content)
            
            # 提取标题
            title = metadata.get('title', '') or self.extract_title(body)
            
            # 确定文档类型
            doc_type = self.determine_doc_type(file_path, body, metadata)
            
            # 提取标签
            tags = self.extract_tags(body)
            if 'tags' in metadata:
                if isinstance(metadata['tags'], str):
                    tags.extend(metadata['tags'].split(','))
                else:
                    tags.extend(metadata['tags'])
            
            # 解析重要性
            importance = self.parse_importance(metadata)
            
            # 来源
            source = metadata.get('source', 'local')
            
            # 状态
            status = metadata.get('status', '未处理')
            
            return MarkdownDoc(
                file_path=file_path,
                title=title,
                content=body,
                metadata=metadata,
                doc_type=doc_type,
                tags=tags,
                importance=importance,
                source=source,
                status=status
            )
            
        except Exception as e:
            logger.error(f"解析失败 {file_path}: {e}")
            raise

# ============================================================
# Notion API 客户端
# ============================================================

class NotionClient:
    """Notion API 客户端"""
    
    API_URL = "https://api.notion.com/v1"
    API_VERSION = "2026-03-11"
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": self.API_VERSION
        }
    
    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """发送 API 请求"""
        import urllib.request
        
        url = f"{self.API_URL}{endpoint}"
        request = urllib.request.Request(
            url,
            method=method,
            headers=self.headers
        )
        
        if data:
            request.data = json.dumps(data).encode('utf-8')
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            logger.error(f"API 请求失败: {e.code} - {error_body}")
            raise
    
    def get_database(self, database_id: str) -> dict:
        """获取 Database 信息"""
        return self._request("GET", f"/databases/{database_id}")
    
    def query_database(
        self, 
        database_id: str, 
        filter_cond: dict = None,
        sort: dict = None,
        page_size: int = 100
    ) -> List[dict]:
        """查询 Database"""
        data = {"page_size": page_size}
        
        if filter_cond:
            data["filter"] = filter_cond
        
        if sort:
            data["sorts"] = [sort]
        
        results = []
        response = self._request("POST", f"/databases/{database_id}/query", data)
        results.extend(response.get("results", []))
        
        # 处理分页
        while response.get("has_more"):
            data["start_cursor"] = response["next_cursor"]
            response = self._request("POST", f"/databases/{database_id}/query", data)
            results.extend(response.get("results", []))
        
        return results
    
    def create_page(self, database_id: str, properties: dict, children: List[dict] = None) -> dict:
        """创建页面"""
        data = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        
        if children:
            # 分块上传，每块最多100个
            data["children"] = children[:100]
            page = self._request("POST", "/pages", data)
            
            # 如果还有更多block，追加到页面
            if len(children) > 100:
                remaining = children[100:]
                while remaining:
                    chunk = remaining[:100]
                    remaining = remaining[100:]
                    block_data = {"children": chunk}
                    page_id = page["id"]
                    try:
                        self._request("PATCH", f"/blocks/{page_id}/children", block_data)
                    except Exception as e:
                        logger.warning(f"追加blocks失败: {e}")
        
        return page
    
    def update_page(self, page_id: str, properties: dict, children: List[dict] = None) -> dict:
        """更新页面"""
        data = {"properties": properties}
        
        page = self._request("PATCH", f"/pages/{page_id}", data)
        
        if children is not None:
            if children:
                # 分块上传
                block_data = {"children": children[:100]}
                try:
                    self._request("PATCH", f"/blocks/{page_id}/children", block_data)
                    if len(children) > 100:
                        remaining = children[100:]
                        while remaining:
                            chunk = remaining[:100]
                            remaining = remaining[100:]
                            self._request("PATCH", f"/blocks/{page_id}/children", {"children": chunk})
                except Exception as e:
                    logger.warning(f"更新blocks失败: {e}")
        
        return page
    
    def archive_page(self, page_id: str) -> dict:
        """归档页面"""
        return self._request("PATCH", f"/pages/{page_id}", {"archived": True})

# ============================================================
# Markdown 转 Notion 转换器
# ============================================================

class MarkdownToNotionConverter:
    """Markdown 到 Notion 的转换器"""
    
    def __init__(self, notion_client: NotionClient):
        self.notion = notion_client
    
    def markdown_to_blocks(self, markdown: str) -> List[dict]:
        """将 Markdown ���容转换为 Notion blocks"""
        blocks = []
        lines = markdown.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 跳过空行
            if not line.strip():
                i += 1
                continue
            
            # 标题
            if line.startswith('# '):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}
                })
            elif line.startswith('## '):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]}
                })
            elif line.startswith('### '):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]}
                })
            
            # 列表
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line.strip()[2:]}}]}
                })
            
            # 数字列表
            elif re.match(r'^\d+\.\s+', line.strip()):
                match = re.match(r'^(\d+)\.\s+(.*)', line.strip())
                if match:
                    blocks.append({
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": match.group(2)}}]}
                    })
            
            # 代码块
            elif line.strip().startswith('```'):
                code_content = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_content.append(lines[i])
                    i += 1
                # 限制每个代码块的长度
                code_text = '\n'.join(code_content)[:1900]
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code_text}}],
                        "language": "markdown"
                    }
                })
            
            # 分割线
            elif line.strip() == '---':
                blocks.append({
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                })
            
            # 引用
            elif line.strip().startswith('>'):
                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": [{"type": "text", "text": {"content": line.strip()[1:].strip()}}]}
                })
            
            # 普通段落
            else:
                # 处理内联格式
                text = line
                rich_text = self._parse_inline_formatting(text)
                if rich_text:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text}
                    })
            
            i += 1
        
        return blocks
    
    def _parse_inline_formatting(self, text: str) -> List[dict]:
        """解析行内格式（粗体、斜体、代码）"""
        if not text.strip():
            return []
        
        rich_text = []
        
        # 分割代码块
        parts = re.split(r'(`[^`]+`)', text)
        
        for part in parts:
            if part.startswith('`') and part.endswith('`'):
                # 代码格式
                rich_text.append({
                    "type": "text",
                    "text": {"content": part[1:-1]},
                    "annotations": {"code": True}
                })
            else:
                # 处理粗体和斜体
                sub_parts = re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*)', part)
                for sub_part in sub_parts:
                    if sub_part.startswith('**') and sub_part.endswith('**'):
                        rich_text.append({
                            "type": "text",
                            "text": {"content": sub_part[2:-2]},
                            "annotations": {"bold": True}
                        })
                    elif sub_part.startswith('*') and sub_part.endswith('*'):
                        rich_text.append({
                            "type": "text",
                            "text": {"content": sub_part[1:-1]},
                            "annotations": {"italic": True}
                        })
                    elif sub_part:
                        rich_text.append({
                            "type": "text",
                            "text": {"content": sub_part}
                        })
        
        return rich_text if rich_text else [{"type": "text", "text": {"content": text}}]
    
    def create_properties(self, doc: MarkdownDoc, database_id: str) -> dict:
        """创建 Notion 页面属性"""
        properties = {}
        
        # 标题
        properties["名称"] = {
            "title": [{"text": {"content": doc.title[:200]}}]
        }
        
        # 类型
        if doc.doc_type != "default":
            type_map = {
                "memory": "记忆库",
                "agents": "节点库", 
                "projects": "项目系统",
                "flows": "流程系统",
                "knowledge": "知识库",
            }
            type_name = type_map.get(doc.doc_type, doc.doc_type)
            properties["类型"] = {"select": {"name": type_name}}
        
        # 标签
        if doc.tags:
            properties["标签"] = {
                "multi_select": [{"name": tag[:50]} for tag in doc.tags[:20]]
            }
        
        # 来源
        if doc.source:
            properties["来源"] = {"select": {"name": doc.source}}
        
        # 状态 - 跳过，因为数据库的status选项未知
        # if doc.status:
        #     properties["状态"] = {"status": {"name": doc.status}}
        
        # 文件路径
        properties["文件路径"] = {
            "rich_text": [{"text": {"content": str(doc.file_path)}}]
        }
        
        # 重要性
        if doc.importance:
            importance_map = {
                5: "MVP",
                4: "重要",
                3: "一般",
                2: "普通",
                1: "实验"
            }
            importance_name = importance_map.get(doc.importance, "一般")
            properties["重要性"] = {"select": {"name": importance_name}}
        
        return properties

# ============================================================
# 同步管理器
# ============================================================

class SyncManager:
    """同步管理器"""
    
    # 文档类型到数据库的映射（暂时都使用默认数据库）
    TYPE_TO_DATABASE = {
        "memory": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "agents": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "projects": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "flows": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "knowledge": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "default": os.getenv("NOTION_DATABASE_DEFAULT", ""),
    }
    
    def __init__(self, notion_token: str, root_path: str):
        self.notion = NotionClient(notion_token)
        self.parser = MarkdownParser()
        self.converter = MarkdownToNotionConverter(self.notion)
        self.root_path = Path(root_path)
        self.stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }
        
        # 缓存已存在的页面
        self.existing_pages = {}
        self._load_existing_pages()
    
    def _load_existing_pages(self):
        """加载已存在的页面索引"""
        logger.info("加载已存在的 Notion 页面...")
        
        for doc_type, database_id in self.TYPE_TO_DATABASE.items():
            if not database_id:
                continue
            
            try:
                pages = self.notion.query_database(database_id)
                for page in pages:
                    page_id = page['id']
                    file_path = None
                    
                    # 中文属性名
                    if "文件路径" in page.get("properties", {}):
                        rich_text = page["properties"]["文件路径"].get("rich_text", [])
                        if rich_text:
                            file_path = rich_text[0].get("plain_text", "")
                    
                    self.existing_pages[page_id] = {
                        "database_id": database_id,
                        "file_path": file_path
                    }
                
                logger.info(f"  {doc_type}: {len(pages)} pages")
                
            except Exception as e:
                logger.warning(f"  无法加载 {doc_type} 数据库: {e}")
    
    def _get_database_id(self, doc: MarkdownDoc) -> str:
        """获取文档对应的 Database ID"""
        database_id = self.TYPE_TO_DATABASE.get(doc.doc_type, "")
        
        if not database_id:
            database_id = os.getenv("NOTION_DATABASE_DEFAULT", "")
        
        if not database_id:
            logger.warning(f"未配置 {doc.doc_type} 类型的数据库，使用默认数据库")
            database_id = DEFAULT_DATABASE_ID
        
        return database_id
    
    def _find_existing_page(self, file_path: Path) -> Optional[str]:
        """查找已存在的页面"""
        for page_id, info in self.existing_pages.items():
            if info.get("file_path") == str(file_path):
                return page_id
        return None
    
    def sync_file(self, file_path: Path) -> bool:
        """同步单个文件"""
        try:
            doc = self.parser.parse(file_path)
            database_id = self._get_database_id(doc)
            
            if not database_id:
                logger.error(f"未找到数据库配置，跳过: {file_path}")
                self.stats["skipped"] += 1
                return False
            
            # 检查是否已存在
            existing_page_id = self._find_existing_page(file_path)
            
            # 准备内容
            blocks = self.converter.markdown_to_blocks(doc.content)
            properties = self.converter.create_properties(doc, database_id)
            
            if existing_page_id:
                # 更新现有页面
                logger.info(f"更新: {doc.title}")
                self.notion.update_page(existing_page_id, properties, blocks)
                self.stats["updated"] += 1
            else:
                # 创建新页面
                logger.info(f"创建: {doc.title}")
                self.notion.create_page(database_id, properties, blocks)
                self.stats["created"] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"同步失败 {file_path}: {e}")
            self.stats["errors"] += 1
            return False
    
    def sync_directory(self, subdir: str = "") -> int:
        """同步目录下的所有 Markdown 文件"""
        sync_path = self.root_path / subdir if subdir else self.root_path
        
        md_files = list(sync_path.glob("**/*.md"))
        # 排除 README.md 和节点模块
        md_files = [f for f in md_files if f.name != "README.md" and "node_modules" not in str(f)]
        
        logger.info(f"找到 {len(md_files)} 个 Markdown 文件")
        
        success_count = 0
        for md_file in md_files:
            if self.sync_file(md_file):
                success_count += 1
        
        return success_count
    
    def print_stats(self):
        """打印同步统计"""
        logger.info("=" * 50)
        logger.info("同步完成!")
        logger.info(f"  创建: {self.stats['created']}")
        logger.info(f"  更新: {self.stats['updated']}")
        logger.info(f"  跳过: {self.stats['skipped']}")
        logger.info(f"  错误: {self.stats['errors']}")
        logger.info("=" * 50)

# ============================================================
# 主程序
# ============================================================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI联盟 Notion 同步工具")
    parser.add_argument("--token", help="Notion API Token")
    parser.add_argument("--path", default=".", help="要同步的目录路径")
    parser.add_argument("--dry-run", action="store_true", help="仅测试不实际同步")
    parser.add_argument("--download", action="store_true", help="从 Notion 下载到本地")
    parser.add_argument("--bidirectional", action="store_true", help="双向同步")
    
    args = parser.parse_args()
    
    notion_token = args.token or os.getenv("NOTION_API_TOKEN")
    
    if not notion_token:
        logger.error("未设置 NOTION_API_TOKEN")
        return 1
    
    # 下载模式
    if args.download:
        manager = BidirectionalSyncManager(notion_token, args.path)
        downloaded = manager.download_all()
        logger.info(f"下载完成: {downloaded} 个页面")
        return 0
    
    # 创建同步管理器
    manager = SyncManager(notion_token, args.path)
    
    if args.dry_run:
        logger.info("Dry run 模式，仅解析文件不实际同步")
        return 0
    
    # 双向同步模式
    if args.bidirectional:
        logger.info("开始双向同步...")
        bi_manager = BidirectionalSyncManager(notion_token, args.path)
        downloaded = bi_manager.download_all()
        logger.info(f"Notion -> 本地: {downloaded} 个页面")
        success = bi_manager.sync_directory()
        bi_manager.print_stats()
        return 0
    
    # 执行同步
    success = manager.sync_directory()
    manager.print_stats()
    
    return 0 if manager.stats["errors"] == 0 else 1

# ============================================================
# 双向同步管理器
# ============================================================

import urllib.request

class BidirectionalSyncManager:
    """双向同步管理器"""
    
    TYPE_TO_DATABASE = {
        "memory": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "agents": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "projects": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "flows": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "knowledge": os.getenv("NOTION_DATABASE_DEFAULT", ""),
        "default": os.getenv("NOTION_DATABASE_DEFAULT", ""),
    }
    
    def __init__(self, notion_token: str, root_path: str):
        self.notion = NotionClient(notion_token)
        self.parser = MarkdownParser()
        self.converter = MarkdownToNotionConverter(self.notion)
        self.root_path = Path(root_path)
        self.stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0, "downloaded": 0}
        self.existing_pages = {}
        self._load_existing_pages()
    
    def _load_existing_pages(self):
        logger.info("加载已存在的 Notion 页面...")
        database_id = os.getenv("NOTION_DATABASE_DEFAULT", "")
        if database_id:
            try:
                pages = self.notion.query_database(database_id)
                for page in pages:
                    file_path = None
                    if "文件路径" in page.get("properties", {}):
                        rich_text = page["properties"]["文件路径"].get("rich_text", [])
                        if rich_text:
                            file_path = rich_text[0].get("plain_text", "")
                    self.existing_pages[page["id"]] = {"database_id": database_id, "file_path": file_path}
                logger.info(f"  已加载 {len(pages)} 个页面")
            except Exception as e:
                logger.warning(f"  加载失败: {e}")
    
    def _get_database_id(self, doc_type: str = "default") -> str:
        return os.getenv("NOTION_DATABASE_DEFAULT", "")
    
    def fetch_page_content(self, page_id: str) -> List[dict]:
        try:
            headers = {
                "Authorization": f"Bearer {self.notion.token}",
                "Content-Type": "application/json",
                "Notion-Version": "2026-03-11"
            }
            url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            logger.info(f"Fetching: {url}")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                return result.get("results", [])
        except Exception as e:
            logger.error(f"获取页面内容失败 {page_id}: {e}")
            return []
    
    def blocks_to_markdown(self, blocks: List[dict]) -> str:
        md_lines = []
        for block in blocks:
            block_type = block.get("type", "")
            content = block.get(block_type, {})
            rich_text = content.get("rich_text", [])
            text = "".join(rt.get("text", {}).get("content", "") for rt in rich_text if rt.get("type") == "text")
            
            if block_type == "heading_1": md_lines.append(f"# {text}")
            elif block_type == "heading_2": md_lines.append(f"## {text}")
            elif block_type == "heading_3": md_lines.append(f"### {text}")
            elif block_type == "paragraph": md_lines.append(text)
            elif block_type == "bulleted_list_item": md_lines.append(f"- {text}")
            elif block_type == "numbered_list_item": md_lines.append(f"1. {text}")
            elif block_type == "code":
                md_lines.append(f"```{content.get('language', 'markdown')}")
                md_lines.append(text)
                md_lines.append("```")
            elif block_type == "quote": md_lines.append(f"> {text}")
            elif block_type == "divider": md_lines.append("---")
            
            if block.get("has_children"):
                children = self.fetch_page_content(block["id"])
                if children:
                    md_lines.append(self.blocks_to_markdown(children))
        return "\n".join(md_lines)
    
    def download_page(self, page: dict, output_dir: Path) -> Optional[Path]:
        try:
            props = page.get("properties", {})
            name_list = props.get("名称", {}).get("title", [])
            title = name_list[0].get("plain_text", "Untitled") if name_list else "Untitled"
            
            file_path_list = props.get("文件路径", {}).get("rich_text", [])
            file_path_str = file_path_list[0].get("plain_text", "") if file_path_list else ""
            
            type_select = props.get("类型", {}).get("select", {})
            doc_type = type_select.get("name", "default") if type_select else "default"
            
            if file_path_str:
                output_path = Path(file_path_str)
            else:
                type_dir_map = {"记忆库": "Notion系统/01-Memory-记忆库", "节点库": "Notion系统/02-Agents-节点库",
                    "项目系统": "Notion系统/03-Projects-项目系统", "流程系统": "Notion系统/04-Flows-流程系统",
                    "知识库": "Notion系统/05-Knowledge-知识库"}
                subdir = type_dir_map.get(doc_type, "Notion系统")
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
                output_path = output_dir / subdir / f"{safe_title}.md"
            
            blocks = self.fetch_page_content(page["id"])
            content = self.blocks_to_markdown(blocks)
            
            frontmatter = f"""---
title: {title}
type: {doc_type}
notion_id: {page["id"]}
source: notion
---

"""
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(frontmatter + content)
            logger.info(f"下载: {title} -> {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"下载页面失败: {e}")
            return None
    
    def download_all(self, output_dir: Path = None) -> int:
        output_dir = output_dir or self.root_path / "AI创业者联盟"
        logger.info(f"下载所有页面到: {output_dir}")
        
        downloaded = 0
        database_id = self._get_database_id()
        if database_id:
            try:
                pages = self.notion.query_database(database_id)
                for page in pages:
                    if self.download_page(page, output_dir):
                        downloaded += 1
            except Exception as e:
                logger.warning(f"下载失败: {e}")
        logger.info(f"下载完成: {downloaded} 个页面")
        return downloaded
    
    def sync_file(self, file_path: Path) -> bool:
        try:
            doc = self.parser.parse(file_path)
            database_id = self._get_database_id(doc.doc_type)
            if not database_id:
                self.stats["skipped"] += 1
                return False
            
            existing_page_id = None
            for page_id, info in self.existing_pages.items():
                if info.get("file_path") == str(file_path):
                    existing_page_id = page_id
                    break
            
            blocks = self.converter.markdown_to_blocks(doc.content)
            properties = self.converter.create_properties(doc, database_id)
            
            if existing_page_id:
                logger.info(f"更新: {doc.title}")
                self.notion.update_page(existing_page_id, properties, blocks)
                self.stats["updated"] += 1
            else:
                logger.info(f"创建: {doc.title}")
                self.notion.create_page(database_id, properties, blocks)
                self.stats["created"] += 1
            return True
        except Exception as e:
            logger.error(f"同步失败 {file_path}: {e}")
            self.stats["errors"] += 1
            return False
    
    def sync_directory(self) -> int:
        md_files = list(self.root_path.glob("**/*.md"))
        md_files = [f for f in md_files if f.name != "README.md" and "node_modules" not in str(f)]
        logger.info(f"找到 {len(md_files)} 个 Markdown 文件")
        
        success_count = 0
        for md_file in md_files:
            if self.sync_file(md_file):
                success_count += 1
        return success_count
    
    def print_stats(self):
        logger.info("=" * 50)
        logger.info("同步完成!")
        logger.info(f"  创建: {self.stats['created']}")
        logger.info(f"  更新: {self.stats['updated']}")
        logger.info(f"  跳过: {self.stats['skipped']}")
        logger.info(f"  错误: {self.stats['errors']}")
        logger.info("=" * 50)

if __name__ == "__main__":
    exit(main())