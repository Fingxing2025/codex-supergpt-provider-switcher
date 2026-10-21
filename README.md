# Codex / SuperGPT 桌面配置切换器

在 Linux 桌面上，为**新建的本地聊天**切换官方账号、SuperGPT 与 SuperGPT 独立 API。两个 SuperGPT 模式都带有通过中转接口生成图片的技能。

| 模式 | 模型接口 | ChatGPT 身份 | Work 内置浏览器 | SuperGPT 生图 |
| --- | --- | --- | --- | --- |
| 官方账号 | 官方 | 使用 | 取决于账号和现有工具配置 | 不设置此路由 |
| SuperGPT（含图片生成） | SuperGPT | 保留 | 已在下述版本观察到可用 | 支持 |
| SuperGPT 独立 API（含生图，无 Work 浏览器） | SuperGPT | 模型请求不要求 | 关闭 | 支持 |

这是个人使用配置的脱敏分享，不属于 OpenAI 或 SuperGPT 官方项目。已在 `Codex 0.163.0-alpha.10.2` 和桌面版本 `26.1013.40934` 上观察到中转聊天可以打开、读取内置浏览器网页；其他版本和账号的行为需要自行确认。

## 前置条件

- Linux，Python 3.11 或以上，以及 `zenity`。
- 已安装 ChatGPT/Codex 桌面应用。使用官方模式或带 Work 浏览器的 SuperGPT 模式时，需要自己的 ChatGPT 账号登录及现有浏览器工具配置。
- 自己的 SuperGPT API key，且中转站兼容 Responses API。
- 默认桌面程序路径 `/usr/lib/chatgpt/ChatGPT`，内置 CLI 路径 `/usr/lib/chatgpt/resources/codex`。可通过下面的选项覆盖。

## 安装与使用

在项目目录运行：

```bash
python3 configure.py
```

首次运行会隐藏输入内容地询问 SuperGPT 密钥。如果本机已有 `$CODEX_HOME/supergpt-api-key`，则读取该文件。默认 `CODEX_HOME` 是当前用户的 `~/.codex`。

安装程序会生成三份私有模板、安装 `supergpt-imagegen` 技能，导出当前安装版本自带的 GPT 模型元数据，并添加应用菜单入口 **Codex Provider Switcher**。它不会切换当前的 `config.toml`，也不会修改 `auth.json`。

配置以已有 `config.official.toml` 为基础；第一次没有官方模板时，使用活动配置。安装程序保留基础配置中的其他设置值，重新生成 TOML 排版，因此不保留注释。独立 API 模板会关闭浏览器与电脑操作插件，移除 `node_repl`、`cua_repl` 服务，并使用 Codex 界面，避免 Work 浏览器认证前置检查。安装器不会补装缺失的 Work 浏览器插件。

1. 正常退出 ChatGPT/Codex 桌面应用。
2. 从应用菜单打开 **Codex Provider Switcher**，或运行 `~/.local/bin/codex-desktop-provider`。
3. 选择所需模式，应用随后启动。
4. **新建本地聊天**。旧聊天仍可能保留原来的模型提供商。

自定义路径和默认模型：

```bash
CODEX_HOME="$HOME/.codex" \
CODEX_DESKTOP_APP="/path/to/ChatGPT" \
python3 configure.py --codex-cli /path/to/codex \
  --model gpt-6.1-sol --official-model gpt-6.1-sol
```

`configure.py` 导出的模型目录来自本机安装文件，不会查询中转接口，也不会发起付费模型对话。目录中出现某个模型，不代表该 API key 拥有调用权限。

已有安装更新时，先获取仓库更新，再运行 `python3 configure.py`。模板和生图技能会更新，并保存被覆盖文件的备份。随后退出桌面应用，重新选择模式并新建聊天。

## 配置中的关键区别

见 [带 Work 浏览器的脱敏示例](examples/supergpt.example.toml)和[独立 API 示例](examples/supergpt-api.example.toml)。示例只展示关键字段，完整技能指令由安装器加入。

- 模型接口为 `https://api.supergpt.dev/v1`，协议为 `responses`。
- 带 Work 浏览器模式使用 `requires_openai_auth = true` 保留账号认证路径。
- 独立 API 模式使用 `requires_openai_auth = false`，模型请求不要求 ChatGPT 身份；本地登录文件仍然保留。
- 使用 `experimental_bearer_token` 配置独立中转密钥。
- 该组合中不要再添加 `[model_providers.supergpt.auth]` 命令认证表。
- 模型元数据保存在本地文件，避免依赖中转站的模型目录发现行为。

`experimental_bearer_token` 是实验配置字段。此分享记录的是上述安装版本的观察结果，不是对后续版本的兼容承诺。它也不会把 ChatGPT 网页聊天或云端聊天改为第三方接口。

## SuperGPT 图片生成

两个 SuperGPT 模板都会启用 [supergpt-imagegen 技能](skills/supergpt-imagegen/SKILL.md)，并添加生图路由指令。默认使用 **`gpt-image-2.5-sunburst`、`quality=max`、`1024x1024`、PNG**。该模型按上游文档的画质优先定位选择；SuperGPT 模型广场列出模型，并不保证每把密钥都有权限。

在新建的 SuperGPT 聊天中直接请求生成图片即可。技能调用 `https://api.supergpt.dev/v1/images/generations`，读取本机中转密钥，不依赖 Work 浏览器或 ChatGPT 登录令牌。它支持生成新图片，目前不支持编辑已有图片。

也可手动调用（成功生成可能产生 SuperGPT 费用）：

```bash
"${CODEX_HOME:-$HOME/.codex}/skills/supergpt-imagegen/scripts/generate.sh" \
  --prompt "一张蓝天白云的水彩画" \
  --out "$PWD/outputs/imagegen/sky.png"
```

输出路径已存在时会拒绝覆盖。每次生成请使用新文件名。可用 `--model`、`--quality` 指定其他支持的设置；显式选择旧模型时默认质量为 `high`。

只查看参数而不发送生图请求：

```bash
"${CODEX_HOME:-$HOME/.codex}/skills/supergpt-imagegen/scripts/generate.sh" \
  --config "${CODEX_HOME:-$HOME/.codex}/config.supergpt-api.toml" \
  --prompt "检查配置" --dry-run
```

**尚未使用真实密钥验证 `sunburst` 的 `max` 参数及完整生图流程。** 若中转拒绝模型或参数，脚本会报告错误，不会自动降级、换模型或重试。超时也可能已计费，重复请求前应先查看中转控制台。

## 如何确认实际生效

在新建聊天中让模型实际使用 Work 内置浏览器打开网页、读取页面并截图。同时查看 SuperGPT 控制台是否出现对应的调用记录。

模型自称“正在使用 SuperGPT”不能证明请求归属；本地配置只能证明保存的设置。客户端会话中的 `model_provider`、实际工具结果和中转控制台记录可以帮助交叉核对。

**不能承诺完全不消耗官方额度。** 旧官方聊天继续运行、其他官方任务以及工具服务都应与中转调用分开核对。本项目没有完成“所有官方任务停止后，仅使用中转聊天”的隔离额度对比。

如果官方五小时额度耗尽后发送按钮不可用，可选择独立 API 模式并新建聊天。该模式已在本地诊断中确认不要求 ChatGPT 模型认证，但**尚未在官方额度实际耗尽时验证桌面发送按钮的行为**；带 Work 浏览器模式也不能保证避开界面的额度限制。

## 凭据与备份

生成的密钥文件、配置模板、切换时的活动配置和备份均使用 `0600` 权限。密钥会以明文保存在本机私有模板内，这是该配置字段的工作方式。

公开仓库仅包含通用程序和占位示例。请把本机的 API key、`auth.json`、真实配置、聊天记录、数据库及备份留在本机。`.gitignore` 用于降低误提交风险，不能代替提交前检查。

切换器在覆盖 `config.toml` 前，会在同一目录生成 `config.toml.before-provider-switch-*` 备份。安装程序覆盖现有模板时也会创建 `*.before-setup-*` 备份。退出桌面应用后，可将需要恢复的备份复制回原路径。

## 参考

- [官方配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [账号认证与自定义提供商](https://learn.chatgpt.com/docs/auth)
- [内置浏览器说明](https://learn.chatgpt.com/docs/browser)
- [上游图片模型选择与提示词说明](https://developers.openai.com/api/docs/guides/image-prompting)
- [SuperGPT 模型广场](https://console.supergpt.dev/model-plaza)

