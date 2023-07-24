import json
import os
from flask import Flask, url_for, render_template
from os.path import isfile
from os import listdir, urandom
from werkzeug.middleware.proxy_fix import ProxyFix
from argparse import ArgumentParser

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

def parseConfigs(configPath):
    with open(configPath,'r') as confFile:
        configs = json.load(confFile)
        confFile.close()

    mode = configs['mode']

    if mode not in ['Const','SPage','MPage','Dynamic']:
        confs = None
        print('Unsupported Mode')
    else:
        confs = [mode]
        if mode == 'Const':
            confs.append(configs['size'])
        elif mode == 'SPage':
            confs.append(configs['page_name'])
        confs.append(configs["adjustable"])
        
    return confs

current_dir = os.path.dirname(os.path.abspath(__file__))
configs = parseConfigs(current_dir+'/config.json')

# Note: the route decorator only answers to GET requests

# Default behaviour for const and spage
@app.route('/')
def send():
    mode = configs[0]
    if mode == 'Const':
        size = configs[1]
        return sendXBytes(size)
    elif mode in ('SPage'):
        pageName = configs[1]
        if isfile('templates/'+pageName):
            return render_template(pageName)
        else:
            return ('Page not found',404)
    else:
        return ('Current mode does not support that operation',400)

# Response "on demand" (for mpage and dynamic) - given an Int
# MPage   - return page by index
# Dynamic - respond with x random bytes
@app.route('/<int:i>')
def sendInt(i):
    mode = configs[0]
    if mode == 'MPage':
        return sendPageByIndex(i-1)
    elif mode == 'Dynamic':
        return sendXBytes(i)
    else:
        return ('Current mode does not support that operation',400)

# Response "on demand" (for mpage and dynamic) - given a string
# MPage   - return page by name
# Dynamic - return page by name
@app.route('/<string:name>')
def sendPageByName(name):
    mode = configs[0]
    if mode in ('MPage','Dynamic'):
        if isfile('templates/'+name):
            return render_template(name)
        else:
            return ('Page not found',404)
    else:
        return ('Current mode does not support that operation',400)

def sendPageByIndex(index):
    dir = sorted(listdir('templates'))
    print(dir)
    if index < len(dir) and isfile('templates/'+dir[index]):
        return render_template(dir[index])
    else:
        return ('Page not found',404)

def sendXBytes(x):
    if x > 33:
        return urandom(x-33)
    else:
        return ('',200)

# Does not respond
@app.route('/ignore')
def ignore():
    return ('',200)

# Change default size for const
@app.route('/set/<int:size>')
def setSize(size):
    if configs[0] == 'Const':
        if configs[2]:
            configs[1] = size
            return send()
        return ('Not adjustable',400)
    else:
        return ('Bad input for mode',400)

# Change default page for spage
@app.route('/set/<string:name>')
def setPageName(name): 
    if configs[0] == 'SPage':
        if configs[2]:
            if isfile('templates/'+name):
                configs[1] = name
                return send()
            else:
                return ('Page not found',404)
        return ('Not adjustable',400)
    else:
        return ('Bad input for mode',400)

# Use to check correct url formats (outdated route examples)
# 
# with app.test_request_context():
#     print(url_for('chaff'))
#     print(url_for('default'))
#     print(url_for('set_default', size=1024))
#     print(url_for('specific',size=2048))
#     print(url_for('same'))

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=8000, type=int, help='port to listen on')
    args = parser.parse_args()
    app.run(host='127.0.0.1', port=args.port)