from flask import Flask, url_for, redirect, render_template, session, flash
from flask_wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room, disconnect
from flask_triangle import Triangle
from json import dumps as json_dumps
from random import choice as random_choice

from uuid import uuid4
import shelve


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
        self.uid = uuid4()

    def __repr__(self):
        return self.username

    def __hash__(self):
        return int(self.uid)


class Game:
    def __init__(self, player_a, player_b):
        self.player_a = player_a
        self.player_b = player_b
        self.field = ['---', '---', '---']
        self.first_player = self.active_player = random_choice([player_a, player_b])
        self.winner = None
        self.finished = False
        self.room = str(uuid4())

    def __repr__(self):
        return str(self.player_a) + ', ' + str(self.player_b)

    @staticmethod
    def start_game(player_a, player_b):
        game = Game(player_a, player_b)

        # assign this game to all players in lobby
        ns_name, room = '/tictactoe/wait', 'lobby'
        for client in socketio.rooms.get(ns_name, {}).get(room, set()):
            sid = client.session.get('sid')
            ServerSessionStorage(sid)['game'] = game
        ServerSessionStorage()['game'] = game

        socketio.emit('game started', namespace='/tictactoe/wait', room='lobby')
        socketio.close_room('lobby')

    def close_game(self):
        self.finished = True
        # TODO: add database persistence here

    def get_data_for_client(self):
        return {'field': self.field,
                'turn': self.active_player.username,
                'gameOver': self.finished,
                'winner': self.winner.username if self.winner else None
                }

    def make_move(self, row, column):
        if ServerSessionStorage()['player'] != self.active_player:
            return
        if self.finished:
            return

        if self.field[row][column] == '-':
            if self.active_player == self.first_player:
                symbol = 'X'
            else:
                symbol = '0'
            l = list(self.field[row])
            l[column] = symbol
            self.field[row] = ''.join(l)

        if self.check_endgame():
            self.close_game()
        else:
            self.active_player = self.other_player()

    def check_endgame(self):
        f = self.field
        wins = [
            # lines
            any(row[0] == row[1] == row[2] != '-' for row in f),

            # columns
            any(f[0][col] == f[1][col] == f[2][col] != '-' for col in range(3)),

            # diagonals
            f[0][0] == f[1][1] == f[2][2] != '-',
            f[0][2] == f[1][1] == f[2][0] != '-',
        ]
        if any(wins):
            self.winner = self.active_player
            return True
        elif '-' not in ''.join(self.field):
            self.winner = None
            return True
        else:
            return False




    def other_player(self):
        if ServerSessionStorage()['player'] == self.player_a:
            return self.player_b
        elif ServerSessionStorage()['player'] == self.player_b:
            return self.player_a


waiting_player = None
session_by_player = {}      # {player: session ID}

flask_app = Flask(__name__)
flask_app.debug = True
flask_app.config['SECRET_KEY'] = 'DHD3ru029fj#@%wdHOIUJvg'
Triangle(flask_app)
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
            ServerSessionStorage()['player'] = player
            session_by_player[player] = session['sid']
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
    elif player == waiting_player:
        # ordinary page refresh
        return render_template('wait.html', username=player.username)
    elif waiting_player.username == player.username:
        # username collision; please relog
        flash('User with name %s is already waiting for opponent.' % waiting_player.username)
        # TODO: enable flashes in templates
        return redirect(url_for('login'))
    else:
        Game.start_game(waiting_player, player)
        waiting_player = None
        return redirect(url_for('game_view'))


@flask_app.route('/game')
def game_view():
    game, player = ServerSessionStorage()['game'], ServerSessionStorage()['player']
    if not game or not player:
        return redirect(url_for('login'))
    elif game and game.finished:
        return redirect(url_for('login'))

    return render_template('game.html', game=game, myName=player.username)


###############################
# WEBSOCKET EVENTS

@socketio.on('connect', namespace='/tictactoe/wait')
def connect_wait():
    join_room('lobby')


@socketio.on('connect', namespace='/tictactoe/game')
def connect_game():
    game = ServerSessionStorage()['game']
    if game:
        join_room(game.room)
        game_data = game.get_data_for_client()
        emit('update game', game_data, room=game.room)


@socketio.on('make move', namespace='/tictactoe/game')
def process_move(json):
    print json
    row, column = json.get('row'), json.get('column')
    game = ServerSessionStorage()['game']
    game.make_move(row, column)
    game_data = game.get_data_for_client()
    emit('update game', game_data, room=game.room)


@socketio.on('disconnect', namespace='/tictactoe/game')
def process_disconnect():
    game = ServerSessionStorage()['game']
    if game:
        game.winner = game.other_player()
        game.close_game()
        emit('update game', game.get_data_for_client(), room=game.room)

if __name__ == '__main__':
    socketio.run(flask_app)
