import os
#from api.v1 import blueprint as api_v1_blueprint
from api import create_api_app
# for adding new API versions: from api_vX import blueprint as api_vX_blueprint

app = create_api_app(os.getenv('FLASK_CONFIG') or 'default')


@app.shell_context_processor
def make_shell_context():
    pass


@app.cli.command()
def test():
    """Running Unit Tests"""
    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)




