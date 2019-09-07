from flask import Blueprint
from flask_restplus import Api

blueprint = Blueprint('v1', __name__)
api_v1 = Api(blueprint)

from api.v1 import routes
