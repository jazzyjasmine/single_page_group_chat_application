import string
import random
import uuid
from collections import deque
from flask import Flask, request, jsonify

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

'''
key: username
value: (password, auth_key)

example:
"jasmine": ("1234jas", "jaoginrsuljsv")
'''
users = {}

chats = {}


@app.route('/')
@app.route('/auth')
@app.route('/create')
@app.route('/chat/<int:chat_id>')
def index(chat_id=None):
    return app.send_static_file('index.html')


# -------------------------------- API ROUTES ----------------------------------
@app.route('/api/homepage', methods=['POST'])
def homepage():
    if request.method == 'POST':
        if not is_valid_account(request.headers['username'], request.headers['auth_key']):
            return jsonify({"verification": "fail"})
        else:
            return jsonify({"verification": "success"})


@app.route('/api/auth', methods=['POST'])
def auth():
    username = request.headers['username']
    password = request.headers['password']
    # log in succeeds
    if username in users and users[username][0] == password:
        return jsonify({"result": "success",
                        "auth_key": users[username][1]})

    # create account henceforth
    # create account fails due to duplicate username
    if username in users:
        return jsonify({"result": "username exists"})

    # create account succeeds
    new_auth_key = uuid.uuid1().hex
    users[username] = (password, new_auth_key)
    return jsonify({"result": "success",
                    "auth_key": new_auth_key})


@app.route('/api/createchat', methods=['GET', 'POST'])
def create_chat():
    username = request.headers['username']
    if request.method == 'GET':
        chat_ids = get_chatrooms_by_username(username)
        if not chat_ids:
            return jsonify({"result": "empty"})
        else:
            chat_ids_str = ",".join(chat_ids)
            return jsonify({"chat_ids": chat_ids_str})

    if request.method == 'POST':
        new_chat_id = len(chats) + 1  # chat_id starts from 1
        chats[new_chat_id] = new_chat(username)
        return jsonify({"chat_id": str(new_chat_id)})


def get_chatrooms_by_username(username):
    chat_ids = []
    for chat_id in chats:
        if username in chats[chat_id]['authorized_users']:
            chat_ids.append(str(chat_id))
    return chat_ids


def new_chat(username):
    magic_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=40))

    return dict([
        ("authorized_users", {username}),
        ("magic_key", magic_key),
        ("messages", [])
    ])


@app.route('/api/chat', methods=['GET', 'POST'])
def handle_request():
    if request.method == 'GET':
        chat_id = int(request.headers["chat_id"])
        if not chats[chat_id]["messages"]:
            return jsonify({"empty": "yes"})
        return jsonify(list(chats[chat_id]["messages"]))

    if request.method == 'POST':
        post_type = request.headers['post_type']
        if post_type == 'authentication':
            possible_chat_id = int(request.headers['chat_id'])
            possible_auth_key = request.headers['auth_key']
            possible_username = request.headers['username']
            possible_magic_key = request.headers['magic_key']
            return authenticate(possible_chat_id, possible_auth_key, possible_username, possible_magic_key)
        if post_type == 'getMagicLink':
            chat_id = int(request.headers['chat_id'])
            magic_key = chats[chat_id]['magic_key']
            magic_link = 'http://127.0.0.1:5000/chat/' + str(chat_id) + '?magic_key=' + magic_key
            return jsonify({"magic_link": magic_link})
        if post_type == 'postMessage':
            message_body = request.headers["message_body"]
            chat_id = int(request.headers['chat_id'])
            auth_key = request.headers['auth_key']
            username = request.headers['username']
            return post_new_message(chat_id, message_body, auth_key, username)


def post_new_message(chat_id, message_body, auth_key, username):
    if not is_valid_account(username, auth_key):
        return jsonify({'result': 'invalid_account'})

    message_dict = {"username": username, "message_body": message_body}
    if not chats[chat_id]["messages"]:
        chats[chat_id]["messages"] = deque([message_dict])
    elif len(chats[chat_id]["messages"]) + 1 <= 30:
        chats[chat_id]["messages"].append(message_dict)
    else:
        chats[chat_id]["message"].popleft()
        chats[chat_id]["message"].append(message_dict)

    return jsonify({'result': 'success'})


def authenticate(possible_chat_id, possible_auth_key, possible_username, possible_magic_key):
    # if chat id not valid, redirect to home page
    if possible_chat_id not in chats:
        return jsonify({"authentication": "fail"})

    has_valid_account = is_valid_account(possible_username, possible_auth_key)

    # chat id is valid henceforth
    if has_valid_account and possible_username in chats[possible_chat_id]["authorized_users"]:
        return jsonify({"authentication": "success"})

    has_valid_magic_key = is_valid_magic_key(possible_magic_key, possible_chat_id)

    if not has_valid_account and has_valid_magic_key:
        return jsonify({"authentication": "pending"})

    if has_valid_account and has_valid_magic_key:
        chats[possible_chat_id]["authorized_users"].add(possible_username)
        return jsonify({"authentication": "success"})

    return jsonify({"authentication": "fail"})


def is_valid_magic_key(possible_magic_key, valid_chat_id):
    return possible_magic_key == chats[valid_chat_id]["magic_key"]


def is_valid_account(username, auth_key):
    return username in users and users[username][1] == auth_key
