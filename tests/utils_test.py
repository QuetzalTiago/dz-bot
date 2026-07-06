import json

import pytest

from cogs.utils import config as config_mod
from cogs.utils.checks import is_owner_or_admin, require_manage_messages
from cogs.utils.formatting import format_local, split_message, to_local


def test_split_message_short():
    assert split_message("hello") == ["hello"]


def test_split_message_splits_on_limit():
    text = "\n".join("line" for _ in range(1000))
    chunks = split_message(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == text


def test_split_message_hard_split_long_line():
    text = "x" * 250
    chunks = split_message(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == text


def test_to_local_and_format():
    dt = to_local("2023-10-10T15:00:00+00:00", "UTC")
    assert dt.strftime("%H:%M") == "15:00"
    assert format_local("2023-10-10T15:00:00+00:00", "%Y-%m-%d", "UTC") == "2023-10-10"


def test_config_env_override(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"prefix": "!", "secrets": {"discordToken": "file-token"}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()
    monkeypatch.setenv("DZ_SECRET_DISCORD_TOKEN", "env-token")

    loaded = config_mod.load_config()
    assert loaded["secrets"]["discordToken"] == "env-token"
    config_mod.reset_cache()


def test_config_env_override_new_secret_uses_camel_case_key(monkeypatch, tmp_path):
    # Regression test: a secret with no matching entry already in config.json
    # (the documented "no config file, env vars only" deployment) used to be
    # stored under a snake_case key derived from the env var name, but every
    # consumer (e.g. GeniusAPI) reads the camelCase key directly - so the
    # value was silently unreachable and a KeyError was raised at startup.
    cfg = tmp_path / "config.json"
    cfg.write_text('{"secrets": {}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()
    monkeypatch.setenv("DZ_SECRET_GENIUS_API_KEY", "env-genius-key")

    loaded = config_mod.load_config()
    assert loaded["secrets"]["geniusApiKey"] == "env-genius-key"
    assert "genius_api_key" not in loaded["secrets"]
    config_mod.reset_cache()


def test_config_env_override_new_top_level_key_uses_camel_case_key(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"secrets": {}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()
    monkeypatch.setenv("DZ_AI_MODEL", "env-model")

    loaded = config_mod.load_config()
    assert loaded["aiModel"] == "env-model"
    assert "ai_model" not in loaded
    config_mod.reset_cache()


def test_config_env_override_does_not_clobber_list_valued_key(monkeypatch, tmp_path):
    # Regression test: DZ_OWNERS is documented as a *separate* override read
    # directly by bot.py::_load_owner_ids, but the generic DZ_<KEY> loop's
    # camelCase mapping for "owners" collides with the same env var name. If
    # the generic loop clobbers "owners" (a list) with the raw env string,
    # _load_owner_ids' `for raw_id in config.get("owners", [])` iterates over
    # the string's characters instead of parsing an actual list of IDs.
    cfg = tmp_path / "config.json"
    cfg.write_text('{"owners": [111, 222], "secrets": {}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()
    monkeypatch.setenv("DZ_OWNERS", "123,456")

    loaded = config_mod.load_config()

    assert loaded["owners"] == [111, 222]
    config_mod.reset_cache()


def test_load_config_missing_file_returns_empty_config(monkeypatch, tmp_path):
    missing = tmp_path / "does-not-exist.json"
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(missing))
    config_mod.reset_cache()

    loaded = config_mod.load_config()

    assert loaded == {"secrets": {}}
    config_mod.reset_cache()


def test_load_config_invalid_json_raises(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json")
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()

    with pytest.raises(json.JSONDecodeError):
        config_mod.load_config()
    config_mod.reset_cache()


def test_get_secret_reads_from_config_file(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"secrets": {"discordToken": "file-token"}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()

    assert config_mod.get_secret("discordToken") == "file-token"
    config_mod.reset_cache()


def test_get_secret_falls_back_to_env_var(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"secrets": {}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()
    monkeypatch.setenv("DZ_SECRET_GENIUS_API_KEY", "env-genius-key")

    assert config_mod.get_secret("geniusApiKey") == "env-genius-key"
    config_mod.reset_cache()


def test_get_secret_missing_required_raises_keyerror(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"secrets": {}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()

    with pytest.raises(KeyError):
        config_mod.get_secret("someMissingSecret")
    config_mod.reset_cache()


def test_get_secret_missing_optional_returns_none(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"secrets": {}}')
    monkeypatch.setattr(config_mod, "CONFIG_PATH", str(cfg))
    config_mod.reset_cache()

    assert config_mod.get_secret("someMissingSecret", required=False) is None
    config_mod.reset_cache()


def test_checks_return_check_decorators():
    # The helpers should return command checks without raising at definition.
    assert callable(is_owner_or_admin())
    assert callable(require_manage_messages())
