from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from cogs.ai import AI, MAX_CONVERSATION_TURNS, MAX_PROMPT_CHARS, to_markdown


class FakeResponse:
    def __init__(self, status, json_data=None):
        self.status = status
        self._json = json_data or {}

    async def json(self):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def bot():
    return MagicMock(spec=commands.Bot)


@pytest.fixture
def cog(bot):
    config = {
        "secrets": {"openaiKey": "test_key", "openaiUrl": "http://example.com/api"},
    }
    ai_cog = AI(bot, config)
    # newchat() invokes `self.chat(...)` directly (not `.callback(...)`), which
    # only works once discord.py's Cog.__new__/add_cog machinery binds the
    # command's `.cog` back-reference - mimic that binding here.
    ai_cog.chat.cog = ai_cog
    return ai_cog


def test_init_does_not_raise_when_openai_secrets_are_not_configured(bot):
    # Regression test: this used to be `config["secrets"]["openaiKey"/"openaiUrl"]`,
    # a direct index that raised KeyError (and failed the whole cog's load) on a
    # deployment without those optional keys, unlike every sibling API-key cog
    # (weather/football/formula1/ufc/steam/spotify/genius), which all use .get(...).
    ai_cog = AI(bot, {"secrets": {}})
    assert ai_cog.api_key is None
    assert ai_cog.api_url is None


def mock_ctx(guild=True):
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    if guild:
        ctx.guild = MagicMock(spec=discord.Guild)
        ctx.guild.id = 111
    else:
        ctx.guild = None
    ctx.channel = MagicMock()
    ctx.channel.id = 222
    ctx.author = MagicMock()
    ctx.author.id = 333
    return ctx


def test_to_markdown_indents_and_replaces_bullets():
    result = to_markdown("hello\n• item")
    assert result == "> hello\n>   * item"


def test_conversation_key_scopes_by_guild_and_author(cog):
    ctx = mock_ctx(guild=True)
    assert cog._conversation_key(ctx) == (111, 333)


def test_conversation_key_falls_back_to_channel_in_dm(cog):
    ctx = mock_ctx(guild=False)
    assert cog._conversation_key(ctx) == (222, 333)


def test_conversation_key_does_not_leak_across_guilds(cog):
    ctx_a = mock_ctx(guild=True)
    ctx_b = mock_ctx(guild=True)
    ctx_b.guild.id = 999
    assert cog._conversation_key(ctx_a) != cog._conversation_key(ctx_b)


def test_get_conversation_starts_with_system_prompt(cog):
    ctx = mock_ctx()
    conversation = cog.get_conversation(ctx)
    assert conversation == [{"role": "system", "content": cog.initial_prompt}]
    # Same key returns the same list object, not a fresh one.
    assert cog.get_conversation(ctx) is conversation


def test_clear_conversation_removes_entry(cog):
    ctx = mock_ctx()
    cog.get_conversation(ctx)
    key = cog._conversation_key(ctx)
    assert key in cog.conversations
    cog.clear_conversation(ctx)
    assert key not in cog.conversations


def test_clear_conversation_is_noop_when_absent(cog):
    ctx = mock_ctx()
    cog.clear_conversation(ctx)  # must not raise


def test_trim_keeps_short_conversation_untouched(cog):
    conversation = [{"role": "system", "content": "s"}] + [
        {"role": "user", "content": str(i)} for i in range(5)
    ]
    assert cog._trim(list(conversation)) == conversation


def test_trim_drops_oldest_turns_but_keeps_system_message(cog):
    system = {"role": "system", "content": "s"}
    turns = [{"role": "user", "content": str(i)} for i in range(MAX_CONVERSATION_TURNS + 10)]
    conversation = [system] + turns
    trimmed = cog._trim(conversation)
    assert trimmed[0] == system
    assert len(trimmed) == MAX_CONVERSATION_TURNS + 1
    assert trimmed[1:] == turns[-MAX_CONVERSATION_TURNS:]


@pytest.mark.asyncio
async def test_call_api_returns_content_on_success(cog):
    fake_session = MagicMock()
    fake_session.post = MagicMock(
        return_value=FakeResponse(
            200, {"choices": [{"message": {"content": "hi there"}}]}
        )
    )
    with patch("cogs.ai.get_session", return_value=fake_session):
        result = await cog._call_api([{"role": "user", "content": "hey"}])
    assert result == "hi there"


@pytest.mark.asyncio
async def test_call_api_raises_on_non_200(cog):
    fake_session = MagicMock()
    fake_session.post = MagicMock(return_value=FakeResponse(500))
    with patch("cogs.ai.get_session", return_value=fake_session):
        with pytest.raises(RuntimeError, match="status 500"):
            await cog._call_api([{"role": "user", "content": "hey"}])


@pytest.mark.asyncio
async def test_call_api_raises_on_empty_content(cog):
    # Some OpenAI-compatible endpoints return content: null on a filtered response.
    fake_session = MagicMock()
    fake_session.post = MagicMock(
        return_value=FakeResponse(200, {"choices": [{"message": {"content": None}}]})
    )
    with patch("cogs.ai.get_session", return_value=fake_session):
        with pytest.raises(RuntimeError, match="empty content"):
            await cog._call_api([{"role": "user", "content": "hey"}])


@pytest.mark.asyncio
async def test_ask_too_long_rejected_without_calling_api(cog):
    ctx = mock_ctx()
    with patch.object(cog, "_call_api", new=AsyncMock()) as call_api:
        await cog.ask.callback(cog, ctx, question="x" * (MAX_PROMPT_CHARS + 1))
    call_api.assert_not_awaited()
    ctx.send.assert_awaited_once_with("That question is too long. Please shorten it.")
    ctx.message.add_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_success_sends_response_and_reactions(cog):
    ctx = mock_ctx()
    with patch.object(cog, "_call_api", new=AsyncMock(return_value="the answer")):
        await cog.ask.callback(cog, ctx, question="what's up")
    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once_with("> the answer")


@pytest.mark.asyncio
async def test_ask_send_failure_sets_error_reaction(cog):
    # Regression test: a successful API call followed by a failed ctx.send
    # (e.g. rate limit) must still clear the stuck PROCESSING reaction.
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=Exception("rate limited"))
    with patch.object(cog, "_call_api", new=AsyncMock(return_value="the answer")):
        await cog.ask.callback(cog, ctx, question="what's up")
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_ask_send_failure_swallows_reaction_cleanup_error(cog):
    # Regression test: a doubly-failing cleanup (send fails, then clearing the
    # reaction also fails) must not raise out of the command.
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=Exception("rate limited"))
    ctx.message.clear_reactions = AsyncMock(side_effect=Exception("message gone"))
    with patch.object(cog, "_call_api", new=AsyncMock(return_value="the answer")):
        await cog.ask.callback(cog, ctx, question="what's up")


@pytest.mark.asyncio
async def test_ask_api_error_sets_error_reaction(cog):
    ctx = mock_ctx()
    with patch.object(cog, "_call_api", new=AsyncMock(side_effect=Exception("boom"))):
        await cog.ask.callback(cog, ctx, question="what's up")
    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_once_with("There was an error connecting to the AI service.")


@pytest.mark.asyncio
async def test_chat_too_long_rejected(cog):
    ctx = mock_ctx()
    with patch.object(cog, "_call_api", new=AsyncMock()) as call_api:
        await cog.chat.callback(cog, ctx, prompt="x" * (MAX_PROMPT_CHARS + 1))
    call_api.assert_not_awaited()
    ctx.send.assert_awaited_once_with("That message is too long. Please shorten it.")


@pytest.mark.asyncio
async def test_chat_success_persists_conversation(cog):
    ctx = mock_ctx()
    with patch.object(cog, "_call_api", new=AsyncMock(return_value="reply text")):
        await cog.chat.callback(cog, ctx, prompt="hello")

    conversation = cog.get_conversation(ctx)
    roles = [m["role"] for m in conversation]
    assert roles == ["system", "user", "assistant"]
    assert conversation[-1]["content"] == "reply text"
    ctx.send.assert_awaited_once_with("> reply text")
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_chat_send_failure_sets_error_reaction(cog):
    # Regression test: same gap as ask() - a failed ctx.send after a
    # successful API call must not leave the PROCESSING reaction stuck.
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=Exception("rate limited"))
    with patch.object(cog, "_call_api", new=AsyncMock(return_value="reply text")):
        await cog.chat.callback(cog, ctx, prompt="hello")
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_chat_send_failure_swallows_reaction_cleanup_error(cog):
    # Regression test: same doubly-failing cleanup as ask() must not raise.
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=Exception("rate limited"))
    ctx.message.clear_reactions = AsyncMock(side_effect=Exception("message gone"))
    with patch.object(cog, "_call_api", new=AsyncMock(return_value="reply text")):
        await cog.chat.callback(cog, ctx, prompt="hello")


@pytest.mark.asyncio
async def test_chat_error_does_not_store_assistant_turn(cog):
    ctx = mock_ctx()
    with patch.object(cog, "_call_api", new=AsyncMock(side_effect=Exception("down"))):
        await cog.chat.callback(cog, ctx, prompt="hello")

    conversation = cog.get_conversation(ctx)
    roles = [m["role"] for m in conversation]
    # The failed call's user turn stays (so a retry has context) but no
    # assistant turn is appended for the failure.
    assert roles == ["system", "user"]
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_newchat_without_prompt_clears_and_acks(cog):
    ctx = mock_ctx()
    cog.get_conversation(ctx)
    key = cog._conversation_key(ctx)

    await cog.newchat.callback(cog, ctx)

    assert key not in cog.conversations
    ctx.send.assert_awaited_once()
    assert "cleared" in ctx.send.call_args[0][0].lower()
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_newchat_with_prompt_clears_then_starts_new_chat(cog):
    ctx = mock_ctx()
    cog.get_conversation(ctx)

    with patch.object(cog, "_call_api", new=AsyncMock(return_value="fresh reply")):
        await cog.newchat.callback(cog, ctx, prompt="hi again")

    conversation = cog.get_conversation(ctx)
    # Only the new turn survives - the old conversation was cleared first.
    assert [m["role"] for m in conversation] == ["system", "user", "assistant"]
    assert conversation[1]["content"] == "hi again"
    ctx.send.assert_any_await("> fresh reply")


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    with patch(
        "cogs.ai.load_config",
        return_value={
            "secrets": {"openaiKey": "k", "openaiUrl": "http://example.com"}
        },
    ):
        from cogs import ai

        await ai.setup(bot)
    bot.add_cog.assert_awaited_once()
