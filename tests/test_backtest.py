def test_backtest_imports():
    import python_client.backtest as b
    assert hasattr(b, 'Backtest')
