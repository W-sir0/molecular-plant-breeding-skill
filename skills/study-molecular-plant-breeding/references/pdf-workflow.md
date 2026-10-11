# 本地 PDF 阅读说明

## 安装与检查

脚本仅访问本地文件，不上传资料。依赖 `pypdf`，扫描页 OCR 依赖 `pdftoppm` 与所选识别引擎。先运行：

```bash
python scripts/book.py inspect '/path/to/book.pdf'
```

`text_layer_samples` 只表示所抽样页面是否提取到文字，不代表全书均可搜索。元数据可能不可靠；书目应看版权页。扫描件的普通 `extract` 会明确要求使用 OCR，不把空输出假装成完整索引。

## 按需 OCR

在技能目录中运行，输出放在本地忽略目录：

```bash
# macOS：Vision + Swift 命令行工具（离线识别）
python scripts/book.py extract '/path/to/book.pdf' --pages 313-315 --ocr vision --out .local/mas.json
# Linux / Windows 等：Tesseract 与中文简体、英文语言包
python scripts/book.py extract '/path/to/book.pdf' --pages 313-315 --ocr tesseract --lang chi_sim+eng --out .local/mas.json
```

`--pages` 是从 1 开始的 PDF 物理页，可以写 `33,54-55`。脚本拒绝越界页码。Vision 方案只在 macOS 上运行；`swift` 或识别语言缺失时会报告错误。Tesseract 方案不会自动下载安装语言包。可以从 Tesseract 官方 `tessdata_fast` 仓库获取 `chi_sim.traineddata`，放入本地语言目录；若不安装到系统目录，将 `TESSDATA_PREFIX` 设为同时含中文和英文模型的目录。Vision 若报 `nilError`，改用 Tesseract；本项目在当前 macOS 环境的 Vision 调用遇到该错误，真实书页已用 Tesseract 路径核验。每次输出是一个独立范围，不会自动合并或覆盖之前不同范围的搜索内容；输出同名文件会整体替换，保留不同主题时使用不同文件名。

脚本保留来源 SHA-256、总页数、识别引擎和各页文字。使用 JSON 后仍需对照原页；OCR 只是定位辅助，未核验文字不能视为准确引文。

## 检索与复核

```bash
python scripts/book.py search .local/mas.json --query '前景 背景' --limit 5
```

多个关键词用空格分隔，默认要求同页全部出现。Unicode 会统一化并忽略文本空格，便于中文识别中被拆开的词。搜索结果只返回本地缓存中的页码和短片段，不会检索未抽取页面；未命中时改用相关术语或扩大候选范围。OCR 错字不会被自动修复。

需要视觉复核时，在系统 PDF 阅读器打开对应物理页，或用 Poppler：

```bash
pdftoppm -f 313 -l 313 -scale-to 1800 -png '/path/to/book.pdf' .local/check
```

引用时写两类页码。当前参考扫描版的偏移已经实测发生变化：书内 p. 1 对应 PDF 第 33 页，书内 p. 283 对应第 314 页，不能用一个公式覆盖全书。利用目录和已校准的附近页定位，实际页眉确认后再引用。优先检查公式、单位、上下标、正负号和表格结构。换版本需重新校准，不依赖文件名判断。

PDF、缓存全文与截图不要提交到公开仓库。仓库 `.gitignore` 提供基础排除；发布时还应检查待提交清单。配套 PDF 由项目维护者确认已取得公开再分发授权后单独发布到 Release；代码仓库的 MIT 许可证不覆盖教材，也不授权代理在其他目的地再次上传。
