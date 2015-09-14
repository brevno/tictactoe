from flask import Flask, url_for, redirect, render_template, session, flash
from flask_wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room, disconnect

from uuid import uuid4


class ServerSessionStorage(object):
    session_storage = {}

    def __new__(cls, sid=None):
        if sid is None:
            sid = session.get('sid')
        if sid in cls.session_storage:
            return cls.session_storage[sid]
        else:
            new_session = super(ServerSessionStorage, cls).__new__(cls, sid)
            new_session.__initialized = False
            cls.session_storage[sid] = new_session
            return new_session

    def __init__(self, sid=None):
        if not self.__initialized:
            self.__initialized = True
            self.sid = sid or session.get('sid')
            self.dict = {}

    def __setitem__(self, key, value):
        self.dict[key] = value

    def __getitem__(self, item):
        return self.dict.get(item)


class Player:
    def __init__(self, username):
        self.username = username
        self.uid = str(uuid4())

    def register_online(self):
        online_players[self.uid] = self

    @staticmethod
    def get_by_uid(uid):
        return online_players.get(uid)


class Game:
    def __init__(self, player_a, player_b):
        self.player_a = player_a
        self.player_b = player_b
        self.uid = str(uuid4())
        self.field = ['---', '---', '---']

    def register_online(self):
        online_games[self.uid] = self

    @staticmethod
    def get_by_uid(uid):
        return online_games.get(uid)

    @staticmethod
    def start_game(player_a, player_b):
        game = Game(player_a, player_b)
        game.register_online()

        # assign this game to all players in lobby
        ns_name, room = '/tictactoe', 'lobby'
        for client in socketio.rooms.get(ns_name, {}).get(room, set()):
            sid = client.session.get('sid')
            ServerSessionStorage(sid)['game'] = game

        socketio.emit('game started', namespace='/tictactoe', room='lobby')
        socketio.close_room('lobby')


online_players = {}     # {uid: Player}
online_games = {}       # {uid: Game}
waiting_player = None

flask_app = Flask(__name__)
flask_app.debug = True
flask_app.config['SECRET_KEY'] = 'DHD3ru029fj#@%wdHOIUJvg'
socketio = SocketIO(flask_app)


###############################
# FORMS

class LoginForm(Form):
    name = StringField('name', validators=[DataRequired()])


###############################
# VIEWS

@flask_app.before_request
def make_session_permanent():
    session.permanent = True


@flask_app.route('/')
def index():
    return redirect(url_for('login'))


@flask_app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if not session.get('sid'):
            session['sid'] = str(uuid4())
        player = ServerSessionStorage()['player']
        if not player or player.username != form.name.data:
            player = Player(form.name.data)
            player.register_online()     # TODO: delete from online players on disconnect
            ServerSessionStorage()['player'] = player
        return redirect(url_for('wait'))

    return render_template('login.html', form=form)


@flask_app.route('/wait')
def wait():

    global waiting_player

    sid = session.get('sid')
    if not sid:
        return redirect(url_for('login'))

    player = ServerSessionStorage()['player']
    if waiting_player is None:
        # this player logged first; wait for opponent
        waiting_player = player
        return render_template('wait.html', username=player.username)
    elif player.uid == waiting_player.uid:
        # ordinary page refresh
        return render_template('wait.html', username=player.username)
    elif waiting_player.username == player.username:
        # username collision; please relog
        flash('User with name %s is already waiting for opponent.' % waiting_player.username)
        # TODO: enable flashes in templates
        return redirect(url_for('login'))
    else:
        Game.start_game(player, waiting_player)
        waiting_player = None
        return redirect(url_for('game_view'))


@flask_app.route('/game')
def game_view():
    if not ServerSessionStorage()['game']:
        return redirect(url_for('login'))

    return render_template('game.html', game=ServerSessionStorage()['game'])


###############################
# WEBSOCKET EVENTS

@socketio.on('connect', namespace='/tictactoe/wait')
def test_connect():
    print 'connect'
    join_room('lobby')


@socketio.on('disconnect', namespace='/tictactoe')
def test_disconnect():
    print 'disconnect'


@socketio.on('game started', namespace='/tictactoe')
def game_started():
    print 'game started'


if __name__ == '__main__':
    socketio.run(flask_app)
