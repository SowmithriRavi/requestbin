import json
import os

from flask import Response
from flask import session, make_response, request

from requestbin import app, db
from flask import safe_join

base_dir = os.path.dirname(__file__)
# This is the path to the upload directory
app.config['UPLOAD_FOLDER'] = safe_join(base_dir,'resources')

# These are the extension that we are accepting to be uploaded
app.config['ALLOWED_EXTENSIONS'] = set(['xml'])

# For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

def _response(object, code=200):
    jsonp = request.args.get('jsonp')
    if jsonp:
        resp = make_response('%s(%s)' % (jsonp, json.dumps(object)), 200)
        resp.headers['Content-Type'] = 'text/javascript'
    else:
        resp = make_response(json.dumps(object), code)
        resp.headers['Content-Type'] = 'application/json'
        resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.endpoint('api.bins')
def bins():
    private = request.form.get('private') == 'true'
    bin = db.create_bin(private)
    if bin.private:
        session[bin.name] = bin.secret_key
    return _response(bin.to_dict())


@app.endpoint('api.bin')
def bin(name):
    try:
        bin = db.lookup_bin(name)
    except KeyError:
        return _response({'error': "Bin not found"}, 404)

    return _response(bin.to_dict())


@app.endpoint('api.requests')
def requests(bin):
    try:
        bin = db.lookup_bin(bin)
    except KeyError:
        return _response({'error': "Bin not found"}, 404)
    inspect_query = request.args.get('inspect')
    if inspect_query == 'headers':
        return _response([r.headers for r in bin.requests])
    elif inspect_query == 'form':
        return _response([dict(r.form_data) for r in bin.requests])
    elif inspect_query == 'query':
        return _response([r.query_string for r in bin.requests])
    elif inspect_query in ('raw', 'body'):
        return _response([r.raw for r in bin.requests])
    else:
        return _response([r.to_dict() for r in bin.requests])


@app.endpoint('api.request')
def request_(bin, name):
    try:
        bin = db.lookup_bin(bin)
    except KeyError:
        return _response({'error': "Bin not found"}, 404)

    for req in bin.requests:
        if req.id == name:
            return _response(req.to_dict())

    return _response({'error': "Request not found"}, 404)


@app.endpoint('api.stats')
def stats():
    stats = {
        'bin_count': db.count_bins(),
        'request_count': db.count_requests(),
        'avg_req_size_kb': db.avg_req_size(),}
    resp = make_response(json.dumps(stats), 200)
    resp.headers['Content-Type'] = 'application/json'
    return resp

@app.endpoint('api.xml')
def requests(name):
    import os
    file_name = name
    FILE = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
    f = open(FILE, 'r')
    try:
        bin = db.lookup_bin(name=name)
    except KeyError:
        print' key already there'
        bin = db.create_bin(name=name)
    db.create_request(bin, request)
    return Response(f.read(), content_type='application/xml')


@app.endpoint('api.upload.file')
def upload_file(name):
    if not allowed_file(name):
        return _response({'error': 'Uploads can be done on specific set of extensions only - {}'.format(app.config['ALLOWED_EXTENSIONS'])}, 400)

    output_file_name = os.path.join(app.config['UPLOAD_FOLDER'], name)
    replace = request.args.get('replace')
    if replace != 'true' and os.path.isfile(output_file_name):
        return _response({'error': 'The resource {} already exists'.format(output_file_name)}, 400)
    if 'file' in request.files:
        form_file = request.files['file']
        if not form_file.filename == '':
            form_file.save(output_file_name)
            return _response({'Success':'File {} uploaded to request bin'.format(output_file_name)})

    if not request.data == '':
        import xml.etree.ElementTree as ET
        from xml.etree.ElementTree import ParseError
        try:
            tree = ET.XML(request.data)
        except ParseError:
            return _response({'error': 'Request content type has to be xml'}, 400)
        f = None
        try:
            f = open(output_file_name, 'w+')
            f.write(ET.tostring(tree))
        except IOError:
            f.close()
            return _response({'error': 'Error occurred while writing to file {}'.format(output_file_name)}, 500)

        return _response({'Success': 'File {} uploaded to request bin'.format(output_file_name)})

    return _response({'error': 'No data to upload'}, 400)
