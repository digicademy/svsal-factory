from flask import Blueprint
from flask_restplus import Api

#api_v1 = Blueprint('v1', __name__, url_prefix='/v1')
blueprint = Blueprint('v1', __name__)
api_v1 = Api(blueprint)

from api.v1 import routes