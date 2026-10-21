#!/usr/bin/env python3
"""在本机生成私有配置模板和桌面入口；不会切换当前配置。"""

import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib


def private_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        fd, backup = tempfile.mkstemp(prefix=path.name + ".before-setup-", dir=path.parent)
        os.close(fd)
        shutil.copyfile(path, backup)
        os.chmod(backup, 0o600)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_config(source, values, provider=None):
    # 只替换顶层路由字段和 SuperGPT 表，保留插件、浏览器等其他设置。
    output = []
    at_root = True
    skip = False
    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            at_root = False
            section = stripped.split("#", 1)[0].strip().strip("[]")
            skip = section == "model_providers.supergpt" or section.startswith("model_providers.supergpt.")
        if skip:
            continue
        if at_root and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in {"model_provider", "model", "model_catalog_json"}:
                continue
        output.append(line)
    header = "".join(f"{key} = {json.dumps(value, ensure_ascii=False)}\n" for key, value in values.items())
    result = header + "".join(output).rstrip() + "\n"
    if provider:
        result += "\n[model_providers.supergpt]\n"
        for key, value in provider.items():
            encoded = str(value).lower() if isinstance(value, bool) else json.dumps(value)
            result += f"{key} = {encoded}\n"
    tomllib.loads(result)  # 写入前拒绝无效 TOML。
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--official-model", default=None, help="默认沿用当前配置的模型")
    parser.add_argument("--codex-cli", default=os.environ.get("CODEX_CLI_PATH", "/usr/lib/chatgpt/resources/codex"))
    args = parser.parse_args()
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
    active_path = codex_home / "config.toml"
    source = active_path.read_text(encoding="utf-8") if active_path.exists() else ""
    current = tomllib.loads(source)
    key_path = codex_home / "supergpt-api-key"
    key = key_path.read_text().strip() if key_path.exists() else getpass.getpass("SuperGPT API key（输入不回显）: ").strip()
    if not key or "\n" in key or "\r" in key:
        raise SystemExit("密钥为空或含换行，未生成配置。")

    # 仅导出当前安装版本的本地模型元数据，不调用远程模型。
    bundled = subprocess.run([args.codex_cli, "debug", "models", "--bundled"], check=True, capture_output=True, text=True)
    catalog = json.loads(bundled.stdout)
    models = catalog["models"]
    models = [model for model in models if model.get("slug", "").startswith("gpt-") and not model.get("slug", "").startswith("gpt-image-")]
    if args.model not in {model.get("slug") for model in models}:
        raise SystemExit("指定模型不在当前安装版本的本地目录中；请使用 --model 指定已有模型。")
    catalog_path = codex_home / "supergpt-codex-models.json"
    provider = {
        "name": "SuperGPT",
        "base_url": "https://api.supergpt.dev/v1",
        "wire_api": "responses",
        "supports_websockets": False,
        "requires_openai_auth": True,
        "experimental_bearer_token": key,
    }
    official = update_config(source, {"model_provider": "openai", "model": args.official_model or current.get("model", args.model)})
    supergpt = update_config(source, {"model_provider": "supergpt", "model": args.model, "model_catalog_json": str(catalog_path)}, provider)
    private_write(catalog_path, json.dumps({"models": models}, ensure_ascii=False, indent=2) + "\n")
    private_write(key_path, key + "\n")
    private_write(codex_home / "config.official.toml", official)
    private_write(codex_home / "config.supergpt.toml", supergpt)

    source_script = Path(__file__).resolve().parent / "codex-desktop-provider"
    installed_script = Path.home() / ".local/bin/codex-desktop-provider"
    private_write(installed_script, source_script.read_text(encoding="utf-8"))
    installed_script.chmod(0o700)
    # 将用户选定的 CODEX_HOME 写入本机启动脚本，桌面入口无需继承终端环境。
    import shlex
    launcher_path = Path.home() / ".local/bin/codex-provider-switcher-launcher"
    desktop_app = os.environ.get("CODEX_DESKTOP_APP", "/usr/lib/chatgpt/ChatGPT")
    launcher = "#!/usr/bin/env bash\nexport CODEX_HOME=" + shlex.quote(str(codex_home)) + "\nexport CODEX_DESKTOP_APP=" + shlex.quote(desktop_app) + "\nexec " + shlex.quote(str(installed_script)) + "\n"
    private_write(launcher_path, launcher)
    launcher_path.chmod(0o700)
    desktop_exec = str(launcher_path).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    entry = '[Desktop Entry]\nType=Application\nName=Codex Provider Switcher\nComment=Choose the provider for new local Codex chats\nExec="' + desktop_exec + '"\nIcon=chatgpt\nTerminal=false\nCategories=Development;\n'
    private_write(Path.home() / ".local/share/applications/codex-provider-switcher.desktop", entry)
    print("已生成本机配置和桌面入口。当前 config.toml 未切换；请退出桌面应用后使用切换器。")
    print("配置、密钥及备份保存在本机，请勿上传。模型目录不代表中转账号实际拥有这些模型的权限。")


if __name__ == "__main__":
    main()

