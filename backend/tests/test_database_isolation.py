from app.database.connection import engine


def test_tests_run_against_the_isolated_test_database():
    """
    Guards the guard: if this ever fails, every other test in the suite
    has been writing to the wrong database.
    """

    assert engine.url.database == "armando_furniture_test"
    assert engine.url.port == 5433
