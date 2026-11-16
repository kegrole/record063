# encnorm

`encnorm` 把来源不同、编码不同的 HTML 页面统一解码并修复可逆乱码，最终写出 UTF-8（不带 BOM）文本与一份确定性 JSON 报告。项目只使用 Python 标准库，不依赖第三方包。

## 快速开始

```bash
python -m encnorm.cli --dir demo/pages --manifest demo/manifest.json --out out/report.json
```

命令在 stdout 打印一行摘要，包含页面数、修复数、issue 数和归一后输出目录。报告写到 `--out` 指定的路径，归一文本写到该路径同级的 `normalized/` 目录，输出文件名为“原文件名 + `.txt`”。也可以用 `python -m encnorm` 执行同一入口。

参数：

- `--dir`：页面目录，默认 `demo/pages`。
- `--manifest`：来源清单，默认 `demo/manifest.json`。
- `--out`：报告 JSON 输出路径，必填；同级创建 `normalized/`。

## 编码名归一

所有声明名先去除首尾空白并转小写，再映射到四个规范名之一：

| 输入名称（大小写不敏感） | 规范名 |
| --- | --- |
| `utf-8`、`utf8`、`u8` | `utf-8` |
| `gbk`、`gb2312`、`gb18030` 及带连字符写法 | `gbk` |
| `big5`、`big-5` | `big5` |
| `latin-1`、`iso-8859-1`、`iso8859-1`、`latin1` | `latin-1` |

认不出来的名称等同于没有声明，返回空串而不是猜测编码。

## 声明优先级、BOM 与探测顺序

每个页面按以下顺序确定“选定编码”：

1. HTTP 响应头中的 `http_charset`。只要能归一成规范名就立即采用，优先级最高。
2. HTML 前 1024 字节内的 meta 声明。支持两种写法：
   - `<meta charset="gbk">`；
   - `<meta http-equiv="Content-Type" content="text/html; charset=gbk">`。
3. 没有声明时检查 BOM。文件以 `EF BB BF` 开头则按 UTF-8 解码，并在解码前剥掉这三个字节；BOM 不是声明，`declared_charset` 仍为空串。
4. 仍没有结果时探测原始字节，严格按 `utf-8` → `gbk` → `big5` → `latin-1` 尝试，第一个完整严格解码成功的编码生效；Latin-1 能映射任意字节，是最终兜底。

HTTP 头与 meta 同时存在时只使用 HTTP 头，meta 中的冲突声明不会影响解码。

## 整份失败后的逐行兜底

先尝试用选定编码对整份字节做严格解码。整份成功时不产生 issue；失败时不放弃页面，而是按行解码：

1. 每一行先尝试选定编码。
2. 选定编码失败的行，再按探测顺序 `utf-8` → `gbk` → `big5` → `latin-1` 严格尝试。
3. 成功的第一个兜底编码用于该行，并在 issue 中记录行号与编码，例如 `line 2 decoded with fallback charset gbk`。
4. 理论上 Latin-1 不会失败；若极端情况下仍无法解码，则保留原始字节并在 issue 中记录行号。

行号从 1 开始，换行符属于所在行，输出仍保持原换行结构。

### `used_charset` 写法

- 没有任何行使用兜底：只写选定编码，如 `utf-8`。
- 一部分行使用兜底：选定编码在前，之后按首次使用顺序追加去重后的兜底编码，用 `+` 连接，如 `utf-8+gbk`。
- 所有行都使用兜底：不写选定编码，只写实际兜底编码；同一单文件示例会得到 `gbk`。

## 乱码逆转

逐行解码完成后，对完整文本依次尝试 `latin-1`、`gbk` 两个候选。某个候选必须同时满足以下三条才算乱码：

1. 当前文本能用该候选编码严格编码回字节；
2. 这些字节能按 UTF-8 严格解码；
3. UTF-8 解出的文本与当前文本不同。

取第一个满足条件的候选进行修复；两个候选都不满足时，文本一个字符都不改。因此真正的 Latin-1 文本、普通 ASCII 和正常中文不会被误修。典型效果：

- `cafÃ©` 经 Latin-1 候选还原为 `café`；
- `鏁版嵁` 经 GBK 候选还原为 `数据`。

发生任意修复时 `repaired` 为 `true`，否则为 `false`。

## BOM 处理

仅在没有 HTTP/meta 声明时 BOM 才参与选码；一旦识别到 UTF-8 BOM，三个 BOM 字节会在解码前删除。所有归一输出和 JSON 报告都以无 BOM 的 UTF-8 写出，文本中也不会保留 `U+FEFF`。

## 报告字段

报告顶层固定为 `pages` 与 `summary` 两部分，键顺序稳定。

`pages` 中每条记录正好包含五个字段：

| 字段 | 含义 |
| --- | --- |
| `file` | 页面文件名 |
| `declared_charset` | HTTP/meta 声明归一后的编码；无声明为空串，BOM 不算声明 |
| `used_charset` | 实际使用的编码表达式，按上述 `+` 规则组合 |
| `repaired` | 是否发生乱码逆转 |
| `issue` | 逐行兜底等问题说明；无问题为空串 |

`summary` 正好包含四个字段：

| 字段 | 含义 |
| --- | --- |
| `files` | 页面总数 |
| `ok` | `issue` 为空串的页面数 |
| `repaired` | `repaired` 为 `true` 的页面数 |
| `issues` | `issue` 非空的页面数 |

报告使用 `ensure_ascii=False`、固定缩进和 `\n` 换行；处理顺序来自 manifest，不使用随机或随文件系统顺序变化的遍历，因此同一份输入重复运行的报告和归一文本逐字节一致。

## 包结构

| 模块 | 职责 |
| --- | --- |
| `httpheader.py` | HTTP charset 名称归一 |
| `meta.py` | 前 1024 字节中的两种 meta charset 识别 |
| `bom.py` | UTF-8 BOM 检测与剥离 |
| `probe.py` | UTF-8、GBK、Big5、Latin-1 严格探测 |
| `mojibake.py` | Latin-1/GBK 乱码逆转的三条件判断 |
| `decode.py` | 声明选码、BOM、探测、整份/逐行解码与 `used_charset` 组合 |
| `report.py` | manifest 读取、UTF-8 文本写出、报告汇总 |
| `cli.py` / `__main__.py` | 命令行入口 |

## 测试

```bash
python -m unittest test_encnorm -v
```

测试会校验随仓库提供的九个夹具与 manifest 字节内容、15 条判定口径、两次重跑的字节级一致性，以及各模块的独立边界行为。也可以在 `tests/` 目录中运行 `python -m unittest test_encnorm -v`。
