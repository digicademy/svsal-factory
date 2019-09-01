from flask import Blueprint
from flask import jsonify

api_v1 = Blueprint('api_v1', __name__)


@api_v1.route('/')
def index():
    response = jsonify({'status': 'ok'})
    return response # list of available endpoints


@api_v1.errorhandler(404)
def page_not_found(e):
    response = jsonify({'error': 'not found'})
    response.status_code = 404
    return response