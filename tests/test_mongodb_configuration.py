import pytest
from creditrisk import cloud_storage


def test_snapshots_are_compressed_and_legacy_json_remains_readable(monkeypatch):
    import json
    import mongomock
    from uuid import uuid4
    db = mongomock.MongoClient().test
    files = {}
    class Bucket:
        def __init__(self, _):
            pass
        def upload_from_stream(self, _, stream):
            key = uuid4().hex
            files[key] = stream.read()
            return key
        def download_to_stream(self, key, stream):
            stream.write(files[key])
        def delete(self, key):
            del files[key]
    monkeypatch.setattr('gridfs.GridFSBucket', Bucket)
    monkeypatch.setattr(cloud_storage, 'database', lambda: db)
    state = {'datasets': [{'notes': 'x' * 100000}], 'runs': []}
    cloud_storage.write_snapshot('owner', state, 0)
    doc = db.workspaces.find_one({'_id': 'owner'})
    assert doc['encoding'] == 'gzip'
    assert len(files[doc['snapshot']]) < 1000
    assert cloud_storage.read_snapshot('owner')['state'] == state
    files['old'] = json.dumps(state).encode()
    db.workspaces.insert_one({'_id': 'legacy', 'snapshot': 'old', 'revision': 1})
    assert cloud_storage.read_snapshot('legacy')['state'] == state


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
