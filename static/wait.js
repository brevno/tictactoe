var socket = io.connect('http://' + document.domain + ':' + location.port + '/tictactoe/wait');
socket.on('connect', function() {
    socket.emit('my event', {data: 'I\'m connected!'});
});
socket.on('game started', function(data){
    window.location = '/game';
});
``