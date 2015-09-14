var socket = io.connect('http://' + document.domain + ':' + location.port + '/tictactoe/game');
socket.on('connect', function() {
    socket.emit('my event', {data: 'I\'m connected!'});
});
socket.on('game started', function(data){
    window.location = '/game';
});
``