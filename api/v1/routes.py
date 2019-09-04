from flask_restplus import Resource, fields
from flask import jsonify
from api.v1 import api_v1

# routing here


@api_v1.route('/')
class HelloWorld(Resource):
    def get(self):
        return {'hello': 'world'}

'''
@api_v1.errorhandler(404)
def page_not_found(e):
    response = jsonify({'v1_error': 'not found'})
    response.status_code = 404
    return response
'''
'''
@api_v1.errorhandler
def default_error_handler(error):
    return {'message': str(error)}, getattr(error, 'code', 500)
'''