import pytest
from creditrisk import cloud_storage


def test_separate_credentials_are_passed_without_uri_encoding(monkeypatch):
    monkeypatch.setenv('MONGODB_URI', 'mongodb://localhost:27017/?retryWrites=true')
    monkeypatch.setenv('MONGODB_USERNAME', 'database-user')
    monkeypatch.setenv('MONGODB_PASSWORD', 'p@ss:/word%')
    seen = {}
    def client(uri, **kwargs):
        seen.update(kwargs)
        return {'creditrisk_ai': 'database'}
    monkeypatch.setattr('pymongo.MongoClient', client)
    cloud_storage.database.cache_clear()
    try:
        assert cloud_storage.database() == 'database'
        assert seen['username'] == 'database-user'
        assert seen['password'] == 'p@ss:/word%'
        assert seen['authSource'] == 'admin'
    finally:
        cloud_storage.database.cache_clear()


@pytest.mark.parametrize('uri', ['mongodb://<username>:<password>@localhost', 'not-a-uri', 'mongodb://localhost\n'])
def test_bad_uri_is_rejected_without_echoing_secret(monkeypatch, uri):
    monkeypatch.setenv('MONGODB_URI', uri)
    cloud_storage.database.cache_clear()
    try:
        with pytest.raises(Exception) as error:
            cloud_storage.database()
        assert 'MONGODB_URI' in str(error.value)
        assert uri not in str(error.value)
    finally:
        cloud_storage.database.cache_clear()
