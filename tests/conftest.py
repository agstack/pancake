"""
Test Configuration and Fixtures
"""
import pytest

try:
    from app import create_app, db
    from app.models import Packet, ChatThread, ChatParticipant
except ModuleNotFoundError:
    pytest.skip(
        "No `app` package found – skipping app-dependent tests for this POC.",
        allow_module_level=True,
    )


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    app = create_app('testing')
    return app


@pytest.fixture(scope='function')
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Create database session for tests"""
    with app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_packet_data():
    """Sample packet data for testing"""
    return {
        'Header': {
            'id': '01HQTEST123456789ABC',
            'geoid': 'test-geoid-123',
            'timestamp': '2024-01-01T12:00:00Z',
            'type': 'note'
        },
        'Body': {
            'message': 'Test observation'
        },
        'Footer': {
            'hash': 'placeholder',  # Will be computed
            'enc': 'none'
        }
    }

