# 分子植物育种学习 Skill

[![Tests](https://github.com/W-sir0/molecular-plant-breeding-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/W-sir0/molecular-plant-breeding-skill/actions/workflows/tests.yml)

把徐云碧《分子植物育种》作为**本地阅读资料**，让 AI 根据具体书页讲解概念、比较方法、安排复习并出题。项目包含原创学习工作流程和 PDF 定位工具，不包含教材正文、扫描图或全文 OCR。

## 能做什么

- 从问题找到阅读范围，保留 PDF 页码与书内页码。
- 围绕标记、群体、QTL、辅助选择、环境互作等主题进行概念辨析。
- 制作学习计划、知识卡片、自测题及错题反馈。
- 阅读扫描版：macOS 使用本机 Vision；其他平台可使用 Tesseract 中文 OCR。
- 区分教材中的历史资料、已核对的书页和另外查证的新进展。

## 安装

下载仓库后，将 `skills/study-molecular-plant-breeding` 文件夹复制到 `~/.codex/skills/`，重启或刷新 Codex 的技能列表。也可直接让支持 SKILL.md 的代理读取该文件夹。

PDF 是可选的本地参考资料，**请使用自己有权访问的版本**。没有 PDF 仍可进行一般学习，但不能声称回答来自已查阅的教材页。

## 直接使用

```text
使用 $study-molecular-plant-breeding，读取我提供的《分子植物育种》PDF。
比较 RIL、DH、NIL 群体适用的问题，给出来源页码，再出 3 道应用题。
```

```text
使用 $study-molecular-plant-breeding，我每天有 30 分钟。
帮我围绕 QTL 分析和标记辅助选择制定两周复习计划；先检查我的基础。
```

```text
使用 $study-molecular-plant-breeding，核对我对连锁与关联分析的理解。
逐条指出论证缺口，未读到的书页不要编造引用。
```

## PDF 工具

需要 Python 3.10+；安装 `requirements.txt` 中的依赖。扫描件 OCR 还需要 Poppler 的 `pdftoppm`。macOS 自带 Vision，运行源码需要 Swift 命令行工具；Tesseract 方案需自行安装 `chi_sim` 和 `eng` 语言包。

```bash
python -m pip install -r requirements.txt
python skills/study-molecular-plant-breeding/scripts/book.py inspect '/path/to/book.pdf'
# --pages 使用从 1 开始的 PDF 物理页码；只处理需要的范围
python skills/study-molecular-plant-breeding/scripts/book.py extract '/path/to/book.pdf' --pages 313-315 --ocr tesseract --out .local/mas.json
python skills/study-molecular-plant-breeding/scripts/book.py search .local/mas.json --query '前景 背景' --limit 5
```

上例页码用于所核对扫描版的标记辅助选择主题，仅作定位示例。已视觉核对书内 p. 282、283 分别对应 PDF 第 313、314 页；全书偏移并不固定。换一个版本必须重新检查页码。中文搜索会忽略 OCR 插入的空格，但不会自动修正错字；没有结果不等于书中没有讨论该主题。JSON 记录原文件 SHA-256、抽取方法和物理页码，方便核对；局部索引不是全文搜索。

详细使用见 [PDF 阅读说明](skills/study-molecular-plant-breeding/references/pdf-workflow.md)。首次使用建议提取 1-3 页并对照扫描图检查，再扩大范围。

## 参考书与公开范围

参考书：徐云碧著，陈建国等译，《分子植物育种》，科学出版社，2014 年，ISBN 978-7-03-041047-4。书目和定位信息经用户提供版本的版权页、目录及正文起始页核对。

参考版本原著为 2010 年出版，中译本为 2014 年出版。它适合学习相关基础，涉及软件、数据库、法规或近期技术时应另查当前一手来源。

仓库的 MIT 许可证仅覆盖本项目原创代码和文档，不授予原书权利。未取得原书公开再分发授权，仓库不分发整本 PDF，也不提供未授权下载链接。书籍、OCR 文本、截图和本地路径配置应保存在 `.local/` 等忽略目录中；`.gitignore` 不会移除已经提交的文件。

## 验证

```bash
python -m unittest discover -s tests -v
```

测试采用原创最小 PDF 和模拟识别结果，检查页码边界、扫描件处理、中文检索、缓存来源及命令行行为。OCR 精确度须针对实际书页人工核验。本地已通过 22 项测试，并在所提供扫描版的 PDF 第 313-315 页完成 Tesseract 中文识别与关键词检索，视觉核对其中两页页码。Vision 在当前 macOS 环境返回 `nilError`，保留可选支持及明确错误提示；未声称该路径已成功验证。
