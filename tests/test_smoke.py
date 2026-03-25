"""Smoke test — vérifie que le module src est importable."""


def test_import_src():
    import src  # noqa: F401


def test_main_runs():
    from src.main import main
    main()
