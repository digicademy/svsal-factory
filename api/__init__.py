from flask import Flask
from config import config
from flask_restplus import Api

api = Api()


# app factory
def create_api_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    api.init_app(app)

    # APIs

    # generic/utils
    from api.tasks import tasks_bp as tasks_blueprint
    app.register_blueprint(tasks_blueprint, url_prefix='/tasks')

    # specific versions
    from api.v1 import blueprint as api_v1_blueprint
    app.register_blueprint(api_v1_blueprint, url_prefix='/v1')
    # from api.vX import blueprint as api_vX_blueprint
    # app.register_blueprint(api_vX_blueprint, url_prefix='/vX')

    return app
