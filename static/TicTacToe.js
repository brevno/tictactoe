var socket = io.connect('http://' + document.domain + ':' + location.port + '/tictactoe/game');


var app = angular.module('TicTacToe', []);
app.factory('socket', function ($rootScope) {
    return {
        on: function (eventName, callback) {
            socket.on(eventName, function () {
                var args = arguments;
                $rootScope.$apply(function () {
                    callback.apply(socket, args);
                });
            });
        },
        emit: function (eventName, data, callback) {
            socket.emit(eventName, data, function () {
                var args = arguments;
                $rootScope.$apply(function () {
                    if (callback) {
                        callback.apply(socket, args);
                    }
                });
            })
        }
    };
});
app.controller('ctrlField', function($scope, socket){
    socket.on('update game', function(data){
        $scope.field = data['field']
    });

    $scope.field = ['---', '---', '---'];
    $scope.clickCell = function(rowIndex, columnIndex){
        socket.emit('make move', {row: rowIndex, column: columnIndex});
    };
    $scope.cellData = function(rowIndex, columnIndex){
        var symbol = $scope.field[rowIndex][columnIndex];
        if (symbol == '-') {
            return '';
        } else {
            return symbol;
        }
    }
    $scope.$on('$destroy', function(event){
        event.preventDefault();
        alert('disconnect');
    });
});
app.controller('ctrlInfo', function($scope, socket){
    socket.on('update game', function(data){
        $scope.turn = data['turn'];
        $scope.gameOver = data['gameOver'];
        $scope.winner = data['winner'];
    });
});

window.addEventListener("beforeunload", function (e) {
    var confirmationMessage = "\o/";

    (e || window.event).returnValue = confirmationMessage; //Gecko + IE
    return confirmationMessage;                            //Webkit, Safari, Chrome
});

window.addEventListener("unload", function (e) {
    alert('disconnect');
    socket.disconnect();
});