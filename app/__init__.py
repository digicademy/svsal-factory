from flask import Flask, render_template
from config import config


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # -------------------------------------

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.errorhandler(404)
    def error(self):
        msg = 'Page not found'
        return render_template('error.html', status_code=404, msg=msg), 404

    # -------------------------------------

    from .api.v1 import api_v1 as api_v1_blueprint
    app.register_blueprint(api_v1_blueprint, url_prefix='/api/v1')


    return app