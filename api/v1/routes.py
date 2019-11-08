from flask_restplus import Resource
from flask import request
from api.v1 import api_v1
from api.tasks import async_api
from api.v1.works import factory as work_factory
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
        start = time.time()
        print("Starting transformation, time: '%s'" % start)
        time.sleep(20)
        end = time.time()
        print("Ending transformation, time: '%s'" % end)
        return {'answer': 'processed'}


@api_v1.route('/texts/<string:wid>')
class WorkFactoryEvent(Resource):
    @async_api
    def post(self, wid, path=''):
        start = time.time()
        print("Starting transformation, time: '%s'" % start)
        request_data = request.data # TODO process request data (once they are available in a more extensive format)
        work_factory.transform(wid, request_data)
        end = time.time()
        print("Ending transformation, time: '%s'" % end)
        print('Elapsed time: ', end - start)
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