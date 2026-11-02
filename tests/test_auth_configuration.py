from creditrisk.web import create_app


def test_local_env_loaded_without_overriding_platform(monkeypatch, tmp_path):
    import creditrisk.web as web
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    monkeypatch.setenv('AUTH_ENABLED', '0')
    (tmp_path / '.env').write_text('SESSION_SECRET=' + 'a' * 40 + '\nAUTH_ENABLED=1\n')
    monkeypatch.setattr(web, 'ROOT', tmp_path)
    app = create_app({'TESTING': True})
    assert app.secret_key == 'a' * 40
    assert not app.test_client().get('/api/auth/session').json['enabled']


def test_production_requires_auth_unless_explicit_demo(monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.delenv('AUTH_ENABLED', raising=False)
    client = create_app({'TESTING': True}).test_client()
    assert client.get('/').location.endswith('/login')
    assert client.get('/api/models').status_code == 401


def test_best_model_filename_and_versioned_fallback(monkeypatch, tmp_path):
    import creditrisk.web as web
    monkeypatch.setattr(web, 'ROOT', tmp_path)
    paths = []
    monkeypatch.setattr(web, 'load_models', lambda path: (paths.append(path.name) or {'RF': object()}, []))
    web.model_registry.cache_clear()
    try:
        web.model_registry()
        assert paths == ['best_model_v1.pkl']
        (tmp_path / 'models').mkdir()
        (tmp_path / 'models/best_model.pkl').touch()
        web.model_registry.cache_clear()
        web.model_registry()
        assert paths[-1] == 'best_model.pkl'
    finally:
        web.model_registry.cache_clear()



