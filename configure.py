#!/usr/bin/env python3
"""在本机生成私有配置模板和桌面入口；不会切换当前配置。"""

import argparse
import copy
import datetime
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

IMAGE_INSTRUCTIONS = """SuperGPT image generation: when the user asks to generate a new image in this SuperGPT mode, use the supergpt-imagegen skill and its local generate.sh helper. This image route uses the SuperGPT API key and does not need Work browser or ChatGPT login. Use a unique absolute output path, inspect the returned image, and display the saved image inline. Do not silently substitute the official image-generation route or retry a possibly billed request. If the user explicitly requests the official route, follow that request. Do not modify model authentication or re-enable browser tools to enable image generation. Default image settings: model=gpt-image-2.5-sunburst, quality=max, size=1024x1024. If the provider rejects these settings, report the error instead of silently lowering quality or switching models."""
IMAGE_MARKER_START = "[supergpt-imagegen routing]"
IMAGE_MARKER_END = "[/supergpt-imagegen routing]"


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


def toml_value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{toml_value(key)} = {toml_value(item)}" for key, item in value.items()) + " }"
    raise ValueError("Unsupported TOML value type: " + type(value).__name__)


def serialize_config(config):
    # 按解析后的值生成模板，支持原配置中的多行字符串和数组表。
    lines = []

    def emit(table, path=()):
        if path:
            lines.extend(("", "[" + ".".join(toml_value(part) for part in path) + "]"))
        for key, value in table.items():
            if not isinstance(value, dict):
                lines.append(f"{toml_value(key)} = {toml_value(value)}")
        for key, value in table.items():
            if isinstance(value, dict):
                emit(value, path + (key,))

    emit(config)
    result = "\n".join(lines).lstrip() + "\n"
    if tomllib.loads(result) != config:
        raise ValueError("Generated configuration does not preserve the source values.")
    return result


def image_instructions(existing):
    # 只替换本安装器添加的指令块，保留用户自己的开发者指令。
    if IMAGE_MARKER_START in existing and IMAGE_MARKER_END in existing:
        before, rest = existing.split(IMAGE_MARKER_START, 1)
        _, after = rest.split(IMAGE_MARKER_END, 1)
        existing = (before + after).strip()
    block = IMAGE_MARKER_START + "\n" + IMAGE_INSTRUCTIONS + "\n" + IMAGE_MARKER_END
    return (existing.rstrip() + "\n\n" + block).lstrip()


def relay_config(base, model, catalog_path, key, skill_path, independent=False):
    result = copy.deepcopy(base)
    result.update(model_provider="supergpt", model=model, model_catalog_json=str(catalog_path))
    result.setdefault("model_providers", {})["supergpt"] = {
        "name": "SuperGPT",
        "base_url": "https://api.supergpt.dev/v1",
        "wire_api": "responses",
        "supports_websockets": False,
        "requires_openai_auth": not independent,
        "experimental_bearer_token": key,
    }
    result.setdefault("desktop", {})["conversationDetailMode"] = "STEPS_COMMANDS" if independent else "STEPS_PROSE"
    for name in ("browser@openai-bundled", "unified-computer-use@openai-bundled"):
        plugins = result.setdefault("plugins", {})
        if independent or name in plugins:
            plugins.setdefault(name, {})["enabled"] = not independent
    if independent:
        servers = result.get("mcp_servers", {})
        servers.pop("node_repl", None)
        servers.pop("cua_repl", None)
    result["developer_instructions"] = image_instructions(result.get("developer_instructions", ""))
    skills = result.setdefault("skills", {}).setdefault("config", [])
    entry = next((item for item in skills if item.get("path") == str(skill_path)), None)
    if entry is None:
        skills.append({"path": str(skill_path), "enabled": True})
    else:
        entry["enabled"] = True
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
    active = tomllib.loads(source)
    # 优先从已有官方模板继承浏览器配置，避免从独立 API 模式反向生成时丢失工具。
    official_path = codex_home / "config.official.toml"
    current = tomllib.loads(official_path.read_text(encoding="utf-8")) if official_path.exists() else active
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
    official = copy.deepcopy(current)
    official.update(model_provider="openai", model=args.official_model or current.get("model", args.model))
    if current.get("model_provider") == "supergpt":
        official.pop("model_catalog_json", None)
    official.get("model_providers", {}).pop("supergpt", None)
    skill_path = codex_home / "skills/supergpt-imagegen"
    supergpt = relay_config(official, args.model, catalog_path, key, skill_path)
    independent = relay_config(official, args.model, catalog_path, key, skill_path, independent=True)
    templates = {
        "config.official.toml": serialize_config(official),
        "config.supergpt.toml": serialize_config(supergpt),
        "config.supergpt-api.toml": serialize_config(independent),
    }
    project_path = Path(__file__).resolve().parent
    skill_source = project_path / "skills/supergpt-imagegen"
    skill_files = ("SKILL.md", "agents/openai.yaml", "scripts/generate.sh", "scripts/generate.py")
    skill_contents = {name: (skill_source / name).read_text(encoding="utf-8") for name in skill_files}
    private_write(catalog_path, json.dumps({"models": models}, ensure_ascii=False, indent=2) + "\n")
    private_write(key_path, key + "\n")
    for name, content in skill_contents.items():
        destination = skill_path / name
        private_write(destination, content)
        if name.endswith(".sh"):
            destination.chmod(0o700)
    for name, content in templates.items():
        private_write(codex_home / name, content)

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
    print("已生成三种模式、生图技能和桌面入口。当前 config.toml 未切换；请退出桌面应用后使用切换器。")
    print("配置、密钥及备份保存在本机，请勿上传。模型目录不代表中转账号实际拥有这些模型的权限。")


if __name__ == "__main__":
    main()

