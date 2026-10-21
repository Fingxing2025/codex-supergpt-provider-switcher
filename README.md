# Codex / SuperGPT 桌面配置切换器

在 Linux 桌面上，为**新建的本地聊天**切换官方模型提供商与 SuperGPT。SuperGPT 模板保留 ChatGPT 账号身份，用于 Work 内置浏览器认证，并为模型接口配置独立的 SuperGPT 密钥。

这是个人使用配置的脱敏分享，不属于 OpenAI 或 SuperGPT 官方项目。已在 `Codex 0.163.0-alpha.10.2` 和桌面版本 `26.1013.40934` 上观察到中转聊天可以打开、读取内置浏览器网页；其他版本和账号的行为需要自行确认。

## 前置条件

- Linux，Python 3.11 或以上，以及 `zenity`。
- 已安装 ChatGPT/Codex 桌面应用，并使用自己的 ChatGPT 账号登录。
- 自己的 SuperGPT API key，且中转站兼容 Responses API。
- 默认桌面程序路径 `/usr/lib/chatgpt/ChatGPT`，内置 CLI 路径 `/usr/lib/chatgpt/resources/codex`。可通过下面的选项覆盖。

## 安装与使用

在项目目录运行：

```bash
python3 configure.py
```

首次运行会隐藏输入内容地询问 SuperGPT 密钥。如果本机已有 `$CODEX_HOME/supergpt-api-key`，则读取该文件。默认 `CODEX_HOME` 是当前用户的 `~/.codex`。

安装程序会保留现有配置中的插件、浏览器和其他设置，生成两份私有模板，导出当前安装版本自带的 GPT 模型元数据，并添加应用菜单入口 **Codex Provider Switcher**。它不会切换当前的 `config.toml`，也不会修改 `auth.json`。

1. 正常退出 ChatGPT/Codex 桌面应用。
2. 从应用菜单打开 **Codex Provider Switcher**，或运行 `~/.local/bin/codex-desktop-provider`。
3. 选择 **SuperGPT** 或 **官方账号**，应用随后启动。
4. **新建本地聊天**。旧聊天仍可能保留原来的模型提供商。

自定义路径和默认模型：

```bash
CODEX_HOME="$HOME/.codex" \
CODEX_DESKTOP_APP="/path/to/ChatGPT" \
python3 configure.py --codex-cli /path/to/codex \
  --model gpt-6.1-sol --official-model gpt-6.1-sol
```

`configure.py` 导出的模型目录来自本机安装文件，不会查询中转接口，也不会发起付费模型对话。目录中出现某个模型，不代表该 API key 拥有调用权限。

## 配置中的关键区别

见 [脱敏配置示例](examples/supergpt.example.toml)。

- 模型接口为 `https://api.supergpt.dev/v1`，协议为 `responses`。
- 使用 `requires_openai_auth = true` 保留账号认证路径。
- 使用 `experimental_bearer_token` 配置独立中转密钥。
- 该组合中不要再添加 `[model_providers.supergpt.auth]` 命令认证表。
- 模型元数据保存在本地文件，避免依赖中转站的模型目录发现行为。

`experimental_bearer_token` 是实验配置字段。此分享记录的是上述安装版本的观察结果，不是对后续版本的兼容承诺。它也不会把 ChatGPT 网页聊天或云端聊天改为第三方接口。

## 如何确认实际生效

在新建聊天中让模型实际使用 Work 内置浏览器打开网页、读取页面并截图。同时查看 SuperGPT 控制台是否出现对应的调用记录。

模型自称“正在使用 SuperGPT”不能证明请求归属；本地配置只能证明保存的设置。客户端会话中的 `model_provider`、实际工具结果和中转控制台记录可以帮助交叉核对。

**不能承诺完全不消耗官方额度。** 旧官方聊天继续运行、其他官方任务以及工具服务都应与中转调用分开核对。本项目没有完成“所有官方任务停止后，仅使用中转聊天”的隔离额度对比。

## 凭据与备份

生成的密钥文件、配置模板、切换时的活动配置和备份均使用 `0600` 权限。密钥会以明文保存在本机私有模板内，这是该配置字段的工作方式。

公开仓库仅包含通用程序和占位示例。请把本机的 API key、`auth.json`、真实配置、聊天记录、数据库及备份留在本机。`.gitignore` 用于降低误提交风险，不能代替提交前检查。

切换器在覆盖 `config.toml` 前，会在同一目录生成 `config.toml.before-provider-switch-*` 备份。安装程序覆盖现有模板时也会创建 `*.before-setup-*` 备份。退出桌面应用后，可将需要恢复的备份复制回原路径。

## 参考

- [官方配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [账号认证与自定义提供商](https://learn.chatgpt.com/docs/auth)
- [内置浏览器说明](https://learn.chatgpt.com/docs/browser)

