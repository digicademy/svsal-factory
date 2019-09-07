from flask_restplus import Resource
from api.v1 import api_v1
from api.tasks import async_api
import time


# ++++ V1 ROUTES ++++


@api_v1.route('/')
class HelloWorld(Resource):
    def get(self):
        return {'status': 'test_ok'}


@api_v1.route('/testasync')
class LongRunningTask(Resource):
    @async_api
    def get(self, path=''):
        # perform some intensive processing
        print("starting processing task, path: '%s'" % path)
        time.sleep(20)
        print("completed processing task, path: '%s'" % path)
        return {'answer': 'processed'}


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