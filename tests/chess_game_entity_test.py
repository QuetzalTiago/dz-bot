from cogs.db.entities.chess_game import ChessGame


def base_game_data(**overrides):
    data = {
        "id": "abc123",
        "rated": True,
        "variant": "standard",
        "speed": "blitz",
        "perf": "blitz",
        "createdAt": 1000,
        "lastMoveAt": 2000,
        "status": "mate",
        "players": {"white": {"user": {"name": "a"}}, "black": {"user": {"name": "b"}}},
        "opening": {"eco": "B01", "name": "Scandinavian Defense"},
        "moves": "e4 d5",
        "clock": {"initial": 300, "increment": 0},
        "winner": "white",
    }
    data.update(overrides)
    return data


def test_chess_game_stores_opening_when_present():
    game = ChessGame(base_game_data())
    assert game.opening == {"eco": "B01", "name": "Scandinavian Defense"}
    assert game.id == "abc123"
    assert game.winner == "white"


def test_chess_game_aborted_without_opening_does_not_raise():
    # Regression: Lichess omits "opening" entirely for games ended via
    # "aborted"/"noStart" (no moves played), which previously raised
    # KeyError and silently dropped the game from the database.
    data = base_game_data(status="aborted", moves=None, winner=None)
    del data["opening"]

    game = ChessGame(data)

    assert game.opening is None
    assert game.status == "aborted"


def test_chess_game_optional_fields_default_to_none_when_missing():
    data = base_game_data()
    del data["moves"]
    del data["clock"]
    del data["winner"]

    game = ChessGame(data)

    assert game.moves is None
    assert game.clock is None
    assert game.winner is None
