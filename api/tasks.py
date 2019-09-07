from functools import wraps
import threading
import time
import uuid
from datetime import datetime
from flask_restplus import Resource
from flask_restplus import Api

from flask import Blueprint, abort, jsonify, current_app, request#, url_for
from werkzeug.exceptions import HTTPException, InternalServerError

from api.utils import timestamp, url_for


# ++++ BLUEPRINT ++++

tasks_bp = Blueprint('tasks', __name__)
tasks_api = Api(tasks_bp)

tasks = {}


@tasks_bp.before_app_first_request
def before_first_request():
    """Start a background thread that cleans up old tasks."""
    def clean_old_tasks():
        """ Cleans up old tasks from our in-memory data structure. """
        global tasks
        while True:
            # Only keep tasks that are running or that finished less than 5 minutes ago.
            five_min_ago = timestamp() - 5 * 60
            tasks = {id: task for id, task in tasks.items()
                     if 't' not in task or task['t'] > five_min_ago}
            time.sleep(60)

    # if not current_app.config['TESTING']:
    #    thread = threading.Thread(target=clean_old_tasks)
    #    thread.start()
    thread = threading.Thread(target=clean_old_tasks)
    thread.start()


# ++++ DECORATORS ++++

def async_api(wrapped_function):
    @wraps(wrapped_function)
    def wrapped(*args, **kwargs):
        def task_call(flask_app, environ):
            # Create a request context similar to that of the original request
            # so that the task can have access to flask.g, flask.request, etc.
            with flask_app.request_context(environ):
                try:
                    tasks[task_id]['return_value'] = wrapped_function(*args, **kwargs)
                except HTTPException as e:
                    tasks[task_id]['return_value'] = current_app.handle_http_exception(e)
                except Exception as e:
                    # The function raised an exception, so we set a 500 error
                    tasks[task_id]['return_value'] = InternalServerError()
                    if current_app.debug:
                        # We want to find out if something happened so reraise
                        raise
                finally:
                    # We record the time of the response, to help in garbage collecting old tasks
                    tasks[task_id]['completion_timestamp'] = datetime.timestamp(datetime.utcnow())

        # Assign an id to the asynchronous task
        task_id = uuid.uuid4().hex

        # Record the task, and then launch it
        tasks[task_id] = {'task_thread': threading.Thread(
            target=task_call, args=(current_app._get_current_object(),
                               request.environ))}
        tasks[task_id]['task_thread'].start()

        # Return a 202 response, with a link that the client can use to obtain task status
        print(url_for('tasks.GetTaskStatus', task_id=task_id))
        return 'accepted', 202, {'Location': url_for('tasks.GetTaskStatus', task_id=task_id)}
        #print(url_for('tasks.get_status', task_id=task_id))
        #return 'accepted', 202, {'Location': url_for('tasks.get_status', task_id=task_id)}
    return wrapped


# ++++ ROUTES ++++

# task locations are generic (/tasks/{task_id}), not bound to specific api versions
"""
    Return status about an asynchronous task. If this request returns a 202
    status code, it means that task hasn't finished yet. Else, the response
    from the task is returned.
    """
@tasks_bp.route('/<task_id>') # async_api
@tasks_api.route('/<task_id>') # restplus
class GetTaskStatus(Resource):
    def get(self, task_id):
        task = tasks.get(task_id)
        if task is None:
            abort(404)
        if 'return_value' not in task:
            print(str(threading.active_count()))
            return 'still_processing', 202, {'Location': url_for('tasks.GetTaskStatus', task_id=task_id)}
        return task['return_value']


"""
@tasks_bp.route('/<task_id>', methods=['GET'])
def get_status(task_id):

    task = tasks.get(task_id)
    if task is None:
        abort(404)
    if 'return_value' not in task:
        return jsonify('still_processing'), 202, {'Location': url_for('tasks.get_status', task_id=task_id)}
    return task['return_value']
"""

# see
# https://github.com/miguelgrinberg/flack/commit/0c372464b341a2df60ef8d93bdca2001009a42b5
# https://stackoverflow.com/questions/31866796/making-an-asynchronous-task-in-flask
